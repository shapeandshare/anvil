# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SQLAlchemy ORM model definitions.

Each module in this package defines a single ORM model class
representing a persistent entity in the anvil application database.
"""

# Import ALL model modules to register their tables with
# ``Base.metadata``. Without these imports, SQLAlchemy cannot resolve
# foreign-key references (e.g. ``Sample.import_source_id → import_sources.id``)
# or create tables via ``metadata.create_all()`` at test startup.
from . import (
    audit_event,
    backup_operation,
    content_blob,
    content_corpus,
    content_entry,
    content_import_job,
    content_ingest_session,
    content_lock,
    content_source,
    content_tag,
    content_version,
    content_version_run_ref,
    corpus,
    corpus_file,
    curation_operation,
    dataset,
    import_source,
    instance_record,
    license_entry,
    runtime_config,
    sample,
    training_config,
)
