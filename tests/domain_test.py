"""
Test suite for the domain module.

This test suite verifies the functionality of all domain classes including:
1. Data classes (RouteLitElement, Actions, Head, etc.)
2. TypedDicts (RouteLitEvent, AssetTarget)
3. Abstract base classes (RouteLitRequest)
4. Utility classes (PropertyDict, SessionKeys)
5. Response classes (RouteLitResponse, ActionsResponse)
"""

import json
from typing import Dict, List, Optional

from routelit.domain import (
    COOKIE_SESSION_KEY,
    ActionsResponse,
    AddAction,
    AssetTarget,
    Head,
    PropertyDict,
    RemoveAction,
    RouteLitElement,
    RouteLitEvent,
    RouteLitRequest,
    RouteLitResponse,
    SessionKeys,
    UpdateAction,
    ViteComponentsAssets,
)


class MockRouteLitRequest(RouteLitRequest):
    """Mock implementation of RouteLitRequest for testing"""

    def __init__(
        self,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        referrer: Optional[str] = None,
        is_json_request: bool = False,
        json_data: Optional[Dict] = None,
        query_params: Optional[Dict[str, str]] = None,
        query_param_lists: Optional[Dict[str, List[str]]] = None,
        session_id: str = "test_session",
        pathname: str = "/test",
        host: str = "localhost:8000",
    ):
        self._method = method
        self._headers = headers or {}
        self._referrer = referrer
        self._is_json_request = is_json_request
        self._json_data = json_data
        self._query_params = query_params or {}
        self._query_param_lists = query_param_lists or {}
        self._session_id = session_id
        self._pathname = pathname
        self._host = host
        super().__init__()

    def get_headers(self) -> Dict[str, str]:
        return self._headers

    def get_referrer(self) -> Optional[str]:
        return self._referrer

    def is_json(self) -> bool:
        return self._is_json_request

    def get_json(self) -> Optional[Dict]:
        return self._json_data

    def get_query_param(self, key: str) -> Optional[str]:
        return self._query_params.get(key)

    def get_query_param_list(self, key: str) -> List[str]:
        return self._query_param_lists.get(key, [])

    def get_session_id(self) -> str:
        return self._session_id

    def get_pathname(self) -> str:
        return self._pathname

    def get_host(self) -> str:
        return self._host

    @property
    def method(self) -> str:
        return self._method


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
        action = AddAction(address=[0, 1], element=element, key="new-div")

        assert action.type == "add"
        assert action.address == [0, 1]
        assert action.element == element
        assert action.key == "new-div"

    def test_remove_action(self):
        """Test RemoveAction creation and properties"""
        action = RemoveAction(address=[1, 2, 3], key="remove-me")

        assert action.type == "remove"
        assert action.address == [1, 2, 3]
        assert action.key == "remove-me"

    def test_update_action(self):
        """Test UpdateAction creation and properties"""
        props = {"text": "Updated text", "color": "blue"}
        action = UpdateAction(address=[0], props=props, key="update-me")

        assert action.type == "update"
        assert action.address == [0]
        assert action.props == props
        assert action.key == "update-me"

    def test_actions_response(self):
        """Test ActionsResponse creation"""
        add_action = AddAction(address=[0], element=RouteLitElement(name="div", props={}, key="new"), key="new")
        remove_action = RemoveAction(address=[1], key="old")

        response = ActionsResponse(actions=[add_action, remove_action], target="app")

        assert len(response.actions) == 2
        assert response.target == "app"
        assert response.actions[0] == add_action
        assert response.actions[1] == remove_action

    def test_actions_response_fragment_target(self):
        """Test ActionsResponse with fragment target"""
        update_action = UpdateAction(address=[0, 1], props={"visible": False}, key="toggle")
        response = ActionsResponse(actions=[update_action], target="fragment")

        assert response.target == "fragment"
        assert len(response.actions) == 1


class TestSessionKeys:
    """Test SessionKeys NamedTuple"""

    def test_session_keys_creation(self):
        """Test SessionKeys creation and access"""
        keys = SessionKeys(
            ui_key="session:ui",
            state_key="session:state",
            fragment_addresses_key="session:fragments",
            fragment_params_key="session:params",
        )

        assert keys.ui_key == "session:ui"
        assert keys.state_key == "session:state"
        assert keys.fragment_addresses_key == "session:fragments"
        assert keys.fragment_params_key == "session:params"

    def test_session_keys_indexing(self):
        """Test SessionKeys tuple indexing"""
        keys = SessionKeys("ui", "state", "fragments", "params")

        assert keys[0] == "ui"
        assert keys[1] == "state"
        assert keys[2] == "fragments"
        assert keys[3] == "params"

    def test_session_keys_unpacking(self):
        """Test SessionKeys tuple unpacking"""
        keys = SessionKeys("ui", "state", "fragments", "params")
        ui, state, fragments, params = keys

        assert ui == "ui"
        assert state == "state"
        assert fragments == "fragments"
        assert params == "params"


class TestRouteLitEvent:
    """Test RouteLitEvent TypedDict"""

    def test_event_creation(self):
        """Test creating RouteLitEvent"""
        event: RouteLitEvent = {
            "type": "click",
            "componentId": "button-1",
            "data": {"x": 100, "y": 200},
            "formId": "form-1",
        }

        assert event["type"] == "click"
        assert event["componentId"] == "button-1"
        assert event["data"]["x"] == 100
        assert event["formId"] == "form-1"

    def test_event_without_form_id(self):
        """Test RouteLitEvent without formId"""
        event: RouteLitEvent = {
            "type": "changed",
            "componentId": "input-1",
            "data": {"value": "new text"},
            "formId": None,
        }

        assert event["type"] == "changed"
        assert event["formId"] is None

    def test_navigate_event(self):
        """Test navigate event type"""
        event: RouteLitEvent = {
            "type": "navigate",
            "componentId": "nav-link",
            "data": {"url": "/new-page"},
            "formId": None,
        }

        assert event["type"] == "navigate"
        assert event["data"]["url"] == "/new-page"


class TestAssetTarget:
    """Test AssetTarget TypedDict"""

    def test_asset_target_creation(self):
        """Test AssetTarget creation"""
        asset: AssetTarget = {"package_name": "my-components", "path": "/static/js/components.js"}

        assert asset["package_name"] == "my-components"
        assert asset["path"] == "/static/js/components.js"


class TestViteComponentsAssets:
    """Test ViteComponentsAssets dataclass"""

    def test_vite_assets_creation(self):
        """Test ViteComponentsAssets creation"""
        assets = ViteComponentsAssets(
            package_name="ui-components", js_files=["main.js", "components.js"], css_files=["styles.css", "theme.css"]
        )

        assert assets.package_name == "ui-components"
        assert assets.js_files == ["main.js", "components.js"]
        assert assets.css_files == ["styles.css", "theme.css"]

    def test_vite_assets_empty_files(self):
        """Test ViteComponentsAssets with empty file lists"""
        assets = ViteComponentsAssets(package_name="empty-package", js_files=[], css_files=[])

        assert len(assets.js_files) == 0
        assert len(assets.css_files) == 0


class TestHead:
    """Test Head dataclass"""

    def test_head_creation_empty(self):
        """Test Head creation with default values"""
        head = Head()

        assert head.title is None
        assert head.description is None

    def test_head_creation_with_values(self):
        """Test Head creation with title and description"""
        head = Head(title="My App", description="A great application")

        assert head.title == "My App"
        assert head.description == "A great application"

    def test_head_partial_values(self):
        """Test Head creation with only title"""
        head = Head(title="Just Title")

        assert head.title == "Just Title"
        assert head.description is None


class TestRouteLitResponse:
    """Test RouteLitResponse dataclass"""

    def test_response_creation(self):
        """Test RouteLitResponse creation"""
        elements = [
            RouteLitElement(name="div", props={"class": "container"}, key="main"),
            RouteLitElement(name="p", props={"text": "Hello"}, key="greeting"),
        ]
        head = Head(title="Test Page")

        response = RouteLitResponse(elements=elements, head=head)

        assert len(response.elements) == 2
        assert response.head.title == "Test Page"

    def test_get_str_json_elements(self):
        """Test JSON serialization of elements"""
        elements = [
            RouteLitElement(name="button", props={"text": "Click"}, key="btn"),
            RouteLitElement(name="input", props={"type": "text"}, key="input1"),
        ]
        head = Head()
        response = RouteLitResponse(elements=elements, head=head)

        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)

        assert len(parsed) == 2
        assert parsed[0]["name"] == "button"
        assert parsed[0]["props"]["text"] == "Click"
        assert parsed[1]["name"] == "input"
        assert parsed[1]["key"] == "input1"

    def test_get_str_json_elements_with_children(self):
        """Test JSON serialization with nested elements"""
        child = RouteLitElement(name="span", props={"text": "Child"}, key="child")
        parent = RouteLitElement(name="div", props={"class": "parent"}, key="parent", children=[child])

        response = RouteLitResponse(elements=[parent], head=Head())
        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)

        assert len(parsed) == 1
        assert parsed[0]["children"][0]["name"] == "span"
        assert parsed[0]["children"][0]["props"]["text"] == "Child"


class TestPropertyDict:
    """Test PropertyDict utility class"""

    def test_property_dict_creation_empty(self):
        """Test PropertyDict creation with no initial data"""
        pd = PropertyDict()

        assert len(pd) == 0
        assert pd.get_data() == {}

    def test_property_dict_creation_with_data(self):
        """Test PropertyDict creation with initial data"""
        initial = {"name": "John", "age": 30}
        pd = PropertyDict(initial)

        assert len(pd) == 2
        assert pd["name"] == "John"
        assert pd["age"] == 30

    def test_attribute_access(self):
        """Test accessing properties as attributes"""
        pd = PropertyDict({"username": "alice", "email": "alice@example.com"})

        assert pd.username == "alice"
        assert pd.email == "alice@example.com"
        assert pd.nonexistent is None  # Should return None for missing keys

    def test_attribute_setting(self):
        """Test setting properties as attributes"""
        pd = PropertyDict()

        pd.name = "Bob"
        pd.score = 95

        assert pd["name"] == "Bob"
        assert pd["score"] == 95
        assert pd.name == "Bob"

    def test_dictionary_operations(self):
        """Test dictionary-like operations"""
        pd = PropertyDict({"a": 1, "b": 2})

        # Test __getitem__
        assert pd["a"] == 1

        # Test __setitem__
        pd["c"] = 3
        assert pd.c == 3

        # Test __delitem__
        del pd["b"]
        assert "b" not in pd
        assert pd.b is None

        # Test __contains__
        assert "a" in pd
        assert "b" not in pd

    def test_iteration(self):
        """Test iteration over PropertyDict"""
        pd = PropertyDict({"x": 10, "y": 20, "z": 30})

        keys = list(pd)
        assert set(keys) == {"x", "y", "z"}

        # Test iteration in context
        items = {key: pd[key] for key in pd}
        assert items == {"x": 10, "y": 20, "z": 30}

    def test_pop_method(self):
        """Test pop method"""
        pd = PropertyDict({"keep": "this", "remove": "that"})

        # Pop existing key
        value = pd.pop("remove")
        assert value == "that"
        assert "remove" not in pd

        # Pop non-existing key with default
        value = pd.pop("missing", "default")
        assert value == "default"

    def test_get_method(self):
        """Test get method"""
        pd = PropertyDict({"exists": "value"})

        assert pd.get("exists") == "value"
        assert pd.get("missing") is None
        assert pd.get("missing", "default") == "default"

    def test_string_representations(self):
        """Test string representations"""
        pd = PropertyDict({"test": "data"})

        repr_str = repr(pd)
        assert "PropertyDict" in repr_str
        assert "test" in repr_str

        str_str = str(pd)
        assert "test" in str_str

    def test_private_attributes(self):
        """Test that private attributes are handled correctly"""
        pd = PropertyDict()

        # Private attributes should not go into _data
        pd._private = "private_value"
        assert hasattr(pd, "_private")
        assert "_private" not in pd._data


class TestRouteLitRequest:
    """Test RouteLitRequest abstract base class"""

    def test_basic_request_creation(self):
        """Test basic request creation"""
        request = MockRouteLitRequest()

        assert request.method == "GET"
        assert request.get_host() == "localhost:8000"
        assert request.get_pathname() == "/test"
        assert request.get_session_id() == "test_session"

    def test_ui_event_extraction_from_json(self):
        """Test UI event extraction from JSON data"""
        ui_event = {"type": "click", "componentId": "btn-1", "data": {"value": "clicked"}, "formId": None}
        json_data = {"uiEvent": ui_event}

        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.ui_event == ui_event
        assert request.ui_event["type"] == "click"

    def test_fragment_id_extraction(self):
        """Test fragment ID extraction from JSON"""
        json_data = {"fragmentId": "my-fragment"}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.fragment_id == "my-fragment"

    def test_no_ui_event_when_not_json(self):
        """Test that UI event is None when request is not JSON"""
        request = MockRouteLitRequest(is_json_request=False)

        assert request.ui_event is None
        assert request.fragment_id is None

    def test_clear_event(self):
        """Test clearing UI event"""
        ui_event = {"type": "click", "componentId": "btn", "data": {}, "formId": None}
        json_data = {"uiEvent": ui_event}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.ui_event is not None
        request.clear_event()
        assert request.ui_event is None

    def test_clear_fragment_id(self):
        """Test clearing fragment ID"""
        json_data = {"fragmentId": "test-fragment"}
        request = MockRouteLitRequest(is_json_request=True, json_data=json_data)

        assert request.fragment_id == "test-fragment"
        request.clear_fragment_id()
        assert request.fragment_id is None

    def test_get_host_pathname(self):
        """Test host pathname generation"""
        request = MockRouteLitRequest(host="example.com", pathname="/app/page")

        host_pathname = request.get_host_pathname()
        assert host_pathname == "example.com/app/page"

    def test_get_host_pathname_with_referer(self):
        """Test host pathname with referer"""
        headers = {"X-Referer": "https://other.com/different/path"}
        request = MockRouteLitRequest(host="example.com", pathname="/app/page", headers=headers)

        # Without use_referer
        host_pathname = request.get_host_pathname(use_referer=False)
        assert host_pathname == "example.com/app/page"

        # With use_referer
        host_pathname = request.get_host_pathname(use_referer=True)
        assert host_pathname == "other.com/different/path"

    def test_get_host_pathname_with_standard_referer(self):
        """Test host pathname with standard referer header"""
        request = MockRouteLitRequest(host="example.com", pathname="/app/page", referrer="https://ref.com/ref/path")

        host_pathname = request.get_host_pathname(use_referer=True)
        assert host_pathname == "ref.com/ref/path"

    def test_get_ui_session_keys(self):
        """Test UI session keys generation"""
        request = MockRouteLitRequest(session_id="sess123", host="app.com", pathname="/dashboard")

        ui_key, state_key = request.get_ui_session_keys()

        assert ui_key == "sess123:app.com/dashboard"
        assert state_key == "sess123:app.com/dashboard:state"

    def test_get_session_keys(self):
        """Test complete session keys generation"""
        request = MockRouteLitRequest(session_id="sess456", host="myapp.com", pathname="/home")

        keys = request.get_session_keys()

        assert keys.ui_key == "sess456:myapp.com/home:ui"
        assert keys.state_key == "sess456:myapp.com/home:state"
        assert keys.fragment_addresses_key == "sess456:myapp.com/home:ui:fragments"
        assert keys.fragment_params_key == "sess456:myapp.com/home:ui:fragment_params"

    def test_get_session_keys_with_referer(self):
        """Test session keys generation with referer"""
        headers = {"X-Referer": "https://ref.com/ref"}
        request = MockRouteLitRequest(session_id="sess789", host="app.com", pathname="/page", headers=headers)

        keys = request.get_session_keys(use_referer=True)

        assert keys.ui_key == "sess789:ref.com/ref:ui"
        assert keys.state_key == "sess789:ref.com/ref:state"

    def test_query_params(self):
        """Test query parameter handling"""
        query_params = {"search": "test", "page": "1"}
        query_param_lists = {"tags": ["python", "web"], "categories": ["dev"]}

        request = MockRouteLitRequest(query_params=query_params, query_param_lists=query_param_lists)

        assert request.get_query_param("search") == "test"
        assert request.get_query_param("missing") is None
        assert request.get_query_param_list("tags") == ["python", "web"]
        assert request.get_query_param_list("missing") == []

    def test_internal_referer_priority(self):
        """Test that X-Referer header takes priority over standard referer"""
        headers = {"X-Referer": "https://internal.com/path"}
        request = MockRouteLitRequest(headers=headers, referrer="https://external.com/other")

        internal_ref = request._get_internal_referrer()
        assert internal_ref == "https://internal.com/path"

    def test_internal_referer_fallback(self):
        """Test fallback to standard referer when X-Referer is not present"""
        request = MockRouteLitRequest(referrer="https://fallback.com/path")

        internal_ref = request._get_internal_referrer()
        assert internal_ref == "https://fallback.com/path"

    def test_malformed_json_handling(self):
        """Test handling of malformed JSON data"""
        # Test with non-dict JSON data
        request = MockRouteLitRequest(is_json_request=True, json_data="not a dict")

        assert request.ui_event is None
        assert request.fragment_id is None

    def test_empty_json_handling(self):
        """Test handling of empty JSON data"""
        request = MockRouteLitRequest(is_json_request=True, json_data={})

        assert request.ui_event is None
        assert request.fragment_id is None


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_property_dict_with_none_initial(self):
        """Test PropertyDict with None as initial data"""
        pd = PropertyDict(None)

        assert len(pd) == 0
        assert pd.get_data() == {}

    def test_element_with_empty_props(self):
        """Test RouteLitElement with empty props"""
        element = RouteLitElement(name="div", props={}, key="empty")

        assert element.props == {}
        assert element.name == "div"

    def test_response_with_empty_elements(self):
        """Test RouteLitResponse with empty elements list"""
        response = RouteLitResponse(elements=[], head=Head())

        json_str = response.get_str_json_elements()
        parsed = json.loads(json_str)

        assert parsed == []

    def test_session_keys_with_special_characters(self):
        """Test session keys with special characters in paths"""
        request = MockRouteLitRequest(
            session_id="sess@123", host="app-test.com", pathname="/path/with-dashes_and_underscores"
        )

        keys = request.get_session_keys()

        assert "sess@123" in keys.ui_key
        assert "app-test.com" in keys.ui_key
        assert "path/with-dashes_and_underscores" in keys.ui_key

    def test_property_dict_attribute_deletion(self):
        """Test deleting attributes from PropertyDict"""
        pd = PropertyDict({"delete_me": "value", "keep_me": "other"})

        # Delete via attribute access should work through __delitem__
        del pd["delete_me"]

        assert "delete_me" not in pd
        assert pd.delete_me is None
        assert pd.keep_me == "other"
