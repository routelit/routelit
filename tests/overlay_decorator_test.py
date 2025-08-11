from routelit.builder import RouteLitBuilder
from routelit.routelit import RouteLit


class TestCreateOverlayDecorator:
    """Tests for the `create_overlay_decorator` helper on RouteLit."""

    def test_fragment_registration(self):
        rl = RouteLit()
        popup = rl.create_overlay_decorator("popup")

        @popup()
        def my_popup(ui: RouteLitBuilder):
            ui.text("Popup content")

        # The fragment should be registered under its function name
        assert "my_popup" in rl.fragment_registry
