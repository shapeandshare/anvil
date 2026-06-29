# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""SQLAlchemy ORM model definitions.

Most modules in this package define a single ORM model class
representing a persistent entity in the anvil application database.
The following modules contain multiple co-dependent model classes
grouped together to eliminate circular import cycles between
bidirectional ORM relationships:

- ``content_corpus`` — ContentCorpus, ContentVersion, ContentEntry
- ``corpus`` — Corpus, CorpusFile
"""
