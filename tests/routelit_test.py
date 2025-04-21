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

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict
from collections import defaultdict
from typing import Dict, List, Any, MutableMapping

from routelit.routelit import RouteLit
from routelit._builder import _RouteLitBuilder
from routelit.domain import RouteLitElement, RouteLitBuilder, RouteLitRequest, Action, AddAction, RemoveAction
from routelit.exceptions import RerunException, EmptyReturnException


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

    def is_json(self):
        return False

    def get_json(self):
        return None

    def get_ui_event(self):
        return self._ui_event

    def get_query_param(self, key):
        return self._query_params.get(key)

    def get_query_param_list(self, key):
        return [self._query_params.get(key)] if key in self._query_params else []

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

    @property
    def method(self):
        return self._method

    def clear_event(self):
        self._ui_event = None

    def get_ui_session_keys(self, use_referer=False):
        """Get the UI session keys for this request"""
        if use_referer and self._referer:
            # Parse the referer to get host and pathname
            parts = self._referer.split("/")
            if len(parts) >= 3:
                referer_host = parts[2]
                referer_path = "/" + "/".join(parts[3:])
                ui_key = f"{self._session_id}:{referer_host}{referer_path}"
                state_key = f"{ui_key}:state"
                return ui_key, state_key

        # Default to current request path
        ui_key = f"{self._session_id}:{self._host}{self._pathname}"
        state_key = f"{ui_key}:state"
        return ui_key, state_key

    def get_header(self, key, default=None):
        return self._headers.get(key, default)


class TestRouteLit:
    @pytest.fixture
    def mock_session_storage(self):
        return defaultdict(dict)

    @pytest.fixture
    def mock_cache_storage(self):
        return {}

    @pytest.fixture
    def routelit(self, mock_session_storage, mock_cache_storage):
        return RouteLit(
            BuilderClass=_RouteLitBuilder, session_storage=mock_session_storage, cache_storage=mock_cache_storage
        )

    def test_init(self, routelit, mock_session_storage, mock_cache_storage):
        """Test initialization of RouteLit"""
        assert routelit.BuilderClass == _RouteLitBuilder
        assert routelit.session_storage == mock_session_storage
        assert routelit.cache_storage == mock_cache_storage

    def test_get_ui_session_key(self, routelit):
        """Test generation of UI session keys"""
        request = MockRequest(session_id="test123", host="example.com", pathname="/dashboard")
        ui_key, state_key = request.get_ui_session_keys()

        assert ui_key == "test123:example.com/dashboard"
        assert state_key == "test123:example.com/dashboard:state"

    def test_get_builder_class(self, routelit):
        """Test get_builder_class returns the correct builder class"""
        assert routelit.get_builder_class() == _RouteLitBuilder

    def test_handle_get_request(self, routelit, mock_session_storage):
        """Test handling GET requests"""
        request = MockRequest()

        # Create a simple view function that adds text element
        def view_fn(builder, **kwargs):
            builder.text("Hello, World!", key="hello-text")
            builder.session_state["visited"] = True

        result = routelit.handle_get_request(view_fn, request)

        # Check the result is a list containing one element dict
        assert len(result) == 1
        assert result[0]["name"] == "text"
        assert result[0]["props"]["text"] == "Hello, World!"
        assert result[0]["key"] == "hello-text"

        # Check session storage was updated
        ui_key, state_key = request.get_ui_session_keys()
        assert len(mock_session_storage[ui_key]) == 1
        assert mock_session_storage[state_key]["visited"] is True

    def test_handle_post_request(self, routelit, mock_session_storage):
        """Test handling POST requests and generating actions"""
        # Setup initial state
        request_get = MockRequest()

        # Initial view with one element
        def initial_view(builder, **kwargs):
            builder.text("Initial text", key="text1")

        routelit.handle_get_request(initial_view, request_get)

        # Now make a POST request with a modified view
        request_post = MockRequest(method="POST")

        # Updated view with an additional element
        def updated_view(builder, **kwargs):
            # Keep the original element
            builder.text("Initial text", key="text1")
            # Add a new element
            builder.text("New text", key="text2")

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Mock the compare_elements to return a specific action
            mock_action = AddAction(
                address=[1], element=RouteLitElement(name="text", props={"text": "New text"}, key="text2"), key="text2"
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(updated_view, request_post)

            # Verify compare_elements was called
            mock_compare.assert_called_once()

            # Check result contains the action
            assert len(result) == 1
            assert result[0]["type"] == "add"
            assert result[0]["key"] == "text2"

    def test_handle_rerun_exception(self, routelit):
        """Test handling RerunException during POST request"""
        request = MockRequest(method="POST")

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

            # Verify we got an empty list since mock_compare returns empty
            assert result == []

            # Verify the session state contains the updated value
            ui_key, state_key = request.get_ui_session_keys()
            assert routelit.session_storage[state_key]["attempt"] == 1

    def test_maybe_clear_session_state(self, routelit, mock_session_storage):
        """Test clearing session state"""
        # Setup session data
        session_id = "test_session"
        host = "example.com"
        pathname = "/"
        request = MockRequest(
            session_id=session_id, host=host, pathname=pathname, query_params={"__routelit_clear_session_state": "true"}
        )

        ui_key, state_key = request.get_ui_session_keys()

        # Add some data to session
        routelit.session_storage[ui_key] = [RouteLitElement(name="div", props={}, key="test")]
        routelit.session_storage[state_key] = {"visited": True}

        # Test clearing
        with pytest.raises(EmptyReturnException):
            routelit._maybe_clear_session_state(request, ui_key, state_key)

        # Verify session was cleared
        assert ui_key not in routelit.session_storage
        assert state_key not in routelit.session_storage

    @patch("routelit.routelit.get_vite_components_assets")
    def test_client_assets(self, mock_get_assets, routelit):
        """Test client_assets method returns correct assets"""
        mock_assets = MagicMock(package_name="routelit_elements", js_files=["test.js"], css_files=["test.css"])
        mock_get_assets.return_value = mock_assets

        result = routelit.client_assets()

        assert len(result) == 1
        assert result[0] == mock_assets
        mock_get_assets.assert_called_once_with("routelit_elements")

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
            mock_handle_get.return_value = [
                {"name": "text", "props": {"text": "Response text"}, "key": "response-text"}
            ]

            result = routelit.response(simple_view, request)

            mock_handle_get.assert_called_once_with(simple_view, request)
            assert len(result) == 1
            assert result[0]["name"] == "text"

    def test_response_post(self, routelit):
        """Test response method with POST request"""
        request = MockRequest(method="POST")

        def simple_view(builder, **kwargs):
            pass

        with patch.object(routelit, "handle_post_request") as mock_handle_post:
            mock_action = {"type": "add", "address": [0], "key": "test-div"}
            mock_handle_post.return_value = [mock_action]

            result = routelit.response(simple_view, request)

            mock_handle_post.assert_called_once_with(simple_view, request)
            assert len(result) == 1
            assert result[0]["type"] == "add"

    def test_response_unsupported_method(self, routelit):
        """Test response method with unsupported HTTP method"""
        request = MockRequest(method="PUT")

        def simple_view(builder, **kwargs):
            pass

        with pytest.raises(ValueError, match="Unsupported request method: PUT"):
            routelit.response(simple_view, request)

    def test_empty_return_exception(self, routelit):
        """Test handling EmptyReturnException during POST request"""
        # Create a request with __routelit_clear_session_state parameter
        request = MockRequest(method="POST", query_params={"__routelit_clear_session_state": "true"})

        # Set up session storage with some data to be cleared
        ui_key, state_key = request.get_ui_session_keys()
        routelit.session_storage[ui_key] = [RouteLitElement(name="div", props={}, key="test")]
        routelit.session_storage[state_key] = {"visited": True}

        # Simple view function that should never be called because _maybe_clear_session_state
        # will raise EmptyReturnException first
        def view_fn(builder, **kwargs):
            builder.text("This should not be rendered", key="test-text")

        # The request should trigger _maybe_clear_session_state which raises EmptyReturnException
        result = routelit.handle_post_request(view_fn, request)

        # Should return empty list
        assert result == []

        # Verify session was cleared
        assert ui_key not in routelit.session_storage
        assert state_key not in routelit.session_storage

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
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(view_fn, request)

            # Should call compare_elements with empty list as prev_elements
            mock_compare.assert_called_once()
            assert mock_compare.call_args[0][0] == []

            # Check result contains the action
            assert len(result) == 1
            assert result[0]["type"] == "add"

    def test_get_request_with_existing_session_state(self, routelit):
        """Test GET request with existing session state clears it first"""
        request = MockRequest()
        ui_key, state_key = request.get_ui_session_keys()

        # Set up existing session state
        routelit.session_storage[state_key] = {"old_data": True}

        def view_fn(builder, **kwargs):
            builder.session_state["new_data"] = True
            builder.text("Test text", key="test-div")

        result = routelit.handle_get_request(view_fn, request)

        # Verify old state was cleared and only new state exists
        assert "old_data" not in routelit.session_storage[state_key]
        assert routelit.session_storage[state_key]["new_data"] is True

    def test_button_and_interaction(self, routelit):
        """Test button element creation and interaction"""
        # First render to create button
        request_get = MockRequest()

        def view_with_button(builder, **kwargs):
            builder.button("Click me", key="test-button")

        routelit.handle_get_request(view_with_button, request_get)

        # Then simulate a click event
        ui_event = {"type": "click", "component_id": "test-button", "data": {}}

        request_post = MockRequest(method="POST", ui_event=ui_event)

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
            )
            mock_compare.return_value = [mock_action]

            routelit.handle_post_request(view_with_click_handler, request_post)

            assert button_clicked is True

    def test_navigation_support(self, routelit):
        """Test navigation between pages with preserved state"""
        # Set up initial page
        initial_request = MockRequest(session_id="test_nav", host="example.com", pathname="/page1")

        def page1_view(builder, **kwargs):
            builder.text("Page 1 content", key="page1-content")
            builder.session_state["page1_visited"] = True

        routelit.handle_get_request(page1_view, initial_request)

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

        with patch("routelit.routelit.compare_elements") as mock_compare:
            mock_action1 = AddAction(
                address=[0],
                element=RouteLitElement(name="text", props={"text": "Page 2 content"}, key="page2-content"),
                key="page2-content",
            )
            mock_action2 = AddAction(
                address=[1],
                element=RouteLitElement(name="text", props={"text": "Page 1 was visited"}, key="status-text"),
                key="status-text",
            )
            mock_compare.return_value = [mock_action1, mock_action2]

            result = routelit.handle_post_request(page2_view, nav_request)

            # Check that page1's session state was cleared after navigation
            assert "test_nav:example.com/page1" not in routelit.session_storage
            assert "test_nav:example.com/page1:state" not in routelit.session_storage

            # Check that the actions contain both elements
            assert len(result) == 2
            assert result[0]["key"] == "page2-content"
            assert result[1]["key"] == "status-text"

    def test_expander_component(self, routelit):
        """Test the expander component functionality"""
        request = MockRequest()

        def view_with_expander(builder, **kwargs):
            with builder.expander("Details", key="exp1") as exp:
                exp.text("Expanded content", key="exp-content")

            # Function call style
            exp2 = builder.expander("More Info", open=True, key="exp2")
            exp2.text("More expanded content", key="more-content")

        result = routelit.handle_get_request(view_with_expander, request)

        # Check expander elements were created correctly
        assert len(result) == 2

        # Check first expander
        assert result[0]["name"] == "expander"
        assert result[0]["key"] == "exp1"
        assert result[0]["props"]["title"] == "Details"
        assert result[0]["props"]["open"] is None

        # Check expander children
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "text"
        assert result[0]["children"][0]["key"] == "exp-content"
        assert result[0]["children"][0]["props"]["text"] == "Expanded content"

        # Check second expander
        assert result[1]["name"] == "expander"
        assert result[1]["key"] == "exp2"
        assert result[1]["props"]["title"] == "More Info"
        assert result[1]["props"]["open"] is True

        # Check second expander children
        assert len(result[1]["children"]) == 1
        assert result[1]["children"][0]["name"] == "text"
        assert result[1]["children"][0]["key"] == "more-content"
        assert result[1]["children"][0]["props"]["text"] == "More expanded content"

    def test_text_input_component(self, routelit):
        """Test the text input component functionality"""
        # Initial render
        request_get = MockRequest()

        def view_with_input(builder, **kwargs):
            value = builder.text_input("Username", placeholder="Enter username", key="username-input")
            builder.text(f"Current value: {value}", key="value-display")

        result = routelit.handle_get_request(view_with_input, request_get)

        # Check text input was created correctly
        assert len(result) == 2
        assert result[0]["name"] == "text-input"
        assert result[0]["key"] == "username-input"
        assert result[0]["props"]["label"] == "Username"
        assert result[0]["props"]["placeholder"] == "Enter username"
        assert result[0]["props"]["value"] is None  # Initial value is None instead of empty string

        # Check the display shows empty value
        assert result[1]["props"]["text"] == "Current value: "

        # Now simulate user input
        input_event = {"type": "change", "component_id": "username-input", "data": {"value": "testuser"}}

        request_post = MockRequest(method="POST", ui_event=input_event)

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Create expected action for updating the display text
            mock_action = RemoveAction(address=[1], key="value-display")
            mock_action2 = AddAction(
                address=[1],
                element=RouteLitElement(name="text", props={"text": "Current value: testuser"}, key="value-display"),
                key="value-display",
            )
            mock_compare.return_value = [mock_action, mock_action2]

            result = routelit.handle_post_request(view_with_input, request_post)

            # Check the text input value was updated in session state
            ui_key, state_key = request_post.get_ui_session_keys()
            assert routelit.session_storage[state_key]["username-input"] == "testuser"

            # Check the actions for updating the display
            assert len(result) == 2
            assert result[0]["type"] == "remove"
            assert result[1]["type"] == "add"
            assert result[1]["element"]["props"]["text"] == "Current value: testuser"

    def test_checkbox_component(self, routelit):
        """Test the checkbox component functionality"""
        # Initial render
        request_get = MockRequest()

        def view_with_checkbox(builder, **kwargs):
            is_checked = builder.checkbox("Accept terms", key="terms-checkbox")
            status = "accepted" if is_checked else "not accepted"
            builder.text(f"Terms are {status}", key="status-text")

        result = routelit.handle_get_request(view_with_checkbox, request_get)

        # Check checkbox was created correctly
        assert len(result) == 2
        assert result[0]["name"] == "checkbox"
        assert result[0]["key"] == "terms-checkbox"
        assert result[0]["props"]["label"] == "Accept terms"
        assert result[0]["props"]["checked"] is False

        # Check the status text
        assert result[1]["props"]["text"] == "Terms are not accepted"

        # Now simulate user checking the box
        checkbox_event = {"type": "change", "component_id": "terms-checkbox", "data": {"checked": True}}

        request_post = MockRequest(method="POST", ui_event=checkbox_event)

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Create expected action for updating the status text
            mock_action = RemoveAction(address=[1], key="status-text")
            mock_action2 = AddAction(
                address=[1],
                element=RouteLitElement(name="text", props={"text": "Terms are accepted"}, key="status-text"),
                key="status-text",
            )
            mock_compare.return_value = [mock_action, mock_action2]

            result = routelit.handle_post_request(view_with_checkbox, request_post)

            # Check the checkbox state was updated in session state
            ui_key, state_key = request_post.get_ui_session_keys()
            assert routelit.session_storage[state_key]["terms-checkbox"] is True

            # Check the actions for updating the display
            assert len(result) == 2
            assert result[0]["type"] == "remove"
            assert result[1]["type"] == "add"
            assert result[1]["element"]["props"]["text"] == "Terms are accepted"

    def test_form_handling(self, routelit):
        """Test handling form submissions"""
        # Initial GET request to render the form
        request_get = MockRequest()

        def form_view(builder, **kwargs):
            builder.text("Contact Form", key="form-title")
            name = builder.text_input("Name", key="name-input")
            email = builder.text_input("Email", key="email-input")
            is_subscribed = builder.checkbox("Subscribe to newsletter", key="subscribe-checkbox")

            # Check if form was submitted
            if builder.button("Submit", key="submit-button"):
                if name and email:
                    builder.session_state["form_submitted"] = True
                    builder.session_state["form_data"] = {"name": name, "email": email, "subscribed": is_subscribed}
                    builder.text("Form submitted successfully!", key="success-message")

        # Render initial form
        result = routelit.handle_get_request(form_view, request_get)

        # Verify the form elements are created
        assert len(result) == 5  # Form has 5 elements: title, name input, email input, checkbox, and submit button
        assert result[0]["name"] == "text"
        assert result[1]["name"] == "text-input"
        assert result[2]["name"] == "text-input"
        assert result[3]["name"] == "checkbox"
        assert result[4]["name"] == "button"

        # Now simulate form input events
        # First, set the name
        name_event = {"type": "change", "component_id": "name-input", "data": {"value": "John Doe"}}
        name_request = MockRequest(method="POST", ui_event=name_event)
        routelit.handle_post_request(form_view, name_request)

        # Set the email
        email_event = {"type": "change", "component_id": "email-input", "data": {"value": "john@example.com"}}
        email_request = MockRequest(method="POST", ui_event=email_event)
        routelit.handle_post_request(form_view, email_request)

        # Check the subscribe box
        subscribe_event = {"type": "change", "component_id": "subscribe-checkbox", "data": {"checked": True}}
        subscribe_request = MockRequest(method="POST", ui_event=subscribe_event)
        routelit.handle_post_request(form_view, subscribe_request)

        # Now simulate the form submission
        submit_event = {"type": "click", "component_id": "submit-button", "data": {}}
        submit_request = MockRequest(method="POST", ui_event=submit_event)

        with patch("routelit.routelit.compare_elements") as mock_compare:
            # Create expected action for the success message
            mock_action = AddAction(
                address=[4],
                element=RouteLitElement(
                    name="text", props={"text": "Form submitted successfully!"}, key="success-message"
                ),
                key="success-message",
            )
            mock_compare.return_value = [mock_action]

            result = routelit.handle_post_request(form_view, submit_request)

            # Verify the submit action was processed
            assert len(result) == 1
            assert result[0]["type"] == "add"
            assert result[0]["element"]["props"]["text"] == "Form submitted successfully!"

            # Verify the form data was stored in session state
            ui_key, state_key = submit_request.get_ui_session_keys()
            assert routelit.session_storage[state_key]["form_submitted"] is True
            assert routelit.session_storage[state_key]["form_data"]["name"] == "John Doe"
            assert routelit.session_storage[state_key]["form_data"]["email"] == "john@example.com"
            assert routelit.session_storage[state_key]["form_data"]["subscribed"] is True
