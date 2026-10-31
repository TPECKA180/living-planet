class IsolationError(RuntimeError):
    """Never send a request across an unverified private-state boundary."""
