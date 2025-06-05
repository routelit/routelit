from typing import Any, ClassVar, Dict, List, MutableMapping

import pytest

from routelit.builder import RouteLitBuilder
from routelit.domain import RouteLitElement, RouteLitRequest, SessionKeys
from routelit.exceptions import RerunException


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
        return RouteLitBuilder(request=mock_request, session_state={})

    def test_init_defaults(self, builder, mock_request):
        """Test builder initialization with default values."""
        assert builder.request == mock_request
        assert builder.initial_fragment_id is None
        assert builder.fragments == {}
        assert builder.prefix == ""
        assert builder.session_state == {}
        assert builder.parent_element is None
        assert builder.parent_builder is None
        assert builder.address is None
        assert builder.elements == []
        assert builder.num_non_widget == 0
        assert builder.active_child_builder is None

    def test_init_with_parent(self, builder):
        """Test initialization with a parent element and builder."""
        parent_element = RouteLitElement(key="parent_key", name="div", props={})
        nested_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            parent_element=parent_element,
            parent_builder=builder,
            address=[0],
        )
        assert nested_builder.prefix == "parent_key"  # Prefix defaults to parent key
        assert nested_builder.parent_element == parent_element
        assert nested_builder.parent_builder == builder
        assert nested_builder.address == [0]
        assert parent_element.children is nested_builder.elements  # Parent children points to builder elements

    def test_init_with_prefix_override(self, builder):
        """Test prefix override during initialization."""
        parent_element = RouteLitElement(key="parent_key", name="div", props={})
        nested_builder = RouteLitBuilder(
            request=builder.request,
            session_state=builder.session_state,
            parent_element=parent_element,
            prefix="custom_prefix",  # Override prefix
        )
        assert nested_builder.prefix == "custom_prefix"

    def test_id_generation(self, builder):
        """Test generation of IDs for non-widget and widget elements."""
        # Non-widget
        builder.num_non_widget = 5
        assert builder._new_text_id("text") == "_text_5"
        # Widget
        # Hash of 'My Button' is '19e...'. First 8 chars: '19e9c728'
        assert builder._new_widget_id("button", "My Button") == "_button_19e9c728"

    def test_id_generation_with_prefix(self, builder):
        """Test ID generation when a prefix is set."""
        builder.prefix = "section1"
        builder.num_non_widget = 2
        assert builder._new_text_id("div") == "section1_div_2"
        # Hash of 'Submit' is '155...'. First 8 chars: '155f816c'
        assert builder._new_widget_id("btn", "Submit") == "section1_btn_155f816c"

    def test_get_event_value(self, builder):
        """Test retrieving event values."""
        component_id = "my_component"
        event_type = "click"
        event_data = {"x": 10, "y": 20}
        builder.request._ui_event = {"type": event_type, "componentId": component_id, "data": event_data}

        # Correct event, no attribute
        has_event, data = builder._get_event_value(component_id, event_type)
        assert has_event is True
        assert data == event_data

        # Correct event, with attribute
        has_event, value = builder._get_event_value(component_id, event_type, attribute="x")
        assert has_event is True
        assert value == 10

        # Correct event, wrong attribute - The implementation uses .get() so it returns None, not KeyError
        has_event, value = builder._get_event_value(component_id, event_type, attribute="z")
        assert has_event is True
        assert value is None  # .get() returns None for missing keys

        # Wrong component_id
        has_event, data = builder._get_event_value("other_component", event_type)
        assert has_event is False
        assert data is None

        # Wrong event_type
        has_event, data = builder._get_event_value(component_id, "change")
        assert has_event is False
        assert data is None

        # No event
        builder.request._ui_event = None
        has_event, data = builder._get_event_value(component_id, event_type)
        assert has_event is False
        assert data is None

    def test_append_element_simple(self, builder):
        """Test appending an element directly to the builder."""
        element = RouteLitElement(key="el1", name="text", props={})
        builder._append_element(element)
        assert builder.elements == [element]

    def test_add_non_widget(self, builder):
        """Test adding a non-widget element increments counter."""
        assert builder.num_non_widget == 0
        element = RouteLitElement(key="nw1", name="div", props={})
        builder._add_non_widget(element)
        assert builder.elements == [element]
        assert builder.num_non_widget == 1
        element2 = RouteLitElement(key="nw2", name="span", props={})
        builder._add_non_widget(element2)
        assert builder.elements == [element, element2]
        assert builder.num_non_widget == 2

    def test_add_widget(self, builder):
        """Test adding a widget element does not increment non-widget counter."""
        assert builder.num_non_widget == 0
        element = RouteLitElement(key="w1", name="button", props={})
        builder._add_widget(element)
        assert builder.elements == [element]
        assert builder.num_non_widget == 0  # Stays 0

    def test_address_calculation(self, builder):
        """Test address calculation for next and last elements."""
        builder.address = [1]  # Simulate being a nested builder
        assert builder._get_next_address() == [1, 0]  # Next address before adding first element is 0
        el1 = builder._create_element("text", "t1")
        assert builder._get_last_address() == [1, 0]  # Address of the first added element is index 0
        assert el1.address is None  # Address is not set by create_element by default
        assert builder._get_next_address() == [1, 1]  # Next address after adding first element (at 0) is 1
        next_addr = builder._get_next_address()  # Calculate next address before adding
        el2 = builder._create_non_widget_element("div", "d1", address=next_addr)
        assert el2.address == [1, 1]  # Address passed is used by the element
        assert builder._get_last_address() == [1, 1]  # Address of the second added element seems to be 1

    def test_nested_builder_context_manager(self, builder):
        """Test using a nested builder via context manager (__enter__/__exit__)."""
        parent_element = builder._create_element("container", key="cont1")
        assert builder.active_child_builder is None

        with builder._build_nested_builder(parent_element) as nested:
            assert builder.active_child_builder == nested
            assert nested.parent_builder == builder
            assert nested.prefix == "cont1"
            assert nested.address == [0]  # Address of the parent element

            # Elements added inside 'with' go to the nested builder
            nested_el = nested._create_element("item", key="item1")
            assert nested.elements == [nested_el]
            assert builder.elements == [parent_element]  # Original builder unchanged so far
            assert parent_element.children == [nested_el]  # Parent element's children are updated

        # After exiting context
        assert builder.active_child_builder is None
        assert builder.elements == [parent_element]  # Still only contains parent
        assert len(parent_element.children) == 1  # Child was added

    def test_append_element_redirects_to_active_child(self, builder):
        """Test that append_element redirects to the active child builder."""
        parent_element = builder._create_element("container", key="cont1")
        with builder._build_nested_builder(parent_element) as nested:
            # Appending directly to the parent builder while child is active
            redirected_element = RouteLitElement(key="redir", name="span", props={})
            builder._append_element(redirected_element)

            assert nested.elements == [redirected_element]  # Element added to nested builder
            assert builder.elements == [parent_element]  # Parent unchanged

    def test_id_generation_redirects_to_active_child(self, builder):
        """Test that ID generation uses the active child builder's state."""
        parent_element = builder._create_element("container", key="cont1")
        with builder._build_nested_builder(parent_element) as nested:
            nested.num_non_widget = 3
            builder.num_non_widget = 10  # Parent has different count

            # Generate ID using parent builder while child is active
            new_id = builder._new_text_id("p")

            assert new_id == "cont1_p_3"  # Uses nested builder's prefix and count

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
        assert frag_builder.prefix == "frag1"
        assert frag_builder.address == [0]  # Index of the parent frag_element (which is at index 0)

        # Add element inside fragment
        with frag_builder as fb:
            fb._create_element("text", key="t1", props={"content": "hello"})  # Explicit key doesn't get prefixed

        assert len(frag_element.children) == 1
        assert frag_element.children[0].key == "t1"  # Key remains "t1" when using create_element

    def test_get_elements_without_fragment(self, builder):
        """Test get_elements when no initial fragment ID is set."""
        builder._create_element("div", "d1")
        builder._create_element("span", "s1")
        assert builder.get_elements() == builder.elements

    def test_get_elements_with_fragment(self, builder, mock_request):
        """Test get_elements when an initial fragment ID is set."""
        # Simulate being called for a fragment request
        mock_request._fragment_id = "frag1"
        fragmented_builder = RouteLitBuilder(
            request=mock_request,
            session_state={},
            initial_fragment_id="frag1",  # Set the initial fragment ID
        )

        # Build elements *as if* they are inside the fragment
        # In a real scenario, the fragment's view function would be called
        # directly with this builder.
        fragmented_builder._create_element("text", "t1")
        fragmented_builder._create_element("button", "b1")

        # get_elements should return the elements directly (not wrapped in fragment)
        # because this builder *is* the fragment builder in this context.
        # However, the current implementation wraps it unnecessarily. Let's test that behavior.
        # Update: Refactored `_fragment` and builder init.
        # The builder used within `@routelit.fragment` won't have `initial_fragment_id` set.
        # The `initial_fragment_id` is used by `RouteLit` to know *which* builder to use.

        # Let's simulate the structure RouteLit creates
        main_builder = RouteLitBuilder(request=MockRequestBuilder(), session_state={})
        main_builder._create_element("header", "h1")
        frag_element = main_builder._create_non_widget_element("fragment", "frag1", address=[1])
        # Normally, RouteLit would call the fragment view function with a builder
        # whose parent_element is frag_element.
        frag_builder = main_builder._build_nested_builder(frag_element)
        with frag_builder as fb:
            fb._create_element("text", "t1")
            fb._create_element("button", "b1")

        # If we are RouteLit handling a request for fragment_id='frag1':
        # RouteLit would construct a new builder specifically for the fragment call:
        request_for_fragment = MockRequestBuilder(fragment_id="frag1")
        builder_for_fragment_call = RouteLitBuilder(
            request=request_for_fragment,
            session_state={},
            initial_fragment_id="frag1",  # This tells RouteLit *which* view to call
            fragments=main_builder.fragments,  # Pass existing fragment map
            # Parent/address would be set if RouteLit passed them, but let's assume not for clarity
        )
        # Now, the fragment view function is called with builder_for_fragment_call
        # Let's assume it does the same thing:
        builder_for_fragment_call._create_element("text", "t1")
        builder_for_fragment_call._create_element("button", "b1")

        # When RouteLit calls get_elements on this builder, it expects the direct children:
        result_elements = builder_for_fragment_call.get_elements()
        # After type fixes, get_elements always returns a List[RouteLitElement], never None
        # In this case, since there are no elements in the first child, it returns an empty list
        assert result_elements == []  # Should return empty list when no elements are present

    def test_rerun(self, builder):
        """Test the rerun method raises RerunException."""
        builder.session_state["value"] = 1
        builder.elements.append(RouteLitElement(key="el1", name="text", props={}))

        with pytest.raises(RerunException) as exc_info:
            builder.rerun()

        # Check exception details
        assert exc_info.value.scope == "auto"
        assert exc_info.value.state == {"value": 1}

        # Check builder state after raise (elements cleared)
        assert builder.elements == []
        # Check request event cleared (default)
        assert builder.request.ui_event is None

    def test_rerun_scope_app_and_clear_event_false(self, builder):
        """Test rerun with specific scope and event clearing disabled."""
        builder.request._ui_event = {"type": "click"}
        builder.request._fragment_id = "frag1"

        with pytest.raises(RerunException) as exc_info:
            builder.rerun(scope="app", clear_event=False)

        assert exc_info.value.scope == "app"
        # Check request state after raise
        assert builder.request.ui_event == {"type": "click"}  # Event not cleared
        assert builder.request.fragment_id is None  # Fragment ID cleared for 'app' scope

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
        assert builder.num_non_widget == 1  # link is non-widget

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
        assert builder.num_non_widget == 1

        # Check children were added correctly via nested builder
        assert len(link_area_element.children) == 2
        assert link_area_element.children[0].name == "img"
        assert link_area_element.children[0].key == "icon"  # Keys not prefixed by create_element
        assert link_area_element.children[1].name == "span"
        assert link_area_element.children[1].key == "label"

    def test_get_client_resource_paths(self):
        """Test retrieving static asset targets from the class."""

        # Define a subclass with specific assets
        class CustomBuilder(RouteLitBuilder):
            static_assets_targets: ClassVar[List[Dict[str, str]]] = [
                {"package_name": "package1", "src_dir": "src1"},
                {"package_name": "package2", "src_dir": "src2"},
            ]

        assert CustomBuilder.get_client_resource_paths() == [
            {"package_name": "package1", "src_dir": "src1"},
            {"package_name": "package2", "src_dir": "src2"},
        ]

        # Check base class has empty list by default (if not overridden)
        assert RouteLitBuilder.get_client_resource_paths() == []

    def test_fragment_key_collision(self, builder):
        """Test behavior when creating fragments with the same key."""
        frag_builder1 = builder._fragment("duplicate_frag")
        assert "duplicate_frag" in builder.fragments
        assert len(builder.elements) == 1
        first_frag_element = builder.elements[0]
        assert first_frag_element.key == "duplicate_frag"
        assert first_frag_element.address == [0]  # The first fragment has address [0] in the current implementation

        # Create another fragment with the same key
        frag_builder2 = builder._fragment("duplicate_frag")
        assert len(builder.elements) == 2  # A new element should be added
        second_frag_element = builder.elements[1]
        assert second_frag_element.key == "duplicate_frag"
        assert second_frag_element.address == [1]  # Address should be the next one

        # The fragments map should store the address of the *last* fragment created with that key
        assert builder.fragments["duplicate_frag"] == [1]

        # Check the builders are distinct and linked to the correct elements
        assert frag_builder1 != frag_builder2
        assert frag_builder1.parent_element == first_frag_element
        assert frag_builder2.parent_element == second_frag_element

    def test_session_state_in_nested_builders(self, builder):
        """Test that session_state is shared across nested builders."""
        builder.session_state["outer_value"] = 100
        parent_element = builder._create_element("container", key="cont")

        with builder._build_nested_builder(parent_element) as nested:
            assert nested.session_state == builder.session_state  # Should be the same object
            assert nested.session_state["outer_value"] == 100

            # Modify state from nested builder
            nested.session_state["inner_value"] = 200
            nested.session_state["outer_value"] = 101

        # Check state modifications are reflected in the original builder's state
        assert builder.session_state["inner_value"] == 200
        assert builder.session_state["outer_value"] == 101

        # Create another level of nesting
        nested_builder = builder._build_nested_builder(parent_element)
        with nested_builder as inner_nested:
            assert inner_nested.session_state["inner_value"] == 200
            inner_nested.session_state["deep_value"] = 300

        assert builder.session_state["deep_value"] == 300

    def test_deeply_nested_builders(self, builder):
        """Test address calculation and ID generation in deeply nested builders."""
        with builder._build_nested_builder(builder._create_element("div", "level1")) as b1:
            assert b1.prefix == "level1"
            assert b1.address == [0]
            with b1._build_nested_builder(b1._create_element("div", "level2")) as b2:
                assert b2.prefix == "level2"  # Prefix is not concatenated
                assert b2.address == [0, 0]  # Address reflects nesting
                b2.num_non_widget = 5
                with b2._build_nested_builder(b2._create_element("div", "level3")) as b3:
                    assert b3.prefix == "level3"  # Prefix is not concatenated
                    assert b3.address == [0, 0, 0]
                    b3.num_non_widget = 8

                    # Test ID generation from the deepest level
                    assert b3._new_text_id("text") == "level3_text_8"
                    # Test ID generation from an outer level (should use active inner level)
                    # The actual implementation appears to use the active builder (b2), not b3
                    assert b1._new_text_id("span") == "level2_span_5"

                    # Test address calculation
                    _el3 = b3._create_element("p", "p1")
                    assert b3._get_last_address() == [0, 0, 0, 0]
                    # Current implementation returns the next index
                    assert b3._get_next_address() == [0, 0, 0, 1]

                # Test address calculation after exiting inner context
                _el2 = b2._create_element("p", "p2")  # Added to level2 builder
                assert b2._get_last_address() == [0, 0, 1]  # Address relative to level2
                # Current implementation returns the next available index
                assert b2._get_next_address() == [0, 0, 2]

            # Test address calculation after exiting level2 context
            _el1 = b1._create_element("p", "p3")  # Added to level1 builder
            assert b1._get_last_address() == [0, 1]  # Address relative to level1
            # Current implementation returns the next available index
            assert b1._get_next_address() == [0, 2]

    def test_link_edge_cases(self, builder):
        """Test link and link_area with missing or empty arguments."""
        # Link with empty text
        link1 = builder.link("/", text="", key="l1")
        assert link1.props["text"] == ""

        # Link with no text (should default to empty string)
        link2 = builder.link("/", key="l2")  # No text provided
        assert link2.props["text"] == ""  # The default behavior appears to be an empty string

        # Link area with empty href
        with builder.link_area("", key="la1") as la1_builder:
            la1_builder._create_element("div", "d1")
        assert builder.elements[-1].props["href"] == ""

        # The link_area method requires href parameter, so we can't test with no href
        # Removing that test case as it's not valid

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
        assert builder.num_non_widget == 1

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
        assert builder.num_non_widget == 0  # Button is a widget

    def test_container_with_children(self, builder):
        """Test creating a container with child elements."""
        with builder.container(key="main", className="wrapper") as container:
            container._create_non_widget_element("text", key="header", props={"content": "Header"})
            container._create_non_widget_element("text", key="content", props={"content": "Content"})

        assert len(builder.elements) == 1
        container_element = builder.elements[0]
        assert container_element.name == "container"
        assert container_element.key == "main"
        assert container_element.props["className"] == "wrapper"
        assert len(container_element.children) == 2
        assert container_element.children[0].props["content"] == "Header"
        assert container_element.children[1].props["content"] == "Content"

    def test_form_element_creation(self, builder):
        """Test creating a form with input fields."""
        with builder.form(key="contact-form") as form:
            # Add onSubmit to the form props directly after creation
            form.parent_element.props["onSubmit"] = "handleSubmit"

            form._create_element(
                "input", key="name", props={"placeholder": "Enter name", "type": "text", "required": True}
            )
            form._create_element("input", key="email", props={"placeholder": "Enter email", "type": "email"})
            form._create_element("button", key="submit", props={"text": "Submit", "type": "submit"})

        assert len(builder.elements) == 1
        form_element = builder.elements[0]
        assert form_element.name == "form"
        assert form_element.key == "contact-form"
        assert form_element.props["onSubmit"] == "handleSubmit"
        assert len(form_element.children) == 3
        assert form_element.children[0].name == "input"
        assert form_element.children[0].props["required"] is True
        assert form_element.children[2].name == "button"
        assert form_element.children[2].props["type"] == "submit"

    def test_dynamic_element_creation(self, builder):
        """Test creating elements dynamically based on data."""
        items = ["Apple", "Banana", "Cherry"]
        builder.session_state["selected"] = "Banana"

        # Create a container to use as a list
        with builder.container(key="fruit-list", className="items") as list_builder:
            for item in items:
                is_selected = builder.session_state["selected"] == item
                list_builder._create_non_widget_element(
                    "div",  # Use div instead of list_item
                    key=f"item-{item.lower()}",
                    props={"content": item, "className": f"item {'selected' if is_selected else ''}"},
                )

        assert len(builder.elements) == 1
        list_element = builder.elements[0]
        assert list_element.name == "container"  # Changed from list to container
        assert len(list_element.children) == 3
        assert list_element.children[1].props["content"] == "Banana"
        assert "selected" in list_element.children[1].props["className"]
        assert "selected" not in list_element.children[0].props["className"]

    def test_event_handling_with_state_update(self, builder):
        """Test handling events that update session state."""
        builder.session_state["counter"] = 0

        # Simulate an event for increment button
        increment_id = "inc-btn"
        builder.request._ui_event = {"type": "click", "componentId": increment_id, "data": {}}

        _button = builder._create_element(
            "button", key=increment_id, props={"text": "Increment", "onClick": "handleIncrement"}
        )
        has_event, _ = builder._get_event_value(increment_id, "click")

        if has_event:
            builder.session_state["counter"] += 1
            builder._create_non_widget_element(
                "text", key="counter-display", props={"content": f"Count: {builder.session_state['counter']}"}
            )

        assert builder.session_state["counter"] == 1
        assert len(builder.elements) == 2
        assert builder.elements[1].props["content"] == "Count: 1"

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
        builder.elements = []  # Clear previous elements

        builder._create_non_widget_element("text", key="main", props={"content": "Main Content"})
        if builder.session_state["show_details"]:
            builder._create_non_widget_element("text", key="details", props={"content": "Detailed Info"})

        assert len(builder.elements) == 2
        assert builder.elements[1].props["content"] == "Detailed Info"

    def test_nested_fragment_handling(self, builder):
        """Test handling nested fragments."""
        main_frag = builder._fragment("main-fragment")

        with main_frag as mf:
            mf._create_non_widget_element("text", key="main-text", props={"content": "Main Content"})

            # Create nested fragment
            nested_frag = mf._fragment("nested-fragment")
            with nested_frag as nf:
                nf._create_non_widget_element("text", key="nested-text", props={"content": "Nested Content"})

        assert "main-fragment" in builder.fragments
        assert "nested-fragment" in main_frag.fragments

        # Main fragment has text and nested fragment
        main_element = builder.elements[0]
        assert len(main_element.children) == 2
        assert main_element.children[0].props["content"] == "Main Content"
        assert main_element.children[1].name == "fragment"

        # Nested fragment has text
        nested_element = main_element.children[1]
        assert len(nested_element.children) == 1
        assert nested_element.children[0].props["content"] == "Nested Content"

    def test_fragment_with_custom_props(self, builder):
        """Test creating a fragment with custom properties."""
        # Create fragment first without props
        main_frag = builder._fragment("custom-fragment")

        # Manually add custom props after creation
        fragment_element = builder.elements[0]
        fragment_element.props["data-testid"] = "main-content"
        fragment_element.props["aria-label"] = "Main Content"

        with main_frag as mf:
            mf._create_element("div", "content", props={"text": "Fragment Content"})

        # Assert props were correctly added
        assert fragment_element.name == "fragment"
        assert fragment_element.key == "custom-fragment"
        assert fragment_element.props["data-testid"] == "main-content"
        assert fragment_element.props["aria-label"] == "Main Content"

    def test_rerun_with_custom_scope_and_state(self, builder):
        """Test rerun with custom scope and specific state."""
        builder.session_state["counter"] = 10
        builder.session_state["user"] = {"name": "Test"}

        # Test standard rerun functionality
        with pytest.raises(RerunException) as exc_info:
            builder.rerun(scope="page")

        # Check the exception details
        assert exc_info.value.scope == "page"
        assert "counter" in exc_info.value.state
        assert "user" in exc_info.value.state

        # For state_keys test, we can only verify that all keys are in the state
        assert exc_info.value.state["counter"] == 10
        assert exc_info.value.state["user"] == {"name": "Test"}

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
        assert dialog_builder.prefix == "my-dialog"

        # Add element inside dialog
        with dialog_builder as db:
            db.text("Dialog content", key="dialog-text")

        assert len(dialog_element.children) == 1
        assert dialog_element.children[0].props["body"] == "Dialog content"

    def test_dialog_close_event(self, builder):
        """Test dialog close event handling."""
        builder.request._ui_event = {"type": "close", "componentId": "my-dialog", "data": {}}

        with pytest.raises(RerunException):
            builder._dialog("my-dialog")

    def test_markdown_creation(self, builder):
        """Test creating a markdown component."""
        builder.markdown("# Hello World\n\nThis is **bold**", key="my-markdown", allow_unsafe_html=True)

        assert len(builder.elements) == 1
        markdown_element = builder.elements[0]
        assert markdown_element.name == "markdown"
        assert markdown_element.key == "my-markdown"
        assert markdown_element.props["body"] == "# Hello World\n\nThis is **bold**"
        assert markdown_element.props["allowUnsafeHtml"] is True
        assert builder.num_non_widget == 1

    def test_text_creation(self, builder):
        """Test creating a text component."""
        builder.text("Simple text content", key="my-text")

        assert len(builder.elements) == 1
        text_element = builder.elements[0]
        assert text_element.name == "markdown"  # text uses markdown internally
        assert text_element.key == "my-text"
        assert text_element.props["body"] == "Simple text content"
        assert text_element.props["allowUnsafeHtml"] is False
        assert builder.num_non_widget == 1

    def test_title_creation(self, builder):
        """Test creating a title component."""
        builder.title("Page Title", key="page-title", className="large")

        assert len(builder.elements) == 1
        title_element = builder.elements[0]
        assert title_element.name == "title"
        assert title_element.key == "page-title"
        assert title_element.props["body"] == "Page Title"
        assert title_element.props["className"] == "large"
        assert builder.num_non_widget == 1

    def test_header_creation(self, builder):
        """Test creating a header component."""
        builder.header("Main Header", key="main-header")

        assert len(builder.elements) == 1
        header_element = builder.elements[0]
        assert header_element.name == "header"
        assert header_element.key == "main-header"
        assert header_element.props["body"] == "Main Header"
        assert builder.num_non_widget == 1

    def test_subheader_creation(self, builder):
        """Test creating a subheader component."""
        builder.subheader("Section Header", key="section-header")

        assert len(builder.elements) == 1
        subheader_element = builder.elements[0]
        assert subheader_element.name == "subheader"
        assert subheader_element.key == "section-header"
        assert subheader_element.props["body"] == "Section Header"
        assert builder.num_non_widget == 1

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
        assert builder.num_non_widget == 1

    def test_expander_creation(self, builder):
        """Test creating an expander component."""
        with builder.expander("Details", open=True, key="exp1") as exp:
            exp.text("Expanded content", key="exp-content")

        assert len(builder.elements) == 1
        expander_element = builder.elements[0]
        assert expander_element.name == "expander"
        assert expander_element.key == "exp1"
        assert expander_element.props["title"] == "Details"
        assert expander_element.props["open"] is True
        assert len(expander_element.children) == 1
        assert expander_element.children[0].props["body"] == "Expanded content"

    def test_columns_creation_with_integer(self, builder):
        """Test creating columns with integer specification."""
        col1, col2, col3 = builder.columns(3, key="my-columns", vertical_alignment="center", columns_gap="large")

        assert len(builder.elements) == 1
        container_element = builder.elements[0]
        assert container_element.name == "container"
        assert container_element.key == "my-columns"
        assert "rl-flex" in container_element.props["className"]
        assert "rl-flex-row" in container_element.props["className"]
        assert container_element.props["style"]["alignItems"] == "center"
        assert container_element.props["style"]["columnGap"] == "3rem"

        # Check that three columns were created
        assert len(container_element.children) == 3
        for child in container_element.children:
            assert child.name == "container"
            assert child.props["style"]["flex"] == 1

        # Test using the column builders
        col1.text("Column 1", key="col1-text")
        col2.text("Column 2", key="col2-text")
        col3.text("Column 3", key="col3-text")

        assert len(container_element.children[0].children) == 1
        assert len(container_element.children[1].children) == 1
        assert len(container_element.children[2].children) == 1

    def test_columns_creation_with_list(self, builder):
        """Test creating columns with list specification."""
        col1, col2 = builder.columns([2, 1], vertical_alignment="bottom", columns_gap="medium")

        assert len(builder.elements) == 1
        container_element = builder.elements[0]
        assert container_element.props["style"]["alignItems"] == "flex-end"
        assert container_element.props["style"]["columnGap"] == "2rem"

        # Check column flex values
        assert len(container_element.children) == 2
        assert container_element.children[0].props["style"]["flex"] == 2
        assert container_element.children[1].props["style"]["flex"] == 1

    def test_flex_creation(self, builder):
        """Test creating a flex container."""
        with builder.flex(
            direction="row",
            wrap="wrap",
            justify_content="center",
            align_items="stretch",
            align_content="between",
            gap="1rem",
            key="flex-container",
            className="custom-flex",
        ) as flex:
            flex.text("Flex item 1", key="item1")
            flex.text("Flex item 2", key="item2")

        assert len(builder.elements) == 1
        flex_element = builder.elements[0]
        assert flex_element.name == "flex"
        assert flex_element.key == "flex-container"
        assert flex_element.props["direction"] == "row"
        assert flex_element.props["flexWrap"] == "wrap"
        assert flex_element.props["justifyContent"] == "center"
        assert flex_element.props["alignItems"] == "stretch"
        assert flex_element.props["alignContent"] == "between"
        assert flex_element.props["gap"] == "1rem"
        assert flex_element.props["className"] == "custom-flex"
        assert len(flex_element.children) == 2

    def test_button_functionality(self, builder):
        """Test button creation and click event handling."""
        # Test button without event
        clicked = builder.button("Click Me", key="my-button", disabled=False)
        assert clicked is False

        assert len(builder.elements) == 1
        button_element = builder.elements[0]
        assert button_element.name == "button"
        assert button_element.key == "my-button"
        assert button_element.props["text"] == "Click Me"
        assert button_element.props["eventName"] == "click"
        assert button_element.props["disabled"] is False

        # Test button with click event
        builder.request._ui_event = {"type": "click", "componentId": "my-button", "data": {}}
        builder.elements.clear()  # Clear previous elements

        callback_called = False

        def on_click():
            nonlocal callback_called
            callback_called = True

        clicked = builder.button("Click Me", key="my-button", on_click=on_click)
        assert clicked is True
        assert callback_called is True

    def test_text_input_functionality(self, builder):
        """Test text input creation and change event handling."""
        # Test initial value
        value = builder.text_input("Username", value="initial", key="username")
        assert value == "initial"

        assert len(builder.elements) == 1
        input_element = builder.elements[0]
        assert input_element.name == "text-input"
        assert input_element.key == "username"
        assert input_element.props["label"] == "Username"
        assert input_element.props["value"] == "initial"
        assert input_element.props["type"] == "text"

        # Test value change
        builder.request._ui_event = {"type": "change", "componentId": "username", "data": {"value": "new_value"}}
        builder.elements.clear()

        callback_value = None

        def on_change(new_val):
            nonlocal callback_value
            callback_value = new_val

        value = builder.text_input("Username", key="username", on_change=on_change, type="email")
        assert value == "new_value"
        assert callback_value == "new_value"
        assert builder.session_state["username"] == "new_value"

        input_element = builder.elements[0]
        assert input_element.props["type"] == "email"

    def test_textarea_functionality(self, builder):
        """Test textarea creation and change event handling."""
        value = builder.textarea("Description", value="initial text", key="desc", rows=5)
        assert value == "initial text"

        assert len(builder.elements) == 1
        textarea_element = builder.elements[0]
        assert textarea_element.name == "textarea"
        assert textarea_element.key == "desc"
        assert textarea_element.props["label"] == "Description"
        assert textarea_element.props["value"] == "initial text"
        assert textarea_element.props["rows"] == 5

    def test_radio_functionality(self, builder):
        """Test radio group creation and selection."""
        options = ["Option 1", "Option 2", {"label": "Option 3", "value": "opt3"}]
        value = builder.radio("Choose option", options, value="Option 1", key="radio1", flex_direction="row")
        assert value == "Option 1"

        assert len(builder.elements) == 1
        radio_element = builder.elements[0]
        assert radio_element.name == "radio"
        assert radio_element.key == "radio1"
        assert radio_element.props["label"] == "Choose option"
        assert radio_element.props["value"] == "Option 1"
        assert radio_element.props["options"] == options
        assert radio_element.props["flexDirection"] == "row"

        # Test value change
        builder.request._ui_event = {"type": "change", "componentId": "radio1", "data": {"value": "opt3"}}
        builder.elements.clear()

        value = builder.radio("Choose option", options, key="radio1")
        assert value == "opt3"
        assert builder.session_state["radio1"] == "opt3"

    def test_select_functionality(self, builder):
        """Test select dropdown creation and selection."""
        options = [{"label": "First", "value": 1}, {"label": "Second", "value": 2, "disabled": True}, "Third"]
        value = builder.select("Select item", options, value=1, key="select1")
        assert value == 1

        assert len(builder.elements) == 1
        select_element = builder.elements[0]
        assert select_element.name == "select"
        assert select_element.key == "select1"
        assert select_element.props["label"] == "Select item"
        assert select_element.props["value"] == 1
        assert select_element.props["options"] == options

        # Test value change
        builder.request._ui_event = {"type": "change", "componentId": "select1", "data": {"value": "Third"}}
        builder.elements.clear()

        callback_value = None

        def on_change(new_val):
            nonlocal callback_value
            callback_value = new_val

        value = builder.select("Select item", options, key="select1", on_change=on_change)
        assert value == "Third"
        assert callback_value == "Third"
        assert builder.session_state["select1"] == "Third"

    def test_checkbox_functionality(self, builder):
        """Test checkbox creation and toggle event handling."""
        checked = builder.checkbox("Accept terms", checked=False, key="terms")
        assert checked is False

        assert len(builder.elements) == 1
        checkbox_element = builder.elements[0]
        assert checkbox_element.name == "checkbox"
        assert checkbox_element.key == "terms"
        assert checkbox_element.props["label"] == "Accept terms"
        assert checkbox_element.props["checked"] is False

        # Test checkbox toggle
        builder.request._ui_event = {"type": "change", "componentId": "terms", "data": {"checked": True}}
        builder.elements.clear()

        callback_value = None

        def on_change(new_val):
            nonlocal callback_value
            callback_value = new_val

        checked = builder.checkbox("Accept terms", key="terms", on_change=on_change)
        assert checked is True
        assert callback_value is True
        assert builder.session_state["terms"] is True

    def test_checkbox_group_functionality(self, builder):
        """Test checkbox group creation and selection."""
        options = ["Apple", "Banana", {"label": "Cherry", "value": "cherry"}]
        value = builder.checkbox_group("Select fruits", options, value=["Apple"], key="fruits", flex_direction="row")
        assert value == ["Apple"]

        assert len(builder.elements) == 1
        checkbox_group_element = builder.elements[0]
        assert checkbox_group_element.name == "checkbox-group"
        assert checkbox_group_element.key == "fruits"
        assert checkbox_group_element.props["label"] == "Select fruits"
        assert checkbox_group_element.props["value"] == ["Apple"]
        assert checkbox_group_element.props["options"] == options
        assert checkbox_group_element.props["flexDirection"] == "row"

        # Test value change
        builder.request._ui_event = {"type": "change", "componentId": "fruits", "data": {"value": ["Apple", "cherry"]}}
        builder.elements.clear()

        callback_value = None

        def on_change(new_val):
            nonlocal callback_value
            callback_value = new_val

        value = builder.checkbox_group("Select fruits", options, key="fruits", on_change=on_change)
        assert value == ["Apple", "cherry"]
        assert callback_value == ["Apple", "cherry"]
        assert builder.session_state["fruits"] == ["Apple", "cherry"]

    def test_set_page_config(self, builder):
        """Test setting page configuration."""
        result = builder.set_page_config(page_title="My App", page_description="A great application")

        assert len(builder.elements) == 1
        head_element = builder.elements[0]
        assert head_element.name == "head"
        assert head_element.key == "__head__"
        assert head_element.props["title"] == "My App"
        assert head_element.props["description"] == "A great application"
        assert builder.head.title == "My App"
        assert builder.head.description == "A great application"
        assert result is None

    def test_get_head(self, builder):
        """Test getting head configuration."""
        head = builder.get_head()
        assert head.title is None
        assert head.description is None

        builder.set_page_config(page_title="Test", page_description="Test desc")
        head = builder.get_head()
        assert head.title == "Test"
        assert head.description == "Test desc"

    def test_maybe_get_event_with_form_submission(self, builder):
        """Test _maybe_get_event with form submission handling."""
        # Set up session state before creating form
        builder.session_state["__events4later_test-form"] = {"input1": {"type": "change", "data": {"value": "test"}}}
        # Set up a form context
        form_builder = builder.form("test-form")

        # Simulate form submission event
        builder.request._ui_event = {"type": "submit", "formId": "test-form", "data": {}}

        # Use the form_builder context to ensure proper form ID detection
        with form_builder as fb:
            try:
                fb._maybe_get_event("input1")
                raise AssertionError()
            except RerunException as e:
                # Check that events were moved to the correct location
                # The RerunException shows the session state contains the moved events
                assert "__events_test-form" in e.state
                assert "__ignore_submit" in e.state
                assert e.state["__ignore_submit"] == "test-form"

    def test_maybe_get_event_with_stored_form_events(self, builder):
        """Test _maybe_get_event with stored form events."""
        # Set up session state before creating form
        builder.session_state["__events_test-form"] = {"input1": {"type": "change", "data": {"value": "stored_value"}}}
        form_builder = builder.form("test-form")

        # Use the form_builder context to ensure proper form ID detection
        with form_builder as fb:
            event = fb._maybe_get_event("input1")
            assert event is not None
            assert event["type"] == "change"
            assert event["data"]["value"] == "stored_value"

            # Event should be removed after retrieval
            assert "input1" not in builder.session_state["__events_test-form"]

    def test_get_parent_form_id(self, builder):
        """Test _get_parent_form_id functionality."""
        # No form context
        assert builder._get_parent_form_id() is None

        # Create form and nested builder
        form_builder = builder.form("my-form")
        with form_builder as fb:
            assert fb._get_parent_form_id() == "my-form"

            # Test with further nesting - the container builder should inherit form context
            # However, the current implementation only checks immediate parent and active children
            # So this test should expect None since container's parent element is not a form
            container_builder = fb.container()
            with container_builder as container:
                assert container._get_parent_form_id() is None

    def test_component_id_generation_patterns(self, builder):
        """Test various ID generation patterns for components."""
        # Test auto-generated IDs
        builder.text("Hello")
        builder.image("test.jpg")
        builder.container()

        assert len(builder.elements) == 3
        assert builder.elements[0].key.startswith("_markdown_")
        assert builder.elements[1].key.startswith("_image_")
        assert builder.elements[2].key.startswith("_container_")

        # Test widget IDs with labels
        builder.button("Submit")
        builder.text_input("Name")

        assert len(builder.elements) == 5
        button_key = builder.elements[3].key
        input_key = builder.elements[4].key
        assert "_button_" in button_key
        assert "_text-input_" in input_key
        # Should contain hash of label
        assert len(button_key.split("_")[-1]) == 8  # 8-char hash
        assert len(input_key.split("_")[-1]) == 8  # 8-char hash

    def test_nested_component_combinations(self, builder):
        """Test complex nested component combinations."""
        with builder.container(key="main") as main:
            main.header("Dashboard", key="title")

            col1, col2 = main.columns(2, key="content-cols")

            with col1:
                with main.expander("Settings", key="settings") as settings:
                    settings.checkbox("Enable notifications", key="notifs")
                    settings.select("Theme", ["Light", "Dark"], key="theme")

            with col2:
                with main.flex(direction="col", key="right-panel") as panel:
                    panel.text_input("Search", key="search")
                    panel.button("Go", key="go-btn")

        # Verify structure
        assert len(builder.elements) == 1
        main_container = builder.elements[0]
        assert main_container.key == "main"

        # Should have header and columns container
        assert len(main_container.children) == 2
        assert main_container.children[0].props["body"] == "Dashboard"

        columns_container = main_container.children[1]
        assert len(columns_container.children) == 2  # Two columns

        # Check left column has expander
        left_col = columns_container.children[0]
        assert len(left_col.children) == 1
        expander = left_col.children[0]
        assert expander.name == "expander"
        assert len(expander.children) == 2  # Checkbox and select

        # Check right column has flex panel
        right_col = columns_container.children[1]
        assert len(right_col.children) == 1
        flex_panel = right_col.children[0]
        assert flex_panel.name == "flex"
        assert len(flex_panel.children) == 2  # Input and button

    def test_container_with_height(self, builder):
        """Test creating a container with height parameter."""
        with builder.container(key="sized-container", height="200px", className="custom-class") as container:
            container.text("Content inside sized container", key="content")

        assert len(builder.elements) == 1
        container_element = builder.elements[0]
        assert container_element.name == "container"
        assert container_element.key == "sized-container"
        assert container_element.props["style"]["height"] == "200px"
        assert container_element.props["className"] == "custom-class"
        assert len(container_element.children) == 1
        assert container_element.children[0].props["body"] == "Content inside sized container"

    def test_form_functionality(self, builder):
        """Test form creation and nested form context."""
        with builder.form("test-form") as form:
            form.text_input("Username", key="username")
            form.text_input("Password", type="password", key="password")
            form.button("Submit", event_name="submit", key="submit-btn")

        assert len(builder.elements) == 1
        form_element = builder.elements[0]
        assert form_element.name == "form"
        assert form_element.key == "test-form"
        assert form_element.props["id"] == "test-form"
        assert len(form_element.children) == 3

        # Check form children
        assert form_element.children[0].name == "text-input"
        assert form_element.children[0].props["label"] == "Username"
        assert form_element.children[1].name == "text-input"
        assert form_element.children[1].props["type"] == "password"
        assert form_element.children[2].name == "button"
        assert form_element.children[2].props["eventName"] == "submit"

    def test_text_input_types(self, builder):
        """Test text input with different input types."""
        # Test various input types
        builder.text_input("Email", type="email", key="email")
        builder.text_input("Age", type="number", key="age")
        builder.text_input("Birthday", type="date", key="birthday")

        assert len(builder.elements) == 3
        assert builder.elements[0].props["type"] == "email"
        assert builder.elements[1].props["type"] == "number"
        assert builder.elements[2].props["type"] == "date"

    def test_columns_edge_cases(self, builder):
        """Test columns with edge cases and different configurations."""
        # Test with single column
        (col1,) = builder.columns(1, key="single-col")
        col1.text("Single column content", key="content")

        assert len(builder.elements) == 1
        container = builder.elements[0]
        assert len(container.children) == 1
        assert container.children[0].props["style"]["flex"] == 1

        # Test with no gap
        builder.elements.clear()
        col1, col2 = builder.columns(2, columns_gap="none", vertical_alignment="bottom")
        assert builder.elements[0].props["style"]["columnGap"] == "0"
        assert builder.elements[0].props["style"]["alignItems"] == "flex-end"

    def test_flex_edge_cases(self, builder):
        """Test flex container with various configurations."""
        with builder.flex(
            direction="row",
            wrap="wrap",
            justify_content="evenly",
            align_items="baseline",
            align_content="around",
            gap="2rem",
            key="complex-flex",
        ) as flex:
            flex.text("Item 1", key="item1")
            flex.text("Item 2", key="item2")

        assert len(builder.elements) == 1
        flex_element = builder.elements[0]
        assert flex_element.props["direction"] == "row"
        assert flex_element.props["flexWrap"] == "wrap"
        assert flex_element.props["justifyContent"] == "evenly"
        assert flex_element.props["alignItems"] == "baseline"
        assert flex_element.props["alignContent"] == "around"
        assert flex_element.props["gap"] == "2rem"

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

        # Check counts
        assert builder.num_non_widget == 6  # text, markdown, image, title, header, subheader
        assert len(builder.elements) == 11  # Total elements

    def test_session_state_persistence_across_events(self, builder):
        """Test that session state persists correctly across multiple events."""
        # Initial state
        builder.session_state["counter"] = 0
        builder.session_state["name"] = "test"

        # Simulate button click
        builder.request._ui_event = {"type": "click", "componentId": "increment", "data": {}}
        clicked = builder.button("Increment", key="increment")

        if clicked:
            builder.session_state["counter"] += 1

        assert builder.session_state["counter"] == 1
        assert builder.session_state["name"] == "test"  # Should remain unchanged

        # Simulate text input change
        builder.request._ui_event = {"type": "change", "componentId": "name-input", "data": {"value": "updated"}}
        name_value = builder.text_input("Name", key="name-input")

        assert name_value == "updated"
        assert builder.session_state["name-input"] == "updated"
        assert builder.session_state["counter"] == 1  # Should remain unchanged
