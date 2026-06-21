# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""File storage abstraction.

``anvil.storage`` defines an abstract ``FileStore`` interface and
provides a ``LocalFileStore`` implementation backed by the local
filesystem. Designed to be extensible to S3-compatible or other
remote backends.
"""
