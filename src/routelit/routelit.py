import asyncio
import contextvars
import functools
import time
from collections.abc import MutableMapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from .assets_utils import get_vite_components_assets
from .builder import RouteLitBuilder
from .domain import (
    ActionsResponse,
    BuilderTranstionParams,
    Head,
    PropertyDict,
    RouteLitElement,
    RouteLitRequest,
    RouteLitResponse,
    SessionKeys,
    ViteComponentsAssets,
)
from .exceptions import EmptyReturnException, RerunException
from .utils.async_to_sync_gen import async_to_sync_generator
from .utils.misc import (
    compare_elements,
    get_elements_at_address,
    set_elements_at_address,
)

ViewFn = Callable[[RouteLitBuilder], Union[None, Awaitable[None]]]
BuilderType = TypeVar("BuilderType", bound=RouteLitBuilder)


class RouteLit(Generic[BuilderType]):
    """
    RouteLit is a class that provides a framework for handling HTTP requests and generating responses in a web application. It manages the routing and view functions that define how the application responds to different requests.

    The class maintains a registry of fragment functions and uses a builder pattern to construct responses. It supports both GET and POST requests, handling them differently based on the request method.

    Key features:
    - Session storage management
    - Fragment registry for reusable view components
    - Support for both GET and POST request handling
    - Builder pattern for constructing responses
    - Support for dependency injection in view functions

    The class is designed to be flexible, allowing for custom builder classes and session storage implementations.
    """

    def __init__(
        self,
        BuilderClass: Type[BuilderType] = RouteLitBuilder,  # type: ignore[assignment]
        session_storage: Optional[MutableMapping[str, Any]] = None,
        inject_builder: bool = True,
        debounce_ms: int = 1000,
    ):
        self.BuilderClass = BuilderClass
        self.session_storage = session_storage or {}
        self.fragment_registry: Dict[str, Callable[[RouteLitBuilder], Any]] = {}
        self._session_builder_context: contextvars.ContextVar[RouteLitBuilder] = contextvars.ContextVar(
            "session_builder"
        )
        self.inject_builder = inject_builder
        self.debounce_ms = debounce_ms

    @contextmanager
    def _set_builder_context(self, builder: BuilderType) -> Generator[BuilderType, None, None]:
        try:
            token = self._session_builder_context.set(builder)
            yield builder
        finally:
            self._session_builder_context.reset(token)
        builder.on_end()

    @property
    def ui(self) -> BuilderType:
        """
        The current builder instance.
        Use this in conjunction with `response(..., inject_builder=False)`
        example:
        ```python
        rl = RouteLit()

        def my_view():
            rl.ui.text("Hello, world!")

        request = ...
        response = rl.response(my_view, request, inject_builder=False)
        ```
        """
        return cast(BuilderType, self._session_builder_context.get())

    def response(
        self,
        view_fn: ViewFn,
        request: RouteLitRequest,
        inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Union[RouteLitResponse, Dict[str, Any]]:
        """Handle the request and return the response.

        Args:
            view_fn (ViewFn): (Callable[[RouteLitBuilder], Any]) The view function to handle the request.
            request (RouteLitRequest): The request object.
            **kwargs (Dict[str, Any]): Additional keyword arguments.

        Returns:
            RouteLitResponse | Dict[str, Any]:
                The response object.
                where Dict[str, Any] is a dictionary that contains the following keys:
                actions (List[Action]), target (Literal["app", "fragment"])

        Example:
        ```python
        from routelit import RouteLit, RouteLitBuilder

        rl = RouteLit()

        def my_view(rl: RouteLitBuilder):
            rl.text("Hello, world!")

        request = ...
        response = rl.response(my_view, request)

        # example with dependency
        def my_view(rl: RouteLitBuilder, name: str):
            rl.text(f"Hello, {name}!")

        request = ...
        response = rl.response(my_view, request, name="John")
        ```
        """
        if request.method == "GET":
            return self.handle_get_request(request, **kwargs)
        elif request.method == "POST":
            return self.handle_post_request(view_fn, request, inject_builder, *args, **kwargs)
        else:
            # set custom exception for unsupported request method
            raise ValueError(request.method)

    def handle_get_request(
        self,
        request: RouteLitRequest,
        **kwargs: Any,
    ) -> RouteLitResponse:
        """ "
        Handle a GET request.
        If the session state is present, it will be cleared.
        The head title and description can be passed as kwargs.
        Example:
        ```python
        return routelit_adapter.response(build_signup_view, head_title="Signup", head_description="Signup page")
        ```

        Args:
            request (RouteLitRequest): The request object.
            **kwargs (Dict[str, Any]): Additional keyword arguments.
                head_title (Optional[str]): The title of the head.
                head_description (Optional[str]): The description of the head.

        Returns:
            RouteLitResponse: The response object.
        """
        session_keys = request.get_session_keys()
        ui_key, state_key, fragment_addresses_key, fragment_params_key = session_keys
        if state_key in self.session_storage:
            self.session_storage.pop(ui_key, None)
            self.session_storage.pop(state_key, None)
            self.session_storage.pop(fragment_addresses_key, None)
            self.session_storage.pop(fragment_params_key, None)
        return RouteLitResponse(
            elements=[],
            head=Head(
                title=kwargs.get("head_title"),
                description=kwargs.get("head_description"),
            ),
        )

    def _get_prev_keys(self, request: RouteLitRequest, session_keys: SessionKeys) -> Tuple[bool, SessionKeys]:
        maybe_event = request.ui_event
        if maybe_event and maybe_event["type"] == "navigate":
            new_session_keys = request.get_session_keys(use_referer=True)
            return True, new_session_keys
        return False, session_keys

    def _write_session_state(
        self,
        *,
        session_keys: SessionKeys,
        prev_elements: List[RouteLitElement],
        prev_fragments: MutableMapping[str, List[int]],
        elements: List[RouteLitElement],
        session_state: MutableMapping[str, Any],
        fragments: MutableMapping[str, List[int]],
        fragment_id: Optional[str] = None,
    ) -> None:
        if fragment_id and (fragment_address := prev_fragments.get(fragment_id, [])) and len(fragment_address) > 0:
            fragment_elements = elements
            new_elements = set_elements_at_address(prev_elements, fragment_address, fragment_elements)
        else:
            new_elements = elements

        ui_key, state_key, fragment_addresses_key, _ = session_keys
        self.session_storage[ui_key] = new_elements
        self.session_storage[state_key] = session_state
        self.session_storage[fragment_addresses_key] = {**prev_fragments, **fragments}

    def _get_prev_elements_at_fragment(
        self, session_keys: SessionKeys, fragment_id: Optional[str]
    ) -> Tuple[List[RouteLitElement], Optional[List[RouteLitElement]]]:
        """
        Returns the previous elements of the full page and the previous elements of the fragment if address is provided.
        """
        prev_elements = self.session_storage.get(session_keys.ui_key, [])
        if fragment_id:
            fragment_address = self.session_storage.get(session_keys.fragment_addresses_key, {}).get(fragment_id, [])
            fragment_elements = get_elements_at_address(prev_elements, fragment_address)
            return prev_elements, fragment_elements
        return prev_elements, None

    def _check_if_form_event(self, request: RouteLitRequest, session_keys: SessionKeys) -> None:
        event = request.ui_event
        if event and event.get("type") != "submit" and (form_id := event.get("formId")):
            session_state = self.session_storage.get(session_keys.state_key, {})
            events = session_state.get(f"__events4later_{form_id}", {})
            events[event["componentId"]] = event
            self.session_storage[session_keys.state_key] = {
                **session_state,
                f"__events4later_{form_id}": events,
            }
            raise EmptyReturnException()

    def _handle_build_params(self, request: RouteLitRequest, session_keys: SessionKeys) -> BuilderTranstionParams:
        self._maybe_clear_session_state(request, session_keys)
        is_navigation_event, prev_session_keys = self._get_prev_keys(request, session_keys)
        prev_elements, maybe_prev_fragment_elements = self._get_prev_elements_at_fragment(
            prev_session_keys, request.fragment_id
        )
        if is_navigation_event:
            self._clear_session_state(prev_session_keys)
        prev_session_state = self.session_storage.get(prev_session_keys.state_key, {})
        prev_fragments = self.session_storage.get(prev_session_keys.fragment_addresses_key, {})
        return BuilderTranstionParams(
            prev_elements=prev_elements,
            maybe_prev_fragment_elements=maybe_prev_fragment_elements,
            prev_session_state=prev_session_state,
            prev_fragments=prev_fragments,
        )

    @staticmethod
    def _build_post_response(
        # transition_params: BuilderTranstionParams,
        prev_elements: List[RouteLitElement],
        elements: List[RouteLitElement],
        fragment_id: Optional[str],
    ) -> Dict[str, Any]:
        # real_prev_elements = transition_params.maybe_prev_fragment_elements or transition_params.prev_elements
        actions = compare_elements(prev_elements, elements)
        target: Literal["app", "fragment"] = "app" if fragment_id is None else "fragment"
        action_response = ActionsResponse(actions=actions, target=target)
        return asdict(action_response)

    def _handle_builder_view_end(
        self,
        builder: RouteLitBuilder,
        session_keys: SessionKeys,
        transition_params: BuilderTranstionParams,
        fragment_id: Optional[str],
    ) -> Dict[str, Any]:
        elements = builder.get_elements()
        self._write_session_state(
            session_keys=session_keys,
            prev_elements=transition_params.prev_elements,
            prev_fragments=transition_params.prev_fragments,
            elements=elements,
            session_state=builder.session_state.get_data(),
            fragments=builder.get_fragments(),
            fragment_id=fragment_id,
        )
        real_prev_elements = transition_params.maybe_prev_fragment_elements or transition_params.prev_elements
        return self._build_post_response(real_prev_elements, elements, fragment_id)

    def _handle_builder_view_end_with_transition_params(
        self,
        builder: RouteLitBuilder,
        session_keys: SessionKeys,
        transition_params: BuilderTranstionParams,
        fragment_id: Optional[str],
    ) -> Tuple[Dict[str, Any], BuilderTranstionParams]:
        resp = self._handle_builder_view_end(builder, session_keys, transition_params, fragment_id)
        elements = deepcopy(builder.get_elements())
        fragments = builder.get_fragments()
        new_transition_params = BuilderTranstionParams(
            prev_elements=elements,
            maybe_prev_fragment_elements=elements,
            prev_session_state=builder.session_state.get_data(),
            prev_fragments=deepcopy(fragments),
        )
        return resp, new_transition_params

    def handle_post_request(
        self,
        view_fn: ViewFn,
        request: RouteLitRequest,
        inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        inject_builder = self.inject_builder if inject_builder is None else inject_builder
        app_view_fn = view_fn
        session_keys = request.get_session_keys()
        try:
            self._check_if_form_event(request, session_keys)
            fragment_id = request.fragment_id
            if fragment_id and fragment_id in self.fragment_registry:
                view_fn = self.fragment_registry[fragment_id]
            transition_params = self._handle_build_params(request, session_keys)
            builder = self.BuilderClass(
                request,
                session_state=PropertyDict(transition_params.prev_session_state),
                fragments=transition_params.prev_fragments,
                initial_fragment_id=fragment_id,
            )
            new_args = (builder, *args) if inject_builder else args
            with self._set_builder_context(builder):
                view_fn(*new_args, **kwargs)
            return self._handle_builder_view_end(builder, session_keys, transition_params, fragment_id)
        except RerunException as e:
            self.session_storage[session_keys.state_key] = e.state
            actual_view_fn = app_view_fn if e.scope == "app" else view_fn
            return self.handle_post_request(actual_view_fn, request, inject_builder, *args, **kwargs)
        except EmptyReturnException:
            # No need to return anything
            return asdict(ActionsResponse(actions=[], target="app"))

    async def handle_post_request_async_stream(
        self,
        view_fn: ViewFn,
        request: RouteLitRequest,
        inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        inject_builder = self.inject_builder if inject_builder is None else inject_builder
        app_view_fn = view_fn
        session_keys = request.get_session_keys()
        try:
            self._check_if_form_event(request, session_keys)
            fragment_id = request.fragment_id
            if fragment_id and fragment_id in self.fragment_registry:
                view_fn = self.fragment_registry[fragment_id]
            transition_params = self._handle_build_params(request, session_keys)
            builder = self.BuilderClass(
                request,
                session_state=PropertyDict(transition_params.prev_session_state),
                fragments=transition_params.prev_fragments,
                initial_fragment_id=fragment_id,
                event_queue=asyncio.Queue(),
                loop=asyncio.get_running_loop(),
            )
            gen = self._generate_view_sumarized_chunks_async(
                view_fn,
                builder,
                session_keys,
                transition_params,
                fragment_id,
                inject_builder,
                args,
                kwargs,
            )
            async for item in gen:
                yield item
        except RerunException as e:
            self.session_storage[session_keys.state_key] = e.state
            actual_view_fn = app_view_fn if e.scope == "app" else view_fn
            async for item in self.handle_post_request_async_stream(
                actual_view_fn, request, inject_builder, *args, **kwargs
            ):
                yield item
        except EmptyReturnException:
            # No need to return anything
            yield asdict(ActionsResponse(actions=[], target="app"))

    def handle_post_request_stream(
        self,
        view_fn: ViewFn,
        request: RouteLitRequest,
        inject_builder: Optional[bool] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Generator[Dict[str, Any], None, None]:
        async_gen = self.handle_post_request_async_stream(view_fn, request, inject_builder, *args, **kwargs)
        yield from async_to_sync_generator(async_gen)

    def get_builder_class(self) -> Type[RouteLitBuilder]:
        return self.BuilderClass

    def _clear_session_state(self, session_keys: SessionKeys) -> None:
        self.session_storage.pop(session_keys.state_key, None)
        self.session_storage.pop(session_keys.ui_key, None)
        self.session_storage.pop(session_keys.fragment_addresses_key, None)
        self.session_storage.pop(session_keys.fragment_params_key, None)

    def _maybe_clear_session_state(self, request: RouteLitRequest, session_keys: SessionKeys) -> None:
        if request.get_query_param("__routelit_clear_session_state"):
            self._clear_session_state(session_keys)
            raise EmptyReturnException()

    def client_assets(self) -> List[ViteComponentsAssets]:
        """
        Render the vite assets for BuilderClass components.
        This function will return a list of ViteComponentsAssets.
        This should be called by the web framework to render the assets.
        """
        assets = []
        for static_path in self.BuilderClass.get_client_resource_paths():
            vite_assets = get_vite_components_assets(static_path["package_name"])
            assets.append(vite_assets)

        return assets

    def default_client_assets(self) -> ViteComponentsAssets:
        return get_vite_components_assets("routelit")

    def _register_fragment(self, key: str, fragment: Callable[[RouteLitBuilder], Any]) -> None:
        self.fragment_registry[key] = fragment

    def _preprocess_fragment_params(
        self, fragment_key: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> Tuple[BuilderType, bool, Tuple[Any, ...], Dict[str, Any]]:
        is_builder_1st_arg = args is not None and len(args) > 0 and isinstance(args[0], RouteLitBuilder)
        rl: BuilderType = cast(RouteLitBuilder, args[0]) if is_builder_1st_arg else self.ui  # type: ignore[assignment]
        if is_builder_1st_arg:
            args = args[1:]
        is_fragment_request = rl.request.fragment_id is not None
        session_keys = rl.request.get_session_keys()
        if not is_fragment_request:
            fragment_params_by_key = {
                fragment_key: {
                    "args": args,
                    "kwargs": kwargs,
                }
            }
            all_fragment_params = self.session_storage.get(session_keys.fragment_params_key, {})
            self.session_storage[session_keys.fragment_params_key] = {
                **all_fragment_params,
                **fragment_params_by_key,
            }
        else:
            fragment_params = self.session_storage.get(session_keys.fragment_params_key, {}).get(fragment_key, {})
            args = fragment_params.get("args", [])
            kwargs = fragment_params.get("kwargs", {})

        return rl, is_builder_1st_arg, args, kwargs

    def fragment(self, key: Optional[str] = None) -> Callable[[ViewFn], ViewFn]:
        """
        Decorator to register a fragment.

        Args:
            key: The key to register the fragment with.

        Returns:
            The decorator function.

        Example:
        ```python
        from routelit import RouteLit, RouteLitBuilder

        rl = RouteLit()

        @rl.fragment()
        def my_fragment(ui: RouteLitBuilder):
            ui.text("Hello, world!")

        @rl.fragment()
        def my_fragment2():
            ui = rl.ui
            ui.text("Hello, world!")
        ```
        """

        def decorator_fragment(view_fn: ViewFn) -> ViewFn:
            fragment_key = key or view_fn.__name__

            @functools.wraps(view_fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                rl, is_builder_1st_arg, args, kwargs = self._preprocess_fragment_params(fragment_key, args, kwargs)

                with rl._fragment(fragment_key):
                    res = view_fn(rl, *args, **kwargs) if is_builder_1st_arg else view_fn(*args, **kwargs)
                    return res

            self._register_fragment(fragment_key, wrapper)
            return wrapper

        return decorator_fragment

    def dialog(self, key: Optional[str] = None) -> Callable[[ViewFn], ViewFn]:
        """Decorator to register a dialog.

        Args:
            key (Optional[str]): The key to register the dialog with.

        Returns:
            The decorator function.

        Example:
        ```python
        from routelit import RouteLit, RouteLitBuilder

        rl = RouteLit()

        @rl.dialog()
        def my_dialog(ui: RouteLitBuilder):
            ui.text("Hello, world!")

        def my_main_view(ui: RouteLitBuilder):
            if ui.button("Open dialog"):
                my_dialog(ui)

        @rl.dialog()
        def my_dialog2():
            ui = rl.ui
            ui.text("Hello, world!")

        def my_main_view2():
            ui = rl.ui
            if ui.button("Open dialog"):
                my_dialog2()
        ```
        """

        def decorator_dialog(view_fn: ViewFn) -> ViewFn:
            fragment_key = key or view_fn.__name__
            dialog_key = f"{fragment_key}-dialog"

            @functools.wraps(view_fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                rl, is_builder_1st_arg, args, kwargs = self._preprocess_fragment_params(fragment_key, args, kwargs)

                with rl._fragment(fragment_key), rl._dialog(dialog_key):
                    res = view_fn(rl, *args, **kwargs) if is_builder_1st_arg else view_fn(*args, **kwargs)
                    return res

            self._register_fragment(fragment_key, wrapper)
            return wrapper

        return decorator_dialog

    def _build_run_view_async(
        self,
        view_fn: Callable[[RouteLitBuilder], None | Awaitable[None]],
        builder: BuilderType,
        inject_builder: bool,
        args: Tuple[Any, ...],
        kwargs: Dict[Any, Any],
    ) -> Awaitable[None]:
        async def run_view_async():
            try:
                new_args = (builder, *args) if inject_builder else args
                with self._set_builder_context(builder):
                    if asyncio.iscoroutinefunction(view_fn):
                        await view_fn(*new_args, **kwargs)
                    else:
                        await asyncio.to_thread(view_fn, *new_args, **kwargs)
            finally:
                print("view_task finally")
                # Always signal completion
                await builder.event_queue.put("COMPLETED")

        return run_view_async

    def _check_if_rl_view_task_failed(self, view_task: asyncio.Task, builder: Optional[BuilderType] = None) -> None:
        if view_task.done() and view_task.exception() is not None:
            exception = view_task.exception()
            if isinstance(exception, (RerunException, EmptyReturnException)):
                if builder:
                    builder.event_queue.task_done()
                raise exception

    async def _generate_view_sumarized_chunks_async(
        self,
        view_fn: Callable[[RouteLitBuilder], None | Awaitable[None]],
        builder: BuilderType,
        session_keys: SessionKeys,
        transition_params: BuilderTranstionParams,
        fragment_id: Optional[str],
        inject_builder: bool,
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        this function should be aware of the view_fn and the builder via the builder.add_data method.
        it should generate a summarized chuck each time after the debounce time while the view_fn is running.
        """

        # Start view_fn as an async task
        run_view_async = self._build_run_view_async(view_fn, builder, inject_builder, args, kwargs)

        # maybe set the context variable here
        view_task = asyncio.create_task(run_view_async(), name="rl_view_fn")

        try:
            last_transition_params = transition_params
            debounce_seconds = self.debounce_ms / 1000.0
            last_event_time = None

            while True:
                try:
                    # Wait for events with timeout for debounce behavior
                    # Always use timeout to provide periodic updates even when view task is taking long
                    timeout = debounce_seconds
                    event = await asyncio.wait_for(builder.event_queue.get(), timeout=timeout)

                    # Check for completion
                    if isinstance(event, str) and event == "COMPLETED":
                        # Check if the task raised an exception and propagate it
                        self._check_if_rl_view_task_failed(view_task, builder)

                        # Process final batch
                        actions, new_transition_params = self._handle_builder_view_end_with_transition_params(
                            builder,
                            session_keys,
                            last_transition_params,
                            fragment_id,
                        )
                        print(
                            "COMPLETED - builder.elements != last_transition_params.prev_elements",
                            builder.elements != last_transition_params.prev_elements,
                        )
                        print(
                            "- new_elements",
                            builder.elements,
                            "\n- old_elements",
                            last_transition_params.prev_elements,
                            "\n- actions",
                            actions,
                        )
                        if builder.elements != last_transition_params.prev_elements:
                            yield actions
                            last_transition_params = new_transition_params
                        builder.event_queue.task_done()
                        break

                    last_event_time = time.time()
                    builder.event_queue.task_done()

                except asyncio.TimeoutError as e:
                    print("TimeoutError", e, view_task.done())
                    # Check if task completed with exception during timeout
                    self._check_if_rl_view_task_failed(view_task)

                    # Timeout occurred - check for updates only if there was recent activity (debounce behavior)
                    if last_event_time is not None:
                        actions, new_transition_params = self._handle_builder_view_end_with_transition_params(
                            builder,
                            session_keys,
                            last_transition_params,
                            fragment_id,
                        )
                        print(
                            "TIMEOUT - builder.elements != last_transition_params.prev_elements",
                            builder.elements != last_transition_params.prev_elements,
                        )
                        print(
                            "- new_elements",
                            builder.elements,
                            "\n- old_elements",
                            last_transition_params.prev_elements,
                            "\n- actions",
                            actions,
                        )
                        if builder.elements != last_transition_params.prev_elements:
                            yield actions
                            last_transition_params = new_transition_params
                        # Reset the event time after processing
                        last_event_time = None

                except asyncio.CancelledError as e:
                    print("CancelledError", e)
                    # Task was cancelled (client disconnected)
                    break

        except (asyncio.CancelledError, GeneratorExit) as e:
            print(f"AsyncGenerator cancelled: {e}")
            # Cancel the task
            if not view_task.done():
                view_task.cancel()
                try:
                    # Wait for the task to be cancelled with a timeout
                    await asyncio.wait_for(view_task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    print("View task cancellation timed out or was cancelled")
                    pass
            raise
        except Exception as e:
            print(f"Error in _generate_view_sumarized_chunks_async: {e}")
            raise
        finally:
            # Always signal cancellation to help the view function exit
            if not view_task.done():
                view_task.cancel()
                try:
                    # Give the task a chance to clean up
                    await asyncio.wait_for(view_task, timeout=1.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    print("Task cleanup timed out or was cancelled")
                    pass
                except Exception as e:
                    print(f"Cleanup error: {e}")
                    pass
