# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Schema-compatibility check for restore operations (FR-023)."""

from .schema_compatibility import SchemaCompatibility


def check_schema_compatibility(
    manifest_schema_revision: str | None,
    manifest_deployment_version: str | None,
    current_schema_revision: str | None,
    current_deployment_version: str | None,
) -> tuple[SchemaCompatibility, str]:
    """Compare a backup manifest's schema/deployment against the running
    deployment and return the compatibility level with a human-readable
    detail string.

    Parameters
    ----------
    manifest_schema_revision : str or None
        Alembic head from the backup manifest.
    manifest_deployment_version : str or None
        ``anvil.__version__`` from the backup manifest.
    current_schema_revision : str or None
        Alembic head of the running deployment.
    current_deployment_version : str or None
        ``anvil.__version__`` of the running deployment.

    Returns
    -------
    tuple[SchemaCompatibility, str]
        ``(compatibility_level, detail_message)``.
    """
    # No manifest metadata available — conservative: warn.
    if not manifest_schema_revision:
        return (
            SchemaCompatibility.WARN,
            "Backup manifest does not contain schema revision information. "
            "Proceed with caution — verify compatibility manually.",
        )

    # No current schema available — can't verify.
    if not current_schema_revision:
        return (
            SchemaCompatibility.WARN,
            "Running deployment schema revision unknown. " "Proceed with caution.",
        )

    if manifest_schema_revision != current_schema_revision:
        return (
            SchemaCompatibility.BLOCKED,
            f"Backup schema revision ({manifest_schema_revision}) differs from "
            f"the running deployment ({current_schema_revision}). "
            f"Restore blocked — upgrade your deployment first.",
        )

    # Schema matches. Check deployment version drift.
    if manifest_deployment_version and current_deployment_version:
        if manifest_deployment_version != current_deployment_version:
            return (
                SchemaCompatibility.WARN,
                f"Schema revision matches, but deployment version differs "
                f"(backup: {manifest_deployment_version}, running: "
                f"{current_deployment_version}). Restore is allowed but "
                f"verify compatibility.",
            )

    return (
        SchemaCompatibility.OK,
        "Schema revision and deployment version match the running deployment.",
    )
