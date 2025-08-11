import asyncio
import hashlib
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Literal,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)

from routelit.domain import (
    Action,
    AssetTarget,
    BuilderTarget,
    Head,
    LastAction,
    NoChangeAction,
    RerunAction,
    RerunType,
    RLOption,
    RouteLitElement,
    RouteLitEvent,
    RouteLitRequest,
    SetAction,
    ViewTaskDoneAction,
)
from routelit.exceptions import RerunException, StopException
from routelit.utils.misc import (
    format_options,
    get_element_at_address,
    remove_none_values,
)
from routelit.utils.property_dict import PropertyDict

VerticalAlignment = Literal["top", "center", "bottom"]
"""
The vertical alignment of the elements.
"""
verticalAlignmentMap: Dict[VerticalAlignment, str] = {
    "top": "flex-start",
    "center": "center",
    "bottom": "flex-end",
}
ColumnsGap = Literal["none", "small", "medium", "large"]
"""
The gap between the columns.
"""
columnsGapMap: Dict[ColumnsGap, str] = {
    "none": "0",
    "small": "1rem",
    "medium": "2rem",
    "large": "3rem",
}

TextInputType = Literal[
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
]
"""
The type of the text input.
"""


class RouteLitBuilder:
    static_assets_targets: ClassVar[List[AssetTarget]] = []

    def __init__(
        self,
        request: RouteLitRequest,
        session_state: PropertyDict,
        fragments: MutableMapping[str, List[int]],
        prev_root_element: Optional[RouteLitElement] = None,
        cancel_event: Optional[asyncio.Event] = None,
        should_rerun_event: Optional[asyncio.Event] = None,
        initial_fragment_id: Optional[str] = None,
        initial_target: Optional[BuilderTarget] = None,
        event_queue: Optional[asyncio.Queue] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        parent_element: Optional[RouteLitElement] = None,
        parent_builder: Optional["RouteLitBuilder"] = None,
        last_fragment_address: Optional[List[int]] = None,
    ):
        self.request = request
        self.initial_fragment_id = initial_fragment_id
        self.last_fragment_address = last_fragment_address
        self.initial_target = (
            initial_target if initial_target is not None else "app" if initial_fragment_id is None else "fragment"
        )
        self.fragments = fragments
        self.prev_root_element = prev_root_element
        self.has_prev_diff = False
        self._event_queue = event_queue
        self._loop = loop
        self.cancel_event = cancel_event
        self.head: Optional[Head] = None
        self._parent_element = parent_element or RouteLitElement.create_root_element()
        self._root_element = self._parent_element
        self.session_state = session_state
        self.parent_builder = parent_builder
        self.active_child_builder: Optional[RouteLitBuilder] = None
        self._prev_active_child_builder: Optional[RouteLitBuilder] = None
        self.q_by_name: Dict[str, int] = {}
        self.should_rerun_event = should_rerun_event
        if self._root_element.name == RouteLitElement.ROOT_ELEMENT_NAME and initial_fragment_id is None:
            self._on_init()

    def _on_init(self) -> None:
        pass

    def get_request(self) -> RouteLitRequest:
        return self.request

    def _get_prefix(self) -> str:
        return self.active_child_builder._get_prefix() if self.active_child_builder else self._parent_element.key

    def _schedule_event(self, event_data: Action) -> bool:
        """
        Schedule an event to be put in the queue from sync context
        Returns True if the event was scheduled, False otherwise.
        """

        if not (self._event_queue and self._loop):
            # Nothing to do - no queue/loop configured.
            return False

        # Guard against scheduling onto a closed loop (can happen during
        # teardown).
        if self._loop.is_closed():
            return False

        self._loop.call_soon_threadsafe(self._event_queue.put_nowait, event_data)
        return True

    @property
    def elements(self) -> List[RouteLitElement]:
        return self._root_element.get_children()

    @property
    def root_element(self) -> RouteLitElement:
        if self.initial_fragment_id and self._root_element.children:
            return self._root_element.children[0]
        return self._root_element

    @property
    def elements_count(self) -> int:
        return len(self.elements)

    @property
    def address(self) -> List[int]:
        return self._root_element.address or []

    def _get_next_address(self) -> List[int]:
        if self.active_child_builder:
            return self.active_child_builder._get_next_address()
        else:
            return [*self.address, self.elements_count]

    def _get_last_address(self) -> List[int]:
        if self.active_child_builder:
            return self.active_child_builder._get_last_address()
        else:
            return [*self.address, self.elements_count - 1]

    def _build_nested_builder(self, element: RouteLitElement) -> "RouteLitBuilder":
        if element.address is None:
            element.address = self._get_last_address()
        prev_root_element = (
            self.prev_root_element
            if self.prev_root_element and self.prev_root_element.key == element.key
            else get_element_at_address(self.prev_root_element, element.address)
            if self.prev_root_element
            else None
        )
        last_fragment_address = element.address if element.name == "fragment" else self.last_fragment_address
        builder = self.__class__(
            self.request,
            fragments=self.fragments,
            event_queue=self._event_queue,
            loop=self._loop,
            cancel_event=self.cancel_event,
            session_state=self.session_state,
            parent_element=element,
            parent_builder=self,
            initial_target=self.initial_target,
            prev_root_element=prev_root_element,
            should_rerun_event=self.should_rerun_event,
            last_fragment_address=last_fragment_address,
        )
        return builder

    def _get_parent_form_id(self) -> Optional[str]:
        if self._parent_element and self._parent_element.name == "form":
            return self._parent_element.key
        if self.active_child_builder:
            return self.active_child_builder._get_parent_form_id()
        if self._prev_active_child_builder:
            return self._prev_active_child_builder._get_parent_form_id()
        return None

    def _new_text_id(self, name: str) -> str:
        prefix = self._get_prefix()
        q_by_name = self.active_child_builder.q_by_name if self.active_child_builder else self.q_by_name
        if name in q_by_name:
            q_by_name[name] += 1
        else:
            q_by_name[name] = 1
        key = f"{prefix}_{name}_{q_by_name[name]}"
        return key

    def _new_widget_id(self, name: str, label: str) -> str:
        hashed = hashlib.sha256(label.encode()).hexdigest()[:8]
        prefix = self._get_prefix()
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
            _event: RouteLitEvent = events[component_id]
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
        if event is not None and event.get("type") == event_type:
            if attribute is None:
                return True, event["data"]
            else:
                return True, event["data"].get(attribute)
        return False, None

    def _append_element(self, element: RouteLitElement) -> None:
        """
        Append an element to the current builder.
        Returns the index of the element in the builder.
        Do not use this method directly, use the other methods instead, unless you are creating a custom element.
        """
        if self.active_child_builder:
            self.active_child_builder._append_element(element)
            return

        # do not append elements if the builder should rerun (when streaming)
        if self.should_rerun_event and self.should_rerun_event.is_set():
            return

        if self.cancel_event and self.cancel_event.is_set():
            raise StopException("Builder cancelled")

        element.props = remove_none_values(element.props)
        self._parent_element.append_child(element)

        if element.name == "fragment" and element.key != self.initial_fragment_id and element.address is not None:
            self.fragments[element.key] = element.address

        # skip sending action for fragment as root
        if self.initial_target == "fragment" and element.name == "fragment" and self.initial_fragment_id is not None:
            return

        # skip the first address for fragment as root
        address = self._get_last_address()[1:] if self.initial_target == "fragment" else self._get_last_address()

        # check if the element is the same as the previous one
        if (
            self.prev_root_element is not None
            and self.prev_root_element.children is not None
            and len(address) > 0
            and address[-1] < len(self.prev_root_element.children)
            and (prev_element := self.prev_root_element.children[address[-1]])
            and prev_element.key == element.key
            and prev_element.props == element.props
        ):
            self._schedule_event(NoChangeAction(address=address, target=self.initial_target))
            return

        new_element = element.to_dict()
        if element.name == "fragment" and self.last_fragment_address is not None and element.address is not None:
            new_element["address"] = element.address[len(self.last_fragment_address) - 1 :]

        self._schedule_event(
            SetAction(
                element=new_element,
                key=element.key,
                address=address,
                target=self.initial_target,
            )
        )

    def _add_non_widget(self, element: RouteLitElement) -> RouteLitElement:
        self._append_element(element)
        return element

    def _add_widget(self, element: RouteLitElement) -> None:
        self._append_element(element)

    def create_element(
        self,
        name: str,
        key: Optional[str] = None,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[RouteLitElement]] = None,
        address: Optional[List[int]] = None,
        virtual: Optional[bool] = None,
        **kwargs: Any,
    ) -> RouteLitElement:
        return RouteLitElement(
            key=key or hashlib.sha256(name.encode()).hexdigest()[:8],
            name=name,
            props={**(props or {}), **kwargs},
            children=children,
            address=address,
            virtual=virtual,
        )

    def _create_element(
        self,
        name: str,
        key: str,
        props: Optional[Dict[str, Any]] = None,
        children: Optional[List[RouteLitElement]] = None,
        address: Optional[List[int]] = None,
        virtual: Optional[bool] = None,
    ) -> RouteLitElement:
        element = RouteLitElement(
            key=key,
            name=name,
            props=props or {},
            children=children,
            address=address,
            virtual=virtual,
        )
        self._add_widget(element)
        return element

    def _fragment(self, key: Optional[str] = None) -> "RouteLitBuilder":
        key = key or self._new_text_id("fragment")
        fragment = self._create_element(
            name="fragment",
            key=key,
            props={"id": key},
            address=self._get_next_address(),
            virtual=True,
        )
        return self._build_nested_builder(fragment)

    def _x_dialog(
        self,
        element_type: str,
        key: str,
        *,
        on_close: Optional[Callable[[], Optional[bool]]] = None,
        **kwargs: Any,
    ) -> "RouteLitBuilder":
        is_closed, _ = self._get_event_value(key, "close")
        if is_closed:
            should_rerun = True
            if on_close and (result := on_close()) is not None:
                should_rerun = result
            if should_rerun:
                self.rerun(scope="app")
        dialog = self._create_element(
            name=element_type,
            key=key,
            props={"id": key, **kwargs},
            virtual=True,
        )
        return self._build_nested_builder(dialog)

    def _create_builder_element(
        self,
        name: str,
        key: str,
        props: Optional[Dict[str, Any]] = None,
        address: Optional[List[int]] = None,
        virtual: Optional[bool] = None,
    ) -> "RouteLitBuilder":
        element = self._create_element(
            name=name,
            key=key,
            props=props or {},
            address=address,
            virtual=virtual,
        )
        return self._build_nested_builder(element)

    def _dialog(self, key: Optional[str] = None, **kwargs: Any) -> "RouteLitBuilder":
        return self._x_dialog(
            "dialog",
            key or self._new_text_id("dialog"),
            open=True,
            closable=True,
            **kwargs,
        )

    def form(self, key: str) -> "RouteLitBuilder":
        """
        Creates a form area that do not submit input values to the server until the form is submitted.
        Use button(..., event_name="submit") to submit the form.

        Args:
            key (str): The key of the form.

        Returns:
            RouteLitBuilder: A builder for the form.

        Example:
        ```python
        with ui.form("login"):
            username = ui.text_input("Username")
            password = ui.text_input("Password", type="password")
            is_submitted = ui.button("Login", event_name="submit")
            if is_submitted:
                ui.text(f"Login successful for {username}")
        ```
        """
        form = self._create_element(
            name="form",
            key=key,
            props={"id": key},
            virtual=True,
        )
        return self._build_nested_builder(form)

    def link(
        self,
        href: str,
        text: str = "",
        *,
        replace: bool = False,
        is_external: bool = False,
        key: Optional[str] = None,
        rl_element_type: str = "link",
        rl_text_attr: str = "text",
        rl_virtual: Optional[bool] = None,
        **kwargs: Any,
    ) -> RouteLitElement:
        """
        Creates a link component. Use this to navigate to a different page.

        Args:
            href (str): The href of the link.
            text (str): The text of the link.
            replace (bool): Whether to replace the current page from the history.
            is_external (bool): Whether the link is external to the current app.
            key (Optional[str]): The key of the link.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the link.

        Example:
        ```python
        ui.link("/signup", text="Signup")
        ui.link("/login", text="Login", replace=True)
        ui.link("https://www.google.com", text="Google", is_external=True)
        ```
        """
        new_element = self._create_element(
            name=rl_element_type,
            key=key or self._new_text_id(rl_element_type),
            props={
                "href": href,
                "replace": replace,
                "isExternal": is_external,
                rl_text_attr: text,
                **kwargs,
            },
            virtual=rl_virtual,
        )
        return new_element

    def link_area(
        self,
        href: str,
        replace: bool = False,
        is_external: bool = False,
        key: Optional[str] = None,
        className: Optional[str] = None,
        **kwargs: Any,
    ) -> "RouteLitBuilder":
        """
        Creates a link area component. Use this element which is a container of other elements.

        Args:
            href (str): The href of the link.
            replace (bool): Whether to replace the current page.
            is_external (bool): Whether the link is external.
            key (Optional[str]): The key of the link area.
            className (Optional[str]): The class name of the link area.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the link area.

        Example:
        ```python
        with ui.link_area("https://www.google.com"):
            with ui.flex(direction="row", gap="small"):
                ui.image("https://www.google.com/favicon.ico", width="24px", height="24px")
                ui.text("Google")
        ```
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

    def container(self, key: Optional[str] = None, height: Optional[str] = None, **kwargs: Any) -> "RouteLitBuilder":
        """
        Creates a container component.

        Args:
            key (Optional[str]): The key of the container.
            height (Optional[str]): The height of the container.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the container.

        Example:
        ```python
        with ui.container(height="100px"):
            ui.text("Container")
        ```
        """
        container = self._create_element(
            name="container",
            key=key or self._new_text_id("container"),
            props={"style": {"height": height}, **kwargs},
        )
        return self._build_nested_builder(container)

    def markdown(
        self,
        body: str,
        *,
        allow_unsafe_html: bool = False,
        key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Creates a markdown component.

        Args:
            body (str): The body of the markdown.
            allow_unsafe_html (bool): Whether to allow unsafe HTML.
            key (Optional[str]): The key of the markdown.

        Example:
        ```python
        ui.markdown("**Bold** *italic* [link](https://www.google.com)")
        ```
        """
        self._create_element(
            name="markdown",
            key=key or self._new_text_id("markdown"),
            props={"body": body, "allowUnsafeHtml": allow_unsafe_html, **kwargs},
        )

    def text(self, body: str, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates a text component.

        Args:
            body (str): The body of the text.
            key (Optional[str]): The key of the text.

        Example:
        ```python
        ui.text("Text")
        ```
        """
        self.markdown(body, allow_unsafe_html=False, key=key, **kwargs)

    def title(self, body: str, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates a title component.

        Args:
            body (str): The body of the title.
            key (Optional[str]): The key of the title.

        Example:
        ```python
        ui.title("Title")
        ```
        """
        self._create_element(
            name="title",
            key=key or self._new_text_id("title"),
            props={"children": body, **kwargs},
        )

    def header(self, body: str, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates a header component.

        Args:
            body (str): The body of the header.
            key (Optional[str]): The key of the header.

        Example:
        ```python
        ui.header("Header")
        ```
        """
        self._create_element(
            name="header",
            key=key or self._new_text_id("header"),
            props={"children": body, **kwargs},
        )

    def subheader(self, body: str, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates a subheader component.

        Args:
            body (str): The body of the subheader.
            key (Optional[str]): The key of the subheader.

        Example:
        ```python
        ui.subheader("Subheader")
        ```
        """
        self._create_element(
            name="subheader",
            key=key or self._new_text_id("subheader"),
            props={"children": body, **kwargs},
        )

    def image(self, src: str, *, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates an image component.

        Args:
            src (str): The source of the image.
            key (Optional[str]): The key of the image.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the image.

        Example:
        ```python
        ui.image("https://www.google.com/favicon.ico", alt="Google", width="24px", height="24px")
        ```
        """
        self._create_element(
            name="image",
            key=key or self._new_text_id("image"),
            props={"src": src, **kwargs},
        )

    def expander(self, title: str, *, is_open: Optional[bool] = None, key: Optional[str] = None) -> "RouteLitBuilder":
        """
        Creates an expander component that can be used as both a context manager and a regular function call.

        Args:
            title (str): The title of the expander.
            is_open (Optional[bool]): Whether the expander is open.
            key (Optional[str]): The key of the expander.

        Returns:
            RouteLitBuilder: A builder for the expander.
        ```python
        Usage:
            def build_index_view(ui: RouteLitBuilder):
                # Context manager style
                with ui.expander("Title"):
                    ui.text("Content")

                with ui.expander("Title", is_open=True) as exp0:
                    exp0.text("Content")

                # Function call style
                exp = ui.expander("Title")
                exp.text("Content")
        ```
        """
        new_key = key or self._new_widget_id("expander", title)
        new_element = self._create_element(
            name="expander",
            key=new_key,
            props={"title": title, "open": is_open},
        )
        return self._build_nested_builder(new_element)

    def columns(
        self,
        spec: Union[int, List[int]],
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
            col1, col2 = ui.columns(2)
            # usage inline
            col1.text("Column 1")
            col2.text("Column 2")
            # usage as context manager
            with col1:
                ui.text("Column 1")
            with col2:
                ui.text("Column 2")
            # usage with different widths
            col1, col2, col3 = ui.columns([2, 1, 1])
            col1.text("Column 1")
            col2.text("Column 2")
            col3.text("Column 3")
        ```
        """
        if isinstance(spec, int):
            spec = [1] * spec
        container_key = key or self._new_text_id("container")
        container = self._create_element(
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
                column = self._create_element(
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
        **kwargs: Any,
    ) -> "RouteLitBuilder":
        """
        Creates a flex container with the given direction, wrap, justify content, align items, align content, gap, and key.
        """
        container = self._create_element(
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

    def _x_button(
        self,
        element_type: str,
        text: str,
        *,
        event_name: Literal["click", "submit"] = "click",
        key: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        rl_virtual: Optional[bool] = None,
        **kwargs: Any,
    ) -> bool:
        button = self._create_element(
            name=element_type,
            key=key or self._new_widget_id(element_type, text),
            props={
                "children": text,
                "rlEventName": event_name,
                **kwargs,
            },
            virtual=rl_virtual,
        )
        is_clicked, _ = self._get_event_value(button.key, event_name)
        if is_clicked and on_click:
            on_click()
        return is_clicked

    def button(
        self,
        text: str,
        *,
        key: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Creates a button with the given text, key, on click, and keyword arguments.

        Args:
            text (str): The text of the button.
            key (Optional[str]): The key of the button.
            on_click (Optional[Callable[[], None]]): The function to call when the button is clicked.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the button.

        Returns:
            bool: Whether the button was clicked.

        Example:
        ```python
        is_clicked = ui.button("Click me", on_click=lambda: print("Button clicked"))
        if is_clicked:
            ui.text("Button clicked")
        ```
        """
        return self._x_button("button", text, event_name="click", key=key, on_click=on_click, **kwargs)

    def form_submit_button(
        self,
        text: str,
        *,
        key: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> bool:
        """
        Creates a form submit button with the given text, key, on click, and keyword arguments.

        Args:
            text (str): The text of the button.
            key (Optional[str]): The key of the button.
            on_click (Optional[Callable[[], None]]): The function to call when the button is clicked.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the button.

        Returns:
            bool: Whether the button was clicked.

        Example:
        ```python
        with ui.form(key="form_key"):
            is_submitted = ui.form_submit_button("Submit", on_click=lambda: print("Form submitted"))
            if is_submitted:
                ui.text("Form submitted")
        ```
        """
        return self._x_button("button", text, event_name="submit", key=key, on_click=on_click, **kwargs)

    def _x_input(
        self,
        element_type: str,
        key: str,
        *,
        value: Optional[Any] = None,
        on_change: Optional[Callable[[Any], None]] = None,
        event_name: str = "change",
        event_value_attr: str = "value",
        value_attr: str = "defaultValue",
        rl_format_func: Optional[Callable[[Any], Any]] = None,
        **kwargs: Any,
    ) -> Optional[Union[str, Any]]:
        new_value: Any = self.session_state.get(key, value)
        has_changed, event_value = self._get_event_value(key, event_name, event_value_attr)
        if has_changed:
            new_value = event_value
            if rl_format_func:
                new_value = rl_format_func(new_value)
            self.session_state[key] = new_value
            if on_change:
                on_change(new_value)
        self._create_element(
            name=element_type,
            key=key,
            props={
                value_attr: new_value,
                **kwargs,
            },
        )
        return new_value

    def _x_radio_select(
        self,
        element_type: str,
        key: str,
        *,
        options: List[Union[RLOption, str, Dict[str, Any]]],
        value: Optional[Any] = None,
        on_change: Optional[Callable[[Any], None]] = None,
        format_func: Optional[Callable[[Any], str]] = None,
        options_attr: str = "options",
        **kwargs: Any,
    ) -> Any:
        new_value = self.session_state.get(key, value)
        has_changed, event_value = self._get_event_value(key, "change", "value")
        if has_changed:
            new_value = event_value
            self.session_state[key] = new_value
            if on_change:
                on_change(new_value)
        new_options = format_options(options, format_func)
        self._create_element(
            name=element_type,
            key=key,
            props={
                "value": new_value,
                options_attr: new_options,
                **kwargs,
            },
        )
        return new_value

    def text_input(
        self,
        label: str,
        *,
        type: TextInputType = "text",
        value: Optional[str] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Creates a text input with the given label and value.

        Args:
            label (str): The label of the text input.
            type (TextInputType): The type of the text input.
            value (Optional[str]): The value of the text input.
            key (Optional[str]): The key of the text input.
            on_change (Optional[Callable[[str], None]]): The function to call when the value changes. The function will be called with the new value.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the text input.

        Returns:
            str: The text value of the text input.

        Example:
        ```python
        name = ui.text_input("Name", value="John", on_change=lambda value: print(f"Name changed to {value}"))
        ui.text(f"Name is {name}")
        ```
        """
        return self._x_input(
            "single-text-input",
            key or self._new_widget_id("text-input", label),
            value=value,
            on_change=on_change,
            type=type,
            label=label,
            **kwargs,
        )

    def hr(self, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Creates a horizontal rule.
        """
        self._create_element(name="hr", key=key or self._new_text_id("hr"), props=kwargs)

    def textarea(
        self,
        label: str,
        *,
        value: Optional[str] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Creates a textarea with the given label and value.

        Args:
            label (str): The label of the textarea.
            value (Optional[str]): The value of the textarea.
            key (Optional[str]): The key of the textarea.
            on_change (Optional[Callable[[str], None]]): The function to call when the value changes. The function will be called with the new value.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the textarea.

        Returns:
            str: The text value of the textarea.

        Example:
        ```python
        text = ui.textarea("Text", value="Hello, world!", on_change=lambda value: print(f"Text changed to {value}"))
        ui.text(f"Text is {text}")
        ```
        """
        return self._x_input(
            "single-textarea",
            key or self._new_widget_id("textarea", label),
            value=value,
            on_change=on_change,
            label=label,
            **kwargs,
        )

    def radio(
        self,
        label: str,
        options: List[Union[RLOption, str, Dict[str, Any]]],
        *,
        value: Optional[Any] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[Any], None]] = None,
        flex_direction: Literal["row", "col"] = "col",
        format_func: Optional[Callable[[Any], str]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Creates a radio group with the given label and options.

        Args:
            label (str): The label of the radio group.
            options (List[RLOption | str | Dict[str, Any]]): The options of the radio group. Each option can be a string or a dictionary with the following keys:
                - label: The label of the option.
                - value: The value of the option.
                - caption: The caption of the option.
                - disabled: Whether the option is disabled.
            value (str | int | None): The value of the radio group.
            key (str | None): The key of the radio group.
            on_change (Callable[[str | int | None], None] | None): The function to call when the value changes. The function will be called with the new value.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the radio group.
        Returns:
            str | int | None: The value of the selected radio option.

        Example:
        ```python
        value = ui.radio("Radio", options=["Option 1", {"label": "Option 2", "value": "option2"}, {"label": "Option 3", "value": "option3", "disabled": True}], value="Option 1", on_change=lambda value: print(f"Radio value changed to {value}"))
        ui.text(f"Radio value is {value}")
        ```
        """
        return self._x_radio_select(
            "radio",
            key or self._new_widget_id("radio", label),
            options=options,
            value=value,
            on_change=on_change,
            label=label,
            format_func=format_func,
            flexDirection=flex_direction,
            **kwargs,
        )

    def select(
        self,
        label: str,
        options: List[Union[RLOption, str, Dict[str, Any]]],
        *,
        value: Any = "",
        key: Optional[str] = None,
        on_change: Optional[Callable[[Any], None]] = None,
        format_func: Optional[Callable[[Any], str]] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Creates a select dropdown with the given label and options.

        Args:
            label (str): The label of the select dropdown.
            options (List[RLOption | str | Dict[str, Any]]): The options of the select dropdown. Each option can be a string or a dictionary with the following keys: (label, value, disabled)
                - label: The label of the option.
                - value: The value of the option.
                - disabled: Whether the option is disabled.
            value (str | int): The value of the select dropdown.
            key (str | None): The key of the select dropdown.
            on_change (Callable[[str | int | None], None] | None): The function to call when the value changes. The function will be called with the new value.
            format_func (Callable[[Any], str] | None): The function to format the options.
            kwargs (Dict[str, Any]): The keyword arguments to pass to the select dropdown.

        Returns:
            Any: The value of the select dropdown.

        Example:
        ```python
        value = ui.select("Select", options=["Option 1", {"label": "Option 2", "value": "option2"}, {"label": "Option 3", "value": "option3", "disabled": True}], value="Option 1", on_change=lambda value: print(f"Select value changed to {value}"))
        ui.text(f"Select value is {value}")
        ```
        """
        return self._x_radio_select(
            "select",
            key or self._new_widget_id("select", label),
            options=options,
            value=value,
            on_change=on_change,
            format_func=format_func,
            label=label,
            **kwargs,
        )

    def _x_checkbox(
        self,
        element_type: str,
        key: str,
        *,
        checked: bool = False,
        on_change: Optional[Callable[[bool], None]] = None,
        checked_attr: str = "checked",
        **kwargs: Any,
    ) -> bool:
        value_key = key
        default_key = f"__{key}_default"

        current_value = self.session_state.get(key)
        previous_default = self.session_state.get(f"__{key}_default")

        # Initialize or update if default changed
        if current_value is None:
            # First time - use the checked parameter
            self.session_state[value_key] = checked
            self.session_state[default_key] = checked
            current_value = checked
        elif previous_default != checked:
            # Default value changed - update to new default
            self.session_state[value_key] = checked
            self.session_state[default_key] = checked
            current_value = checked

        # Handle user interaction events
        has_changed, event_value = self._get_event_value(key, "change", "checked")
        if has_changed:
            new_value = bool(event_value) if event_value is not None else False
            self.session_state[value_key] = new_value
            if on_change:
                on_change(new_value)
            current_value = new_value

        self._create_element(
            name=element_type,
            key=key,
            props={
                checked_attr: current_value,
                **kwargs,
            },
        )
        return bool(current_value)

    def checkbox(
        self,
        label: str,
        *,
        checked: bool = False,
        key: Optional[str] = None,
        on_change: Optional[Callable[[bool], None]] = None,
        **kwargs: Any,
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

        Example:
        ```python
        is_checked = ui.checkbox("Check me", on_change=lambda checked: print(f"Checkbox is {'checked' if checked else 'unchecked'}"))
        if is_checked:
            ui.text("Checkbox is checked")
        ```
        """
        return self._x_checkbox(
            "single-checkbox",
            key or self._new_widget_id("checkbox", label),
            checked=checked,
            on_change=on_change,
            label=label,
            **kwargs,
        )

    def _x_checkbox_group(
        self,
        element_type: str,
        key: str,
        *,
        options: List[Union[RLOption, str, Dict[str, Any]]],
        format_func: Optional[Callable[[Any], str]] = None,
        value: Optional[List[Any]] = None,
        on_change: Optional[Callable[[List[Any]], None]] = None,
        value_attr: str = "value",
        options_attr: str = "options",
        **kwargs: Any,
    ) -> List[Any]:
        new_value: List[Any] = self.session_state.get(key, value) or []
        if not isinstance(new_value, list):
            new_value = value or []
        has_changed, event_value = self._get_event_value(key, "change", "value")
        if has_changed:
            new_value = event_value if isinstance(event_value, list) else []
            self.session_state[key] = new_value
            if on_change:
                on_change(new_value)
        new_options = format_options(options, format_func)
        self._create_element(
            name=element_type,
            key=key,
            props={
                value_attr: new_value,
                options_attr: new_options,
                **kwargs,
            },
        )
        return new_value

    def checkbox_group(
        self,
        label: str,
        options: List[Union[RLOption, str, Dict[str, Any]]],
        *,
        value: Optional[List[Any]] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[List[Any]], None]] = None,
        format_func: Optional[Callable[[Any], str]] = None,
        flex_direction: Literal["row", "col"] = "col",
        **kwargs: Any,
    ) -> List[Any]:
        """
        Creates a checkbox group with the given label and options.

        Args:
            label (str): The label of the checkbox group.
            options (List[RLOption | str | Dict[str, Any]]): The options of the checkbox group. Each option can be a string or a dictionary with the following keys: label, value, caption (optional), disabled (optional).
            value (List[str | int] | None): The value of the checkbox group.
            key (str | None): The key of the checkbox group.
            on_change (Callable[[List[str | int]], None] | None): The function to call when the value changes.
            format_func (Callable[[Any], str] | None): The function to format the options.
            flex_direction (Literal["row", "col"]): The direction of the checkbox group: "row", "col".
            kwargs (Dict[str, Any]): The keyword arguments to pass to the checkbox group.
        Returns:
            List[str | int]: The value of the checkbox group.

        Example:
        ```python
        selected_options = ui.checkbox_group("Checkbox Group", options=["Option 1", {"label": "Option 2", "value": "option2"}, {"label": "Option 3", "value": "option3", "disabled": True}], value=["Option 1"], on_change=lambda value: print(f"Checkbox group value changed to {value}"))
        ui.text(f"Selected options: {', '.join(selected_options) if selected_options else 'None'}")
        ```
        """
        return self._x_checkbox_group(
            "checkbox-group",
            key or self._new_widget_id("checkbox-group", label),
            label=label,
            options=options,
            value=value,
            on_change=on_change,
            format_func=format_func,
            flexDirection=flex_direction,
            **kwargs,
        )

    def rerun(self, scope: RerunType = "auto", clear_event: bool = True) -> None:
        """
        Reruns the current page. Use this to rerun the app or the fragment depending on the context.

        Args:
            scope (RerunType): The scope of the rerun. "auto" will rerun the app or the fragment depending on the context, "app" will rerun the entire app
            clear_event (bool): Whether to clear the event.

        Example:
        ```python
        counter = ui.session_state.get("counter", 0)
        ui.text(f"Counter is {counter}")
        should_increase = ui.button("Increment")
        if should_increase:
            ui.session_state["counter"] = counter + 1
            ui.rerun()
        ```
        """
        if self.should_rerun_event:
            self.should_rerun_event.set()
        if clear_event:
            self.request.clear_event()
        if scope == "app":
            self.request.clear_fragment_id()
        target = "app" if scope == "app" else self.initial_target
        # when running in stream mode, we need to schedule the rerun action to the event queue
        # so that the rerun action would be got with event queue loop can be cancelled
        if self._schedule_event(RerunAction(address=[-1], target=target)):
            return
        raise RerunException(self.session_state.get_data(), scope=scope)

    def get_head(self) -> Head:
        if self.head is None:
            self.head = Head()
        return self.head

    def set_page_config(self, page_title: Optional[str] = None, page_description: Optional[str] = None) -> None:
        """
        Sets the page title and description.

        Args:
            page_title (str | None): The title of the page.
            page_description (str | None): The description of the page.
        """
        self.head = Head(title=page_title, description=page_description)
        self._create_element(
            name="head",
            key="__head__",
            props={
                "title": page_title,
                "description": page_description,
            },
        )

    def __enter__(self) -> "RouteLitBuilder":
        # When using with builder.element():
        # Make parent builder redirect to this one
        if self.parent_builder:
            self._prev_active_child_builder = self.parent_builder.active_child_builder
            self.parent_builder.active_child_builder = self
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        # Reset parent's active child when exiting context
        if self.parent_builder:
            if self._prev_active_child_builder:
                self.parent_builder.active_child_builder = self._prev_active_child_builder
                self._prev_active_child_builder = None
            else:
                self.parent_builder.active_child_builder = None

    def __call__(self, *args: Any, **kwds: Any) -> "RouteLitBuilder":
        return self

    @property
    def parent_element(self) -> RouteLitElement:
        return self._parent_element

    def get_fragments(self) -> MutableMapping[str, List[int]]:
        return self.fragments

    def handle_view_task_done(self) -> None:
        self._schedule_event(
            ViewTaskDoneAction(
                address=[-1],
                target=self.initial_target,
            )
        )

    def on_end(self) -> None:
        self.session_state.pop("__ignore_submit", None)
        if self.should_rerun_event and self.should_rerun_event.is_set():
            return  # skip the last action when should_rerun is True
        self._schedule_event(
            LastAction(
                address=None,
                target=self.initial_target,
            )
        )

    @classmethod
    def get_client_resource_paths(cls) -> List[AssetTarget]:
        static_assets_targets = []
        for c in cls.__mro__:
            if hasattr(c, "static_assets_targets") and isinstance(c.static_assets_targets, list):
                static_assets_targets.extend(c.static_assets_targets)
        # Remove duplicates while preserving order (works with unhashable types like dictionaries)
        seen = []
        result = []
        for item in static_assets_targets:
            if item not in seen:
                seen.append(item)
                result.append(item)
        return result
