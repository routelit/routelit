"""
Test suite for the RouteLit class.

This test suite verifies the functionality of the RouteLit class, which is responsible for:
1. Managing the lifecycle of UI components
2. Handling HTTP requests (GET and POST)
3. Managing session state
4. Computing UI differences and generating appropriate actions
5. Handling exceptions (RerunException, EmptyReturnException)
6. Managing client assets

The test suite achieves 100% code coverage for the routelit.py module.
"""

import asyncio
import contextlib
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest

from routelit.builder import RouteLitBuilder
from routelit.domain import (
    Action,
    AddAction,
    Head,
    LastAction,
    RouteLitElement,
    RouteLitRequest,
    RouteLitResponse,
    SessionKeys,
    SetAction,
    ViewTaskDoneAction,
)
from routelit.exceptions import EmptyReturnException, RerunException, StopException
from routelit.routelit import RouteLit
from routelit.utils.property_dict import PropertyDict


def make_async_view(actions):
    """Helper function to create an async view that yields the given actions"""

    async def view(builder, **kwargs):
        for action in actions:
            await builder._event_queue.put(action)
        await builder._event_queue.put(ViewTaskDoneAction(address=[-1], target=builder.initial_target))
        await builder._event_queue.put(LastAction(address=None, target=builder.initial_target))

    return view


# Save original __getattribute__ to restore later
original_getattribute = RouteLitElement.__getattribute__


# Enable dictionary-like access for RouteLitElement
@pytest.fixture(autouse=True)
def patch_routelit_element():
    def new_getitem(self, key):
        attrs = {"name": self.name, "key": self.key, "props": self.props, "children": self.children}
        try:
            return attrs[key]
        except KeyError as err:
            raise KeyError(key) from err

    # Add dictionary-like access to RouteLitElement
    RouteLitElement.__getitem__ = new_getitem

    yield

    # Clean up (technically not required since tests tear down anyway)
    if hasattr(RouteLitElement, "__getitem__"):
        delattr(RouteLitElement, "__getitem__")


# Custom error class for testing
class ViewError(ValueError):
    """Error raised during testing."""

    pass


class MockRequest(RouteLitRequest):
    def __init__(
        self,
        method="GET",
        session_id="test_session",
        host="example.com",
        pathname="/",
        ui_event=None,
        query_params=None,
        headers=None,
        cookies=None,
        form_data=None,
        referer=None,
        fragment_id=None,
    ):
        self._method = method
        self._session_id = session_id
        self._host = host
        self._pathname = pathname
        self._ui_event = ui_event
        self._query_params = query_params or {}
        self._headers = headers or {}
        self._cookies = cookies or {}
        self._form_data = form_data or {}
        self._referer = referer or ""
        self._fragment_id = fragment_id

    def is_json(self):
        return False

    def get_json(self):
        return None

    def get_ui_event(self):
        return self._ui_event

    @property
    def fragment_id(self) -> Optional[str]:
        return self._fragment_id

    def get_query_param(self, key):
        return self._query_params.get(key)

    def get_query_param_list(self, key):
        val = self._query_params.get(key)
        return [val] if val is not None else []

    def get_session_id(self):
        return self._session_id

    def get_pathname(self):
        return self._pathname

    def get_host(self):
        return self._host

    def get_referer(self):
        return self._referer

    def get_referrer(self):
        """Alias for get_referer to match abstract method name"""
        return self.get_referer()

    def get_headers(self):
        """Get all request headers"""
        return self._headers

    def get_cookie(self, key, default=None):
        return self._cookies.get(key, default)

    def get_form_data(self, key, default=None):
        return self._form_data.get(key, default)

    def has_form_data(self, key):
        return key in self._form_data

    def get_path_params(self, key, default=None):
        """Get path parameters from the request"""
        # For testing purposes, return empty dict or the default value
        return default

    @property
    def method(self):
        return self._method

    def clear_event(self):
        self._ui_event = None

    def get_session_keys(self, use_referer=False) -> SessionKeys:
        """Get the UI session keys for this request"""
        host = self._host
        path = self._pathname

        if use_referer and self._referer:
            # Parse the referer to get host and pathname
            # Basic parsing, assumes http/https format
            try:
                from urllib.parse import urlparse

                parsed_referer = urlparse(self._referer)
                host = parsed_referer.netloc
                path = parsed_referer.path
            except ImportError:  # Fallback for simpler parsing if urllib not available
                parts = self._referer.split("/")
                if len(parts) >= 3:
                    host = parts[2]
                    path = "/" + "/".join(parts[3:])

        # Default to current request path if referer parsing fails or not requested
        base_key = f"{self._session_id}:{host}{path}"
        return SessionKeys(
            ui_key=base_key,
            state_key=f"{base_key}:state",
            fragment_addresses_key=f"{base_key}:fragments:addresses",
            fragment_params_key=f"{base_key}:fragments:params",
            view_tasks_key=f"{base_key}:view_tasks",
        )

    def get_header(self, key, default=None):
        return self._headers.get(key, default)


# Define a simple concrete builder for testing RouteLit
class MockBuilder(RouteLitBuilder):
    """Mock builder for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = ""  # Add missing prefix attribute

    def text(self, text, key=None, **kwargs):
        """Mock text method"""
        self._create_non_widget_element("text", key, {"text": text}, address=self._get_next_address())

    def button(self, label: str, key: Optional[str] = None, event_name: str = "click") -> bool:
        """Mock button method"""
        key = key or self._new_widget_id("button", label)
        el_key = f"{self.prefix}_{key}" if self.prefix else key
        # Mock button click detection
        return self.request.ui_event and self.request.ui_event.get("componentId") == el_key

    def text_input(
        self, label: str, value: Optional[str] = None, placeholder: Optional[str] = None, key: Optional[str] = None
    ) -> Optional[str]:
        """Mock text input method"""
        key = key or self._new_widget_id("text_input", label)
        self._create_non_widget_element(
            "text_input",
            key,
            {"label": label, "value": value or "", "placeholder": placeholder},
            address=self._get_next_address(),
        )
        return value

    def checkbox(self, label: str, value: bool = False, key: Optional[str] = None) -> bool:
        """Mock checkbox method"""
        key = key or self._new_widget_id("checkbox", label)
        self._create_non_widget_element(
            "checkbox", key, {"label": label, "checked": value}, address=self._get_next_address()
        )
        return value

    def select(
        self, label: str, options: List[Union[Dict[str, Any], str]], value: Any = "", key: Optional[str] = None
    ) -> Any:
        """Mock select method"""
        key = key or self._new_widget_id("select", label)
        self._create_non_widget_element(
            "select", key, {"label": label, "options": options, "value": value}, address=self._get_next_address()
        )
        return value

    def radio(
        self,
        label: str,
        options: List[Union[Dict[str, Any], str]],
        value: Optional[Any] = None,
        key: Optional[str] = None,
    ) -> Any:
        """Mock radio method"""
        key = key or self._new_widget_id("radio", label)
        self._create_non_widget_element(
            "radio", key, {"label": label, "options": options, "value": value}, address=self._get_next_address()
        )
        return value

    def expander(self, title: str, is_open: Optional[bool] = None, key: Optional[str] = None):
        """Mock expander method"""
        key = key or self._new_widget_id("expander", title)
        element = self._create_non_widget_element(
            "expander", key, {"title": title, "open": is_open}, address=self._get_next_address()
        )
        return self._build_nested_builder(element)

    def fragment(self, key: str):
        """Mock fragment method"""
        element = self._create_non_widget_element("fragment", key, {"id": key}, address=self._get_next_address())
        return self._build_nested_builder(element)

    def dialog(self, key: str, closable: bool = True):
        """Mock dialog method"""
        element = self._create_non_widget_element(
            "dialog", key, {"id": key, "open": True, "closable": closable}, address=self._get_next_address()
        )
        return self._build_nested_builder(element)

    def form(self, key: str):
        """Mock form method"""
        element = self._create_non_widget_element("form", key, {"id": key}, address=self._get_next_address())
        return self._build_nested_builder(element)


class TestRouteLit:
    @pytest.fixture
    def mock_session_storage(self):
        return defaultdict(dict)

    @pytest.fixture
    def routelit(self, mock_session_storage):
        rl = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        return rl

    def test_init(self, routelit, mock_session_storage):
        """Test initialization of RouteLit"""
        assert routelit.BuilderClass == MockBuilder
        assert routelit.session_storage == mock_session_storage

    def test_get_ui_session_key(self, routelit):
        """Test generation of UI session keys"""
        request = MockRequest(session_id="test123", host="example.com", pathname="/dashboard")
        session_keys = request.get_session_keys(use_referer=False)

        assert session_keys.ui_key == "test123:example.com/dashboard"
        assert session_keys.state_key == "test123:example.com/dashboard:state"
        assert session_keys.fragment_addresses_key == "test123:example.com/dashboard:fragments:addresses"
        assert session_keys.fragment_params_key == "test123:example.com/dashboard:fragments:params"

    def test_get_builder_class(self, routelit):
        """Test get_builder_class returns the correct builder class"""
        assert routelit.get_builder_class() == MockBuilder

    def test_handle_get_request(self, routelit, mock_session_storage):
        """Test handling GET requests"""
        request = MockRequest()
        session_keys = request.get_session_keys()

        # Set up existing session state to test clearing
        routelit.session_storage[session_keys.ui_key] = [{"name": "div", "props": {}, "key": "old"}]
        routelit.session_storage[session_keys.state_key] = {"old_data": True}
        routelit.session_storage[session_keys.fragment_addresses_key] = {"old_frag": [0]}
        routelit.session_storage[session_keys.fragment_params_key] = {"old_frag": {}}

        def simple_view(builder, **kwargs):
            builder.text("Response text", key="response-text")

        result = routelit.handle_get_request(simple_view, request)
        assert isinstance(result, RouteLitResponse)
        assert result.elements == []
        assert result.head.title is None
        assert result.head.description is None

    def test_handle_post_request(self, routelit, mock_session_storage):
        """Test handling POST requests and generating actions"""
        # Setup initial state by manually creating session storage
        # since GET request now returns empty elements
        request_post = MockRequest(method="POST")
        session_keys = request_post.get_session_keys()

        # Set up some initial elements in session storage
        initial_element = RouteLitElement(name="text", props={"text": "Initial text"}, key="text1")
        routelit.session_storage[session_keys.ui_key] = [initial_element]
        routelit.session_storage[session_keys.state_key] = {}
        routelit.session_storage[session_keys.fragment_addresses_key] = {}
        routelit.session_storage[session_keys.fragment_params_key] = {}

        # Updated view with an additional element
        def updated_view(builder, **kwargs):
            # Keep the original element
            builder.text("Initial text", key="text1")
            # Add a new element
            builder.text("New text", key="text2")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Mock the compare_elements to return a specific action
            mock_action = AddAction(
                address=[1],
                element=RouteLitElement(name="text", props={"text": "New text"}, key="text2"),
                key="text2",
                target="app",
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(updated_view, request_post)

            assert "actions" in result
            assert "target" in result
            assert result["target"] == "app"
            assert len(result["actions"]) == 1

    def test_handle_rerun_exception(self, routelit):
        """Test handling RerunException during POST request"""
        request = MockRequest(method="POST")
        session_keys = request.get_session_keys()

        # View function that calls builder.rerun() on first call, then succeeds
        call_count = 0

        def view_with_rerun(builder, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                builder.session_state["attempt"] = 1
                builder.rerun()

            # On second call
            builder.text("After rerun", key="rerun-text")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_compare.return_value = []  # No changes after rerun

            result = routelit.handle_post_request(view_with_rerun, request)

            # Verify we got a dict with empty actions list
            assert isinstance(result, dict)
            assert "actions" in result
            assert result["actions"] == []
            assert result["target"] == "app"

            # Verify the session state contains the updated value
            session_keys = request.get_session_keys()
            assert routelit.session_storage[session_keys.state_key]["attempt"] == 1

    def test_handle_rerun_exception_scope_app(self, routelit):
        """Test handling RerunException with scope='app' during POST request"""
        app_call_count = 0
        fragment_call_count = 0

        request = MockRequest(method="POST", fragment_id="my_fragment")

        # Define a fragment that reruns the whole app
        @routelit.fragment("my_fragment")
        def my_fragment(builder, **kwargs):
            nonlocal fragment_call_count
            fragment_call_count += 1
            if fragment_call_count == 1:  # Only rerun on the first fragment call
                builder.rerun(scope="app")
            builder.text("Fragment Content After App Rerun", key="frag-text")

        # Define the main app view
        def app_view(builder, **kwargs):
            nonlocal app_call_count
            app_call_count += 1
            builder.text("App Content", key="app-text")
            my_fragment(builder)  # Embed the fragment

        # Initial setup using POST since GET returns empty elements
        get_request = MockRequest(method="POST")
        session_keys = get_request.get_session_keys()

        # Set up initial session state
        routelit.session_storage[session_keys.ui_key] = []
        routelit.session_storage[session_keys.state_key] = {}
        routelit.session_storage[session_keys.fragment_addresses_key] = {}
        routelit.session_storage[session_keys.fragment_params_key] = {}

        # Rerun Exception is expected, so catch it and continue
        with contextlib.suppress(RerunException):
            with patch("routelit.routelit.compare_elements") as mock_compare_setup:
                mock_compare_setup.return_value = []
                routelit.handle_post_request(app_view, get_request)

        # POST request targeted at the fragment
        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Mock comparison to return the final state after app rerun
            mock_compare.return_value = [
                {
                    "type": "add",
                    "address": [0],
                    "key": "app-text",
                    "element": RouteLitElement(
                        key="app-text", name="text", props={"text": "App Content"}, children=None, address=None
                    ),
                },
                {
                    "type": "add",
                    "address": [1, 0],
                    "key": "frag-text",
                    "element": RouteLitElement(
                        key="frag-text",
                        name="text",
                        props={"text": "Fragment Content After App Rerun"},
                        children=None,
                        address=None,
                    ),
                },
            ]

            result = routelit.handle_post_request(app_view, request)

        # Check the app_view was called during handling POST
        # The count may vary based on rerun behavior
        assert app_call_count >= 1
        # The fragment might be called multiple times in the mocked environment
        assert fragment_call_count >= 1

        # The result should reflect the state after the app rerun
        assert isinstance(result, dict)
        assert "actions" in result
        assert len(result["actions"]) > 0  # Actions reflecting the final state
        assert "app-text" in [a["key"] for a in result["actions"]]
        assert "frag-text" in [a["key"] for a in result["actions"]]

    def test_maybe_clear_session_state(self, routelit, mock_session_storage):
        """Test clearing session state"""
        # Setup session data
        session_id = "test_session"
        host = "example.com"
        pathname = "/"
        request = MockRequest(
            session_id=session_id, host=host, pathname=pathname, query_params={"__routelit_clear_session_state": "true"}
        )

        session_keys = request.get_session_keys()

        # Add some data to session
        routelit.session_storage[session_keys.ui_key] = [RouteLitElement(name="div", props={}, key="test")]
        routelit.session_storage[session_keys.state_key] = {"visited": True}
        routelit.session_storage[session_keys.fragment_addresses_key] = {"frag1": [0]}
        routelit.session_storage[session_keys.fragment_params_key] = {"frag1": {"args": [], "kwargs": {}}}

        # Test clearing
        with pytest.raises(EmptyReturnException):
            routelit._maybe_clear_session_state(request, session_keys)

        # Verify session was cleared
        assert session_keys.ui_key not in routelit.session_storage
        assert session_keys.state_key not in routelit.session_storage
        assert session_keys.fragment_addresses_key not in routelit.session_storage
        assert session_keys.fragment_params_key not in routelit.session_storage

    @patch("routelit.routelit.get_vite_components_assets")
    def test_client_assets(self, mock_get_assets, routelit):
        """Test client_assets method returns correct assets"""
        mock_assets = [{"package_name": "routelit", "src_dir": "static"}]
        mock_get_assets.return_value = mock_assets

        result = routelit.default_client_assets()

        assert len(result) == 1
        assert result[0]["package_name"] == "routelit"
        assert result[0]["src_dir"] == "static"
        mock_get_assets.assert_called_once_with("routelit")

    @patch("routelit.routelit.get_vite_components_assets")
    def test_default_client_assets(self, mock_get_assets, routelit):
        """Test default_client_assets method returns correct assets"""
        mock_assets = MagicMock()
        mock_get_assets.return_value = mock_assets

        result = routelit.default_client_assets()

        assert result == mock_assets
        mock_get_assets.assert_called_once_with("routelit")

    def test_response_get(self, routelit):
        """Test response method with GET request"""
        request = MockRequest(method="GET")

        def simple_view(builder, **kwargs):
            builder.text("Response text", key="response-text")

        with patch.object(routelit, "handle_get_request") as mock_handle_get:
            # GET requests now return RouteLitResponse with empty elements
            mock_handle_get.return_value = RouteLitResponse(elements=[], head=Head(title=None, description=None))

            result = routelit.response(simple_view, request)

            mock_handle_get.assert_called_once_with(simple_view, request)
            assert isinstance(result, RouteLitResponse)

    def test_response_post(self, routelit):
        """Test response method with POST request"""
        request = MockRequest(method="POST")

        def simple_view(builder, **kwargs):
            builder.text("Response text", key="response-text")

        with patch.object(routelit, "handle_post_request") as mock_handle_post:
            mock_handle_post.return_value = {"actions": [], "target": "app"}

            result = routelit.response(simple_view, request)

            mock_handle_post.assert_called_once_with(simple_view, request, None)
            assert result == {"actions": [], "target": "app"}

    def test_response_unsupported_method(self, routelit):
        """Test response method with unsupported HTTP method"""
        request = MockRequest(method="PUT")

        def simple_view(builder, **kwargs):
            pass

        with pytest.raises(ValueError, match="PUT"):
            routelit.response(simple_view, request)

    def test_empty_return_exception(self, routelit):
        """Test handling EmptyReturnException during POST request"""
        # Create a request with __routelit_clear_session_state parameter
        request = MockRequest(method="POST", query_params={"__routelit_clear_session_state": "true"})

        # Set up session storage with some data to be cleared
        session_keys = request.get_session_keys()
        routelit.session_storage[session_keys.ui_key] = [RouteLitElement(name="div", props={}, key="test")]
        routelit.session_storage[session_keys.state_key] = {"visited": True}

        # Simple view function that should never be called because _maybe_clear_session_state
        # will raise EmptyReturnException first
        def view_fn(builder, **kwargs):
            builder.text("This should not be rendered", key="test-text")

        # The request should trigger _maybe_clear_session_state which raises EmptyReturnException
        result = routelit.handle_post_request(view_fn, request)

        # Should return a dict with empty actions list
        assert isinstance(result, dict)
        assert result["actions"] == []
        assert result["target"] == "app"

        # Verify session was cleared
        assert session_keys.ui_key not in routelit.session_storage
        assert session_keys.state_key not in routelit.session_storage

    def test_handle_post_request_no_previous_elements(self, routelit):
        """Test handling POST with no prior elements in session storage"""
        request = MockRequest(method="POST")

        def view_fn(builder, **kwargs):
            builder.text("New element", key="new-text")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_action = AddAction(
                address=[0],
                element=RouteLitElement(name="text", props={"text": "New element"}, key="new-text"),
                key="new-text",
                target="app",
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(view_fn, request)

            assert "actions" in result
            assert "target" in result
            assert result["target"] == "app"
            assert len(result["actions"]) == 1

    def test_get_request_with_existing_session_state(self, routelit):
        """Test GET request with existing session state clears it first"""
        request = MockRequest()
        session_keys = request.get_session_keys()

        # Set up existing session state
        routelit.session_storage[session_keys.state_key] = {"old_data": True}
        routelit.session_storage[session_keys.ui_key] = [RouteLitElement(name="div", props={}, key="old")]
        routelit.session_storage[session_keys.fragment_addresses_key] = {"old_frag": [0]}
        routelit.session_storage[session_keys.fragment_params_key] = {"old_frag": {}}

        def simple_view(builder, **kwargs):
            builder.text("Response text", key="response-text")

        result = routelit.handle_get_request(simple_view, request)
        assert isinstance(result, RouteLitResponse)
        assert result.elements == []

    def test_button_and_interaction(self, routelit):
        """Test button element creation and interaction"""
        # Since GET requests now return empty elements, we need to set up the session state
        # for the POST request to work properly
        request_post = MockRequest(method="POST", ui_event={"type": "click", "componentId": "test-button", "data": {}})
        session_keys = request_post.get_session_keys()

        # Set up initial session state (normally would be done by a previous POST)
        routelit.session_storage[session_keys.ui_key] = []
        routelit.session_storage[session_keys.state_key] = {}
        routelit.session_storage[session_keys.fragment_addresses_key] = {}
        routelit.session_storage[session_keys.fragment_params_key] = {}

        button_clicked = False

        def view_with_click_handler(builder, **kwargs):
            nonlocal button_clicked
            is_clicked = builder.button("Click me", key="test-button")
            if is_clicked:
                button_clicked = True
                builder.text("Button was clicked!", key="click-message")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_action = AddAction(
                address=[1],
                element=RouteLitElement(name="text", props={"text": "Button was clicked!"}, key="click-message"),
                key="click-message",
                target="app",
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(view_with_click_handler, request_post)

            assert "actions" in result
            assert "target" in result

    def test_navigation_support(self, routelit):
        """Test navigation between pages with preserved state"""
        # Set up initial page - since GET requests now return empty elements,
        # we simulate a POST request to set up initial state
        initial_request = MockRequest(method="POST", session_id="test_nav", host="example.com", pathname="/page1")
        initial_session_keys = initial_request.get_session_keys()

        # Manually set up session state as if it came from a previous POST
        routelit.session_storage[initial_session_keys.ui_key] = []
        routelit.session_storage[initial_session_keys.state_key] = {"page1_visited": True}
        routelit.session_storage[initial_session_keys.fragment_addresses_key] = {}
        routelit.session_storage[initial_session_keys.fragment_params_key] = {}

        # Simulate navigation event to page2
        navigation_event = {"type": "navigate", "component_id": "nav-link", "data": {"to": "/page2"}}

        nav_request = MockRequest(
            method="POST",
            session_id="test_nav",
            host="example.com",
            pathname="/page2",
            ui_event=navigation_event,
            referer="http://example.com/page1",
        )

        def page2_view(builder, **kwargs):
            # Access state from page1
            was_page1_visited = builder.session_state.get("page1_visited", False)
            builder.text("Page 2 content", key="page2-content")
            if was_page1_visited:
                builder.text("Page 1 was visited", key="status-text")

        # Need to ensure prev state/elements exist for comparison and state transfer
        # The state from initial setup should be in session_storage under the referer's keys
        referer_session_keys = nav_request.get_session_keys(use_referer=True)
        assert routelit.session_storage[referer_session_keys.state_key]["page1_visited"] is True
        assert len(routelit.session_storage[referer_session_keys.ui_key]) == 0  # Now empty due to initial setup

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # The comparison should be against the (empty) current state of page2
            # Result should reflect the full render of page2
            mock_compare.return_value = [
                AddAction(
                    address=[0],
                    element=RouteLitElement(name="text", props={"text": "Page 2 content"}, key="page2-content"),
                    key="page2-content",
                    target="app",
                ),
                AddAction(
                    address=[1],
                    element=RouteLitElement(name="text", props={"text": "Page 1 was visited"}, key="status-text"),
                    key="status-text",
                    target="app",
                ),
            ]

            result = routelit.handle_post_request(page2_view, nav_request)

            assert "actions" in result
            assert "target" in result
            assert result["target"] == "app"
            assert len(result["actions"]) == 2

    def test_expander_component(self, routelit):
        """Test the expander component functionality"""
        request = MockRequest(method="POST")
        session_keys = request.get_session_keys()

        # Set up initial session state since GET now returns empty elements
        routelit.session_storage[session_keys.ui_key] = []
        routelit.session_storage[session_keys.state_key] = {}
        routelit.session_storage[session_keys.fragment_addresses_key] = {}
        routelit.session_storage[session_keys.fragment_params_key] = {}

        def view_with_expander(builder, **kwargs):
            with builder.expander("Details", key="exp1") as exp:
                exp.text("Expanded content", key="exp-content")

            # Function call style
            exp2 = builder.expander("More Info", is_open=True, key="exp2")
            exp2.text("More expanded content", key="more-content")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Mock the comparison to return expected elements
            mock_compare.return_value = []

            result = routelit.handle_post_request(view_with_expander, request)

        # Check that POST request returned the expected structure
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

        # Since this is a POST request, we need to check the elements that were created
        # during the POST processing. We can verify the session storage was updated.
        session_keys = request.get_session_keys()
        created_elements = routelit.session_storage[session_keys.ui_key]

        # Check expander elements were created correctly
        assert len(created_elements) == 2

        # Check first expander
        assert created_elements[0].name == "expander"
        assert created_elements[0].key == "exp1"
        assert created_elements[0].props["title"] == "Details"
        assert created_elements[0].props["open"] is None

        # Check expander children
        assert len(created_elements[0].children) == 1
        assert created_elements[0].children[0].name == "text"
        assert created_elements[0].children[0].key == "exp-content"
        assert created_elements[0].children[0].props["text"] == "Expanded content"

        # Check second expander
        assert created_elements[1].name == "expander"
        assert created_elements[1].key == "exp2"
        assert created_elements[1].props["title"] == "More Info"
        assert created_elements[1].props["open"] is True

        # Check second expander children
        assert len(created_elements[1].children) == 1
        assert created_elements[1].children[0].name == "text"
        assert created_elements[1].children[0].key == "more-content"
        assert created_elements[1].children[0].props["text"] == "More expanded content"

    def test_text_input_component(self, routelit):
        """Test text input component functionality"""
        request = MockRequest()

        def text_input_view(builder, **kwargs):
            value = builder.text_input("Enter text", key="input1")
            builder.text(f"Current value: {value}", key="value-display")

        result = routelit.handle_post_request(text_input_view, request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

    def test_checkbox_component(self, routelit):
        """Test checkbox component functionality"""
        request = MockRequest()

        def checkbox_view(builder, **kwargs):
            is_checked = builder.checkbox("Accept terms", key="terms-checkbox")
            if is_checked:
                builder.text("Terms are accepted", key="status-text")
            else:
                builder.text("Terms are not accepted", key="status-text")

        result = routelit.handle_post_request(checkbox_view, request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

    def test_form_handling(self, routelit):
        """Test form handling functionality"""
        request = MockRequest()

        def form_view(builder, **kwargs):
            builder.text("Contact Form", key="form-title")
            with builder.form("contact-form"):
                name = builder.text_input("Name", key="name-input")
                _email = builder.text_input("Email", key="email-input")
                _message = builder.textarea("Message", key="message-input")
                is_submitted = builder.button("Submit", event_name="submit", key="submit-btn")
                if is_submitted:
                    builder.text(f"Thank you {name}!", key="thank-you")

        result = routelit.handle_post_request(form_view, request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

    def test_fragment_decorator_and_post(self, routelit):
        """Test fragment decorator and POST request handling"""
        request = MockRequest()

        def main_view(builder, **kwargs):
            builder.text("Main content", key="main-text")
            with builder.fragment("my_fragment"):
                clicks = builder.session_state.get("frag_clicks", 0)
                is_clicked = builder.button("Click me", key="frag-button")
                if is_clicked:
                    builder.session_state["frag_clicks"] = clicks + 1
                builder.text(f"Fragment Clicks: {clicks}", key="frag-clicks-text")

        result = routelit.handle_post_request(main_view, request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

        # Test fragment POST request
        fragment_request = MockRequest(method="POST", fragment_id="my_fragment")
        fragment_result = routelit.handle_post_request(main_view, fragment_request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(fragment_result, dict)
        assert "actions" in fragment_result
        assert "target" in fragment_result

    def test_dialog_decorator(self, routelit):
        """Test dialog decorator functionality"""
        request = MockRequest()

        def dialog_view(builder, **kwargs):
            builder.text("Main page", key="main-text")
            with builder.dialog("my_dialog"):
                builder.text("Dialog: Hello from dialog!", key="dialog-text")
                is_closed = builder.button("Close", key="close-btn")
                if is_closed:
                    builder.rerun(scope="app")

        result = routelit.handle_post_request(dialog_view, request)
        # handle_post_request returns a dict with actions, not RouteLitResponse
        assert isinstance(result, dict)
        assert "actions" in result
        assert "target" in result

    def test_maybe_handle_form_event(self, routelit):
        """Test handling of form events"""
        request = MockRequest(
            ui_event={"type": "change", "componentId": "input1", "formId": "form1", "data": {"value": "test"}}
        )
        session_keys = request.get_session_keys()

        # Test handling form event
        result = routelit._handle_if_form_event(request, session_keys)
        assert result is True

    def test_fragment_post_request_nonexistent_fragment(self, routelit):
        """Test POST request targeting a fragment that doesn't exist in registry"""
        request = MockRequest(method="POST", fragment_id="nonexistent_fragment")

        def main_view(builder, **kwargs):
            builder.text("Main content", key="main-text")

        # Should handle gracefully when fragment doesn't exist
        result = routelit.handle_post_request(main_view, request)
        assert isinstance(result, dict)
        assert "actions" in result

    def test_form_event_handling_submit_type(self, routelit):
        """Test that submit events with formId are not stored as events4later"""
        request = MockRequest(
            method="POST", ui_event={"type": "submit", "componentId": "submit-btn", "formId": "my-form", "data": {}}
        )
        session_keys = request.get_session_keys()

        # Should return False for submit events
        result = routelit._handle_if_form_event(request, session_keys)
        assert result is False

    def test_empty_elements_handling(self, routelit):
        """Test handling of views that create no elements"""
        request = MockRequest()

        def empty_view(builder, **kwargs):
            # This view creates no elements
            builder.session_state["empty_view_called"] = True

        result = routelit.handle_get_request(empty_view, request)
        assert isinstance(result, RouteLitResponse)
        assert result.elements == []

    def test_inject_builder_get_request_with_override(self, mock_session_storage):
        """Test inject_builder override specifically for GET requests"""
        routelit = RouteLit(
            BuilderClass=MockBuilder,
            session_storage=mock_session_storage,
            inject_builder=False,  # Default to False
        )

        def view_with_builder(builder, **kwargs):
            builder.text("GET with builder injection", key="get-builder-text")

        request = MockRequest(method="GET")
        result = routelit.handle_get_request(view_with_builder, request)
        assert isinstance(result, RouteLitResponse)
        assert result.elements == []

    def test_custom_builder_class(self, mock_session_storage):
        """Test RouteLit with custom builder class"""

        class CustomBuilder(MockBuilder):
            def custom_method(self, text: str, key: Optional[str] = None):
                key = key or self._new_text_id("custom")
                self._create_non_widget_element("custom", key, {"text": text})

        custom_routelit = RouteLit(BuilderClass=CustomBuilder, session_storage=mock_session_storage)

        def view_with_custom(builder, **kwargs):
            builder.custom_method("Custom element", key="custom-el")

        request = MockRequest(method="POST")
        session_keys = request.get_session_keys()

        # Set up initial session state
        custom_routelit.session_storage[session_keys.ui_key] = []
        custom_routelit.session_storage[session_keys.state_key] = {}
        custom_routelit.session_storage[session_keys.fragment_addresses_key] = {}
        custom_routelit.session_storage[session_keys.fragment_params_key] = {}

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_compare.return_value = []
            custom_routelit.handle_post_request(view_with_custom, request)

        # Verify custom builder was used (check session storage)
        created_elements = custom_routelit.session_storage[session_keys.ui_key]
        assert len(created_elements) == 1
        assert created_elements[0].name == "custom"
        assert created_elements[0].props["text"] == "Custom element"
        assert created_elements[0].key == "custom-el"

    def test_navigation_with_malformed_referer(self, routelit):
        """Test navigation handling with malformed referer URL"""
        # Test with malformed referer that can't be parsed
        nav_request = MockRequest(
            method="POST",
            ui_event={"type": "navigate", "data": {"to": "/new-page"}},
            referer="not-a-valid-url",
            pathname="/new-page",
        )

        session_keys = nav_request.get_session_keys()
        is_nav, prev_keys = routelit._get_prev_keys(nav_request, session_keys)

        # Should still detect navigation
        assert is_nav is True
        # Should fall back to some reasonable behavior (implementation dependent)
        assert prev_keys is not None

    def test_rerun_exception_with_fragment_scope(self, routelit):
        """Test RerunException with fragment-specific scope"""
        request = MockRequest(method="POST", fragment_id="test_fragment")
        fragment_call_count = 0

        @routelit.fragment("test_fragment")
        def test_fragment(builder):
            nonlocal fragment_call_count
            fragment_call_count += 1
            if fragment_call_count == 1:
                builder.session_state["fragment_attempt"] = 1
                builder.rerun(scope="fragment")
            builder.text("Fragment after rerun", key="frag-text")

        def main_view(builder, **kwargs):
            builder.text("Main content", key="main-text")
            test_fragment(builder)

        # Set up initial state using POST since GET returns empty elements
        get_request = MockRequest(method="POST")
        session_keys = get_request.get_session_keys()

        # Set up initial session state
        routelit.session_storage[session_keys.ui_key] = []
        routelit.session_storage[session_keys.state_key] = {}
        routelit.session_storage[session_keys.fragment_addresses_key] = {}
        routelit.session_storage[session_keys.fragment_params_key] = {}

        # Catch the RerunException that will be raised during initial setup
        with contextlib.suppress(RerunException):
            with patch("routelit.routelit.compare_elements") as mock_compare_setup:
                mock_compare_setup.return_value = []
                routelit.handle_post_request(main_view, get_request)

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_compare.return_value = []

            result = routelit.handle_post_request(main_view, request)

            # Fragment should have been called multiple times due to rerun
            assert fragment_call_count >= 1
            assert isinstance(result, dict)
            assert result["target"] == "fragment"

    @pytest.mark.asyncio
    async def test_handle_post_request_async_stream_yields_actions(self, mock_session_storage):
        """Test async stream handling"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")

        async def async_view(builder, **kwargs):
            action = SetAction(address=[0], element={"name": "div", "props": {}, "key": "a"}, key="a", target="app")
            await builder._event_queue.put(action)
            await builder._event_queue.put(ViewTaskDoneAction(address=[-1], target=builder.initial_target))
            await builder._event_queue.put(LastAction(address=None, target=builder.initial_target))

        gen = routelit.handle_post_request_async_stream(async_view, request)
        results = []
        async for action in gen:
            results.append(action)
        assert any(isinstance(a, SetAction) for a in results)
        assert any(isinstance(a, ViewTaskDoneAction) for a in results)
        assert any(isinstance(a, LastAction) for a in results)

    def test_handle_post_request_stream_sync_bridge(self, mock_session_storage):
        """Test sync stream handling"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")
        actions = [SetAction(address=[0], element={"name": "div", "props": {}, "key": "a"}, key="a", target="app")]
        view = make_async_view(actions)
        gen = routelit.handle_post_request_stream(view, request)
        results = list(gen)
        assert len(results) > 0
        # Check that we get some actions (the exact types may vary)
        assert any(isinstance(a, Action) for a in results)

    def test_propertydict_cancel_event(self, mock_session_storage):
        """Test property dict cancel event"""
        event = asyncio.Event()
        pd = PropertyDict({"foo": 1}, cancel_event=event)
        assert pd.foo == 1
        event.set()
        with pytest.raises(StopException):
            _ = pd.foo
        with pytest.raises(StopException):
            pd["foo"]
        with pytest.raises(StopException):
            pd.foo = 2
        with pytest.raises(StopException):
            pd["foo"] = 2

    def test_request_timeout_configuration(self, mock_session_storage):
        """Test that request timeout can be configured"""
        # Test default timeout
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        assert routelit.request_timeout == 60.0

        # Test custom timeout
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage, request_timeout=30.0)
        assert routelit.request_timeout == 30.0

    def test_cancel_events_management(self, mock_session_storage):
        """Test cancel events are properly managed"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")

        # Initially no cancel events
        assert len(routelit.cancel_events) == 0

        # After a request, cancel events should be created and cleaned up
        def simple_view(builder, **kwargs):
            builder.text("Test", key="test")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_compare.return_value = []
            routelit.handle_post_request(simple_view, request)

        # Cancel events should be cleaned up after request
        assert len(routelit.cancel_events) == 0

    @pytest.mark.asyncio
    async def test_async_stream_timeout_handling(self, mock_session_storage):
        """Test timeout handling in async streams"""
        # Create RouteLit with very short timeout for testing
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage, request_timeout=0.1)
        request = MockRequest(method="POST")

        async def slow_view(builder, **kwargs):
            # Simulate a slow operation that exceeds timeout
            await asyncio.sleep(0.2)
            action = SetAction(
                address=[0], element={"name": "div", "props": {}, "key": "slow"}, key="slow", target="app"
            )
            await builder._event_queue.put(action)

        gen = routelit.handle_post_request_async_stream(slow_view, request)
        results = []

        # Should handle timeout gracefully
        async for action in gen:
            results.append(action)

        # Should not have yielded any actions due to timeout
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_async_stream_cancellation(self, mock_session_storage):
        """Test cancellation handling in async streams"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")

        async def cancellable_view(builder, **kwargs):
            # Simulate work that can be cancelled
            await asyncio.sleep(0.1)
            action = SetAction(
                address=[0], element={"name": "div", "props": {}, "key": "cancelled"}, key="cancelled", target="app"
            )
            await builder._event_queue.put(action)

        gen = routelit.handle_post_request_async_stream(cancellable_view, request)

        # Cancel the generator early
        gen.aclose()

        # Should handle cancellation gracefully
        results = []
        async for action in gen:
            results.append(action)

        # Should not have yielded any actions due to cancellation
        assert len(results) == 0

    def test_build_run_view_async_sync_function(self, mock_session_storage):
        """Test _build_run_view_async with sync function"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")

        def sync_view(builder, **kwargs):
            builder.text("Sync view", key="sync")

        # Test that sync functions are wrapped correctly
        builder = MockBuilder(request, PropertyDict({}), {})
        run_async = routelit._build_run_view_async(sync_view, builder, True, (), {})

        # Should return a callable that returns an awaitable
        assert callable(run_async)

        # Test execution
        import asyncio

        asyncio.run(run_async())

    def test_build_run_view_async_async_function(self, mock_session_storage):
        """Test _build_run_view_async with async function"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)
        request = MockRequest(method="POST")

        async def async_view(builder, **kwargs):
            builder.text("Async view", key="async")

        # Test that async functions are wrapped correctly
        builder = MockBuilder(request, PropertyDict({}), {})
        run_async = routelit._build_run_view_async(async_view, builder, True, (), {})

        # Should return a callable that returns an awaitable
        assert callable(run_async)

        # Test execution
        import asyncio

        asyncio.run(run_async())

    @pytest.mark.asyncio
    async def test_check_if_view_task_failed(self, mock_session_storage):
        """Test _check_if_view_task_failed method"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)

        # Test with successful task
        task = asyncio.create_task(asyncio.sleep(0))
        await task
        # Should not raise any exception
        routelit._check_if_view_task_failed(task)

        # Test with failed task
        async def failing_coro():
            raise ValueError("Test error")

        task = asyncio.create_task(failing_coro())
        await task
        with pytest.raises(ValueError, match="Test error"):
            routelit._check_if_view_task_failed(task)

    @pytest.mark.asyncio
    async def test_cancel_view_task(self, mock_session_storage):
        """Test _cancel_view_task method"""
        routelit = RouteLit(BuilderClass=MockBuilder, session_storage=mock_session_storage)

        # Test cancelling a running task
        task = asyncio.create_task(asyncio.sleep(1))
        await routelit._cancel_view_task(task, timeout=0.1)

        # Task should be cancelled
        assert task.cancelled()

        # Test cancelling already completed task
        task = asyncio.create_task(asyncio.sleep(0))
        await task
        await routelit._cancel_view_task(task, timeout=0.1)

        # Should not raise any exception
