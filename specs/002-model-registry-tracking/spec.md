# Feature Specification: Model Registry Tracking

**Feature Branch**: `002-model-registry-tracking`  
**Created**: 2026-06-11  
**Status**: Draft  
**Input**: User description: "as a user i want the models i train from experiments to be tracked in model registries, when we run inference we want to pull from the registries and not the experiments"

## User Scenarios & Testing

### User Story 1 — Register a Trained Model from an Experiment (Priority: P1)

As a user, after training a model via an experiment, I want to optionally register the resulting model in a model registry so that I can track versions, recall it later, and use it for inference.

**Why this priority**: This is the core value proposition — without the ability to register models, there is nothing to pull from later.

**Independent Test**: Can be fully tested by training a model through an experiment, then registering it, and confirming the registration appears in a list of registered models. Delivers the ability to name and version trained models.

**Acceptance Scenarios**:

1. **Given** I have completed a training experiment that produced a model, **When** I navigate to the experiments list page, **Then** I see a "Register Model" action for that experiment
2. **Given** I click "Register Model", **When** I provide a model name and optional description, **Then** the model is registered and I'm shown its registry entry
3. **Given** I register the same model name again from a different experiment, **When** the registration completes, **Then** a new version of that model is created automatically
4. **Given** I view the model registry, **When** I browse registered models, **Then** I can see all models with their versions, source experiments, and registration timestamps

---

### User Story 2 — Browse and Select a Registered Model for Inference (Priority: P1)

As a user, I want to browse registered models and select one for inference, rather than pulling from raw experiments, so that I always use a vetted, versioned model.

**Why this priority**: This is the second half of the core value — inference must use registered models, not raw experiment outputs.

**Independent Test**: Can be fully tested by registering a model, then going to the inference page and confirming the registered model appears as selectable (while raw experiment models do not). Delivers production-ready inference selection.

**Acceptance Scenarios**:

1. **Given** I have one or more registered models, **When** I navigate to the inference page, **Then** I see a list of registered models (not experiment checkpoints) to choose from
2. **Given** I select a registered model, **When** I configure sampling parameters and run inference, **Then** the model from the registry is used and text is generated
3. **Given** a model has multiple versions, **When** I select it for inference, **Then** I can choose which specific version to use

---

### User Story 3 — View Model Version History and Metadata (Priority: P2)

As a user, I want to view the full version history of a registered model, including which experiment produced each version and its training metrics, so that I can make informed decisions about which version to use.

**Why this priority**: Version lineage provides trust and reproducibility, but inference can work without it initially.

**Independent Test**: Can be fully tested by registering two versions of the same model, then viewing the version history page and confirming both versions are listed with their source experiment details.

**Acceptance Scenarios**:

1. **Given** a registered model with multiple versions, **When** I view its detail page, **Then** I see a chronological list of all versions
2. **Given** I view a specific version, **When** I inspect its metadata, **Then** I see the source experiment ID, training loss, hyperparameters, trained-on dataset name, and registration timestamp
3. **Given** I view a version's source experiment, **When** I click through to it, **Then** I see the full experiment detail page

---

### Edge Cases

- What happens when a user tries to register a model from a failed or incomplete experiment? Registration should be blocked — only successfully trained models can be registered.
- How does the system handle registering the same model name with an identical source experiment? A new version should still be created (duplicate detection is informational, not blocking).
- What happens when the underlying experiment or its artifacts are deleted after registration? Registered model versions should remain available (registry is independent storage).
- How does inference behave when no models are registered? The inference page should show a helpful message and link to the experiment/training page.
- What happens during inference if the selected model's artifact file is corrupted or missing? A clear error should be shown, and the user should be prompted to retry or select a different version.
- Can users delete models or versions? Yes — individual versions or entire models can be deleted with a confirmation dialog. Deleting a version removes it from the version history; deleting an entire model removes all its versions. If a model is currently selected for inference, the user is warned before deletion.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST be able to register a successfully trained model from an experiment with a name and optional description
- **FR-002**: The system MUST auto-increment version numbers as sequential integers (1, 2, 3...) when a model name is registered more than once
- **FR-003**: Users MUST be able to view a list of all registered models, sorted by most recently registered, and filter by model name via a search field
- **FR-004**: Users MUST be able to view all versions of a specific registered model
- **FR-005**: Users MUST be able to view metadata for each model version, including source experiment ID, training loss, hyperparameters, trained-on dataset name, and registration timestamp
- **FR-006**: The inference page MUST present registered models (not raw experiment checkpoints) as the selectable model source
- **FR-007**: Users MUST be able to select a specific version of a registered model for inference
- **FR-008**: The system MUST preserve registered model artifacts independently from experiment artifacts
- **FR-009**: The system MUST prevent registration of models from failed or incomplete experiments
- **FR-010**: The system MUST display a clear message on the inference page when no models are registered, with a link to training
- **FR-011**: Users MUST be able to delete individual model versions with a confirmation dialog
- **FR-012**: Users MUST be able to delete an entire registered model (all versions) with a confirmation dialog
- **FR-013**: The system MUST warn the user if the model or version they are deleting is currently selected for inference

### Key Entities

- **Registered Model**: A named model tracked in the registry. Has a name, description (optional), creation timestamp, and can have multiple versions.
- **Model Version**: A specific iteration of a registered model. Has a version number (sequential integer), source experiment ID, **its own copy of the model artifact** (independent from experiment storage), training metrics snapshot, and registration timestamp.
- **Experiment**: Existing entity representing a training run. A model version references its source experiment for lineage tracking but does not depend on experiment artifacts for inference.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can register a trained model from an experiment in under 3 clicks after training completes
- **SC-002**: Users can select a registered model and start inference in under 3 clicks
- **SC-003**: The system supports an unlimited number of registered models and versions without degradation
- **SC-004**: Model version history shows complete lineage (source experiment, training metrics) for every version
- **SC-005**: Inference pulls from the model registry exclusively — no experiment artifacts are presented as inference sources

## Clarifications

### Session 2026-06-11

- Q: Can users delete/unregister models or individual versions? → A: Allow deletion of individual model versions and entire models, with confirmation dialog
- Q: Should registering a model copy the artifact to independent registry storage or just reference the experiment artifact? → A: Copy the artifact to registry storage at registration time (registry is fully independent of experiments)
- Q: How should users organize/filter registered models? → A: Chronological list with name search
- Q: What version numbering format should be used? → A: Simple sequential integers (1, 2, 3...)
- Q: Should the trained-on dataset be tracked in model version metadata? → A: Yes, capture dataset name as part of model version metadata

## Assumptions

- Users will continue training models via experiments as before; the registry is an opt-in addition on top of existing flows
- A "model" in the registry maps to the saved model checkpoint/weights produced by a successful training run
- Multiple registrations of the same model name imply intentional version tracking (not accidental duplicates)
- The existing experiment artifact storage mechanism will be reused or extended for registry artifact storage
- Existing experiment detail and inference UI pages will be modified rather than rebuilt from scratch
- The model registry is local (not an external service like MLflow Model Registry) for v1
