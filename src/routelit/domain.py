import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
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

RerunType = Literal["auto", "app"]
"""
  "auto" will rerun the fragment if it is called from a fragment otherwise it will rerun the app.
  "app" will rerun the app.
"""


class RouteLitEvent(TypedDict):
    type: Literal["click", "changed", "navigate"]
    componentId: str
    data: Dict[str, Any]
    formId: Optional[str] = None


class SessionKeys(NamedTuple):
    ui_key: str
    state_key: str
    fragment_addresses_key: str
    """
      Key to the addresses of the fragments in the session state.
      The address is a sequence of indices to the array tree of elements in the session state
      from the root to the target element.
    """
    fragment_params_key: str
    """
      Key to the parameters of the fragments in the session state.
    """


@dataclass
class RouteLitElement:
    name: str
    props: Dict[str, Any]
    key: str
    children: Optional[List["RouteLitElement"]] = None
    address: Optional[Sequence[int]] = None


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


@dataclass
class ActionsResponse:
    actions: List[Action]
    target: Literal["app", "fragment"]


class RouteLitRequest(ABC):
    def __init__(self):
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
    def get_json(self) -> Optional[Any]:
        pass

    def _get_internal_referrer(self) -> Optional[str]:
        return self.get_headers().get("X-Referer") or self.get_referrer()

    def _get_ui_event(self) -> Optional[RouteLitEvent]:
        if self.is_json():
            return self.get_json().get("uiEvent")
        else:
            return None

    @property
    def ui_event(self) -> Optional[RouteLitEvent]:
        return self._ui_event

    def clear_event(self):
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

    def clear_fragment_id(self):
        self._fragment_id = None

    def _get_fragment_id(self) -> Optional[str]:
        if not self.is_json():
            return None
        return self.get_json().get("fragmentId")

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
