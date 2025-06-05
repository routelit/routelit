import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import (
    Any,
    Dict,
    List,
    Literal,
    NamedTuple,
    Optional,
    Tuple,
    TypedDict,
)
from urllib.parse import urlparse

COOKIE_SESSION_KEY = "ROUTELIT_SESSION_ID"
"""
The key of the session id in the cookie.
"""

RerunType = Literal["auto", "app"]
"""
  "auto" will rerun the fragment if it is called from a fragment otherwise it will rerun the app.
  "app" will rerun the app.
"""


class RouteLitEvent(TypedDict):
    """
    The event to be executed by the RouteLit app.
    """

    type: Literal["click", "changed", "navigate"]
    componentId: str
    data: Dict[str, Any]
    formId: Optional[str]


class SessionKeys(NamedTuple):
    """
    The keys to the session state of the RouteLit app.
    """

    ui_key: str
    state_key: str
    fragment_addresses_key: str
    """
      Key to the addresses of the fragments in the session state.
      The address is a List of indices to the array tree of elements in the session state
      from the root to the target element.
    """
    fragment_params_key: str
    """
      Key to the parameters of the fragments in the session state.
    """


@dataclass
class RouteLitElement:
    """
    The element to be rendered by the RouteLit app.
    """

    name: str
    props: Dict[str, Any]
    key: str
    children: Optional[List["RouteLitElement"]] = None
    address: Optional[List[int]] = None


@dataclass
class Action:
    address: List[int]
    """
      (List[int]) The address is the list of indices to the array tree of elements in the session state
      from the root to the target element.
    """


@dataclass
class AddAction(Action):
    """
    The action to add an element.
    """

    element: RouteLitElement
    key: str
    type: Literal["add"] = "add"


@dataclass
class RemoveAction(Action):
    """
    The action to remove an element.
    """

    key: str
    type: Literal["remove"] = "remove"


@dataclass
class UpdateAction(Action):
    """
    The action to update the props of an element.
    """

    props: Dict[str, Any]
    key: str
    type: Literal["update"] = "update"


@dataclass
class ActionsResponse:
    """
    The actions to be executed by the RouteLit app.
    """

    actions: List[Action]
    target: Literal["app", "fragment"]


class RouteLitRequest(ABC):
    """
    The request class for the RouteLit app.
    This class should be implemented by the web framework you want to integrate with.
    """

    def __init__(self) -> None:
        self._ui_event = self._get_ui_event()
        self._fragment_id = self._get_fragment_id()

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
    def get_json(self) -> Optional[Dict[str, Any]]:
        pass

    def _get_internal_referrer(self) -> Optional[str]:
        return self.get_headers().get("X-Referer") or self.get_referrer()

    def _get_ui_event(self) -> Optional[RouteLitEvent]:
        if self.is_json() and (json_data := self.get_json()) and isinstance(json_data, dict):
            return json_data.get("uiEvent")
        else:
            return None

    @property
    def ui_event(self) -> Optional[RouteLitEvent]:
        return self._ui_event

    def clear_event(self) -> None:
        self._ui_event = None

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

    def clear_fragment_id(self) -> None:
        self._fragment_id = None

    def _get_fragment_id(self) -> Optional[str]:
        if not self.is_json():
            return None
        json_data = self.get_json()
        if isinstance(json_data, dict):
            return json_data.get("fragmentId")
        return None

    @property
    def fragment_id(self) -> Optional[str]:
        return self._fragment_id

    def get_host_pathname(self, use_referer: bool = False) -> str:
        if use_referer:
            referrer = self._get_internal_referrer()
            if referrer:
                url = urlparse(referrer)
                if url.netloc and url.path:
                    return url.netloc + url.path
        return self.get_host() + self.get_pathname()

    def get_ui_session_keys(self, use_referer: bool = False) -> Tuple[str, str]:
        session_id = self.get_session_id()
        host_pathname = self.get_host_pathname(use_referer)
        # fragment_id = self.get_fragment_id()
        ui_session_key = f"{session_id}:{host_pathname}"
        session_state_key = f"{session_id}:{host_pathname}:state"
        return ui_session_key, session_state_key

    def get_session_keys(self, use_referer: bool = False) -> SessionKeys:
        session_id = self.get_session_id()
        host_pathname = self.get_host_pathname(use_referer)
        ui_session_key = f"{session_id}:{host_pathname}:ui"
        session_state_key = f"{session_id}:{host_pathname}:state"
        fragment_addresses_key = f"{ui_session_key}:fragments"
        fragment_params_key = f"{ui_session_key}:fragment_params"
        return SessionKeys(
            ui_session_key,
            session_state_key,
            fragment_addresses_key,
            fragment_params_key,
        )


class AssetTarget(TypedDict):
    package_name: str
    path: str


@dataclass
class ViteComponentsAssets:
    package_name: str
    js_files: List[str]
    css_files: List[str]


@dataclass
class Head:
    title: Optional[str] = None
    description: Optional[str] = None


@dataclass
class RouteLitResponse:
    elements: List[RouteLitElement]
    head: Head

    def get_str_json_elements(self) -> str:
        return json.dumps([asdict(element) for element in self.elements])
