"""Source kind enumeration for content origins."""

from enum import StrEnum


class SourceKind(StrEnum):
    """Categorisation of a content source.

    Attributes
    ----------
    INJECTOR : str
        Automated system that pushes content (``"injector"``).
    IMPORTER : str
        Import job that pulls content from an external source
        (``"importer"``).
    MANUAL : str
        Human-curated upload or manual entry (``"manual"``).
    """

    INJECTOR = "injector"
    IMPORTER = "importer"
    MANUAL = "manual"
