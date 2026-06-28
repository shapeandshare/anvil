# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Typed exception hierarchy for the anvil client SDK.

Root exception ``ApiError``; subclasses for each HTTP status category
and transport-level failures. All exceptions carry ``status_code: int | None``
and ``message: str``.
"""
