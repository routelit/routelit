"""
Test suite for the domain module.

This test suite verifies the functionality of all domain classes including:
1. Data classes (RouteLitElement, Actions, Head, etc.)
2. TypedDicts (RouteLitEvent, AssetTarget)
3. Abstract base classes (RouteLitRequest)
4. Utility classes (PropertyDict, SessionKeys)
5. Response classes (RouteLitResponse, ActionsResponse)
6. New action types (FreshBoundaryAction, LastAction, SetAction)
"""

import json
from typing import Any, Dict, List, Optional

from routelit.domain import (
    COOKIE_SESSION_KEY,
    ActionsResponse,
    AddAction,
    AssetTarget,
    FreshBoundaryAction,
    Head,
    LastAction,
    NoChangeAction,
    RemoveAction,
    RerunAction,
    RouteLitElement,
    RouteLitEvent,
    RouteLitRequest,
    RouteLitResponse,
    SessionKeys,
    SetAction,
    UpdateAction,
    ViewTaskDoneAction,
    ViteComponentsAssets,
)
from routelit.exceptions import EmptyReturnException, RerunException, StopException
from routelit.utils.property_dict import PropertyDict


class MockRouteLitRequest(RouteLitRequest):
    def __init__(
        self,
        method: str = "GET",
        session_id: str = "test_session",
        host: str = "example.com",
        pathname: str = "/test",  # Changed from "/" to "/test" to match test expectation
        referrer: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        is_json_request: bool = False,
        json_data: Optional[Dict[str, Any]] = None,
        fragment_id: Optional[str] = None,
        ui_event: Optional[Dict[str, Any]] = None,
    ):
        self._method = method
        self._session_id = session_id
        self._host = host
        self._pathname = pathname
        self._referrer = referrer
        self._headers = headers or {}
        self._query_params = query_params or {}
        self._is_json_request = is_json_request
        self._json_data = json_data or {}
        self._fragment_id = fragment_id
        self._ui_event = ui_event

    @property
    def method(self) -> str:
        return self._method

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def host(self) -> str:
        return self._host

    @property
    def pathname(self) -> str:
        return self._pathname

    @property
    def referrer(self) -> Optional[str]:
        return self._referrer

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @property
    def query_params(self) -> Dict[str, str]:
        return self._query_params

    @property
    def is_json_request(self) -> bool:
        return self._is_json_request

    @property
    def json_data(self) -> Dict[str, Any]:
        return self._json_data

    @property
    def fragment_id(self) -> Optional[str]:
        if self._fragment_id is not None:
            return self._fragment_id
        if self._is_json_request and "fragment_id" in self._json_data:
            return self._json_data["fragment_id"]
        return None

    @property
    def ui_event(self) -> Optional[Dict[str, Any]]:
        if self._ui_event is not None:
            return self._ui_event
        if self._is_json_request and "ui_event" in self._json_data:
            return self._json_data["ui_event"]
        return None

    def clear_event(self) -> None:
        self._ui_event = None
        if self._is_json_request and "ui_event" in self._json_data:
            del self._json_data["ui_event"]

    def clear_fragment_id(self) -> None:
        self._fragment_id = None
        if self._is_json_request and "fragment_id" in self._json_data:
            del self._json_data["fragment_id"]

    def get_referrer(self) -> Optional[str]:
        if self._referrer is not None:
            return self._referrer
        return self._headers.get("referer")

    def get_query_param(self, key: str) -> Optional[str]:
        return self._query_params.get(key)

    def get_headers(self) -> Dict[str, str]:
        return self._headers

    def get_path_params(self) -> Optional[Dict[str, Any]]:
        return None

    def is_json(self) -> bool:
        return self._is_json_request

    def get_json(self) -> Optional[Dict[str, Any]]:
        return self._json_data if self._is_json_request else None

    def get_query_param_list(self, key: str) -> List[str]:
        return [self._query_params.get(key)] if key in self._query_params else []

    def get_session_id(self) -> str:
        return self._session_id

    def get_pathname(self) -> str:
        return self._pathname

    def get_host(self) -> str:
        return self._host

    def get_session_keys(self, use_referer: bool = False) -> SessionKeys:
        base_path = self.get_host_pathname(use_referer)
        return SessionKeys(
            ui_key=f"{self._session_id}:{base_path}:ui",
            state_key=f"{self._session_id}:{base_path}:state",
            fragment_addresses_key=f"{self._session_id}:{base_path}:ui:fragments",
            fragment_params_key=f"{self._session_id}:{base_path}:fragments:params",
            view_tasks_key=f"{self._session_id}:{base_path}:view_tasks",
        )

    def get_host_pathname(self, use_referer: bool = False) -> str:
        if use_referer and self._referrer:
            # Extract host and pathname from referrer
            if self._referrer.startswith("http"):
                # Parse URL-like referrer
                parts = self._referrer.replace("http://", "").replace("https://", "").split("/", 1)
                host = parts[0]
                pathname = "/" + parts[1] if len(parts) > 1 else "/"
                return f"{host}{pathname}"
            return self._referrer
        return f"{self._host}{self._pathname}"


class TestConstants:
    """Test module constants"""

    def test_cookie_session_key(self):
        """Test that the cookie session key constant is defined correctly"""
        assert COOKIE_SESSION_KEY == "ROUTELIT_SESSION_ID"
        assert isinstance(COOKIE_SESSION_KEY, str)


class TestRouteLitElement:
    """Test RouteLitElement dataclass"""

    def test_basic_creation(self):
        """Test basic element creation"""
        element = RouteLitElement(name="div", props={"class": "container"}, key="test-div")

        assert element.name == "div"
        assert element.props == {"class": "container"}
        assert element.key == "test-div"
        assert element.children is None
        assert element.address is None

    def test_creation_with_children(self):
        """Test element creation with children"""
        child1 = RouteLitElement(name="span", props={}, key="child1")
        child2 = RouteLitElement(name="p", props={"text": "Hello"}, key="child2")

        parent = RouteLitElement(name="div", props={"class": "parent"}, key="parent", children=[child1, child2])

        assert len(parent.children) == 2
        assert parent.children[0] == child1
        assert parent.children[1] == child2

    def test_creation_with_address(self):
        """Test element creation with address"""
        element = RouteLitElement(name="button", props={"text": "Click me"}, key="btn", address=[0, 1, 2])

        assert element.address == [0, 1, 2]

    def test_element_equality(self):
        """Test element equality comparison"""
        element1 = RouteLitElement(name="div", props={"id": "test"}, key="div1")
        element2 = RouteLitElement(name="div", props={"id": "test"}, key="div1")
        element3 = RouteLitElement(name="span", props={"id": "test"}, key="div1")

        assert element1 == element2
        assert element1 != element3

    def test_nested_elements(self):
        """Test deeply nested element structures"""
        deep_child = RouteLitElement(name="em", props={}, key="emphasis")
        middle_child = RouteLitElement(name="strong", props={}, key="bold", children=[deep_child])
        parent = RouteLitElement(name="p", props={}, key="paragraph", children=[middle_child])

        assert parent.children[0].children[0] == deep_child
        assert parent.children[0].children[0].name == "em"


class TestActionClasses:
    """Test Action dataclasses"""

    def test_add_action(self):
        """Test AddAction creation and properties"""
        element = RouteLitElement(name="div", props={}, key="new-div")
        action = AddAction(address=[0, 1], element=element, key="new-div", target=None)

        assert action.type == "add"
        assert action.address == [0, 1]
        assert action.element == element
        assert action.key == "new-div"

    def test_remove_action(self):
        """Test RemoveAction creation and properties"""
        action = RemoveAction(address=[1, 2, 3], key="remove-me", target=None)

        assert action.type == "remove"
        assert action.address == [1, 2, 3]
        assert action.key == "remove-me"

    def test_update_action(self):
        """Test UpdateAction creation and properties"""
        props = {"text": "Updated text", "color": "blue"}
        action = UpdateAction(address=[0], props=props, key="update-me", target=None)

        assert action.type == "update"
        assert action.address == [0]
        assert action.props == props
        assert action.key == "update-me"

    def test_fresh_boundary_action(self):
        """Test FreshBoundaryAction creation and properties"""
        action = FreshBoundaryAction(address=[-1], target="app")

        assert action.type == "fresh_boundary"
        assert action.address == [-1]
        assert action.target == "app"

    def test_last_action(self):
        """Test LastAction creation and properties"""
        action = LastAction(address=[0], target="fragment")

        assert action.type == "last"
        assert action.address == [0]
        assert action.target == "fragment"

    def test_set_action(self):
        """Test SetAction creation and properties"""
        element_dict = {"name": "div", "props": {"class": "container"}, "key": "set-div"}
        action = SetAction(address=[0], element=element_dict, key="set-div", target="app")

        assert action.type == "set"
        assert action.address == [0]
        assert action.element == element_dict
        assert action.key == "set-div"
        assert action.target == "app"

    def test_actions_response(self):
        """Test ActionsResponse creation"""
        add_action = AddAction(
            address=[0], element=RouteLitElement(name="div", props={}, key="new"), key="new", target=None
        )
        remove_action = RemoveAction(address=[1], key="old", target=None)

        response = ActionsResponse(actions=[add_action, remove_action], target="app")

        assert len(response.actions) == 2
        assert response.target == "app"
        assert response.actions[0] == add_action
        assert response.actions[1] == remove_action

    def test_actions_response_fragment_target(self):
        """Test ActionsResponse with fragment target"""
        fresh_action = FreshBoundaryAction(address=[-1], target="fragment")
        last_action = LastAction(address=[0], target="fragment")

        response = ActionsResponse(actions=[fresh_action, last_action], target="fragment")

        assert len(response.actions) == 2
        assert response.target == "fragment"
        assert response.actions[0] == fresh_action
        assert response.actions[1] == last_action

    def test_view_task_done_action(self):
        """Test ViewTaskDoneAction creation and properties"""
        action = ViewTaskDoneAction(address=[0], target="app")

        assert action.type == "task_done"
        assert action.address == [0]
        assert action.target == "app"

    def test_rerun_action(self):
        """Test RerunAction creation and properties"""
        action = RerunAction(address=[-1], target="fragment")

        assert action.type == "rerun"
        assert action.address == [-1]
        assert action.target == "fragment"

    def test_no_change_action(self):
        """Test NoChangeAction creation and properties"""
        action = NoChangeAction(address=[0], target="app")

        assert action.type == "no_change"
        assert action.address == [0]
        assert action.target == "app"

    def test_set_action_with_element_dict(self):
        """Test SetAction with element dictionary"""
        element_dict = {"name": "div", "props": {"class": "container"}, "key": "set-div", "address": [0]}
        action = SetAction(address=[0], element=element_dict, key="set-div", target="app")

        assert action.type == "set"
        assert action.address == [0]
        assert action.element == element_dict
        assert action.key == "set-div"
        assert action.target == "app"

    def test_action_inheritance(self):
        """Test that all actions inherit from base Action class"""
        actions = [
            AddAction(address=[0], element=RouteLitElement(name="div", props={}, key="test"), key="test", target="app"),
            RemoveAction(address=[0], key="test", target="app"),
            UpdateAction(address=[0], props={"class": "new"}, key="test", target="app"),
            FreshBoundaryAction(address=[-1], target="app"),
            LastAction(address=[0], target="app"),
            SetAction(address=[0], element={"name": "div", "props": {}, "key": "test"}, key="test", target="app"),
            ViewTaskDoneAction(address=[0], target="app"),
            RerunAction(address=[-1], target="app"),
            NoChangeAction(address=[0], target="app"),
        ]

        for action in actions:
            assert hasattr(action, "address")
            assert hasattr(action, "target")
            assert hasattr(action, "type")


class TestSessionKeys:
    """Test SessionKeys NamedTuple"""

    def test_session_keys_creation(self):
        """Test SessionKeys creation with all fields"""
        keys = SessionKeys(
            ui_key="test:ui",
            state_key="test:state",
            fragment_addresses_key="test:fragments:addresses",
            fragment_params_key="test:fragments:params",
            view_tasks_key="test:view_tasks",
        )

        assert keys.ui_key == "test:ui"
        assert keys.state_key == "test:state"
        assert keys.fragment_addresses_key == "test:fragments:addresses"
        assert keys.fragment_params_key == "test:fragments:params"
        assert keys.view_tasks_key == "test:view_tasks"

    def test_session_keys_indexing(self):
        """Test SessionKeys indexing access"""
        keys = SessionKeys(
            ui_key="test:ui",
            state_key="test:state",
            fragment_addresses_key="test:fragments:addresses",
            fragment_params_key="test:fragments:params",
            view_tasks_key="test:view_tasks",
        )

        assert keys[0] == "test:ui"
        assert keys[1] == "test:state"
        assert keys[2] == "test:fragments:addresses"
        assert keys[3] == "test:fragments:params"
        assert keys[4] == "test:view_tasks"

    def test_session_keys_unpacking(self):
        """Test SessionKeys unpacking"""
        keys = SessionKeys(
            ui_key="test:ui",
            state_key="test:state",
            fragment_addresses_key="test:fragments:addresses",
            fragment_params_key="test:fragments:params",
            view_tasks_key="test:view_tasks",
        )

        ui_key, state_key, fragment_addresses_key, fragment_params_key, view_tasks_key = keys

        assert ui_key == "test:ui"
        assert state_key == "test:state"
        assert fragment_addresses_key == "test:fragments:addresses"
        assert fragment_params_key == "test:fragments:params"
        assert view_tasks_key == "test:view_tasks"


class TestRouteLitEvent:
    """Test RouteLitEvent TypedDict"""

    def test_event_creation(self):
        """Test RouteLitEvent creation with all fields"""
        event = RouteLitEvent(
            type="click",
            componentId="button-1",
            data={"x": 100, "y": 200},
            formId="form-1",
        )

        assert event["type"] == "click"
        assert event["componentId"] == "button-1"
        assert event["data"] == {"x": 100, "y": 200}
        assert event["formId"] == "form-1"

    def test_event_without_form_id(self):
        """Test RouteLitEvent creation without formId"""
        event = RouteLitEvent(
            type="changed",
            componentId="input-1",
            data={"value": "new value"},
            formId=None,
        )

        assert event["type"] == "changed"
        assert event["componentId"] == "input-1"
        assert event["data"] == {"value": "new value"}
        assert event["formId"] is None

    def test_navigate_event(self):
        """Test RouteLitEvent for navigation events"""
        event = RouteLitEvent(
            type="navigate",
            componentId="link-1",
            data={"url": "/new-page"},
            formId=None,
        )

        assert event["type"] == "navigate"
        assert event["componentId"] == "link-1"
        assert event["data"] == {"url": "/new-page"}
        assert event["formId"] is None


class TestAssetTarget:
    """Test AssetTarget TypedDict"""

    def test_asset_target_creation(self):
        """Test AssetTarget creation"""
        asset = AssetTarget(package_name="my-package", path="/static/js/app.js")

        assert asset["package_name"] == "my-package"
        assert asset["path"] == "/static/js/app.js"


class TestViteComponentsAssets:
    """Test ViteComponentsAssets dataclass"""

    def test_vite_assets_creation(self):
        """Test ViteComponentsAssets creation"""
        assets = ViteComponentsAssets(
            package_name="my-package",
            js_files=["app.js", "vendor.js"],
            css_files=["app.css"],
        )

        assert assets.package_name == "my-package"
        assert assets.js_files == ["app.js", "vendor.js"]
        assert assets.css_files == ["app.css"]

    def test_vite_assets_empty_files(self):
        """Test ViteComponentsAssets with empty file lists"""
        assets = ViteComponentsAssets(
            package_name="empty-package",
            js_files=[],
            css_files=[],
        )

        assert assets.package_name == "empty-package"
        assert assets.js_files == []
        assert assets.css_files == []


class TestHead:
    """Test Head dataclass"""

    def test_head_creation_empty(self):
        """Test Head creation with no values"""
        head = Head()

        assert head.title is None
        assert head.description is None

    def test_head_creation_with_values(self):
        """Test Head creation with values"""
        head = Head(title="My Page", description="A test page")

        assert head.title == "My Page"
        assert head.description == "A test page"

    def test_head_partial_values(self):
        """Test Head creation with partial values"""
        head = Head(title="My Page")

        assert head.title == "My Page"
        assert head.description is None


class TestRouteLitResponse:
    """Test RouteLitResponse dataclass"""

    def test_response_creation(self):
        """Test RouteLitResponse creation"""
        element = RouteLitElement(name="div", props={"class": "container"}, key="main")
        head = Head(title="Test Page", description="A test page")

        response = RouteLitResponse(elements=[element], head=head)

        assert len(response.elements) == 1
        assert response.elements[0] == element
        assert response.head == head

    def test_get_str_json_elements(self):
        """Test get_str_json_elements method"""
        element1 = RouteLitElement(name="div", props={"class": "container"}, key="div1")
        element2 = RouteLitElement(name="span", props={"text": "Hello"}, key="span1")

        response = RouteLitResponse(elements=[element1, element2], head=Head())

        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert parsed[0]["name"] == "div"
        assert parsed[0]["props"] == {"class": "container"}
        assert parsed[0]["key"] == "div1"
        assert parsed[1]["name"] == "span"
        assert parsed[1]["props"] == {"text": "Hello"}
        assert parsed[1]["key"] == "span1"

    def test_get_str_json_elements_with_children(self):
        """Test get_str_json_elements with nested elements"""
        child = RouteLitElement(name="span", props={"text": "Child"}, key="child")
        parent = RouteLitElement(name="div", props={"class": "parent"}, key="parent", children=[child])

        response = RouteLitResponse(elements=[parent], head=Head())

        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)

        assert len(parsed) == 1
        assert parsed[0]["name"] == "div"
        assert parsed[0]["key"] == "parent"
        assert "children" in parsed[0]
        assert len(parsed[0]["children"]) == 1
        assert parsed[0]["children"][0]["name"] == "span"
        assert parsed[0]["children"][0]["key"] == "child"


class TestPropertyDict:
    """Test PropertyDict class"""

    def test_property_dict_creation_empty(self):
        """Test PropertyDict creation with empty data"""
        pd = PropertyDict()

        assert len(pd) == 0
        assert isinstance(pd, PropertyDict)  # Check it's a PropertyDict, not dict

    def test_property_dict_creation_with_data(self):
        """Test PropertyDict creation with data"""
        data = {"a": 1, "b": "test", "c": [1, 2, 3]}
        pd = PropertyDict(data)

        assert len(pd) == 3
        assert pd["a"] == 1
        assert pd["b"] == "test"
        assert pd["c"] == [1, 2, 3]

    def test_property_dict_attribute_access(self):
        """Test PropertyDict attribute access"""
        data = {"name": "John", "age": 30}
        pd = PropertyDict(data)

        assert pd.name == "John"
        assert pd.age == 30

    def test_property_dict_attribute_setting(self):
        """Test PropertyDict attribute setting"""
        pd = PropertyDict()

        pd.name = "Jane"
        pd.age = 25

        assert pd["name"] == "Jane"
        assert pd["age"] == 25
        assert pd.name == "Jane"
        assert pd.age == 25

    def test_property_dict_item_setting(self):
        """Test PropertyDict item setting"""
        pd = PropertyDict()

        pd["name"] = "Bob"
        pd["age"] = 35

        assert pd.name == "Bob"
        assert pd.age == 35
        assert pd["name"] == "Bob"
        assert pd["age"] == 35

    def test_dictionary_operations(self):
        """Test standard dictionary operations"""
        pd = PropertyDict({"a": 1, "b": 2})

        # Test get
        assert pd.get("a") == 1
        assert pd.get("c", "default") == "default"

        # Test update
        pd.update({"c": 3, "d": 4})
        assert pd["c"] == 3
        assert pd["d"] == 4

    def test_iteration(self):
        """Test iteration over PropertyDict"""
        data = {"x": 1, "y": 2, "z": 3}
        pd = PropertyDict(data)

        items = list(pd.items())
        assert len(items) == 3
        assert ("x", 1) in items
        assert ("y", 2) in items
        assert ("z", 3) in items

    def test_keys_and_values(self):
        """Test keys and values methods"""
        data = {"a": 1, "b": 2, "c": 3}
        pd = PropertyDict(data)

        keys = list(pd.keys())
        values = list(pd.values())

        assert set(keys) == {"a", "b", "c"}
        assert set(values) == {1, 2, 3}

    def test_pop_method(self):
        """Test pop method"""
        pd = PropertyDict({"a": 1, "b": 2})

        value = pd.pop("a")
        assert value == 1
        assert "a" not in pd
        assert "b" in pd

        # Test pop with default
        default_value = pd.pop("c", "default")
        assert default_value == "default"

    def test_get_method(self):
        """Test get method with default"""
        pd = PropertyDict({"existing": "value"})

        assert pd.get("existing") == "value"
        assert pd.get("missing", "default") == "default"
        assert pd.get("missing") is None

    def test_string_representations(self):
        """Test string representations"""
        pd = PropertyDict({"a": 1, "b": 2})

        str_repr = str(pd)
        assert "a" in str_repr
        assert "b" in str_repr

        repr_repr = repr(pd)
        assert "PropertyDict" in repr_repr

    def test_private_attributes(self):
        """Test that private attributes don't interfere with dict access"""
        pd = PropertyDict({"public": "value"})

        # Set a private attribute
        pd._private = "private_value"

        # Public attribute should still work
        assert pd.public == "value"
        assert pd["public"] == "value"

        # Private attribute should be accessible
        assert pd._private == "private_value"


class TestRouteLitRequest:
    """Test RouteLitRequest abstract base class"""

    def test_basic_request_creation(self):
        """Test basic request creation"""
        request = MockRouteLitRequest()

        assert request.method == "GET"
        assert request.get_session_id() == "test_session"
        assert request.get_pathname() == "/test"
        assert request.get_host() == "example.com"  # Updated to match MockRouteLitRequest default

    def test_ui_event_extraction_from_json(self):
        """Test UI event extraction from JSON data"""
        json_data = {
            "ui_event": {
                "type": "click",
                "componentId": "button-1",
                "data": {"x": 100, "y": 200},
                "formId": "form-1",
            }
        }
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        ui_event = request.ui_event
        assert ui_event is not None
        assert ui_event["type"] == "click"
        assert ui_event["componentId"] == "button-1"
        assert ui_event["data"] == {"x": 100, "y": 200}
        assert ui_event["formId"] == "form-1"

    def test_fragment_id_extraction(self):
        """Test fragment ID extraction from JSON data"""
        json_data = {"fragment_id": "my-fragment"}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.fragment_id == "my-fragment"

    def test_clear_event(self):
        """Test clearing the UI event"""
        json_data = {"ui_event": {"type": "click", "componentId": "btn", "data": {}}}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.ui_event is not None
        request.clear_event()
        assert request.ui_event is None

    def test_clear_fragment_id(self):
        """Test clearing the fragment ID"""
        json_data = {"fragment_id": "test-fragment"}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.fragment_id == "test-fragment"
        request.clear_fragment_id()
        assert request.fragment_id is None

    def test_get_session_keys(self):
        """Test get_session_keys method"""
        request = MockRouteLitRequest(session_id="test123", host="example.com", pathname="/page")

        keys = request.get_session_keys()
        assert keys.ui_key == "test123:example.com/page:ui"
        assert keys.state_key == "test123:example.com/page:state"
        assert keys.fragment_addresses_key == "test123:example.com/page:ui:fragments"
        assert keys.fragment_params_key == "test123:example.com/page:fragments:params"
        assert keys.view_tasks_key == "test123:example.com/page:view_tasks"

    def test_get_session_keys_with_referer(self):
        """Test get_session_keys with referer"""
        request = MockRouteLitRequest(
            session_id="test123",
            host="example.com",
            pathname="/page",
            referrer="https://other.com/other-page",
        )

        keys = request.get_session_keys(use_referer=True)
        assert keys.ui_key == "test123:other.com/other-page:ui"
        assert keys.state_key == "test123:other.com/other-page:state"
        assert keys.fragment_addresses_key == "test123:other.com/other-page:ui:fragments"
        assert keys.fragment_params_key == "test123:other.com/other-page:fragments:params"
        assert keys.view_tasks_key == "test123:other.com/other-page:view_tasks"

    def test_get_referrer_with_internal_referer(self):
        """Test get_referrer with internal referer"""
        request = MockRouteLitRequest(referrer="https://internal.com/internal")
        assert request.get_referrer() == "https://internal.com/internal"

    def test_internal_referer_fallback(self):
        """Test fallback to header referer when internal is None"""
        headers = {"referer": "https://header-referer.com/header"}
        request = MockRouteLitRequest(referrer=None, headers=headers)

        # Should fall back to header referer
        assert request.get_referrer() == "https://header-referer.com/header"

    def test_query_params(self):
        """Test query parameter handling"""
        query_params = {"page": "1", "sort": "name"}
        request = MockRouteLitRequest(query_params=query_params)

        assert request.get_query_param("page") == "1"
        assert request.get_query_param("sort") == "name"
        assert request.get_query_param("missing") is None

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON data"""
        request = MockRouteLitRequest(is_json_request=True, json_data=None)

        # Should handle None JSON gracefully
        assert request.ui_event is None

    def test_empty_json_handling(self):
        """Test handling of empty JSON data"""
        request = MockRouteLitRequest(is_json_request=True, json_data={})

        # Should handle empty JSON gracefully
        assert request.ui_event is None


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_property_dict_with_none_initial(self):
        """Test PropertyDict with None initial data"""
        pd = PropertyDict(None)

        assert len(pd) == 0
        assert isinstance(pd, PropertyDict)  # Check it's a PropertyDict, not dict

    def test_element_with_empty_props(self):
        """Test RouteLitElement with empty props"""
        element = RouteLitElement(name="div", props={}, key="empty")

        assert element.props == {}
        assert element.name == "div"
        assert element.key == "empty"

    def test_response_with_empty_elements(self):
        """Test RouteLitResponse with empty elements list"""
        response = RouteLitResponse(elements=[], head=Head())

        assert len(response.elements) == 0
        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)
        assert parsed == []

    def test_session_keys_with_special_characters(self):
        """Test SessionKeys with special characters in keys"""
        keys = SessionKeys(
            ui_key="test:ui:with:colons",
            state_key="test:state:with:colons",
            fragment_addresses_key="test:fragments:addresses:with:colons",
            fragment_params_key="test:fragments:params:with:colons",
            view_tasks_key="test:view_tasks:with:colons",
        )

        assert keys.ui_key == "test:ui:with:colons"
        assert keys.state_key == "test:state:with:colons"
        assert keys.fragment_addresses_key == "test:fragments:addresses:with:colons"
        assert keys.fragment_params_key == "test:fragments:params:with:colons"
        assert keys.view_tasks_key == "test:view_tasks:with:colons"

    def test_property_dict_attribute_deletion(self):
        """Test deleting attributes from PropertyDict"""
        pd = PropertyDict({"a": 1, "b": 2})

        del pd["a"]
        assert "a" not in pd
        assert "b" in pd
        assert pd["b"] == 2


class TestExceptions:
    """Test exception classes"""

    def test_stop_exception(self):
        """Test StopException creation and properties"""
        exception = StopException("Test stop message")

        assert str(exception) == "Test stop message"
        assert isinstance(exception, Exception)

    def test_empty_return_exception(self):
        """Test EmptyReturnException creation"""
        exception = EmptyReturnException()

        assert isinstance(exception, Exception)
        # EmptyReturnException doesn't take arguments
        assert str(exception) == ""

    def test_rerun_exception(self):
        """Test RerunException creation and properties"""
        state = {"counter": 1, "user": "test"}
        exception = RerunException(state, scope="app")

        assert exception.state == state
        assert exception.scope == "app"
        assert isinstance(exception, Exception)

    def test_rerun_exception_fragment_scope(self):
        """Test RerunException with fragment scope"""
        state = {"fragment_data": "test"}
        exception = RerunException(state, scope="auto")

        assert exception.state == state
        assert exception.scope == "auto"

    def test_rerun_exception_state_mutability(self):
        """Test that RerunException state is mutable"""
        original_state = {"counter": 0}
        exception = RerunException(original_state, scope="app")

        # Modify the state
        exception.state["counter"] = 1
        exception.state["new_key"] = "new_value"

        assert exception.state["counter"] == 1
        assert exception.state["new_key"] == "new_value"
        assert "new_key" in exception.state
