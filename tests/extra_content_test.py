"""
Test suite for the extra head and body content functionality.

This test suite verifies the functionality of the extra head and body content features, which are responsible for:
1. Adding custom content to the HTML head section
2. Adding custom content to the HTML body section
3. Retrieving the custom content for template rendering
"""

from routelit.routelit import RouteLit


class TestExtraContent:
    def test_default_extra_content(self):
        """Test that default extra content is empty"""
        routelit = RouteLit()
        assert routelit.extra_head_content is None
        assert routelit.extra_body_content is None

        # Get methods should return empty strings for None values
        assert routelit.get_extra_head_content() == ""
        assert routelit.get_extra_body_content() == ""

    def test_custom_extra_head_content(self):
        """Test that custom extra head content can be provided"""
        custom_head = '<meta name="theme-color" content="#ffffff">'
        routelit = RouteLit(extra_head_content=custom_head)

        # Should store the original content
        assert routelit.extra_head_content == custom_head

        # Get method should return the content
        assert routelit.get_extra_head_content() == custom_head

    def test_custom_extra_body_content(self):
        """Test that custom extra body content can be provided"""
        custom_body = '<script>console.log("Custom body script");</script>'
        routelit = RouteLit(extra_body_content=custom_body)

        # Should store the original content
        assert routelit.extra_body_content == custom_body

        # Get method should return the content
        assert routelit.get_extra_body_content() == custom_body

    def test_both_extra_content(self):
        """Test that both extra head and body content can be provided"""
        custom_head = '<link rel="icon" href="favicon.ico">'
        custom_body = '<div id="custom-root"></div>'

        routelit = RouteLit(extra_head_content=custom_head, extra_body_content=custom_body)

        # Should store both contents
        assert routelit.extra_head_content == custom_head
        assert routelit.extra_body_content == custom_body

        # Get methods should return the respective content
        assert routelit.get_extra_head_content() == custom_head
        assert routelit.get_extra_body_content() == custom_body
