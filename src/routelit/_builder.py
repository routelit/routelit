from typing import Any, Callable, Dict, List, MutableMapping, Optional, Tuple, Sequence

from .domain import RouteLitElement, RouteLitBuilder, AssetTarget


class _RouteLitBuilder(RouteLitBuilder):
    """
    This is a private class that is used to build the RouteLitBuilder for testing purposes.
    It is not intended to be used directly by the user.
    """
    static_assets_targets: Sequence[AssetTarget] = [
        {
            "package_name": "routelit_elements",
            "path": "static",
        }
    ]

    def text(self, text: str, *, key: Optional[str] = None, **kwargs):
        self.add_non_widget(
            RouteLitElement(
                name="text",
                key=key or self._new_text_id("text"),
                props={"text": text, **kwargs},
            )
        )

    def button(
        self,
        text: str,
        *,
        key: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> bool:
        button = self.create_element(
            name="button",
            key=key or self._new_widget_id("button", text),
            props={"text": text, **kwargs},
        )
        is_clicked, _ = self._get_event_value(button.key, "click")
        if is_clicked and on_click:
            on_click()
        return is_clicked

    def text_input(
        self,
        label: str,
        *,
        value: Optional[str] = None,
        placeholder: Optional[str] = None,
        key: Optional[str] = None,
        on_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> str:
        component_id = key or self._new_widget_id("text-input", label)
        new_value = self.session_state.get(component_id, value)
        has_changed, event_value = self._get_event_value(component_id, "change", "value")
        if has_changed:
            new_value = event_value
            self.session_state[component_id] = new_value
            if on_change:
                on_change(new_value)
        self.create_element(
            name="text-input",
            key=component_id,
            props={
                "label": label,
                "value": new_value,
                "placeholder": placeholder,
                **kwargs,
            },
        )
        return new_value or ""

    def checkbox(
        self,
        label: str,
        checked: bool = False,
        key: Optional[str] = None,
        on_change: Optional[Callable[[bool], None]] = None,
        **kwargs,
    ) -> bool:
        component_id = key or self._new_widget_id("checkbox", label)
        new_checked = self.session_state.get(component_id, checked)
        has_changed, event_checked = self._get_event_value(component_id, "change", "checked")
        if has_changed:
            new_checked = event_checked
            self.session_state[component_id] = new_checked
            if on_change:
                on_change(new_checked)
        self.create_element(
            name="checkbox",
            key=component_id,
            props={"label": label, "checked": new_checked, **kwargs},
        )
        return new_checked

    def expander(self, title: str, *, open: Optional[bool] = None, key: Optional[str] = None) -> "RouteLitComponentsBuilder":
        """
        Creates an expander component that can be used as both a context manager and a regular function call.
        ```python
        Usage:
            def build_index_view(builder: RouteLitBuilder):
                # Context manager style
                with builder.expander("Title"):
                    builder.text("Content")

                with builder.expander("Title", open=True) as exp0:
                    exp0.text("Content")

                # Function call style
                exp = builder.expander("Title")
                exp.text("Content")
        ```
        """
        new_key = key or self._new_widget_id("expander", title)
        new_element = self.create_element(
            name="expander",
            key=new_key,
            props={"title": title, "open": open},
        )

        builder = self.__class__(
            self.request,
            prefix=new_key,
            session_state=self.session_state,
            parent_element=new_element,
            parent_builder=self,
        )
        return builder
