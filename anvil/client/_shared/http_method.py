# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""HTTP method enumeration for the anvil client SDK.

``HttpMethod`` enumerates the HTTP verbs the SDK uses when communicating
with the anvil REST API.
"""

from enum import StrEnum


class HttpMethod(StrEnum):
    """HTTP verb for an API request.

    Attributes
    ----------
    GET : str
        Retrieve a resource (``"get"``).
    POST : str
        Create a resource or trigger an action (``"post"``).
    PUT : str
        Full replacement of a resource (``"put"``).
    DELETE : str
        Remove a resource (``"delete"``).
    PATCH : str
        Partial update of a resource (``"patch"``).
    """

    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"