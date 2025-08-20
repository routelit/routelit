"""
Test suite for the create_overlay_decorator functionality.

This test suite verifies the functionality of the create_overlay_decorator method, which is responsible for:
1. Creating custom overlay decorators (popups, sidebars, sheets, etc.)
2. Registering fragments with custom overlay types
3. Properly handling overlay rendering and state management
"""

from unittest.mock import MagicMock, patch

import pytest

from routelit.builder import RouteLitBuilder
from routelit.domain import RouteLitRequest
from routelit.routelit import RouteLit
from routelit.utils.property_dict import PropertyDict


class TestCreateOverlayDecorator:
    @pytest.fixture
    def mock_session_storage(self):
        return {}

    @pytest.fixture
    def mock_builder(self):
        request = MagicMock(spec=RouteLitRequest)
        from routelit.domain import SessionKeys

        session_keys = SessionKeys(
            ui_key="ui_key",
            state_key="state_key",
            fragment_addresses_key="fragment_addresses_key",
            fragment_params_key="fragment_params_key",
            view_tasks_key="view_tasks_key",
        )
        request.get_session_keys.return_value = session_keys
        request.fragment_id = None

        builder = RouteLitBuilder(request=request, session_state=PropertyDict({}), fragments={})

        # Add mock methods for different overlay types
        builder.popup = MagicMock(return_value=builder)
        builder.drawer = MagicMock(return_value=builder)
        builder._dialog = MagicMock(return_value=builder)

        # Mock _fragment context manager
        builder._fragment = MagicMock()
        builder._fragment.return_value.__enter__ = MagicMock()
        builder._fragment.return_value.__exit__ = MagicMock()

        return builder

    def test_create_overlay_decorator(self, mock_session_storage):
        """Test creating a custom overlay decorator"""
        routelit = RouteLit(session_storage=mock_session_storage)

        # Create custom overlay decorators
        popup = routelit.create_overlay_decorator("popup", "popup")
        drawer = routelit.create_overlay_decorator("drawer", "drawer")

        # Should return a callable
        assert callable(popup)
        assert callable(drawer)

        # The returned callable should also return a callable (the actual decorator)
        assert callable(popup())
        assert callable(drawer())

    def test_custom_overlay_registration(self, mock_session_storage):
        """Test that decorated functions are registered in fragment registry"""
        routelit = RouteLit(session_storage=mock_session_storage)

        # Create custom overlay decorator
        popup = routelit.create_overlay_decorator("popup", "popup")

        # Decorate a function
        @popup("test-popup")
        def my_popup(builder):
            builder.text("Popup content")

        # Should register the fragment
        assert "test-popup" in routelit.fragment_registry

        # Using default name from function
        @popup()
        def another_popup(builder):
            builder.text("Another popup")

        # Should register with function name
        assert "another_popup" in routelit.fragment_registry

    def test_overlay_with_custom_method(self, mock_session_storage, mock_builder):
        """Test that overlay uses the specified builder method"""
        routelit = RouteLit(session_storage=mock_session_storage)

        # Create custom overlay decorator
        popup = routelit.create_overlay_decorator("popup", "popup")

        # Decorate a function
        @popup("test-popup")
        def my_popup(builder):
            builder.text("Popup content")

        # Set up context to use the mock builder
        with patch.object(routelit, "_session_builder_context") as mock_context:
            mock_context.get.return_value = mock_builder

            # Call the decorated function
            my_popup()

            # Should use the popup method
            mock_builder.popup.assert_called_once()

    def test_overlay_with_fallback_method(self, mock_session_storage, mock_builder):
        """Test that overlay falls back to _dialog when method doesn't exist"""
        routelit = RouteLit(session_storage=mock_session_storage)

        # Create overlay with non-existent method
        sidebar = routelit.create_overlay_decorator("sidebar", "sidebar")

        # Remove the sidebar method from mock_builder
        if hasattr(mock_builder, "sidebar"):
            delattr(mock_builder, "sidebar")

        @sidebar("test-sidebar")
        def my_sidebar(builder):
            builder.text("Sidebar content")

        # Set up context to use the mock builder
        with patch.object(routelit, "_session_builder_context") as mock_context:
            mock_context.get.return_value = mock_builder

            # Call the decorated function
            my_sidebar()

            # Should fall back to _dialog method
            mock_builder._dialog.assert_called_once()

    def test_overlay_with_custom_parameters(self, mock_session_storage, mock_builder):
        """Test that overlay passes custom parameters to the builder method"""
        routelit = RouteLit(session_storage=mock_session_storage)

        # Create custom overlay decorator
        drawer = routelit.create_overlay_decorator("drawer", "drawer")

        # Decorate with custom parameters
        @drawer("test-drawer", position="right", width="300px")
        def my_drawer(builder):
            builder.text("Drawer content")

        # Set up context to use the mock builder
        with patch.object(routelit, "_session_builder_context") as mock_context:
            mock_context.get.return_value = mock_builder

            # Call the decorated function
            my_drawer()

            # Should call drawer with the custom parameters
            mock_builder.drawer.assert_called_once_with("test-drawer-drawer", position="right", width="300px")
