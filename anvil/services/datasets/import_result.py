"""Import result data class — outcome of a dataset import operation.

Provides the ``ImportResult`` class used by ``DatasetImportService``
to report the outcome of committing samples to a dataset.
"""


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
        errors: list[dict],
        preview: list[dict],
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
