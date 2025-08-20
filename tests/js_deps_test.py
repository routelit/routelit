"""
Test suite for the JavaScript dependencies functionality.

This test suite verifies the functionality of the JavaScript dependencies feature, which is responsible for:
1. Managing default JavaScript dependencies
2. Allowing custom importmap configuration
3. Generating importmap JSON for client rendering
"""

import json

from routelit.routelit import RouteLit
from routelit.utils.js_deps import DEFAULT_JS_DEPENDENCIES


class TestJsDependencies:
    def test_default_js_dependencies(self):
        """Test that default JS dependencies are set correctly"""
        routelit = RouteLit()
        assert routelit.importmap == DEFAULT_JS_DEPENDENCIES

        # Verify specific keys and values
        assert "react" in routelit.importmap
        assert "react/jsx-runtime" in routelit.importmap
        assert "react-dom" in routelit.importmap
        assert "routelit-client" in routelit.importmap

        # Verify URLs are correct format
        assert routelit.importmap["react"].startswith("https://")
        assert "esm.sh" in routelit.importmap["react"]

    def test_custom_importmap(self):
        """Test that custom importmap can be provided and merges with defaults"""
        custom_imports = {
            "custom-lib": "https://esm.sh/custom-lib@1.0.0",
            "react": "https://custom-cdn.com/react@18.0.0",  # Override default
        }

        routelit = RouteLit(importmap=custom_imports)

        # Custom import should be present
        assert "custom-lib" in routelit.importmap
        assert routelit.importmap["custom-lib"] == "https://esm.sh/custom-lib@1.0.0"

        # Default react should be overridden
        assert routelit.importmap["react"] == "https://custom-cdn.com/react@18.0.0"

        # Other defaults should still be present
        assert "react-dom" in routelit.importmap
        assert "routelit-client" in routelit.importmap

    def test_get_importmap_json(self):
        """Test that importmap JSON is generated correctly"""
        routelit = RouteLit()
        importmap_json = routelit.get_importmap_json()

        # Should be valid JSON
        parsed = json.loads(importmap_json)

        # Should have imports key
        assert "imports" in parsed

        # Imports should match the importmap
        assert parsed["imports"] == routelit.importmap

        # Should be properly formatted JSON with indentation
        assert "  " in importmap_json  # Check for indentation
