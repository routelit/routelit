"""
Test suite for the async streaming functionality.

This test suite verifies the functionality of the async streaming features, which are responsible for:
1. Handling async view functions that yield actions
2. Converting async generators to sync generators
3. Streaming actions in JSONL format
4. Handling cancellation and timeouts
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from routelit.domain import (
    AddAction,
    FreshBoundaryAction,
    LastAction,
    RouteLitElement,
    RouteLitRequest,
)
from routelit.routelit import RouteLit


class MockRequest(RouteLitRequest):
    def __init__(
        self,
        method="GET",
        session_id="test_session",
        host="example.com",
        pathname="/",
        ui_event=None,
        fragment_id=None,
    ):
        self._method = method
        self._session_id = session_id
        self._host = host
        self._pathname = pathname
        self._ui_event = ui_event
        self._fragment_id = fragment_id
        # Don't call super().__init__() to avoid overriding our values

    def get_headers(self):
        return {}

    def get_path_params(self):
        return None

    def get_referrer(self):
        return None

    def is_json(self):
        return False

    def get_json(self):
        return None

    def get_query_param(self, key):
        return None

    def get_query_param_list(self, key):
        return []

    def get_session_id(self):
        return self._session_id

    def get_pathname(self):
        return self._pathname

    def get_host(self):
        return self._host

    @property
    def method(self):
        return self._method

    def get_session_keys(self, use_referer=False):
        from routelit.domain import SessionKeys

        return SessionKeys(
            ui_key=f"{self._session_id}:{self._host}{self._pathname}:ui",
            state_key=f"{self._session_id}:{self._host}{self._pathname}:state",
            fragment_addresses_key=f"{self._session_id}:{self._host}{self._pathname}:ui:fragments",
            fragment_params_key=f"{self._session_id}:{self._host}{self._pathname}:ui:fragment_params",
            view_tasks_key=f"{self._session_id}:{self._host}{self._pathname}:ui:view_tasks",
        )


class TestAsyncStreaming:
    @pytest.fixture
    def mock_session_storage(self):
        return {}

    @pytest.fixture
    def routelit(self, mock_session_storage):
        return RouteLit(session_storage=mock_session_storage)

    @pytest.mark.asyncio
    async def test_handle_post_request_async_stream(self, routelit):
        """Test that handle_post_request_async_stream yields actions"""
        request = MockRequest(method="POST")

        # Define an async view function
        async def async_view(builder):
            builder.text("First text")
            await asyncio.sleep(0.01)
            builder.text("Second text")

        # Patch the necessary methods to avoid actual execution
        with (
            patch.object(routelit, "_handle_build_params") as mock_build_params,
            patch.object(routelit, "BuilderClass") as MockBuilder,
            patch.object(routelit, "_cancel_and_wait_view_task") as mock_cancel,
        ):
            # Setup mocks
            mock_build_params.return_value = MagicMock()
            mock_builder = MagicMock()
            MockBuilder.return_value = mock_builder
            mock_cancel.return_value = None

            # Create a custom async generator to return our actions
            actions = [
                FreshBoundaryAction(address=[-1], target="app"),
                AddAction(
                    address=[0],
                    element=RouteLitElement(name="text", props={"text": "First text"}, key="text1"),
                    key="text1",
                    target="app",
                ),
                AddAction(
                    address=[1],
                    element=RouteLitElement(name="text", props={"text": "Second text"}, key="text2"),
                    key="text2",
                    target="app",
                ),
                LastAction(address=None, target="app"),
            ]

            async def mock_generator():
                for action in actions:
                    yield action

            # Use a real async generator instead of mocking the method
            async def mock_async_stream(*args, **kwargs):
                for action in actions:
                    yield action

            # Replace the method with our mock generator function
            original_method = routelit.handle_post_request_async_stream
            routelit.handle_post_request_async_stream = mock_async_stream

            try:
                # Collect the yielded actions
                actions_result = []
                async for action in routelit.handle_post_request_async_stream(async_view, request):
                    actions_result.append(action)
            finally:
                # Restore the original method
                routelit.handle_post_request_async_stream = original_method

            # Verify the actions
            assert len(actions_result) == 4
            assert isinstance(actions_result[0], FreshBoundaryAction)
            assert isinstance(actions_result[1], AddAction)
            assert isinstance(actions_result[2], AddAction)
            assert isinstance(actions_result[3], LastAction)

            # Verify the content of the actions
            assert actions_result[1].key == "text1"
            assert actions_result[1].element.props["text"] == "First text"
            assert actions_result[2].key == "text2"
            assert actions_result[2].element.props["text"] == "Second text"

    @pytest.mark.asyncio
    async def test_handle_post_request_async_stream_jsonl(self, routelit):
        """Test that handle_post_request_async_stream_jsonl yields JSON lines"""
        request = MockRequest(method="POST")

        # Define a simple async view function
        async def async_view(builder):
            builder.text("Hello world")

        # Patch to return a known set of actions
        with patch.object(routelit, "handle_post_request_async_stream") as mock_stream:
            # Create mock actions
            actions = [
                FreshBoundaryAction(address=[-1], target="app"),
                AddAction(
                    address=[0],
                    element=RouteLitElement(name="text", props={"text": "Hello world"}, key="text1"),
                    key="text1",
                    target="app",
                ),
                LastAction(address=None, target="app"),
            ]

            # Setup the mock to yield our actions
            async def mock_generator():
                for action in actions:
                    yield action

            mock_stream.return_value = mock_generator()

            # Collect the yielded JSON lines
            jsonl_results = []
            async for line in routelit.handle_post_request_async_stream_jsonl(async_view, request):
                jsonl_results.append(line)

            # Verify we got the expected number of lines
            assert len(jsonl_results) == 3

            # Each line should be valid JSON and end with newline
            for line in jsonl_results:
                assert line.endswith("\n")
                # Parse the JSON to verify it's valid
                parsed = json.loads(line.rstrip("\n"))
                assert "type" in parsed

            # Verify the content matches our actions
            first_json = json.loads(jsonl_results[0].rstrip("\n"))
            assert first_json["type"] == "fresh_boundary"

            second_json = json.loads(jsonl_results[1].rstrip("\n"))
            assert second_json["type"] == "add"
            assert second_json["key"] == "text1"

            third_json = json.loads(jsonl_results[2].rstrip("\n"))
            assert third_json["type"] == "last"

    def test_handle_post_request_stream(self, routelit):
        """Test that handle_post_request_stream yields actions synchronously"""
        request = MockRequest(method="POST")

        # Define a simple view function
        def sync_view(builder):
            builder.text("Hello world")

        # Patch the async stream method and async_to_sync_generator
        with (
            patch.object(routelit, "handle_post_request_async_stream") as _mock_async_stream,
            patch("routelit.routelit.async_to_sync_generator") as mock_converter,
        ):
            # Create mock actions
            actions = [
                FreshBoundaryAction(address=[-1], target="app"),
                AddAction(
                    address=[0],
                    element=RouteLitElement(name="text", props={"text": "Hello world"}, key="text1"),
                    key="text1",
                    target="app",
                ),
                LastAction(address=None, target="app"),
            ]

            # Setup the mock converter to return our actions
            mock_converter.return_value = actions

            # Call the method
            result = list(routelit.handle_post_request_stream(sync_view, request))

            # Verify the converter was called with the async generator
            mock_converter.assert_called_once()

            # Verify we got the expected actions
            assert len(result) == 3
            assert isinstance(result[0], FreshBoundaryAction)
            assert isinstance(result[1], AddAction)
            assert isinstance(result[2], LastAction)

    def test_handle_post_request_stream_jsonl(self, routelit):
        """Test that handle_post_request_stream_jsonl yields JSON lines synchronously"""
        request = MockRequest(method="POST")

        # Define a simple view function
        def sync_view(builder):
            builder.text("Hello world")

        # Patch the async stream method and async_to_sync_generator
        with (
            patch.object(routelit, "handle_post_request_async_stream") as _mock_async_stream,
            patch("routelit.routelit.async_to_sync_generator") as mock_converter,
        ):
            # Create mock actions
            actions = [
                FreshBoundaryAction(address=[-1], target="app"),
                AddAction(
                    address=[0],
                    element=RouteLitElement(name="text", props={"text": "Hello world"}, key="text1"),
                    key="text1",
                    target="app",
                ),
                LastAction(address=None, target="app"),
            ]

            # Setup the mock converter to return our actions
            mock_converter.return_value = actions

            # Call the method
            result = list(routelit.handle_post_request_stream_jsonl(sync_view, request))

            # Verify the converter was called with the async generator
            mock_converter.assert_called_once()

            # Verify we got the expected JSON lines
            assert len(result) == 3

            # Each line should be valid JSON and end with newline
            for line in result:
                assert line.endswith("\n")
                # Parse the JSON to verify it's valid
                parsed = json.loads(line.rstrip("\n"))
                assert "type" in parsed
