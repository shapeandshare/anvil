# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Backup, restore, verification, and auto-rotation.

Domain sub-package for full-deployment backup and restore — archive
creation and reading, consistent SQLite snapshots, atomic restore
with crash-safe journal recovery, integrity verification, storage-quota
auto-rotation, and the anvil-backup CLI entry point.
"""
