# Feature Specification: Learning Content Enrichment

**Feature Branch**: `007-learning-content-enrichment`
**Created**: 2026-06-13
**Status**: Draft
**Input**: Learning Content Enrichment Plan covering autograd/backprop visualization, cross-entropy loss explanation, Adam optimizer internals, model parameter anatomy, residual connections, RMSNorm, progressive code stubs (train1/train3/train4), FAQ section, and production scaling context

## User Scenarios & Testing

### User Story 1 - Interactive Backpropagation Lesson (Priority: P1)

As a learner, I want to see how gradients flow backwards through the computation graph so that I can understand how the model learns from its mistakes.

**Why this priority**: Backpropagation is the single most misunderstood concept in neural network training. Karpathy devotes ~40% of his blog post to it, but our platform has zero content on it. This is the biggest educational gap.

**Independent Test**: A user can navigate to `/v1/learn/autograd`, scroll through 5 narrative steps, and see a real computation graph rendering where each node displays its data value, its gradient after backward pass, and the local gradient contributed to each child node. No training run required — uses the existing demo model.

**Acceptance Scenarios**:

1. **Given** the learning arc, **When** a user navigates to the autograd lesson, **Then** they see a scroll-driven narrative with 5 steps explaining the Value class, forward computation graph construction, topological sort, chain rule backpropagation, and gradient accumulation
2. **Given** the autograd lesson, **When** a user scrolls to a step, **Then** a real computation graph is rendered in the pinned visual panel with nodes showing `.data` values and edges annotated with local gradients
3. **Given** a user is viewing a computation graph, **When** the graph includes a branching node (used in multiple paths), **Then** the gradient display shows accumulation from both paths (sum of contributions)
4. **Given** the autograd lesson, **When** a user completes all 5 steps, **Then** they see a "next lesson" link to the existing tokenization or embeddings lesson

---

### User Story 2 - Progressive Code Walkthrough Completion (Priority: P1)

As a learner following the 6-stage curriculum, I want each training script (train0 through train5) to be a working, incremental build-up so that I can understand how a bigram counter evolves into a full GPT.

**Why this priority**: The project Constitution (Article II) mandates this progression. Currently train1, train3, and train4 are empty stubs — a direct compliance gap that undermines the educational arc.

**Independent Test**: A user can run `python examples/train1.py` and see a working MLP with manually computed gradients. They can then run train3, train4 sequentially and see each add one architectural component. Each script is independently runnable with no changes.

**Acceptance Scenarios**:

1. **Given** the examples directory, **When** a user runs `python examples/train1.py`, **Then** it trains a simple 2-layer MLP using manually computed numerical and analytic gradients with SGD, printing loss values
2. **Given** the examples directory, **When** a user runs `python examples/train3.py`, **Then** it trains a single-head causal self-attention model with position embeddings, RMSNorm, and residual connections, printing loss values
3. **Given** the examples directory, **When** a user runs `python examples/train4.py`, **Then** it trains a multi-head (n_head=4) GPT with a single transformer layer, printing loss values
4. **Given** all training scripts exist, **When** a user reads train0.py through train5.py sequentially, **Then** each file adds exactly one new concept (bigram → MLP + manual gradients → autograd → attention → multi-head → Adam) without removing or hiding earlier concepts

---

### User Story 3 - Cross-Entropy Loss Deep-Dive (Priority: P1)

As a learner watching the loss curve decrease during training, I want to understand what the loss number actually means so that I can interpret training progress and diagnose problems.

**Why this priority**: The loss curve is the primary feedback signal during training, but the platform currently shows it as just a number dropping. Learners have no intuition for why ~3.3 is the starting point, what "good" looks like, or how to read curve shapes.

**Independent Test**: A user navigates to `/v1/learn/loss`, types text into a widget, and sees per-token negative log probabilities with an explanation of why random guessing gives `-log(1/27) ≈ 3.3`.

**Acceptance Scenarios**:

1. **Given** the loss lesson, **When** a user types text into the input widget, **Then** they see each token's individual cross-entropy loss and the running average
2. **Given** the loss lesson, **When** a user views the widget, **Then** they see a "random guess baseline" indicator at `-log(1/vocab_size)` with the vocabulary size displayed
3. **Given** the loss lesson, **When** a user scrolls through the steps, **Then** they learn: what cross-entropy measures, how softmax converts logits to probabilities, why -log(prob) is the loss, and how loss curve shapes indicate training quality
4. **Given** a trained model exists, **When** a user types the model's training data text, **Then** the per-token loss is lower (better prediction) than for unseen text

---

### User Story 4 - Model Parameter Anatomy (Priority: P2)

As a learner, I want to see a visual breakdown of where all 4,192 parameters live in the model so that I can understand the relationship between architecture choices and model capacity.

**Why this priority**: The model's 4,192 parameters are abstract until visualized. Showing token embeddings vs. position embeddings vs. attention weights vs. MLP weights vs. output projection helps learners connect hyperparameters to actual model structure.

**Independent Test**: A user navigates to `/v1/learn/parameters` and sees an interactive breakdown showing each matrix group with its shape, parameter count, and percentage of total. Uses the existing demo model.

**Acceptance Scenarios**:

1. **Given** the parameters lesson, **When** a user views the page, **Then** they see a visual breakdown of all named matrices: wte, wpe, per-layer attention weights (Wq/Wk/Wv/Wo), per-layer MLP weights (fc1/fc2), and lm_head
2. **Given** the parameter breakdown, **When** a user views any matrix group, **Then** they see its shape dimensions, total parameter count, and percentage of total model parameters
3. **Given** the parameter breakdown, **When** a user changes the `n_embd` or `n_layer` slider, **Then** the breakdown updates in real-time to show how architecture choices affect parameter count

---

### User Story 5 - Adam Optimizer Interactive Lesson (Priority: P2)

As a learner, I want to see how momentum and adaptive learning rates work inside the Adam optimizer so that I can understand why it converges faster than plain gradient descent.

**Why this priority**: The Adam optimizer is the workhorse of modern deep learning but is often treated as a black box. Showing momentum (m), adaptive LR (v), bias correction, and LR decay helps learners build intuition for optimization dynamics.

**Independent Test**: A user navigates to the Adam lesson and sees a visualization of the optimizer state (m, v, parameter updates) across training steps. Works with real training data or a pre-recorded trajectory.

**Acceptance Scenarios**:

1. **Given** an existing training run with logged optimizer state, **When** a user views the Adam lesson, **Then** they see per-parameter momentum (m) and adaptive learning rate (v) evolving over training steps
2. **Given** the Adam lesson, **When** a user adjusts the beta1 (momentum decay) slider, **Then** they see how the momentum response changes
3. **Given** the Adam lesson, **When** a user adjusts the beta2 (adaptive LR decay) slider, **Then** they see how the adaptive learning rate response changes
4. **Given** the Adam lesson, **When** a user views the optimizer visualization, **Then** they see the linear learning rate decay `lr_t = lr * (1 - step/num_steps)` annotated

---

### User Story 6 - FAQ & Reference Section (Priority: P2)

As a learner exploring the platform, I want answers to common questions — like "Does the model understand anything?", "Why does it hallucinate?", "How is this related to ChatGPT?" — so that I can connect the toy model to real-world LLMs.

**Why this priority**: These questions naturally arise for any learner. Providing answers inline reduces confusion and makes the platform self-contained.

**Independent Test**: A user navigates to `/v1/learn/faq` and sees answers to 5-8 common questions. No model, training run, or API needed.

**Acceptance Scenarios**:

1. **Given** a user navigates to the FAQ page, **When** the page loads, **Then** they see questions addressing: model understanding, hallucinations, relation to ChatGPT, training speed, dataset customization, and production scaling differences
2. **Given** the FAQ page, **When** a user clicks a question, **Then** the answer expands inline (accordion-style or single-page)

---

### User Story 7 - Residual Connections & RMSNorm Explanation (Priority: P2)

As a learner studying the transformer architecture, I want clear explanations of how residual connections stabilize training and how RMSNorm normalizes activations so that I can understand the "plumbing" that makes deep networks trainable.

**Why this priority**: These components are essential to making the transformer work but are currently only present in code without explanation. The graph explorer mentions "LayerNorm" but doesn't explain what normalization does or why residuals matter.

**Independent Test**: A user navigates to the enhanced attention lesson or a dedicated residual/norm step and sees visualizations of the residual stream (x + x_residual) and RMSNorm scaling.

**Acceptance Scenarios**:

1. **Given** the enhanced attention lesson, **When** a user reaches the residual connection step, **Then** they see a visualization showing the residual stream: input flowing through attention/MLP and being added back
2. **Given** the RMSNorm step, **When** a user views the visualization, **Then** they see input vector values, computed RMS, scale factor, and normalized output
3. **Given** both explanations exist, **When** a user reads through them, **Then** they understand why pre-norm + residual enables stable gradient flow through many layers

---

### Edge Cases

- What happens when no trained model exists and a lesson widget needs real model data? (Must fall back to the demo model provisioned by DemoModelProvider)
- What happens when a user enters text with characters outside the model's vocabulary in a lesson widget? (Must show a clear error message and highlight the invalid character)
- What happens when the computation graph for autograd visualization exceeds browser rendering capacity? (Must cap node count at a reasonable limit, e.g., 400 nodes)
- What happens when training loss data is empty or corrupted for the training-loop lesson? (Must show a helpful prompt to run a training experiment first)
- How does the progressive walkthrough handle different Python versions? (Must be stdlib-only like the core engine — no external dependencies)
- What happens when the Adam optimizer lesson has no logged optimizer state? (Must use a pre-computed synthetic trajectory or explain that real data requires a training run)

## Requirements

### Functional Requirements

- **FR-001**: The autograd lesson MUST provide a scroll-driven narrative with at least 5 steps covering: Value class and computation graph construction, forward pass through a simple expression, topological sort for backward pass, chain rule backpropagation, and gradient accumulation at branching nodes
- **FR-002**: The autograd lesson MUST render a real computation graph from the demo model showing each Value node's `.data` value and `.grad` after backward pass
- **FR-003**: The autograd lesson MUST annotate edges in the computation graph with local gradient values from the operation that produced them
- **FR-004**: The autograd lesson MUST visually indicate when a node's gradient is the sum of multiple paths (branching in the computation graph)
- **FR-005**: train1.py MUST implement a complete 2-layer MLP (input → hidden → output) with manually computed numerical gradients and analytic gradients verified against each other, trained with SGD
- **FR-006**: train3.py MUST implement a single-head causal self-attention model with learned position embeddings, RMSNorm, residual connections, and a single transformer block, trained with SGD
- **FR-007**: train4.py MUST implement a multi-head (n_head divisible into n_embd) GPT with learned embeddings, RMSNorm, multi-head attention, residual MLP, and a single transformer layer, trained with SGD
- **FR-008**: Each progressive script (train0-5) MUST be independently runnable with `python examples/trainN.py` using only Python stdlib (no pip dependencies)
- **FR-009**: The loss lesson MUST display per-token cross-entropy values when a user types text, computed from the demo model's forward pass
- **FR-010**: The loss lesson MUST display the random-guess baseline `-log(1/vocab_size)` alongside the actual loss for comparison
- **FR-011**: The loss lesson MUST include steps explaining: what cross-entropy measures, softmax probability conversion, negative log likelihood, and how to interpret loss curve shapes
- **FR-012**: The parameter anatomy lesson MUST display a visual breakdown of all named matrix groups in the model (wte, wpe, per-layer attention Wq/Wk/Wv/Wo, per-layer MLP fc1/fc2, lm_head) with shapes, parameter counts, and percentage of total
- **FR-013**: The parameter anatomy lesson MUST include interactive sliders for `n_embd` and `n_layer` that recalculate the breakdown in real time
- **FR-014**: The Adam optimizer lesson MUST visualize per-parameter momentum (m) and adaptive learning rate (v) buffers across training steps, sourced from real logged data captured during training runs
- **FR-015**: The Adam lesson MUST include interactive controls for beta1 and beta2 parameters that show how momentum and adaptive LR response curves change
- **FR-016**: The FAQ page MUST answer at least 6 of the following questions: "Does the model understand anything?", "Why does it hallucinate?", "How is this related to ChatGPT?", "Why is it so slow?", "Can I make it generate better names?", "What if I change the dataset?", "How does this compare to production LLMs?"
- **FR-017**: The attention lesson MUST be enhanced with steps explaining residual connections (the "add-back" pattern and the gradient highway it creates)
- **FR-018**: The graph explorer or attention lesson MUST include an explanation of RMSNorm showing input values, RMS computation, scale factor, and normalized output
- **FR-019**: All lesson widgets that load model data MUST fall back to the existing demo model when no trained model is available
- **FR-020**: All lesson widgets MUST handle characters outside the model's vocabulary gracefully, displaying a clear error message with the invalid character highlighted

### Key Entities

- **Lesson**: A scroll-driven narrative page with 5 steps, each containing a title, body text, and an optional interactive widget rendered in the pinned visual panel. Lessons belong to a learning arc with prev/next navigation.
- **Computation Graph Node**: A single Value in the autograd computation graph, identified by memory address, with properties: data value (float), gradient after backward pass (float), operation type (input/add/mul/pow/log/exp/relu), depth in graph, and local gradients to children.
- **Training Script (trainN.py)**: A self-contained Python file in `examples/` implementing one stage of the 6-stage curriculum (bigram → MLP → autograd → attention → multi-head → full GPT + Adam). Each script is stdlib-only and independently runnable.
- **Demo Model**: A pre-trained GPT model with tiny capacity (n_embd=16, n_head=4, n_layer=1) provisioned by DemoModelProvider, trained on a small corpus. Used by all lesson widgets as the data source.
- **Parameter Group**: A named matrix in the model's state_dict (e.g., wte, wpe, lm_head, layer0.attn_wq) with a shape, parameter count, and percentage of total. Groups are organized by category: embeddings, attention, MLP, output.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A learner can navigate through all 5 autograd lesson steps and explain in their own words how gradients flow from the loss back to parameters (qualitative, verified by comprehension check)
- **SC-002**: A learner can run `python examples/train1.py`, `train3.py`, and `train4.py` without errors and observe loss decreasing during training
- **SC-003**: A learner viewing the loss lesson can identify why `-log(1/27) ≈ 3.3` is the starting loss for random guessing and what a loss value of 2.0 means in terms of model confidence
- **SC-004**: A learner can look at the parameter anatomy visualization and identify which matrix group consumes the most parameters and how changing `n_embd` or `n_layer` affects total parameters
- **SC-005**: A learner exploring the Adam lesson can describe the difference between momentum (m) and adaptive learning rate (v) and how beta1/beta2 influence each
- **SC-006**: A learner can find answers to at least 4 common questions on the FAQ page within 30 seconds
- **SC-007**: All progressive training scripts (train0 through train5) produce decreasing loss and generate plausible text samples after training, with no runtime errors across Python 3.11+
- **SC-008**: All lesson pages render without server errors and all interactive widgets respond to user input within 1 second

## Assumptions

- All new lessons will follow the existing scroll-driven narrative pattern used by the current 5 lessons (concept.html template + scroll-scene.js)
- Interactive widgets will use the existing widget framework (widget JS classes registered in the concept page script)
- The demo model (DemoModelProvider) is sufficient as a data source for all lesson widgets that need real model activations
- Computation graph visualization will cap at 400 nodes for browser performance (existing limit in forward_graph)
- train1/train3/train4 will reuse building blocks from the existing engine.py (linear, softmax, rmsnorm, GPT.forward) rather than reimplementing from scratch — they demonstrate the incremental assembly but can call into shared helpers
- The Adam optimizer lesson will capture optimizer state (m, v buffers) from the running training engine via a new backend mechanism that logs per-parameter momentum and adaptive LR values at each step
- The FAQ page will be a static content page (no backend integration required)
- RMSNorm and residual connection explanations will be added as new steps within the existing attention lesson rather than creating separate lessons

## Quality Checklist

A separate validation checklist has been created at `specs/007-learning-content-enrichment/checklists/requirements.md`.