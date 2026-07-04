"""Tests for the RemotePollError exception class."""

from __future__ import annotations

from anvil.services.compute.remote_poll_error import RemotePollError


class TestRemotePollError:
    """RemotePollError construction and string representation."""

    def test_construct_with_message(self) -> None:
        """Constructing with a message should store it."""
        err = RemotePollError("polling timed out")
        assert str(err) == "polling timed out"

    def test_is_exception(self) -> None:
        """RemotePollError should be an Exception subclass."""
        err = RemotePollError("fail")
        assert isinstance(err, Exception)

    def test_repr_contains_message(self) -> None:
        """Repr should include the message."""
        err = RemotePollError("connection refused")
        assert "connection refused" in repr(err)

    def test_construct_with_no_args(self) -> None:
        """Constructing with no args should produce an empty message."""
        err = RemotePollError()
        assert str(err) == ""
