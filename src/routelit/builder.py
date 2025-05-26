import hashlib
from collections.abc import MutableMapping, Sequence
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from routelit.domain import (
    AssetTarget,
    Head,
    RerunType,
    RouteLitElement,
    RouteLitEvent,
    RouteLitRequest,
)
from routelit.exceptions import RerunException

VerticalAlignment = Literal["top", "center", "bottom"]
verticalAlignmentMap: Dict[VerticalAlignment, str] = {
    "top": "flex-start",
    "center": "center",
    "bottom": "flex-end",
}
ColumnsGap = Literal["none", "small", "medium", "large"]
columnsGapMap: Dict[ColumnsGap, str] = {
    "none": "0",
    "small": "1rem",
    "medium": "2rem",
    "large": "3rem",
}


class RouteLitBuilder:
    static_assets_targets: Sequence[AssetTarget] = []

    def __init__(
        self,
        request: RouteLitRequest,
        initial_fragment_id: Optional[str] = None,
        fragments: Optional[MutableMapping[str, Sequence[int]]] = None,
        prefix: Optional[str] = None,
        session_state: Optional[MutableMapping[str, Any]] = None,
        parent_element: Optional[RouteLitElement] = None,
        parent_builder: Optional["RouteLitBuilder"] = None,
        address: Optional[Sequence[int]] = None,
    ):
        self.request = request
        self.initial_fragment_id = initial_fragment_id
        self.fragments = fragments or {}
        self.address = address
        self.head = Head()
        # Set prefix based on parent element if not explicitly provided
        if prefix is None:
            self.prefix = parent_element.key if parent_element else ""
        else:
            self.prefix = prefix
        self.elements: List[RouteLitElement] = []
        # self.elements_no_fragments: List[RouteLitElement] = []
        self.num_non_widget = 0
        self.session_state = session_state or {}
        self.parent_element = parent_element
        self.parent_builder = parent_builder
        if parent_element:
            self.parent_element.children = self.elements
        self.active_child_builder: Optional[RouteLitBuilder] = None
        self._prev_active_child_builder: Optional[RouteLitBuilder] = None
        if prefix is None:
            self._on_init()

    def _on_init(self):
        pass

    def get_request(self) -> RouteLitRequest:
        return self.request

    def _get_prefix(self) -> str:
        # Simplify to just use the current prefix which is already properly initialized
        return self.prefix

    def _get_next_address(self) -> Sequence[int]:
        if self.active_child_builder:
            return [
                *(self.active_child_builder.address or []),
                len(self.active_child_builder.elements),
            ]
        else:
            return [*(self.address or []), len(self.elements)]

    def _get_last_address(self) -> Sequence[int]:
        if self.active_child_builder:
            return [
                *(self.active_child_builder.address or []),
                len(self.active_child_builder.elements) - 1,
            ]
        else:
            return [*(self.address or []), len(self.elements) - 1]

    def _build_nested_builder(self, element: RouteLitElement) -> "RouteLitBuilder":
        builder = self.__class__(
            self.request,
            fragments=self.fragments,
            prefix=element.key,
            session_state=self.session_state,
            parent_element=element,
            parent_builder=self,
            address=self._get_last_address(),
        )
        return builder

    def _get_parent_form_id(self) -> Optional[str]:
        if self.parent_element and self.parent_element.name == "form":
            return self.parent_element.key
        if self.active_child_builder:
            return self.active_child_builder._get_parent_form_id()
        if self._prev_active_child_builder:
            return self._prev_active_child_builder._get_parent_form_id()
        return None

    def _new_text_id(self, name: str) -> str:
        no_of_non_widgets = (
            self.num_non_widget if not self.active_child_builder else self.active_child_builder.num_non_widget
        )
        prefix = self.active_child_builder._get_prefix() if self.active_child_builder else self._get_prefix()
        return f"{prefix}_{name}_{no_of_non_widgets}"

    def _new_widget_id(self, name: str, label: str) -> str:
        hashed = hashlib.sha256(label.encode()).hexdigest()[:8]
        prefix = self.active_child_builder._get_prefix() if self.active_child_builder else self._get_prefix()
        return f"{prefix}_{name}_{hashed}"

    def _maybe_get_event(self, component_id: str) -> Optional[RouteLitEvent]:
        event = self.request.ui_event
        if (
            event
            and event.get("type") == "submit"
            and (event_form_id := event.get("formId"))
            and self.session_state.get("__ignore_submit") != event_form_id
            and (form_id := self._get_parent_form_id())
            and event_form_id == form_id
        ):
            events = self.session_state.get(f"__events4later_{form_id}", {})
            self.session_state.pop(f"__events4later_{form_id}", None)
            self.session_state[f"__events_{form_id}"] = events
            self.session_state["__ignore_submit"] = form_id
            self.rerun(scope="app", clear_event=False)

        if event and event.get("componentId") == component_id:
            return event
        if (
            (form_id := self._get_parent_form_id())
            and (events := self.session_state.get(f"__events_{form_id}", {}))
            and component_id in events
        ):
            _event = events[component_id]
            events.pop(component_id, None)
            self.session_state[f"__events_{form_id}"] = events
            return _event
        return None

    def _get_event_value(self, component_id: str, event_type: str, attribute: Optional[str] = None) -> Tuple[bool, Any]:
        """
        Check if the last event is of the given type and component_id.
        If attribute is not None, check if the event has the given attribute.
        Returns a tuple of (has_event, event_data).
        """
        event = self._maybe_get_event(component_id)
        has_event = event and event.get("type") == event_type
        if has_event:
            if attribute is None:
                return True, event["data"]
            else:
                return True, event["data"][attribute]
        return False, None

    def append_element(self, element: RouteLitElement) -> None:
        """
        Append an element to the current builder.
        Returns the index of the element in the builder.
        """
        if self.active_child_builder:
            self.active_child_builder.append_element(element)
        else:
            self.elements.append(element)
            if element.name == "fragment" and element.key != self.initial_fragment_id:
                self.fragments[element.key] = element.address

    def add_non_widget(self, element: RouteLitElement) -> RouteLitElement:
        self.append_element(element)
        if not self.active_child_builder:
            self.num_non_widget += 1
        else:
            self.active_child_builder.num_non_widget += 1
        return element

    def add_widget(self, element: RouteLitElement):
        self.append_element(element)

    def create_element(
        self,
        name: str,
        key: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[RouteLitElement]] = None,
    ) -> RouteLitElement:
        element = RouteLitElement(key=key, name=name, props=props or {}, children=children)
        self.add_widget(element)
        return element

    def create_non_widget_element(
        self,
        name: str,
        key: str,
        props: Optional[Dict[str, Any]] = None,
        address: Optional[Sequence[int]] = None,
    ) -> RouteLitElement:
        element = RouteLitElement(key=key, name=name, props=props or {}, address=address)
        self.add_non_widget(element)
        return element

    def _fragment(self, key: Optional[str] = None) -> "RouteLitBuilder":
        key = key or self._new_text_id("fragment")
        fragment = self.create_non_widget_element(
            name="fragment",
            key=key,
            props={"id": key},
            address=self._get_next_address(),
        )
        return self._build_nested_builder(fragment)

    def _dialog(self, key: Optional[str] = None, closable: bool = True) -> "RouteLitBuilder":
        key = key or self._new_text_id("dialog")
        is_closed, _ = self._get_event_value(key, "close")
        if is_closed:
            self.rerun(scope="app")
        dialog = self.create_non_widget_element(
            name="dialog",
            key=key,
            props={"id": key, "open": True, "closable": closable},
        )
        return self._build_nested_builder(dialog)

    def form(self, key: str) -> "RouteLitBuilder":
        """
        Creates a form area that do not submit input values to the server until the form is submitted.
        Use button(..., event_name="submit") to submit the form.

        Args:
            key (str): The key of the form.
        """
        form = self.create_non_widget_element(
            name="form",
            key=key,
            props={"id": key},
        )
        return self._build_nested_builder(form)

    def link(
        self,
        href: str,
        text: str = "",
        replace: bool = False,
        is_external: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ) -> RouteLitElement:
        """
        Creates a link component.

        Args:
            href (str): The href of the link.
            text (str): The text of the link.
            replace (bool): Whether to replace the current page.
            is_external (bool): Whether the link is external.
            key (Optional[str]): The key of the link.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the link.
        """
        new_element = self.create_non_widget_element(
            name="link",
            key=key or self._new_text_id("link"),
            props={
                "href": href,
                "replace": replace,
                "isExternal": is_external,
                "text": text,
                **kwargs,
            },
        )
        return new_element

    def link_area(
        self,
        href: str,
        replace: bool = False,
        is_external: bool = False,
        key: Optional[str] = None,
        className: Optional[str] = None,
        **kwargs,
    ) -> "RouteLitBuilder":
        """
        Creates a link area component.

        Args:
            href (str): The href of the link.
            replace (bool): Whether to replace the current page.
            is_external (bool): Whether the link is external.
            key (Optional[str]): The key of the link area.
            className (Optional[str]): The class name of the link area.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the link area.
        """
        link_element = self.link(
            href,
            replace=replace,
            is_external=is_external,
            key=key,
            className=f"rl-no-link-decoration {className or ''}",
            **kwargs,
        )
        return self._build_nested_builder(link_element)

    def container(self, key: Optional[str] = None, height: Optional[str] = None, **kwargs) -> "RouteLitBuilder":
        """
        Creates a container component.

        Args:
            key (Optional[str]): The key of the container.
            height (Optional[str]): The height of the container.
        """
        container = self.create_non_widget_element(
            name="container",
            key=key or self._new_text_id("container"),
            props={"style": {"height": height}, **kwargs},
        )
        return self._build_nested_builder(container)

    def markdown(self, body: str, *, allow_unsafe_html: bool = False, key: Optional[str] = None, **kwargs):
        """
        Creates a markdown component.

        Args:
            body (str): The body of the markdown.
            allow_unsafe_html (bool): Whether to allow unsafe HTML.
            key (Optional[str]): The key of the markdown.
        """
        self.create_non_widget_element(
            name="markdown",
            key=key or self._new_text_id("markdown"),
            props={"body": body, "allowUnsafeHtml": allow_unsafe_html, **kwargs},
        )

    def text(self, body: str, key: Optional[str] = None, **kwargs):
        """
        Creates a text component.

        Args:
            body (str): The body of the text.
            key (Optional[str]): The key of the text.
        """
        self.markdown(body, allow_unsafe_html=False, key=key, **kwargs)

    def title(self, body: str, key: Optional[str] = None, **kwargs):
        """
        Creates a title component.

        Args:
            body (str): The body of the title.
            key (Optional[str]): The key of the title.
        """
        self.create_non_widget_element(
            name="title",
            key=key or self._new_text_id("title"),
            props={"children": body, **kwargs},
        )

    def header(self, body: str, key: Optional[str] = None, **kwargs):
        """
        Creates a header component.

        Args:
            body (str): The body of the header.
            key (Optional[str]): The key of the header.
        """
        self.create_non_widget_element(
            name="header",
            key=key or self._new_text_id("header"),
            props={"children": body, **kwargs},
        )

    def subheader(self, body: str, key: Optional[str] = None, **kwargs):
        """
        Creates a subheader component.

        Args:
            body (str): The body of the subheader.
            key (Optional[str]): The key of the subheader.
        """
        self.create_non_widget_element(
            name="subheader",
            key=key or self._new_text_id("subheader"),
            props={"children": body, **kwargs},
        )

    def image(self, src: str, *, key: Optional[str] = None, **kwargs):
        """
        Creates an image component.

        Args:
            src (str): The source of the image.
            key (Optional[str]): The key of the image.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the image.
        """
        self.create_non_widget_element(
            name="image",
            key=key or self._new_text_id("image"),
            props={"src": src, **kwargs},
        )

    def expander(self, title: str, *, open: Optional[bool] = None, key: Optional[str] = None) -> "RouteLitBuilder":
        """
        Creates an expander component that can be used as both a context manager and a regular function call.

        Args:
            title (str): The title of the expander.
            open (Optional[bool]): Whether the expander is open.
            key (Optional[str]): The key of the expander.

        Returns:
            RouteLitBuilder: A builder for the expander.
        ```python
        Usage:
            def build_index_view(rl: RouteLitBuilder):
                # Context manager style
                with rl.expander("Title"):
                    rl.text("Content")

                with rl.expander("Title", open=True) as exp0:
                    exp0.text("Content")

                # Function call style
                exp = rl.expander("Title")
                exp.text("Content")
        ```
        """
        new_key = key or self._new_widget_id("expander", title)
        new_element = self.create_element(
            name="expander",
            key=new_key,
            props={"title": title, "open": open},
        )
        return self._build_nested_builder(new_element)

    def columns(
        self,
        spec: int | List[int],
        *,
        key: Optional[str] = None,
        vertical_alignment: VerticalAlignment = "top",
        columns_gap: ColumnsGap = "small",
    ) -> List["RouteLitBuilder"]:
        """Creates a flexbox layout with several columns with the given spec.

        Args:
            spec (int | List[int]): The specification of the columns. Can be an integer or a list of integers.
            key (Optional[str]): The key of the container.
            vertical_alignment (VerticalAlignment): The vertical alignment of the columns: "top", "center", "bottom".
            columns_gap (ColumnsGap): The gap between the columns: "none", "small", "medium", "large".

        Returns:
            List[RouteLitBuilder]: A list of builders for the columns.

        Examples:
        ```python
            # 2 columns with equal width
            col1, col2 = rl.columns(2)
            # usage inline
            col1.text("Column 1")
            col2.text("Column 2")
            # usage as context manager
            with col1:
                rl.text("Column 1")
            with col2:
                rl.text("Column 2")
            # usage with different widths
            col1, col2, col3 = rl.columns([2, 1, 1])
            col1.text("Column 1")
            col2.text("Column 2")
            col3.text("Column 3")
        ```
        """
        if isinstance(spec, int):
            spec = [1] * spec
        container_key = key or self._new_text_id("container")
        container = self.create_non_widget_element(
            name="container",
            key=container_key,
            props={
                "className": "rl-flex rl-flex-row",
                "style": {
                    "alignItems": verticalAlignmentMap.get(vertical_alignment, "top"),
                    "columnGap": columnsGapMap.get(columns_gap, "small"),
                },
            },
        )
        container_builder = self._build_nested_builder(container)
        with container_builder:
            element_builders = []
            for column_spec in spec:
                column = self.create_non_widget_element(
                    name="container",
                    key=self._new_text_id("col"),
                    props={"style": {"flex": column_spec}},
                )
                element_builders.append(self._build_nested_builder(column))
        return element_builders

    def flex(
        self,
        direction: Literal["row", "col"] = "col",
        wrap: Literal["wrap", "nowrap"] = "nowrap",
        justify_content: Literal["start", "end", "center", "between", "around", "evenly"] = "start",
        align_items: Literal["normal", "start", "end", "center", "baseline", "stretch"] = "normal",
        align_content: Literal["normal", "start", "end", "center", "between", "around", "evenly"] = "normal",
        gap: Optional[str] = None,
        key: Optional[str] = None,
        **kwargs,
    ) -> "RouteLitBuilder":
        """
        Creates a flex container with the given direction, wrap, justify content, align items, align content, gap, and key.
        """
        container = self.create_non_widget_element(
            name="flex",
            key=key or self._new_text_id("flex"),
            props={
                "direction": direction,
                "flexWrap": wrap,
                "justifyContent": justify_content,
                "alignItems": align_items,
                "alignContent": align_content,
                "gap": gap,
                **kwargs,
            },
        )
        return self._build_nested_builder(container)

    def button(
        self,
        text: str,
        *,
        event_name: Optional[str] = "click",
        key: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> bool:
        """
        Creates a button with the given text, event name, key, on click, and keyword arguments.
        Example:
        ```python
        rl.button("Click me", on_click=lambda: print("Button clicked"))
        ```
        """
        button = self.create_element(
            name="button",
            key=key or self._new_widget_id("button", text),
            props={"text": text, "eventName": event_name, **kwargs},
        )
        is_clicked, _ = self._get_event_value(button.key, event_name)
        if is_clicked and on_click:
            on_click()
        return is_clicked

    def _x_input(
        self,
        element_type: Literal["text-input", "textarea"],
        label: str,
        value: Any | None = None,
        key: str | None = None,
        on_change: Callable[[str], None] | None = None,
        event_name: Optional[str] = "change",
        value_attribute: Optional[str] = "value",
        **kwargs,
    ) -> Any | None:
        component_id = key or self._new_widget_id(element_type, label)
        new_value = self.session_state.get(component_id, value)
        has_changed, event_value = self._get_event_value(component_id, event_name, value_attribute)
        if has_changed:
            new_value = event_value
            self.session_state[component_id] = new_value
            if on_change:
                on_change(new_value)
        self.create_element(
            name=element_type,
            key=component_id,
            props={
                "label": label,
                value_attribute: new_value,
                **kwargs,
            },
        )
        return new_value

    def text_input(
        self,
        label: str,
        *,
        type: Literal[
            "text",
            "number",
            "email",
            "password",
            "search",
            "tel",
            "url",
            "date",
            "time",
            "datetime-local",
            "month",
            "week",
        ] = "text",
        value: Optional[str] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> str:
        """
        Creates a text input with the given label and value.

        Args:
            - label: The label of the text input.
            - type: The type of the text input: "text", "number", "email", "password", "search", "tel", "url", "date", "time", "datetime-local", "month", "week".
            - value: The value of the text input.
            - key: The key of the text input.
            - on_change: The function to call when the value changes. The function will be called with the new value.
            - kwargs: The keyword arguments to pass to the text input.

        Returns:
            str: The text value of the text input.

        Example:
        ```python
        rl.text_input("Name", value="John", on_change=lambda value: print(f"Name changed to {value}"))
        ```
        """
        return self._x_input("text-input", label, value, key, on_change, type=type, **kwargs)

    def textarea(
        self,
        label: str,
        *,
        value: Optional[str] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> str:
        """
        Creates a textarea with the given label and value.

        Args:
            - label: The label of the textarea.
            - value: The value of the textarea.
            - key: The key of the textarea.
            - on_change: The function to call when the value changes. The function will be called with the new value.
            - kwargs: The keyword arguments to pass to the textarea.

        Returns:
            str: The text value of the textarea.
        """
        return self._x_input("textarea", label, value, key, on_change, **kwargs)

    def radio(
        self,
        label: str,
        options: Sequence[Dict[str, Any] | str],
        *,
        value: str | int | None = None,
        key: str | None = None,
        on_change: Callable[[str | int | None], None] | None = None,
        flex_direction: Literal["row", "col"] = "col",
        **kwargs,
    ) -> str | int | None:
        """
        Creates a radio group with the given label and options.

        Args:
            - label: The label of the radio group.
            - options: The options of the radio group. Each option can be a string or a dictionary with the following keys:
                - label: The label of the option.
                - value: The value of the option.
                - caption: The caption of the option.
                - disabled: Whether the option is disabled.
            - value: The value of the radio group.
            - key: The key of the radio group.
            - on_change: The function to call when the value changes. The function will be called with the new value.
            - kwargs: The keyword arguments to pass to the radio group.
        Returns:
            str | int | None: The value of the selected radio option.
        """
        return self._x_input(
            "radio", label, value, key, on_change, options=options, flexDirection=flex_direction, **kwargs
        )

    def select(
        self,
        label: str,
        options: Sequence[Dict[str, Any] | str],
        *,
        value: str | int | None = None,
        key: str | None = None,
        on_change: Callable[[str | int | None], None] | None = None,
        **kwargs,
    ) -> Any:
        """
        Creates a select dropdown with the given label and options.

        Args:
            - label: The label of the select dropdown.
            - options: The options of the select dropdown. Each option can be a string or a dictionary with the following keys: (label, value, disabled)
                - label: The label of the option.
                - value: The value of the option.
                - disabled: Whether the option is disabled.
            - value: The value of the select dropdown.
            - key: The key of the select dropdown.
            - on_change: The function to call when the value changes. The function will be called with the new value.
            - kwargs: The keyword arguments to pass to the select dropdown.

        Returns:
            Any: The value of the select dropdown.
        """
        return self._x_input("select", label, value, key, on_change, options=options, **kwargs)

    def checkbox(
        self,
        label: str,
        *,
        checked: bool = False,
        key: str | None = None,
        on_change: Callable[[bool], None] | None = None,
        **kwargs,
    ) -> bool:
        """
        Creates a checkbox with the given label and value.

        Args:
            label (str): The label of the checkbox.
            checked (bool): Whether the checkbox is checked.
            key (str | None): The key of the checkbox.
            on_change (Callable[[bool], None] | None): The function to call when the value changes.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the checkbox.
        Returns:
            bool: Whether the checkbox is checked.
        """
        return self._x_input("checkbox", label, checked, key, on_change, value_attribute="checked", **kwargs)

    def checkbox_group(
        self,
        label: str,
        options: Sequence[Dict[str, Any] | str],
        *,
        value: List[str | int] | None = None,
        key: str | None = None,
        on_change: Callable[[List[str | int]], None] | None = None,
        flex_direction: Literal["row", "col"] = "col",
        **kwargs,
    ) -> List[str | int]:
        """
        Creates a checkbox group with the given label and options.

        Args:
            label (str): The label of the checkbox group.
            options (Sequence[Dict[str, Any] | str]): The options of the checkbox group.
            value (List[str | int] | None): The value of the checkbox group.
            key (str | None): The key of the checkbox group.
            on_change (Callable[[List[str | int]], None] | None): The function to call when the value changes.
            flex_direction (Literal["row", "col"]): The direction of the checkbox group: "row", "col".
            kwargs (Dict[str, Any]): The keyword arguments to pass to the checkbox group.
        Returns:
            List[str | int]: The value of the checkbox group.
        """
        return self._x_input(
            "checkbox-group", label, value, key, on_change, options=options, flexDirection=flex_direction, **kwargs
        )

    def rerun(self, scope: RerunType = "auto", clear_event: bool = True):
        """
        Reruns the current page. Use this to rerun the app or the fragment depending on the context.

        Args:
            scope (RerunType): The scope of the rerun. "auto" will rerun the app or the fragment depending on the context, "app" will rerun the entire app
            clear_event (bool): Whether to clear the event.
        """
        self.elements.clear()
        if clear_event:
            self.request.clear_event()
        if scope == "app":
            self.request.clear_fragment_id()
        raise RerunException(self.session_state, scope=scope)

    def get_head(self) -> Head:
        return self.head

    def set_page_config(self, page_title: str | None = None, page_description: str | None = None):
        """
        Sets the page title and description.

        Args:
            page_title (str | None): The title of the page.
            page_description (str | None): The description of the page.
        """
        self.head = Head(title=page_title, description=page_description)
        new_element = self.create_non_widget_element(
            name="head",
            key="__head__",
            props={
                "title": page_title,
                "description": page_description,
            },
        )
        return new_element

    def __enter__(self):
        # When using with builder.element():
        # Make parent builder redirect to this one
        if self.parent_builder:
            self._prev_active_child_builder = self.parent_builder.active_child_builder
            self.parent_builder.active_child_builder = self
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Reset parent's active child when exiting context
        if self.parent_builder:
            if self._prev_active_child_builder:
                self.parent_builder.active_child_builder = self._prev_active_child_builder
                self._prev_active_child_builder = None
            else:
                self.parent_builder.active_child_builder = None

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self

    def get_elements(self) -> List[RouteLitElement]:
        if self.initial_fragment_id:
            return self.elements[0].children
        return self.elements

    def get_fragments(self) -> MutableMapping[str, Sequence[int]]:
        return self.fragments

    def on_end(self):
        self.session_state.pop("__ignore_submit", None)

    @classmethod
    def get_client_resource_paths(cls) -> Sequence[AssetTarget]:
        return cls.static_assets_targets
