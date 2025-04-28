from typing import (
    Callable,
    Dict,
    List,
    Any,
    Optional,
    Sequence,
    Tuple,
    Union,
    Type,
)
import functools

from collections import ChainMap
from collections.abc import MutableMapping

from dataclasses import asdict

from .builder import RouteLitBuilder
from .domain import (
    Action,
    ActionsResponse,
    RouteLitElement,
    RouteLitRequest,
    ViteComponentsAssets,
    SessionKeys,
)
from .utils import compare_elements, get_elements_at_address, set_elements_at_address
from .assets_utils import get_vite_components_assets
from .exceptions import RerunException, EmptyReturnException


ViewFn = Callable[[RouteLitBuilder], Any]


class RouteLit:
    def __init__(
        self,
        BuilderClass: Type[RouteLitBuilder],
        session_storage: MutableMapping[str, MutableMapping[str, Any]] = {},
        cache_storage: MutableMapping[str, Any] = {},
    ):
        self.BuilderClass = BuilderClass
        self.session_storage = session_storage
        self.cache_storage = cache_storage
        self.fragment_registry: Dict[str, Callable[[RouteLitBuilder], Any]] = {}

    def response(
        self, view_fn: ViewFn, request: RouteLitRequest, **kwargs
    ) -> Union[List[RouteLitElement], List[Action]]:
        if request.method == "GET":
            return self.handle_get_request(view_fn, request, **kwargs)
        elif request.method == "POST":
            return self.handle_post_request(view_fn, request, **kwargs)
        else:
            raise ValueError(f"Unsupported request method: {request.method}")

    def handle_get_request(self, view_fn: ViewFn, request: RouteLitRequest, **kwargs) -> List[Dict[str, Any]]:
        builder = self.BuilderClass(request)
        session_keys = request.get_session_keys()
        ui_key, state_key, fragment_addresses_key, fragment_params_key = session_keys
        if state_key in self.session_storage:
            self.session_storage.pop(ui_key, None)
            self.session_storage.pop(state_key, None)
            self.session_storage.pop(fragment_addresses_key, None)
            self.session_storage.pop(fragment_params_key, None)
        view_fn(builder, **kwargs)
        elements = builder.get_elements()
        self.session_storage[ui_key] = elements
        self.session_storage[state_key] = builder.session_state
        self.session_storage[fragment_addresses_key] = builder.get_fragments()
        return [asdict(element) for element in elements]

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
        prev_fragments: MutableMapping[str, Sequence[int]],
        elements: List[RouteLitElement],
        session_state: Dict[str, Any],
        fragments: MutableMapping[str, Sequence[int]],
        fragment_id: Optional[str] = None,
    ):
        fragment_address = prev_fragments.get(fragment_id, [])
        if len(fragment_address) > 0:
            fragment_elements = elements

            new_elements = set_elements_at_address(prev_elements, fragment_address, fragment_elements)
        else:
            new_elements = elements

        ui_key, state_key, fragment_addresses_key, _ = session_keys
        self.session_storage[ui_key] = new_elements
        self.session_storage[state_key] = session_state
        self.session_storage[fragment_addresses_key] = prev_fragments | fragments

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

    def handle_post_request(self, view_fn: ViewFn, request: RouteLitRequest, *args, **kwargs) -> Dict[str, Any]:
        app_view_fn = view_fn
        session_keys = request.get_session_keys()
        try:
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
            target = "app" if fragment_id is None else "fragment"
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
            return []

    def get_builder_class(self) -> Type[RouteLitBuilder]:
        return self.BuilderClass

    def _clear_session_state(self, session_keys: SessionKeys):
        self.session_storage.pop(session_keys.state_key, None)
        self.session_storage.pop(session_keys.ui_key, None)
        self.session_storage.pop(session_keys.fragment_addresses_key, None)
        self.session_storage.pop(session_keys.fragment_params_key, None)

    def _maybe_clear_session_state(self, request: RouteLitRequest, session_keys: SessionKeys):
        if request.get_query_param("__routelit_clear_session_state"):
            self._clear_session_state(session_keys)
            raise EmptyReturnException()

    def client_assets(self) -> List[ViteComponentsAssets]:
        """
        Render the vite assets for BuilderClass components.
        This function will return a list of ViteComponentsAssets.
        """
        assets = []
        for static_path in self.BuilderClass.get_client_resource_paths():
            vite_assets = get_vite_components_assets(static_path["package_name"])
            assets.append(vite_assets)

        return assets

    def default_client_assets(self) -> List[ViteComponentsAssets]:
        return get_vite_components_assets("routelit")

    def fragment(self, key: Optional[str] = None):
        def decorator_fragment(view_fn: ViewFn):
            fragment_key = key or view_fn.__name__

            @functools.wraps(view_fn)
            def wrapper(rl: RouteLitBuilder, *args, **kwargs):
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
                    self.session_storage[session_keys.fragment_params_key] = (
                        all_fragment_params | fragment_params_by_key
                    )
                else:
                    fragment_params = self.session_storage.get(session_keys.fragment_params_key, {}).get(
                        fragment_key, {}
                    )
                    args = fragment_params.get("args", [])
                    kwargs = fragment_params.get("kwargs", {})

                with rl._fragment(fragment_key) as rl2:
                    res = view_fn(rl2, *args, **kwargs)
                    return res

            self.fragment_registry[fragment_key] = wrapper
            return wrapper

        return decorator_fragment
