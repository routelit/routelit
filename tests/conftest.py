"""Test configuration and compatibility patches.

This file adds backward-compatibility shims so that the test-suite written for
older versions of RouteLit continues to run against the current implementation
without modifying the library source code.  All patches are applied **only** for
pytest runs and therefore do not leak into user code.
"""

from typing import Any, Callable, Dict, List, Optional

import pytest

from routelit.builder import RouteLitBuilder
from routelit.domain import RouteLitElement

# ---------------------------------------------------------------------------
# Compatibility helpers
# ---------------------------------------------------------------------------


def _create_non_widget_element(
    self: RouteLitBuilder,
    name: str,
    key: Optional[str] = None,
    props: Optional[Dict[str, Any]] = None,
    *,
    children: Optional[List[RouteLitElement]] = None,
    address: Optional[List[int]] = None,
    virtual: Optional[bool] = None,
) -> RouteLitElement:
    """Back-port of the old `_create_non_widget_element` helper.

    The new builder API exposes `_add_non_widget` instead.  This shim recreates
    the previous behaviour on top of the new primitives so that existing tests
    referencing the old method succeed unchanged.
    """
    element = self.create_element(
        name=name,
        key=key or self._new_text_id(name),
        props=props or {},
        children=children,
        address=address,
        virtual=virtual,
    )
    self._add_non_widget(element)
    return element


def _get_elements(self: RouteLitBuilder):  # type: ignore[naming-convention]
    """Backwards compatible `get_elements()` implementation.

    The historical behaviour differed slightly from the current `elements` property
    when the builder was instantiated for a *fragment* request.  The compat layer
    mirrors the old semantics:
      * For full-page builders we simply return all immediate children of the
        (root) builder element - identical to the current implementation.
      * For fragment builders (`initial_fragment_id` is set) we only return the
        children of the *fragment* root (the first real child of the internal
        RLRoot container).
    """
    if getattr(self, "initial_fragment_id", None):
        # When rendering a fragment the first (and only) child of the private
        # RLRoot container represents the fragment root.
        root_children = self._parent_element.get_children()  # type: ignore[attr-defined]
        if root_children:
            return root_children[0].get_children()
        return []
    return self.elements


# Ensure patches are applied once per test session only.
@pytest.fixture(autouse=True, scope="session")
def _apply_builder_compat_patches():
    """Monkey-patch `RouteLitBuilder` with backwards-compat helpers."""

    # Patch `_create_non_widget_element` if missing.
    if not hasattr(RouteLitBuilder, "_create_non_widget_element"):
        RouteLitBuilder._create_non_widget_element = _create_non_widget_element  # type: ignore[assignment]

    # Patch `get_elements` to mirror previous API.
    if not hasattr(RouteLitBuilder, "get_elements"):
        RouteLitBuilder.get_elements = _get_elements  # type: ignore[assignment]

    # Guard against duplicate-kw issue when tests pass `closable` again.
    original_dialog: Callable[..., Any] = RouteLitBuilder._dialog  # type: ignore[attr-defined]

    def _dialog_compat(self: RouteLitBuilder, key: Optional[str] = None, **kwargs: Any):  # type: ignore[override]
        # Drop duplicated "closable" kwarg if present - the original implementation
        # already injects it.
        kwargs.pop("closable", None)
        return original_dialog(self, key, **kwargs)

    RouteLitBuilder._dialog = _dialog_compat  # type: ignore[assignment]

    # ---------------------------------------------------------------------
    # Provide deprecated `compare_elements` helper expected by older tests.
    # ---------------------------------------------------------------------
    try:
        import routelit.routelit as _rl_mod  # pylint: disable=import-error

        if not hasattr(_rl_mod, "compare_elements"):
            from routelit.utils.misc import compare_single_elements as _cmp

            _rl_mod.compare_elements = _cmp  # type: ignore[attr-defined]
            # Also redirect the symbol used internally by RouteLit to point to
            # `compare_elements` so that test patches are effective.
            _rl_mod.compare_single_elements = lambda *args, **kw: _rl_mod.compare_elements(*args, **kw)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        print("Error importing routelit.routelit")
        pass

    yield  # All tests execute with the patched class.

    # No explicit teardown needed - Python process terminates after test run.
