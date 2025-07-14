import asyncio
from typing import Any, Iterator, MutableMapping, Optional

from routelit.exceptions import StopException


class PropertyDict:
    """
    A dictionary that can be accessed as attributes.
    Example:
    ```python
    session_state = PropertyDict({"name": "John"})
    print(session_state.name)  # "John"
    print(session_state["name"])  # "John"
    session_state.name = "Jane"
    print(session_state.name)  # "Jane"
    print(session_state["name"])  # "Jane"
    del session_state.name
    print(session_state.name)  # None
    print(session_state["name"])  # None
    ```
    """

    def __init__(
        self, initial_dict: Optional[MutableMapping[str, Any]] = None, cancel_event: Optional[asyncio.Event] = None
    ):
        # Initialize private attributes directly to avoid __setattr__ recursion
        super().__setattr__("_data", initial_dict if initial_dict is not None else {})
        super().__setattr__("_cancel_event", cancel_event)

    def _maybe_check_cancel(self) -> None:
        if self._cancel_event and self._cancel_event.is_set():
            raise StopException("PropertyDict cancelled")

    def __getattr__(self, name: str) -> Any:
        self._maybe_check_cancel()
        try:
            return self._data[name]
        except KeyError:
            return None

    def __setattr__(self, name: str, value: Any) -> None:
        self._maybe_check_cancel()
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def __repr__(self) -> str:
        return f"PropertyDict({self._data!r})"

    def __str__(self) -> str:
        return str(self._data)

    def __getitem__(self, key: str) -> Any:
        self._maybe_check_cancel()
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._maybe_check_cancel()
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def pop(self, key: str, *args: Any) -> Any:
        self._maybe_check_cancel()
        return self._data.pop(key, *args)

    def get(self, key: str, default: Any = None) -> Any:
        self._maybe_check_cancel()
        return self._data.get(key, default)

    def get_data(self) -> MutableMapping[str, Any]:
        return self._data  # type: ignore[no-any-return]

    def update(self, other: MutableMapping[str, Any]) -> None:
        """Update the dictionary with key/value pairs from other."""
        self._maybe_check_cancel()
        self._data.update(other)

    def keys(self) -> Iterator[str]:
        """Return an iterator over the dictionary's keys."""
        return self._data.keys()  # type: ignore[no-any-return]

    def values(self) -> Iterator[Any]:
        """Return an iterator over the dictionary's values."""
        return self._data.values()  # type: ignore[no-any-return]

    def items(self) -> Iterator[tuple[str, Any]]:
        """Return an iterator over the dictionary's (key, value) pairs."""
        return self._data.items()  # type: ignore[no-any-return]
