"""Control-flow exceptions for CLI command helpers."""


class CommandAbort(Exception):
    """Control-flow signal to abort a command with a given exit code.

    Raised by command helpers so their return type carries only the success value,
    not an int sentinel. Caught once at the dispatch() choke-point and converted
    to typer.Exit — not at each run() boundary.
    """

    def __init__(self, code: int = 1) -> None:
        super().__init__(f"Command aborted with exit code {code}")
        self.code = code
