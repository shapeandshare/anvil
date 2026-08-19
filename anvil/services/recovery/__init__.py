# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Resilient startup recovery — database health classification, snapshot,
quarantine, and maintenance-mode recovery surface.

Domain sub-package for pit-of-success database recovery on startup failure.
Provides the ``RecoveryService`` orchestrator, ``DbSnapshot`` for atomic
DB-trio archiving, and ``Quarantine`` for preserving suspect databases before
operator-directed recovery actions. Composes with the existing ``BackupService``
(027) and ``MigrationService`` (011) without introducing new runtime
dependencies.
"""
