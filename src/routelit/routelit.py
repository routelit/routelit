from typing import (
    Callable,
    Dict,
    List,
    Any,
    Optional,
    Tuple,
    Union,
    Type,
)
from collections.abc import MutableMapping

from dataclasses import asdict
from .domain import (
    Action,
    RouteLitElement,
    RouteLitRequest,
    RouteLitBuilder,
    ViteComponentsAssets,
)
from .utils import compare_elements
from .assets_utils import get_vite_components_assets
from .exceptions import RerunException, EmptyReturnException

ViewFn = Callable[[RouteLitBuilder, Dict[str, Any]], None]


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

    def response(
        self, view_fn: ViewFn, request: RouteLitRequest, **kwargs
    ) -> Union[List[RouteLitElement], List[Action]]:
        if request.method == "GET":
            return self.handle_get_request(view_fn, request, **kwargs)
        elif request.method == "POST":
            return self.handle_post_request(view_fn, request, **kwargs)
        else:
            raise ValueError(f"Unsupported request method: {request.method}")

    def handle_get_request(
        self, view_fn: ViewFn, request: RouteLitRequest, **kwargs
    ) -> List[Dict[str, Any]]:
        builder = self.BuilderClass(request)
        ui_session_key, session_state_key = request.get_ui_session_keys()
        if session_state_key in self.session_storage:
            self.session_storage[ui_session_key].clear()
            self.session_storage[session_state_key].clear()
        view_fn(builder, **kwargs)
        elements = builder.get_elements()
        self.session_storage[ui_session_key] = elements
        self.session_storage[session_state_key] = builder.session_state
        return [asdict(element) for element in elements]

    def handle_post_request(
        self, view_fn: ViewFn, request: RouteLitRequest, **kwargs
    ) -> List[Dict[str, Any]]:
        ui_session_key, session_state_key = request.get_ui_session_keys()
        try:
            self._maybe_clear_session_state(request, ui_session_key, session_state_key)
            prev_elements = self.session_storage.get(ui_session_key, [])
            prev_session_state = self.session_storage.get(session_state_key, {})
            builder = self.BuilderClass(request, session_state=prev_session_state)
            view_fn(builder, **kwargs)
            elements = builder.get_elements()
            self.session_storage[ui_session_key] = elements
            self.session_storage[session_state_key] = builder.session_state
            actions = compare_elements(prev_elements, elements)
            return [asdict(action) for action in actions]
        except RerunException as e:
            self.session_storage[session_state_key] = e.state
            return self.handle_post_request(view_fn, request, **kwargs)
        except EmptyReturnException:
            # No need to return anything
            return []

    def get_builder_class(self) -> Type[RouteLitBuilder]:
        return self.BuilderClass

    def _maybe_clear_session_state(
        self, request: RouteLitRequest, ui_session_key: str, session_state_key: str
    ):
        if request.get_query_param("__routelit_clear_session_state"):
            del self.session_storage[session_state_key]
            del self.session_storage[ui_session_key]
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
