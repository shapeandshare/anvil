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
from . import audit_event
from . import content_blob
from . import content_corpus
from . import content_entry
from . import content_import_job
from . import content_ingest_session
from . import content_lock
from . import content_source
from . import content_tag
from . import content_version
from . import content_version_run_ref
from . import corpus
from . import corpus_file
from . import curation_operation
from . import dataset
from . import import_source
from . import license_entry
from . import sample
from . import training_config
