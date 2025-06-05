import functools
from collections.abc import MutableMapping
from dataclasses import asdict
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
)

from .assets_utils import get_vite_components_assets
from .builder import RouteLitBuilder
from .domain import (
    ActionsResponse,
    RouteLitElement,
    RouteLitRequest,
    RouteLitResponse,
    SessionKeys,
    ViteComponentsAssets,
)
from .exceptions import EmptyReturnException, RerunException
from .utils import compare_elements, get_elements_at_address, set_elements_at_address

ViewFn = Callable[[RouteLitBuilder], Any]


class RouteLit:
    def __init__(
        self,
        BuilderClass: Type[RouteLitBuilder] = RouteLitBuilder,
        session_storage: Optional[MutableMapping[str, Any]] = None,
    ):
        self.BuilderClass = BuilderClass
        self.session_storage = session_storage or {}
        self.fragment_registry: Dict[str, Callable[[RouteLitBuilder], Any]] = {}

    def response(
        self, view_fn: ViewFn, request: RouteLitRequest, **kwargs: Any
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
            return self.handle_get_request(view_fn, request, **kwargs)
        elif request.method == "POST":
            return self.handle_post_request(view_fn, request, **kwargs)
        else:
            # set custom exception for unsupported request method
            raise ValueError(request.method)

    def handle_get_request(self, view_fn: ViewFn, request: RouteLitRequest, **kwargs: Any) -> RouteLitResponse:
        session_keys = request.get_session_keys()
        ui_key, state_key, fragment_addresses_key, fragment_params_key = session_keys
        if state_key in self.session_storage:
            self.session_storage.pop(ui_key, None)
            self.session_storage.pop(state_key, None)
            self.session_storage.pop(fragment_addresses_key, None)
            self.session_storage.pop(fragment_params_key, None)
        builder = self.BuilderClass(request, session_state={}, fragments={})
        view_fn(builder, **kwargs)
        elements = builder.get_elements()
        self.session_storage[ui_key] = elements
        self.session_storage[state_key] = builder.session_state
        self.session_storage[fragment_addresses_key] = builder.get_fragments()
        # Initialize fragment_params_key to empty dict if not present
        if fragment_params_key not in self.session_storage:
            self.session_storage[fragment_params_key] = {}
        return RouteLitResponse(
            elements=elements,
            head=builder.get_head(),
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

    def _maybe_handle_form_event(self, request: RouteLitRequest, session_keys: SessionKeys) -> bool:
        event = request.ui_event
        if event and event.get("type") != "submit" and (form_id := event.get("formId")):
            session_state = self.session_storage.get(session_keys.state_key, {})
            events = session_state.get(f"__events4later_{form_id}", {})
            events[event["componentId"]] = event
            self.session_storage[session_keys.state_key] = session_state | {f"__events4later_{form_id}": events}
            return True
        return False

    def handle_post_request(
        self, view_fn: ViewFn, request: RouteLitRequest, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        app_view_fn = view_fn
        session_keys = request.get_session_keys()
        try:
            if self._maybe_handle_form_event(request, session_keys):
                return asdict(ActionsResponse(actions=[], target="app"))
            fragment_id = request.fragment_id
            if fragment_id and fragment_id in self.fragment_registry:
                view_fn = self.fragment_registry[fragment_id]
            self._maybe_clear_session_state(request, session_keys)
            is_navigation_event, prev_session_keys = self._get_prev_keys(request, session_keys)
            prev_elements, maybe_prev_fragment_elements = self._get_prev_elements_at_fragment(
                prev_session_keys, fragment_id
            )
            prev_session_state = self.session_storage.get(prev_session_keys.state_key, {})
            prev_fragments = self.session_storage.get(prev_session_keys.fragment_addresses_key, {})
            builder = self.BuilderClass(
                request,
                session_state=prev_session_state,
                fragments=prev_fragments,
                initial_fragment_id=fragment_id,
            )
            view_fn(builder, *args, **kwargs)
            builder.on_end()
            elements = builder.get_elements()
            self._write_session_state(
                session_keys=session_keys,
                prev_elements=prev_elements,
                prev_fragments=prev_fragments,
                elements=elements,
                session_state=builder.session_state,
                fragments=builder.get_fragments(),
                fragment_id=fragment_id,
            )
            if is_navigation_event:
                self._clear_session_state(prev_session_keys)
            actions = compare_elements(maybe_prev_fragment_elements or prev_elements, elements)
            target: Literal["app", "fragment"] = "app" if fragment_id is None else "fragment"
            action_response = ActionsResponse(actions=actions, target=target)
            return asdict(action_response)
        except RerunException as e:
            self.session_storage[session_keys.state_key] = e.state
            if e.scope == "app":
                return self.handle_post_request(app_view_fn, request, **kwargs)
            else:
                return self.handle_post_request(view_fn, request, **kwargs)
        except EmptyReturnException:
            # No need to return anything
            return asdict(ActionsResponse(actions=[], target="app"))

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
        self, rl: RouteLitBuilder, fragment_key: str, args: Tuple[Any, ...], kwargs: Dict[str, Any]
    ) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
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
            self.session_storage[session_keys.fragment_params_key] = all_fragment_params | fragment_params_by_key
        else:
            fragment_params = self.session_storage.get(session_keys.fragment_params_key, {}).get(fragment_key, {})
            args = fragment_params.get("args", [])
            kwargs = fragment_params.get("kwargs", {})

        return args, kwargs

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
        def my_fragment(rl: RouteLitBuilder):
            rl.text("Hello, world!")
        ```
        """

        def decorator_fragment(view_fn: ViewFn) -> ViewFn:
            fragment_key = key or view_fn.__name__

            @functools.wraps(view_fn)
            def wrapper(rl: RouteLitBuilder, *args: Any, **kwargs: Any) -> Any:
                args, kwargs = self._preprocess_fragment_params(rl, fragment_key, args, kwargs)

                with rl._fragment(fragment_key):
                    res = view_fn(rl, *args, **kwargs)
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
        def my_dialog(rl: RouteLitBuilder):
            rl.text("Hello, world!")
        ```
        """

        def decorator_dialog(view_fn: ViewFn) -> ViewFn:
            fragment_key = key or view_fn.__name__
            dialog_key = f"{fragment_key}-dialog"

            @functools.wraps(view_fn)
            def wrapper(rl: RouteLitBuilder, *args: Any, **kwargs: Any) -> Any:
                args, kwargs = self._preprocess_fragment_params(rl, fragment_key, args, kwargs)

                with rl._fragment(fragment_key), rl._dialog(dialog_key):
                    res = view_fn(rl, *args, **kwargs)
                    return res

            self._register_fragment(fragment_key, wrapper)
            return wrapper

        return decorator_dialog
