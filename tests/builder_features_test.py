from routelit.builder import RouteLitBuilder
from routelit.utils.property_dict import PropertyDict


class SimpleMockRequest:
    """A minimal mock request good enough for RouteLitBuilder unit tests."""

    def __init__(self, method: str = "POST") -> None:
        self.method = method
        self.ui_event = None
        self.fragment_id = None
        self.query_params = {}

    def clear_event(self):
        self.ui_event = None

    def clear_fragment_id(self):
        self.fragment_id = None


def _make_builder() -> RouteLitBuilder:
    """Helper to create a fresh builder instance for unit tests."""
    return RouteLitBuilder(request=SimpleMockRequest(), session_state=PropertyDict({}), fragments={})


class TestLayoutHelpers:
    """Tests for `columns` and `flex` helper methods."""

    def test_columns_int_spec(self):
        builder = _make_builder()
        cols = builder.columns(3)  # 3 equal-width columns
        assert len(cols) == 3, "Should return three builders"
        root_child = builder.elements[0]
        assert root_child.props["className"] == "rl-flex rl-flex-row"
        for col_builder in cols:
            col_el = col_builder.parent_element
            assert col_el.props["style"]["flex"] == 1

    def test_columns_weighted_spec(self):
        builder = _make_builder()
        cols = builder.columns([2, 1])  # weighted columns
        assert [c.parent_element.props["style"]["flex"] for c in cols] == [2, 1]

    def test_flex_container(self):
        builder = _make_builder()
        with builder.flex(direction="row", gap="10px", justify_content="between") as flex_builder:
            flex_builder.text("inside flex")
        container = builder.elements[0]
        assert container.name == "flex"
        assert container.props["direction"] == "row"
        assert container.props["gap"] == "10px"
        assert container.props["justifyContent"] == "between"
        assert container.children and container.children[0].name == "markdown"


class TestHeadConfig:
    """Tests for page head configuration helper."""

    def test_set_page_config(self):
        builder = _make_builder()
        builder.set_page_config(page_title="Hello", page_description="World")
        assert builder.get_head().title == "Hello"
        assert builder.get_head().description == "World"
        head_el = builder.elements[0]
        assert head_el.name == "head"
        assert head_el.props["title"] == "Hello"
        assert head_el.props["description"] == "World"
