"""TUI backend package — protocol, SDK backend, REST backend, and factory."""

from hippo.tui.backend.protocol import TUIBackend
from hippo.tui.backend.sdk import SDKBackend
from hippo.tui.backend.rest import RESTBackend


def create_backend(mode: str, **kwargs) -> TUIBackend:
    """Create a TUIBackend implementation for the given mode.

    Args:
        mode: Backend mode — ``"sdk"`` or ``"rest"``.
        **kwargs: Forwarded to the backend constructor.

    Returns:
        A ``TUIBackend`` instance.

    Raises:
        ValueError: If *mode* is not ``"sdk"`` or ``"rest"``.
    """
    if mode == "sdk":
        return SDKBackend(**kwargs)
    elif mode == "rest":
        return RESTBackend(**kwargs)
    else:
        raise ValueError(
            f"Unknown backend mode: {mode!r}. Valid modes are 'sdk' and 'rest'."
        )


__all__ = ["TUIBackend", "SDKBackend", "RESTBackend", "create_backend"]
