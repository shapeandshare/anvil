"""Business logic and orchestration layer.

``anvil.services`` contains all application business logic — training
coordination, MLflow experiment tracking, dataset import and curation,
model export, corpus management, inference, and compute backend
abstraction. Services consume repositories and expose their
functionality through the ``AnvilWorkbench`` god class.
"""
