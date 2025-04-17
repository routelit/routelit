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
    ):
        self._method = method
        self._session_id = session_id
        self._host = host
        self._pathname = pathname
        self._ui_event = ui_event
        self._query_params = query_params or {}

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

    @property
    def method(self):
        return self._method

    def clear_event(self):
        self._ui_event = None


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
        ui_key, state_key = RouteLit._get_ui_session_key(request)

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
        ui_key, state_key = RouteLit._get_ui_session_key(request)
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
            ui_key, state_key = RouteLit._get_ui_session_key(request)
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

        ui_key, state_key = RouteLit._get_ui_session_key(request)

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
        ui_key, state_key = RouteLit._get_ui_session_key(request)
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
        ui_key, state_key = RouteLit._get_ui_session_key(request)

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
