from urllib.parse import urlparse
from abc import ABC, abstractmethod
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

from routelit.exceptions import RerunException

COOKIE_SESSION_KEY = "ROUTELIT_SESSION_ID"


class RouteLitEvent(TypedDict):
    type: Literal["click", "changed", "navigate"]
    component_id: str
    data: Dict[str, Any]


@dataclass
class RouteLitElement:
    name: str
    props: Dict[str, Any]
    key: str
    children: Optional[List["RouteLitElement"]] = None


@dataclass
class Action:
    address: Sequence[int]
    """
      The address is the sequence of indices to the array tree of elements in the session state
      from the root to the target element.
    """


@dataclass
class AddAction(Action):
    element: RouteLitElement
    key: str
    type: Literal["add"] = "add"


@dataclass
class RemoveAction(Action):
    key: str
    type: Literal["remove"] = "remove"


@dataclass
class UpdateAction(Action):
    props: Dict[str, Any]
    key: str
    type: Literal["update"] = "update"


class RouteLitRequest(ABC):
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        pass

    @abstractmethod
    def get_referrer(self) -> Optional[str]:
        pass

    @abstractmethod
    def is_json(self) -> bool:
        pass

    @abstractmethod
    def get_json(self) -> Optional[Any]:
        pass

    @abstractmethod
    def get_ui_event(self) -> Optional[RouteLitEvent]:
        pass

    @abstractmethod
    def get_query_param(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def get_query_param_list(self, key: str) -> List[str]:
        pass

    @abstractmethod
    def get_session_id(self) -> str:
        pass

    @abstractmethod
    def get_pathname(self) -> str:
        pass

    @abstractmethod
    def get_host(self) -> str:
        pass

    @property
    @abstractmethod
    def method(self) -> str:
        pass

    @abstractmethod
    def clear_event(self):
        pass

    def get_frament_id(self) -> str:
        frament_id = self.get_query_param("__fragment") or ""
        return frament_id

    def get_host_pathname(self, use_referer: bool = False) -> str:
        if use_referer:
            referrer = self.get_referrer()
            url = urlparse(referrer)
            if url.netloc and url.path:
                return url.netloc + url.path
        return self.get_host() + self.get_pathname()

    def get_ui_session_keys(self, use_referer: bool = False) -> Tuple[str, str]:
        session_id = self.get_session_id()
        host_pathname = self.get_host_pathname(use_referer)
        fragment_id = self.get_frament_id()
        ui_session_key = f"{session_id}:{host_pathname}:{fragment_id}"
        session_state_key = f"{session_id}:{host_pathname}:state"
        return ui_session_key, session_state_key


class AssetTarget(TypedDict):
    package_name: str
    path: str


@dataclass
class ViteComponentsAssets:
    package_name: str
    js_files: List[str]
    css_files: List[str]


class RouteLitBuilder:
    static_assets_targets: Sequence[AssetTarget] = []

    def __init__(
        self,
        request: RouteLitRequest,
        prefix: Optional[str] = None,
        session_state: MutableMapping[str, Any] = {},
        parent_element: Optional[RouteLitElement] = None,
        parent_builder: Optional["RouteLitBuilder"] = None,
    ):
        self.request = request
        # Set prefix based on parent element if not explicitly provided
        if prefix is None:
            self.prefix = parent_element.key if parent_element else ""
        else:
            self.prefix = prefix
        self.elements: List[RouteLitElement] = []
        self.num_non_widget = 0
        self.session_state = session_state
        self.parent_element = parent_element
        self.parent_builder = parent_builder
        if parent_element:
            self.parent_element.children = self.elements
        self.active_child_builder: Optional["RouteLitBuilder"] = None
        if prefix is None:
            self._on_init()

    def _on_init(self):
        pass

    def get_request(self) -> RouteLitRequest:
        return self.request

    def _get_prefix(self) -> str:
        # Simplify to just use the current prefix which is already properly initialized
        return self.prefix

    def _new_text_id(self, type: str) -> str:
        no_of_non_widgets = (
            self.num_non_widget if not self.active_child_builder else self.active_child_builder.num_non_widget
        )
        return f"{self._get_prefix()}_{type}_{no_of_non_widgets}"

    def _new_widget_id(self, type: str, label: str) -> str:
        return f"{self._get_prefix()}_{type}_{label}"

    def _get_event_value(self, component_id: str, event_type: str, attribute: Optional[str] = None) -> Tuple[bool, Any]:
        """
        Check if the last event is of the given type and component_id.
        If attribute is not None, check if the event has the given attribute.
        Returns a tuple of (has_event, event_data).
        """
        event = self.request.get_ui_event()
        has_event = event and event["type"] == event_type and event["component_id"] == component_id
        if has_event:
            if attribute is None:
                return True, event["data"]
            else:
                return True, event["data"][attribute]
        return False, None

    def append_element(self, element: RouteLitElement):
        if self.active_child_builder:
            self.active_child_builder.append_element(element)
        else:
            self.elements.append(element)

    def add_non_widget(self, element: RouteLitElement):
        self.append_element(element)
        if not self.active_child_builder:
            self.num_non_widget += 1
        else:
            self.active_child_builder.num_non_widget += 1

    def add_widget(self, element: RouteLitElement):
        self.append_element(element)

    def create_element(
        self, name: str, key: str, props: Dict[str, Any], children: List[RouteLitElement] = None
    ) -> RouteLitElement:
        element = RouteLitElement(key=key, name=name, props=props, children=children)
        self.add_widget(element)
        return element

    def rerun(self, clear_event: bool = True):
        self.elements.clear()
        if clear_event:
            self.request.clear_event()
        raise RerunException(self.session_state)

    def __enter__(self):
        # When using with builder.element():
        # Make parent builder redirect to this one
        if self.parent_builder:
            self._prev_active_child_builder = self.parent_builder.active_child_builder
            self.parent_builder.active_child_builder = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Reset parent's active child when exiting context
        if self.parent_builder:
            if self._prev_active_child_builder:
                self.parent_builder.active_child_builder = self._prev_active_child_builder
                self._prev_active_child_builder = None
            else:
                self.parent_builder.active_child_builder = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self

    def get_elements(self) -> List[RouteLitElement]:
        return self.elements

    @classmethod
    def get_client_resource_paths(cls) -> Sequence[AssetTarget]:
        return cls.static_assets_targets
