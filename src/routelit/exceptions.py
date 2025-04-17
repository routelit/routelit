from typing import Any, MutableMapping


class RerunException(Exception):
    """
    Exception raised to rerun the view function.
    """

    def __init__(self, state: MutableMapping[str, Any]):
        self._state = state

    @property
    def state(self) -> MutableMapping[str, Any]:
        return self._state

class StopExecutionException(Exception):
    """
    Exception raised to stop the execution of the view function.
    """
    pass
