from collections.abc import MutableMapping
from typing import Any

from routelit.domain import RerunType


class RerunException(Exception):
    """
    Exception raised to rerun the view function.
    """

    def __init__(self, state: MutableMapping[str, Any], scope: RerunType):
        self._state = state
        self._scope = scope

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

    @property
    def scope(self) -> RerunType:
        return self._scope


class EmptyReturnException(Exception):
    """
    Exception raised to stop the execution of the view function.
    """

    pass


class StopException(Exception):
    """
    Exception raised to stop the execution of the view function.
    """

    pass
