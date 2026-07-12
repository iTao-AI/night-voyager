class AuthenticationFailedError(Exception):
    """An expected session credential mismatch safe to normalize at the HTTP boundary."""


class StaleSessionError(AuthenticationFailedError):
    """An absent, expired, or revoked session whose client cookie may be cleared."""
