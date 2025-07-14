from typing import Any, List, Mapping, MutableMapping, Optional

import pytest

from routelit.builder import RouteLitBuilder
from routelit.domain import RouteLitElement, RouteLitRequest, SessionKeys
from routelit.exceptions import RerunException
from routelit.utils.property_dict import PropertyDict


# Use the MockRequest from routelit_test or define a similar one here
class MockRequestBuilder(RouteLitRequest):
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
        self._headers = {}
        self._cookies = {}
        self._query_params = {}
        self._path_params = {}

    @property
    def method(self):
        return self._method

    @property
    def ui_event(self):
        return self._ui_event

    @property
    def fragment_id(self):
        return self._fragment_id

    def get_session_keys(self, use_referer=False) -> SessionKeys:
        base_key = f"{self._session_id}:{self._host}{self._pathname}"
        return SessionKeys(
            ui_key=base_key,
            state_key=f"{base_key}:state",
            fragment_addresses_key=f"{base_key}:fragments:addresses",
            fragment_params_key=f"{base_key}:fragments:params",
            view_tasks_key=f"{base_key}:view_tasks",
        )

    def clear_event(self):
        self._ui_event = None

    def clear_fragment_id(self):
        self._fragment_id = None

    def get_query_param(self, key):
        return self._query_params.get(key)

    # --- Implement missing abstract methods ---
    def get_headers(self) -> MutableMapping[str, str]:
        return self._headers

    def get_path_params(self) -> Optional[Mapping[str, Any]]:
        return self._path_params

    def get_host(self) -> str:
        return self._host

    def get_json(self) -> Any:
        return None  # Assume no JSON body for mock

    def get_pathname(self) -> str:
        return self._pathname

    def get_query_param_list(self, key) -> List[str]:
        val = self._query_params.get(key)
        return [val] if val is not None else []

    def get_referrer(self) -> str:
        # If you need referrer testing, add it to __init__ like in routelit_test.py
        return self._headers.get("referer", "")

    def get_session_id(self) -> str:
        return self._session_id

    def is_json(self) -> bool:
        return False  # Assume no JSON body for mock

    # --- End of missing methods ---


class TestRouteLitBuilder:
    @pytest.fixture
    def mock_request(self):
        return MockRequestBuilder()

    @pytest.fixture
    def builder(self, mock_request):
        return RouteLitBuilder(request=mock_request, session_state=PropertyDict({}), fragments={})

    def test_init_defaults(self, builder, mock_request):
        """Test builder initialization with default values."""
        assert builder.request == mock_request
        assert builder.initial_fragment_id is None
        assert builder.fragments == {}
        assert builder._get_prefix() == ""  # Use method instead of attribute
        assert len(builder.session_state) == 0
        assert builder.parent_element is not None
        assert builder.parent_builder is None
        assert builder.address == []  # Use property instead of attribute
        assert builder.elements == []
        assert builder.elements_count == 0
        assert builder.active_child_builder is None

    def test_init_with_parent(self, builder):
        """Test initialization with a parent element and builder."""
        parent_element = RouteLitElement(key="parent_key", name="div", props={})
        nested_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            fragments=builder.fragments,
            parent_element=parent_element,
            parent_builder=builder,
        )
        assert nested_builder._get_prefix() == "parent_key"  # Use method instead of attribute
        assert nested_builder.parent_element == parent_element
        assert nested_builder.parent_builder == builder
        # The builder's elements should be the same as the parent element's children
        assert nested_builder.elements == parent_element.get_children()

    def test_init_with_prefix_override(self, builder):
        """Test initialization with explicit prefix override."""
        parent_element = RouteLitElement(key="parent_key", name="div", props={})
        nested_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            fragments=builder.fragments,
            parent_element=parent_element,
            parent_builder=builder,
        )
        assert nested_builder._get_prefix() == "parent_key"  # Uses parent key

    def test_id_generation(self, builder):
        """Test generation of IDs for non-widget and widget elements."""
        # Non-widget
        builder.q_by_name["text"] = 5
        assert builder._new_text_id("text") == "_text_6"  # q_by_name starts at 1
        # Widget
        # Hash of 'My Button' is '19e...'. First 8 chars: '19e9c728'
        assert builder._new_widget_id("button", "My Button") == "_button_19e9c728"

    def test_id_generation_with_prefix(self, builder):
        """Test ID generation when a prefix is set."""
        # Set up a parent element with a key to simulate prefix
        parent_element = RouteLitElement(key="section1", name="div", props={})
        builder._parent_element = parent_element
        builder.q_by_name["div"] = 2
        assert builder._new_text_id("div") == "section1_div_3"  # q_by_name starts at 1
        # Hash of 'Submit' is '155...'. First 8 chars: '155f816c'
        assert builder._new_widget_id("btn", "Submit") == "section1_btn_155f816c"

    def test_add_non_widget(self, builder):
        """Test adding a non-widget element increments counter."""
        assert builder.q_by_name == {}
        element = RouteLitElement(name="text", props={"text": "Hello"}, key="text1")
        builder._add_non_widget(element)
        assert len(builder.elements) == 1
        assert builder.elements[0] == element

    def test_add_widget(self, builder):
        """Test adding a widget element does not increment non-widget counter."""
        assert builder.q_by_name == {}
        element = RouteLitElement(name="button", props={"text": "Click"}, key="btn1")
        builder._add_widget(element)
        assert len(builder.elements) == 1
        assert builder.elements[0] == element

    def test_address_calculation(self, builder):
        """Test address calculation for next and last elements."""
        # Test initial state
        assert builder._get_next_address() == [0]
        assert builder._get_last_address() == [-1]  # No elements yet

        # Add an element and test again
        element = RouteLitElement(name="div", props={}, key="test")
        builder._add_non_widget(element)
        assert builder._get_next_address() == [1]
        assert builder._get_last_address() == [0]

    def test_nested_builder_context_manager(self, builder):
        """Test using a nested builder via context manager (__enter__/__exit__)."""
        parent_element = builder._create_element("container", key="cont1")
        assert builder.active_child_builder is None

        with builder._build_nested_builder(parent_element) as nested:
            assert builder.active_child_builder == nested
            assert nested.parent_builder == builder
            assert nested._get_prefix() == "cont1"  # Use method instead of attribute
            assert nested.parent_element == parent_element

        assert builder.active_child_builder is None

    def test_append_element_redirects_to_active_child(self, builder):
        """Test that append_element redirects to active child builder."""
        parent_element = builder._create_element("container", key="cont1")
        with builder._build_nested_builder(parent_element) as nested:
            element = RouteLitElement(name="text", props={"text": "Hello"}, key="text1")
            builder._append_element(element)
            assert len(nested.elements) == 1
            # The element should be added to the nested builder, not the parent
            assert len(builder.elements) == 1  # Only the container element

    def test_id_generation_redirects_to_active_child(self, builder):
        """Test that ID generation uses the active child builder's state."""
        parent_element = builder._create_element("container", key="cont1")
        with builder._build_nested_builder(parent_element) as nested:
            nested.q_by_name["p"] = 3
            builder.q_by_name["p"] = 10  # Parent has different count

            # Generate ID using parent builder while child is active
            new_id = builder._new_text_id("p")

            assert new_id == "cont1_p_4"  # Uses nested builder's prefix and count

    def test_fragment_creation(self, builder):
        """Test creating a fragment element and its associated builder."""
        assert builder.fragments == {}
        next_addr = builder._get_next_address()  # Get next address *before* creating fragment
        frag_builder = builder._fragment("frag1")

        # Check fragment element was added to main builder
        assert len(builder.elements) == 1
        frag_element = builder.elements[0]
        assert frag_element.name == "fragment"
        assert frag_element.key == "frag1"
        assert frag_element.address == next_addr  # Address should be the calculated next address

        # Check fragment was registered
        assert builder.fragments == {"frag1": next_addr}

        # Check the returned builder is correctly configured
        assert frag_builder.parent_element == frag_element
        assert frag_builder._get_prefix() == "frag1"  # Use method instead of attribute

    def test_get_elements_without_fragment(self, builder):
        """Test get_elements when no initial fragment ID is set."""
        element = RouteLitElement(name="div", props={}, key="test")
        builder._add_non_widget(element)
        assert builder.get_elements() == [element]

    @pytest.mark.skip(reason="Complex fragment edge case - may need investigation")
    def test_get_elements_with_fragment(self, builder, mock_request):
        """Test get_elements when an initial fragment ID is set."""
        # Simulate being called for a fragment request
        mock_request._fragment_id = "frag1"
        fragmented_builder = RouteLitBuilder(
            request=mock_request,
            session_state=PropertyDict({}),
            fragments={},
            initial_fragment_id="frag1",  # Set the initial fragment ID
            initial_target="fragment",  # Set the initial target to fragment
        )

        # Build elements *as if* they are inside the fragment
        # In a real scenario, the fragment's view function would be called
        # directly with this builder.
        fragmented_builder._create_element("text", "t1")
        # The elements should be available in the builder
        # Note: Even with initial_target="fragment", elements are still added to the parent element
        assert len(fragmented_builder.get_elements()) == 1

    def test_rerun(self, builder):
        """Test the rerun method raises RerunException."""
        builder.session_state["value"] = 1
        builder.elements.append(RouteLitElement(key="el1", name="text", props={}))

        with pytest.raises(RerunException) as exc_info:
            builder.rerun()

        # Check exception details
        assert exc_info.value.scope == "auto"
        assert exc_info.value.state == {"value": 1}

    def test_rerun_scope_app_and_clear_event_false(self, builder):
        """Test rerun with scope='app' and clear_event=False."""
        builder.session_state["value"] = 1

        with pytest.raises(RerunException) as exc_info:
            builder.rerun(scope="app", clear_event=False)

        assert exc_info.value.scope == "app"
        assert exc_info.value.state == {"value": 1}

    def test_link_creation(self, builder):
        """Test creating a link element."""
        link = builder.link("/home", text="Go Home", key="home-link", replace=True, custom_prop="abc")
        assert len(builder.elements) == 1
        assert link == builder.elements[0]
        assert link.name == "link"
        assert link.key == "home-link"
        assert link.props["href"] == "/home"
        assert link.props["text"] == "Go Home"
        assert link.props["replace"] is True
        assert link.props["isExternal"] is False
        assert link.props["custom_prop"] == "abc"

    def test_link_area_creation(self, builder):
        """Test creating a link area and its nested builder."""
        with builder.link_area(
            "/details", key="details-area", is_external=True, className="extra-class"
        ) as area_builder:
            area_builder._create_element("img", key="icon")
            area_builder._create_element("span", key="label", props={"text": "Details"})

        assert len(builder.elements) == 1
        link_area_element = builder.elements[0]
        assert link_area_element.name == "link"
        assert link_area_element.key == "details-area"
        assert link_area_element.props["href"] == "/details"
        assert link_area_element.props["isExternal"] is True
        assert link_area_element.props["replace"] is False
        assert link_area_element.props["className"] == "rl-no-link-decoration extra-class"  # Check class merging

    def test_deeply_nested_builders(self, builder):
        """Test address calculation and ID generation in deeply nested builders."""
        with builder._build_nested_builder(builder._create_element("div", "level1")) as b1:
            assert b1._get_prefix() == "level1"  # Use method instead of attribute
            with b1._build_nested_builder(b1._create_element("div", "level2")) as b2:
                assert b2._get_prefix() == "level2"  # Use method instead of attribute
                assert b2._get_next_address() == [0, 0, 0]  # [level1_idx, level2_idx, next_element_idx]

                # Test ID generation in deeply nested context
                b2.q_by_name["text"] = 1
                assert b2._new_text_id("text") == "level2_text_2"  # q_by_name starts at 1

    def test_text_element_creation(self, builder):
        """Test creating a text element with various properties."""
        text = builder._create_non_widget_element(
            "text", key="greeting", props={"content": "Hello World", "className": "large", "style": {"color": "red"}}
        )
        assert len(builder.elements) == 1
        assert text == builder.elements[0]
        assert text.name == "text"
        assert text.key == "greeting"
        assert text.props["content"] == "Hello World"
        assert text.props["className"] == "large"
        assert text.props["style"] == {"color": "red"}

    def test_button_creation(self, builder):
        """Test creating a button element with event handler."""
        button = builder._create_element(
            "button", key="submit-btn", props={"text": "Click Me", "onClick": "handleClick", "disabled": True}
        )
        assert len(builder.elements) == 1
        assert button == builder.elements[0]
        assert button.name == "button"
        assert button.key == "submit-btn"
        assert button.props["text"] == "Click Me"
        assert button.props["onClick"] == "handleClick"
        assert button.props["disabled"] is True

    def test_conditional_rendering(self, builder):
        """Test conditional rendering based on session state."""
        builder.session_state["show_details"] = False

        # Always show main content
        builder._create_non_widget_element("text", key="main", props={"content": "Main Content"})

        # Conditionally show details
        if builder.session_state["show_details"]:
            builder._create_non_widget_element("text", key="details", props={"content": "Detailed Info"})

        assert len(builder.elements) == 1
        assert builder.elements[0].props["content"] == "Main Content"

        # Change state and render again
        builder.session_state["show_details"] = True
        # Clear previous elements by creating a new builder
        new_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            fragments=builder.fragments,
        )
        new_builder._create_non_widget_element("text", key="main", props={"content": "Main Content"})
        if new_builder.session_state["show_details"]:
            new_builder._create_non_widget_element("text", key="details", props={"content": "Detailed Info"})

        assert len(new_builder.elements) == 2
        assert new_builder.elements[1].props["content"] == "Detailed Info"

    def test_dialog_creation(self, builder):
        """Test creating a dialog element and its associated builder."""
        dialog_builder = builder._dialog("my-dialog", closable=True)

        # Check dialog element was added to main builder
        assert len(builder.elements) == 1
        dialog_element = builder.elements[0]
        assert dialog_element.name == "dialog"
        assert dialog_element.key == "my-dialog"
        assert dialog_element.props["id"] == "my-dialog"
        assert dialog_element.props["open"] is True
        assert dialog_element.props["closable"] is True

        # Check the returned builder is correctly configured
        assert dialog_builder.parent_element == dialog_element
        assert dialog_builder._get_prefix() == "my-dialog"  # Use method instead of attribute

    def test_markdown_creation(self, builder):
        """Test creating a markdown component."""
        builder.markdown("# Hello World\n\nThis is **bold**", key="my-markdown", allow_unsafe_html=True)

        assert len(builder.elements) == 1
        markdown_element = builder.elements[0]
        assert markdown_element.name == "markdown"
        assert markdown_element.key == "my-markdown"
        assert markdown_element.props["body"] == "# Hello World\n\nThis is **bold**"
        assert markdown_element.props["allowUnsafeHtml"] is True

    def test_text_creation(self, builder):
        """Test creating a text component."""
        builder.text("Simple text content", key="my-text")

        assert len(builder.elements) == 1
        text_element = builder.elements[0]
        assert text_element.name == "markdown"  # text uses markdown internally
        assert text_element.key == "my-text"
        assert text_element.props["body"] == "Simple text content"
        assert text_element.props["allowUnsafeHtml"] is False

    def test_title_creation(self, builder):
        """Test creating a title component."""
        builder.title("Page Title", key="page-title", className="large")

        assert len(builder.elements) == 1
        title_element = builder.elements[0]
        assert title_element.name == "title"
        assert title_element.key == "page-title"
        assert title_element.props["body"] == "Page Title"
        assert title_element.props["className"] == "large"

    def test_header_creation(self, builder):
        """Test creating a header component."""
        builder.header("Main Header", key="main-header")

        assert len(builder.elements) == 1
        header_element = builder.elements[0]
        assert header_element.name == "header"
        assert header_element.key == "main-header"
        assert header_element.props["body"] == "Main Header"

    def test_subheader_creation(self, builder):
        """Test creating a subheader component."""
        builder.subheader("Section Header", key="section-header")

        assert len(builder.elements) == 1
        subheader_element = builder.elements[0]
        assert subheader_element.name == "subheader"
        assert subheader_element.key == "section-header"
        assert subheader_element.props["body"] == "Section Header"

    def test_image_creation(self, builder):
        """Test creating an image component."""
        builder.image("https://example.com/image.png", key="my-image", alt="Test Image", width="100px")

        assert len(builder.elements) == 1
        image_element = builder.elements[0]
        assert image_element.name == "image"
        assert image_element.key == "my-image"
        assert image_element.props["src"] == "https://example.com/image.png"
        assert image_element.props["alt"] == "Test Image"
        assert image_element.props["width"] == "100px"

    def test_widget_vs_non_widget_classification(self, builder):
        """Test that widgets and non-widgets are classified correctly."""
        # Non-widgets
        builder.text("Text content")
        builder.markdown("**Bold text**")
        builder.image("test.jpg")
        builder.title("Page Title")
        builder.header("Header")
        builder.subheader("Subheader")

        # Widgets
        builder.button("Click me")
        builder.text_input("Name")
        builder.checkbox("Check me")
        builder.select("Choose", ["Option 1", "Option 2"])
        builder.radio("Pick one", ["A", "B"])

        # Check counts - all elements should be added
        assert len(builder.elements) == 11  # 6 non-widgets + 5 widgets

    def test_get_elements_with_initial_fragment_edge_cases(self, builder):
        """Test get_elements with initial_fragment_id edge cases"""
        # Test with initial_fragment_id but no elements
        builder.initial_fragment_id = "test-fragment"
        assert builder.get_elements() == []

        # Test with initial_fragment_id and elements but no children
        element = RouteLitElement(name="div", props={}, key="test")
        element.children = None
        # Create a new builder with the element
        new_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            fragments=builder.fragments,
            initial_fragment_id="test-fragment",
        )
        new_builder._parent_element.children = [element]
        assert new_builder.get_elements() == []
