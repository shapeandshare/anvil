# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Cross-domain SDK infrastructure.

Shared types, transport, configuration, error hierarchy, and base classes
used by every domain sub-package in the client SDK. Not a domain itself —
internal infrastructure (Article X §10.3).

Sub-packages
------------
errors
    Typed exception hierarchy: ``AuthenticationError``, ``NotFoundError``,
    ``ValidationError``, ``RateLimitError``, ``ServerError``,
    ``ConnectionError``.
"""