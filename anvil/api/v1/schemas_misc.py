# Copyright © 2026 Josh Burt
# one-class:allow — intentional domain grouping of miscellaneous schemas
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Miscellaneous request/response models for various API endpoints.

Pure Pydantic ``BaseModel`` subclasses for model registry, inference,
dataset import, content source, and runtime config endpoints that do
not warrant their own dedicated schema module.
"""

from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field


class RegisterModelBody(BaseModel):
    """Request body for registering a trained model from an experiment.

    Parameters
    ----------
    experiment_id : int
        The experiment ID to register the model from.
    """

    model_config = ConfigDict(extra="forbid")

    experiment_id: int


class InferenceSampleBody(BaseModel):
    """Request body for generating text samples from a registered model.

    Parameters
    ----------
    model_id : int
        Identifier of the model.
    version : int
        Version of the model.
    temperature : float, optional
        Sampling temperature. Defaults to ``0.5``.
    num_samples : int, optional
        Number of samples to generate. Defaults to ``10``.
    prompt : str, optional
        Optional prompt text. Defaults to ``""``.
    top_k : int | None, optional
        Top-K sampling parameter. Defaults to ``None``.
    top_p : float | None, optional
        Top-P (nucleus) sampling parameter. Defaults to ``None``.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: int
    version: int
    temperature: float = 0.5
    num_samples: int = 10
    prompt: str = ""
    top_k: int | None = None
    top_p: float | None = None


class ImportFromCorpusBody(BaseModel):
    """Request body for importing documents from a corpus into a dataset.

    Parameters
    ----------
    corpus_id : int
        The source corpus ID.
    """

    model_config = ConfigDict(extra="forbid")

    corpus_id: int


class CreateSourceBody(BaseModel):
    """Request body for creating a new content source.

    Parameters
    ----------
    slug : str
        Unique machine-readable identifier. Must be 1-255 characters.
    name : str
        Human-readable name. Must be 1-255 characters.
    kind : str, optional
        Source kind (e.g. ``"manual"``). Defaults to ``"manual"``.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    kind: str = "manual"


class ConfigSettingOut(BaseModel):
    """Runtime config setting as returned by the API.

    Parameters
    ----------
    key : str
        The setting name (e.g. ``device``, ``mlflow_uri``).
    value : str
        The current effective value (stringified).
    source : str
        Provenance -- ``override``, ``env``, or ``default``.
    apply_class : str
        How changes take effect (``boot_critical``, ``mlflow_restart``,
        ``applies_live``).
    pending_restart : bool
        ``True`` when a boot-critical override has been saved but not
        yet applied.
    editable : bool
        ``True`` when the setting can be overridden via the UI.
    display_name : str
        Human-readable label for the UI.
    description : str
        Brief description of what this setting controls.
    env_var : str
        The environment variable name (e.g. ``ANVIL_DEVICE``).
    default_value : str
        The code-level default when no env or override is set.
    """

    key: str
    value: str
    source: str
    apply_class: str
    pending_restart: bool = False
    editable: bool = True
    display_name: str = ""
    description: str = ""
    env_var: str = ""
    default_value: str = ""


class UpdateConfigBody(BaseModel):
    """Request body for updating a runtime config setting.

    Parameters
    ----------
    value : str
        The new value to persist as an override.
    """

    model_config = ConfigDict(extra="forbid")

    value: str
