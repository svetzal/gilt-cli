"""Control-flow exceptions for CLI command helpers."""


class CommandAbort(Exception):
    """Control-flow signal to abort a command with a given exit code.

    Raised by command helpers so their return type carries only the success value,
    not an int sentinel. Caught at each run() boundary and converted to the int
    exit-code contract.
    """

    def __init__(self, code: int = 1) -> None:
        super().__init__(f"Command aborted with exit code {code}")
        self.code = code
