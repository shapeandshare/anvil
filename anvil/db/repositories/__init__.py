# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Repository pattern data-access classes.

Each module defines a single repository class that encapsulates all
database queries for its corresponding entity. No SQL or ORM primitives
leak into the service layer.
"""
