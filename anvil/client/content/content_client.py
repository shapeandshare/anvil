# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Content client — domain aggregator for versioned content operations.

``ContentClient`` provides a single entry point for all versioned content
operations: content corpora, sessions, version tagging, session validation,
and SSE composition streaming. It delegates each operation to its
corresponding command class.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .._shared.transport import Transport
from .._shared.stream_event import StreamEvent
from .content_corpus_create_command import ContentCorpusCreateCommand
from .content_corpus_list_command import ContentCorpusListCommand
from .content_session_create_command import ContentSessionCreateCommand
from .content_session_validate_command import ContentSessionValidateCommand
from .content_stream_composition_command import ContentStreamCompositionCommand
from .content_version_tag_command import ContentVersionTagCommand


class ContentClient:
    """Versioned content repository operations.

    Aggregates all content commands behind a single facade. Each public method
    maps to one server API operation.

    Parameters
    ----------
    transport : Transport
        The shared SDK transport instance.
    """

    def __init__(self, transport: Transport) -> None:
        self._corpus_create_cmd = ContentCorpusCreateCommand(transport)
        self._corpus_list_cmd = ContentCorpusListCommand(transport)
        self._session_create_cmd = ContentSessionCreateCommand(transport)
        self._version_tag_cmd = ContentVersionTagCommand(transport)
        self._session_validate_cmd = ContentSessionValidateCommand(transport)
        self._stream_composition_cmd = ContentStreamCompositionCommand(transport)

    async def create_corpus(
        self, name: str, description: str | None = None,
    ) -> dict[str, object]:
        """Create a new versioned content corpus.

        Parameters
        ----------
        name : str
            The corpus name.
        description : str | None, optional
            An optional description.

        Returns
        -------
        dict[str, object]
            The newly created content corpus record.
        """
        return await self._corpus_create_cmd.execute(name, description=description)

    async def list_corpora(self) -> list[dict[str, object]]:
        """List all versioned content corpora.

        Returns
        -------
        list[dict[str, object]]
            A list of content corpus records.
        """
        return await self._corpus_list_cmd.execute()

    async def create_session(
        self, corpus_id: int, name: str | None = None,
    ) -> dict[str, object]:
        """Create a new content session.

        Parameters
        ----------
        corpus_id : int
            The content corpus primary key.
        name : str | None, optional
            An optional session name.

        Returns
        -------
        dict[str, object]
            The newly created session record.
        """
        return await self._session_create_cmd.execute(corpus_id, name=name)

    async def tag_version(self, version_id: int, tag: str) -> dict[str, object]:
        """Apply a tag to a content version.

        Parameters
        ----------
        version_id : int
            The version primary key.
        tag : str
            The tag label to apply.

        Returns
        -------
        dict[str, object]
            The updated version record.
        """
        return await self._version_tag_cmd.execute(version_id, tag)

    async def validate_session(self, session_id: int) -> dict[str, object]:
        """Trigger validation of a content session.

        Parameters
        ----------
        session_id : int
            The session primary key to validate.

        Returns
        -------
        dict[str, object]
            The validation result.
        """
        return await self._session_validate_cmd.execute(session_id)

    async def stream_composition(self) -> AsyncIterator[StreamEvent]:
        """Stream SSE composition events.

        Yields
        ------
        StreamEvent
            Typed SSE events from the server (progress, heartbeat,
            completion).
        """
        return await self._stream_composition_cmd.execute()
