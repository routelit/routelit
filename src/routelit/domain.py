import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    Mapping,
    MutableMapping,
    NamedTuple,
    Optional,
    TypedDict,
    Union,
)
from urllib.parse import urlparse

COOKIE_SESSION_KEY = "ROUTELIT_SESSION_ID"
"""
The key of the session id in the cookie.
"""

BuilderTarget = Literal["app", "fragment"]
RerunType = Literal["auto", "app", "fragment"]
"""
  "auto" will rerun the fragment if it is called from a fragment otherwise it will rerun the app.
  "app" will rerun the app.
"""


if TYPE_CHECKING:
    from .builder import RouteLitBuilder

ViewFn = Callable[["RouteLitBuilder"], Union[None, Awaitable[None]]]


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
    view_tasks_key: str
    """
      Key to the view tasks in the session state.
    """


@dataclass
class RouteLitElement:
    """
    The element to be rendered by the RouteLit app.
    """

    ROOT_ELEMENT_KEY: ClassVar[str] = "root"

    name: str
    props: Dict[str, Any]
    key: str
    children: Optional[List["RouteLitElement"]] = None
    address: Optional[List[int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "props": self.props,
            "key": self.key,
            "address": self.address,
        }

    @staticmethod
    def create_root_element() -> "RouteLitElement":
        return RouteLitElement(
            name=RouteLitElement.ROOT_ELEMENT_KEY,
            props={},
            key="",
            children=[],
            address=None,
        )

    def append_child(self, child: "RouteLitElement") -> None:
        if self.children is None:
            self.children = []
        self.children.append(child)

    def get_children(self) -> List["RouteLitElement"]:
        if self.children is None:
            self.children = []
        return self.children


@dataclass
class Action:
    address: Optional[List[int]]
    """
      (List[int]) The address is the list of indices to the array tree of elements in the session state
      from the root to the target element.
    """
    target: Optional[Literal["app", "fragment"]]
    """
      (Literal["app", "fragment"]) The target is the target of the action.
      If None, the action is applied to the app.
    """


@dataclass
class RerunAction(Action):
    type: Literal["rerun"] = "rerun"


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
class FreshBoundaryAction(Action):
    """
    The action to mark the fresh boundary of the app or fragment.
    It means all elements after this action should be stale.
    This action should be used when streaming, should be just before the first action.
    """

    type: Literal["fresh_boundary"] = "fresh_boundary"


@dataclass
class ViewTaskDoneAction(Action):
    """
    The action to mark that the task is done.
    """

    type: Literal["task_done"] = "task_done"


@dataclass
class LastAction(Action):
    """
    The action to mark that no more actions will be yielded after this action.
    """

    type: Literal["last"] = "last"


@dataclass
class SetAction(Action):
    """
    The action to set an element.
    """

    element: Dict[str, Any]
    key: str
    type: Literal["set"] = "set"


@dataclass
class NoChangeAction(Action):
    """
    The action to mark that no change will be made.
    """

    type: Literal["no_change"] = "no_change"


# Type aliases for async generators
RouteLitElementGenerator = AsyncGenerator[RouteLitElement, None]
"""
Async generator type for RouteLitElement instances.
"""

ActionGenerator = AsyncGenerator[Action, None]
"""
Async generator type for Action instances.
"""


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
    def get_path_params(self) -> Optional[Mapping[str, Any]]:
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

    def get_session_keys(self, use_referer: bool = False) -> SessionKeys:
        session_id = self.get_session_id()
        host_pathname = self.get_host_pathname(use_referer)
        ui_session_key = f"{session_id}:{host_pathname}:ui"
        session_state_key = f"{session_id}:{host_pathname}:state"
        fragment_addresses_key = f"{ui_session_key}:fragments"
        fragment_params_key = f"{ui_session_key}:fragment_params"
        view_tasks_key = f"{ui_session_key}:view_tasks"
        return SessionKeys(
            ui_session_key,
            session_state_key,
            fragment_addresses_key,
            fragment_params_key,
            view_tasks_key,
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


class BuilderTranstionParams(NamedTuple):
    elements: List[RouteLitElement]
    maybe_fragment_elements: Optional[List[RouteLitElement]]
    session_state: MutableMapping[str, Any]
    fragments: MutableMapping[str, List[int]]
