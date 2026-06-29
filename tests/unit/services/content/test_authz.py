# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Unit tests for content authorization — AuthzContext and FastAPI
dependency.

In local single-user mode all management actions are permitted, so
the tests verify that ``require_management_action`` does not raise
and that ``require_content_auth`` returns an ``AuthzContext`` instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from anvil.services.content.authz import AuthzContext, require_content_auth


class TestAuthzContext:
    """AuthzContext construction and management-action guard."""

    def test_construct(self) -> None:
        """AuthzContext can be created with a workbench."""
        wb = MagicMock()
        ctx = AuthzContext(wb)
        assert ctx._workbench is wb

    def test_require_management_action_allows_all(self) -> None:
        """In local mode any action name is permitted (no raise)."""
        ctx = AuthzContext(MagicMock())

        # These are the actions named in the docstring + a generic one
        for action in ("rename", "tag", "compose", "promote", "lock", "anything"):
            ctx.require_management_action(action)  # must not raise


@pytest.mark.asyncio
async def test_require_content_auth_dependency() -> None:
    """require_content_auth returns an AuthzContext when provided a
    workbench.
    """
    wb = MagicMock()
    ctx = await require_content_auth(workbench=wb)
    assert isinstance(ctx, AuthzContext)
    assert ctx._workbench is wb
