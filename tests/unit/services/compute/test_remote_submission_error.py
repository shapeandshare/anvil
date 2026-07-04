"""Tests for the RemoteSubmissionError exception class."""

from __future__ import annotations

from anvil.services.compute.remote_submission_error import RemoteSubmissionError


class TestRemoteSubmissionError:
    """RemoteSubmissionError construction and string representation."""

    def test_construct_with_message(self) -> None:
        """Constructing with a message should store it."""
        err = RemoteSubmissionError("authentication failed")
        assert str(err) == "authentication failed"

    def test_is_exception(self) -> None:
        """RemoteSubmissionError should be an Exception subclass."""
        err = RemoteSubmissionError("fail")
        assert isinstance(err, Exception)

    def test_repr_contains_message(self) -> None:
        """Repr should include the message."""
        err = RemoteSubmissionError("quota exceeded")
        assert "quota exceeded" in repr(err)

    def test_construct_with_no_args(self) -> None:
        """Constructing with no args should produce an empty message."""
        err = RemoteSubmissionError()
        assert str(err) == ""
