import hashlib
from collections.abc import MutableMapping, Sequence
from typing import Any, Dict, List, Optional, Tuple

from routelit.domain import (
    AssetTarget,
    RerunType,
    RouteLitElement,
    RouteLitEvent,
    RouteLitRequest,
)
from routelit.exceptions import RerunException


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
        new_element = self.create_non_widget_element(
            name="link",
            key=key or self._new_text_id("link"),
            props={
                "href": href,
                "replace": replace,
                "is_external": is_external,
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
        link_element = self.link(
            href,
            replace=replace,
            is_external=is_external,
            key=key,
            className=f"no-link-decoration {className or ''}",
            **kwargs,
        )
        return self._build_nested_builder(link_element)

    def rerun(self, scope: RerunType = "auto", clear_event: bool = True):
        self.elements.clear()
        if clear_event:
            self.request.clear_event()
        if scope == "app":
            self.request.clear_fragment_id()
        raise RerunException(self.session_state, scope=scope)

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
