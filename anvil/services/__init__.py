# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Business logic and orchestration layer.

``anvil.services`` contains all application business logic — training
coordination, MLflow experiment tracking, dataset import and curation,
model export, corpus management, inference, and compute backend
abstraction. Services consume repositories and expose their
functionality through the ``AnvilWorkbench`` god class.
"""
