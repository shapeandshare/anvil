# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Import result data class — outcome of a dataset import operation.

Provides the ``ImportResult`` class used by ``DatasetImportService``
to report the outcome of committing samples to a dataset.
"""

from typing import Any


class ImportResult:
    """Outcome of a dataset import operation.

    Attributes
    ----------
    import_source_id : int
        Database ID of the import source record.
    rows_imported : int
        Number of sample rows successfully imported.
    errors : list[dict]
        Error descriptions encountered during parsing.
    preview : list[dict]
        Preview of the first imported samples.
    """

    def __init__(
        self,
        import_source_id: int,
        rows_imported: int,
        errors: list[dict[str, Any]],
        preview: list[dict[str, Any]],
    ):
        """Initialise the import result.

        Parameters
        ----------
        import_source_id : int
            Database ID of the import source record.
        rows_imported : int
            Number of sample rows imported.
        errors : list[dict]
            Error descriptions.
        preview : list[dict]
            Preview of the first imported samples.
        """
        self.import_source_id = import_source_id
        self.rows_imported = rows_imported
        self.errors = errors
        self.preview = preview
