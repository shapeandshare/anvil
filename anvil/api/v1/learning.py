# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Learning content routes and progressive walkthrough data structures.

Provides interactive concept pages (tokenization → full transformer),
the ``LEARNING_ARC`` navigation tree (split into ``LEARNING_ARC_LESSONS``
and ``LEARNING_ARC_ADDITIONAL`` for the index page), and inference/sampling
endpoints. Extracted from ``router.py`` as part of structural decomposition.
"""

from __future__ import annotations

import random
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from anvil.api.v1.schemas import InferenceSampleBody
from anvil.core.autograd import Value
from anvil.core.engine import LlamaModel, softmax

router = APIRouter()

DATA_FUNDAMENTALS_STEPS = [
    {
        "key": "what-are-datasets-and-corpora",
        "title": "Two Ways to Source Data",
        "body": (
            "anvil provides two mechanisms for getting text into the training engine. "
            "<b>Datasets</b> are curated collections you upload or create directly &mdash; "
            "each line becomes one training sample. <b>Corpora</b> are read-only views over "
            "directory structures that auto-chunk files. Both feed into training, but "
            "they serve different workflows. The diagram above shows the full pipeline."
        ),
    },
    {
        "key": "dataset-path",
        "title": "The Dataset Path",
        "body": (
            "Datasets start from text you own: upload <code>.txt</code> files or create "
            "empty datasets to fill later. Each line becomes one training sample. "
            "Once loaded, you can curate &mdash; deduplicate, filter by length, apply "
            "regex replacements, or inline-edit samples. Datasets are your primary tool "
            "for fine-tuning data, evaluation sets, and small-to-medium collections you "
            "want full control over."
        ),
    },
    {
        "key": "corpus-path",
        "title": "The Corpus Path",
        "body": (
            "Corpora are <b>read-only</b> views of directory structures. Point at any "
            "folder, apply glob filters (e.g. <code>**/*.py</code>), and anvil auto-detects "
            "optimal chunking: windowed for prose, file-as-doc for structured files, or "
            "line-by-line for tabular data. Files stay in place &mdash; the corpus is "
            "metadata over the filesystem. Once chunked, you import the corpus contents "
            "into a dataset for downstream curation."
        ),
    },
    {
        "key": "convergence-training",
        "title": "Convergence: Into Training",
        "body": (
            "Both paths converge on the training engine. You can pick a Dataset or a Corpus "
            "as your data source &mdash; both work. The key difference: datasets give you "
            "full ownership (edit, filter, export), while corpora give you auto-discovery "
            "over large directory trees. The fastest workflow: scan with a corpus for "
            "discovery, then import into a dataset for curation."
        ),
    },
    {
        "key": "when-to-use-what",
        "title": "When to Use What",
        "body": (
            "<b>Use Datasets when</b> you have curated text you want to edit, filter, "
            "or deduplicate &mdash; fine-tuning data, evaluation sets, small to medium "
            "collections.<br><br>"
            "<b>Use Corpora when</b> you want to scan existing code repos, documentation "
            "trees, or large directory structures and auto-chunk them optimally.<br><br>"
            "<b>Combine both</b> &mdash; scan with a corpus for discovery, then import "
            "into a dataset for curation. Get the best of both worlds.<br><br>"
            '<b>Pro tip</b> &mdash; head to the <a href="/v1/datasets-page" '
            'class="action-link">Datasets page</a> and start with Add Data. '
            "The <b>All Data</b> table shows everything at a glance."
        ),
    },
]

LEARNING_ARC = [
    {
        "key": "data-fundamentals",
        "title": "Data Fundamentals",
        "path": "/v1/learn/data-fundamentals",
        "desc": "How datasets and corpora feed training data into the engine &mdash; and when to use each.",
    },
    {
        "key": "tokenization",
        "title": "Tokenization",
        "path": "/v1/learn/tokenization",
        "desc": "How the model chops text into character tokens and maps them to IDs.",
    },
    {
        "key": "embeddings",
        "title": "Embeddings",
        "path": "/v1/learn/embeddings",
        "desc": "How each token ID becomes a dense vector the model can compute with.",
    },
    {
        "key": "parameters",
        "title": "Parameters",
        "path": "/v1/learn/parameters",
        "desc": "Where the model's ~4K parameters live and what each matrix does.",
    },
    {
        "key": "autograd",
        "title": "Autograd",
        "path": "/v1/learn/autograd",
        "desc": "How gradients flow backward through the computation graph to train the model.",
    },
    {
        "key": "attention",
        "title": "Attention",
        "path": "/v1/learn/attention",
        "desc": "How each token looks at its predecessors to build context-aware representations.",
    },
    {
        "key": "loss",
        "title": "Cross-Entropy Loss",
        "path": "/v1/learn/loss",
        "desc": "How prediction error is measured and what the loss number means.",
    },
    {
        "key": "sampling",
        "title": "Sampling",
        "path": "/v1/learn/sampling",
        "desc": "How the model picks the next character from its probability distribution.",
    },
    {
        "key": "adam",
        "title": "Adam Optimizer",
        "path": "/v1/learn/adam",
        "desc": "How momentum and adaptive learning rates make training converge faster.",
    },
    {
        "key": "training-loop",
        "title": "Training Loop",
        "path": "/v1/learn/training-loop",
        "desc": "How the model learns by minimizing prediction error step by step.",
    },
    {
        "key": "architecture",
        "title": "Architecture",
        "path": "/v1/learn/architecture",
        "desc": "The full Llama decoder stack — RoPE, RMSNorm, SwiGLU — visualized end to end.",
    },
    {
        "key": "graph",
        "title": "Forward Pass",
        "path": "/v1/learn/graph",
        "desc": "Scrub through the Llama forward pass step by step on an interactive computation graph.",
    },
    {
        "key": "export",
        "title": "Model Export",
        "path": "/v1/learn/export",
        "desc": "How trained models are exported to safetensors for HuggingFace compatibility.",
    },
    {
        "key": "chunking",
        "title": "Chunking Strategies",
        "path": "/v1/learn/chunking",
        "desc": "How long documents are split into context-window-sized training samples — windowed, line, and file strategies.",
    },
    {
        "key": "content-versioning",
        "title": "Content Versioning",
        "path": "/v1/learn/content-versioning",
        "desc": "How training data is content-addressed, versioned, and traced from model back to the exact bytes it learned from.",
    },
    {
        "key": "experiment-tracking",
        "title": "Experiment Tracking",
        "path": "/v1/learn/experiment-tracking",
        "desc": "How MLflow records hyperparameters, loss curves, artifacts, and the model registry for every run.",
    },
    {
        "key": "governance",
        "title": "Data Governance",
        "path": "/v1/learn/governance",
        "desc": "How provenance, an acceptable-use gate, and a hash-chained audit trail keep data inclusion lawful and auditable.",
    },
    {
        "key": "memory-divergence",
        "title": "Memory & Divergence",
        "path": "/v1/learn/memory-divergence",
        "desc": "How anvil estimates memory before training and detects NaN/Inf loss divergence during it.",
    },
    {
        "key": "faq",
        "title": "FAQ",
        "path": "/v1/learn/faq",
        "desc": "Frequently asked questions about how anvil works and what it can do.",
    },
    {
        "key": "glossary",
        "title": "Glossary",
        "path": "/v1/learn/glossary",
        "desc": "Definitions for every technical term used across the learning arc and codebase.",
    },
    {
        "key": "cloud-compute",
        "title": "Training in the Cloud",
        "path": "/v1/learn/cloud-compute",
        "desc": "Run training on external compute with Modal, Modal GPUs, MLflow artifact sync, and the submitted/poll/complete lifecycle.",
    },
]


LEARNING_ARC_ADDITIONAL = [
    {
        "key": "cloud-compute",
        "title": "Training in the Cloud",
        "path": "/v1/learn/cloud-compute",
        "desc": "Run training on external compute with Modal, Modal GPUs, MLflow artifact sync, and the submitted/poll/complete lifecycle.",
    },
    {
        "key": "faq",
        "title": "FAQ",
        "path": "/v1/learn/faq",
        "desc": "Frequently asked questions about how anvil works and what it can do.",
    },
    {
        "key": "glossary",
        "title": "Glossary",
        "path": "/v1/learn/glossary",
        "desc": "Definitions for every technical term used across the learning arc and codebase.",
    },
]

# LEARNING_ARC_LESSONS is derived from LEARNING_ARC by excluding ADDITIONAL items.
_ADDITIONAL_KEYS = frozenset(item["key"] for item in LEARNING_ARC_ADDITIONAL)
LEARNING_ARC_LESSONS = [
    item for item in LEARNING_ARC if item["key"] not in _ADDITIONAL_KEYS
]


def _arc_context(current_key: str) -> dict[str, Any]:
    """Build prev/next navigation context from ``LEARNING_ARC``.

    Parameters
    ----------
    current_key : str
        The key of the current learning module (e.g. ``"tokenization"``).

    Returns
    -------
    dict
        ``arc`` (full list), ``current_key``, ``current_index``,
        ``prev`` (previous module dict or None), and ``next`` (next
        module dict or None).
    """
    idx = next(
        (i for i, item in enumerate(LEARNING_ARC) if item["key"] == current_key), -1
    )
    return {
        "arc": LEARNING_ARC,
        "current_key": current_key,
        "current_index": idx,
        "prev": LEARNING_ARC[idx - 1] if idx > 0 else None,
        "next": LEARNING_ARC[idx + 1] if 0 <= idx < len(LEARNING_ARC) - 1 else None,
    }


def related_lessons(*keys: str) -> list[dict[str, str]]:
    """Resolve learning-arc entries for the given keys, preserving order.

    Used to attach a compact "Related lessons" call-to-action row to
    workspace pages (datasets, training, experiments, etc.) so every page
    links into the relevant parts of the learning platform. Data is sourced
    from :data:`LEARNING_ARC` so lesson titles and paths stay single-sourced.

    Parameters
    ----------
    *keys : str
        Lesson keys to resolve (e.g. ``"tokenization"``), in the order they
        should appear. Unknown keys are silently skipped.

    Returns
    -------
    list of dict
        The matching :data:`LEARNING_ARC` entries, in the requested order.
    """
    by_key = {item["key"]: item for item in LEARNING_ARC}
    return [by_key[key] for key in keys if key in by_key]


TOKENIZATION_STEPS = [
    {
        "key": "what-is-a-token",
        "title": "What is a Token?",
        "body": (
            "This model works with individual characters as tokens. "
            "Not words, not subwords, just single characters. "
            "Type some text into the widget on the right and watch each character get highlighted. "
            "Every letter, space, and punctuation mark is one token."
        ),
        "widget": "tokenization",
    },
    {
        "key": "the-vocabulary",
        "title": "The Vocabulary",
        "body": (
            "The model builds its vocabulary from the sorted unique characters in the training data. "
            "If the data contains a, b, c, and space, those are all the character types it knows. "
            "The widget shows you the full vocabulary count (vocab_size). "
            "Notice there is one extra slot reserved for a special marker called BOS."
        ),
        "widget": "tokenization",
    },
    {
        "key": "token-ids",
        "title": "Token IDs",
        "body": (
            "Every character in the vocabulary gets a numeric ID: its index in the sorted list. "
            "The widget shows each character's ID next to it. "
            "The BOS marker always gets the highest ID (vocab_size - 1). "
            "The model never sees characters, only these integer IDs."
        ),
        "widget": "tokenization",
    },
    {
        "key": "bos-wrapping",
        "title": "BOS Wrapping",
        "body": (
            "Every sequence the model processes begins and ends with the BOS marker "
            "(Begin Of Sequence). The widget shows a highlighted BOS at both ends. "
            "BOS gives the model a fixed starting point so it knows when a sequence "
            "starts and when it ends. Try typing different text and watch the BOS bookends."
        ),
        "widget": "tokenization",
    },
    {
        "key": "from-text-to-numbers",
        "title": "From Text to Numbers",
        "body": (
            "Putting it all together: your text becomes a list of integers. "
            "The model receives [BOS, id_of_a, id_of_b, ..., BOS]. "
            "Each position in this sequence will get its own embedding in the next lesson. "
            "Type longer or shorter text and see how the token count changes."
        ),
        "widget": "tokenization",
    },
    {
        "key": "tokenizer-vocabulary-classes",
        "title": "Tokenizer vs Vocabulary",
        "body": (
            "anvil has two classes for this. Tokenizer (anvil/core/tokenizer.py) "
            "builds its vocabulary from training documents at construction time. "
            "Vocabulary is reconstructable from a saved chars list — it is what "
            "gets loaded for inference when you register and reload a model. "
            "Both produce identical encode/decode semantics (BOS-wrapped, "
            "same vocab_size calculation, same char-to-id mapping). "
            "The saved model stores its chars list so it can be reloaded "
            "without the original training data."
        ),
        "widget": "tokenization",
    },
]

EMBEDDING_STEPS = [
    {
        "key": "what-is-an-embedding",
        "title": "What is an Embedding?",
        "body": (
            "A token ID is just an integer. The model needs a dense vector to compute with. "
            "It looks up each token ID in the WTE (Weight Token Embedding) matrix. "
            "This matrix has one row per token, each row is a 16-dimensional vector (n_embd = 16). "
            "Type some text and watch each character get mapped to its embedding vector."
        ),
        "widget": "embedding",
    },
    {
        "key": "position-matters",
        "title": "Position Matters",
        "body": (
            "The same character at different positions needs different representations. "
            "The letter 'e' at position 0 and position 5 mean different things. "
            "Rather than adding a learned position embedding, this model uses RoPE "
            "(Rotary Position Embedding): it rotates the Query and Key vectors by an "
            "angle that depends on the token's position. Position information is encoded "
            "in the direction of these vectors, not added to the token embedding."
        ),
        "widget": "embedding",
    },
    {
        "key": "the-embedding-space",
        "title": "The Embedding Space",
        "body": (
            "Sixteen dimensions is hard to visualize. The widget projects these vectors "
            "down to 2D using PCA (Principal Component Analysis). "
            "Each dot is one character from your input, colored by its position. "
            "The spatial arrangement comes from the model's actual learned weights."
        ),
        "widget": "embedding",
    },
    {
        "key": "similarity-in-space",
        "title": "Similarity in Space",
        "body": (
            "Dots that are close together in the 2D projection have similar "
            "combined embeddings. Dots far apart are different. "
            "Characters that often appear in similar contexts may cluster together. "
            "This is the model's geometric view of your text."
        ),
        "widget": "embedding",
    },
    {
        "key": "type-and-explore",
        "title": "Type and Explore",
        "body": (
            "Try typing different words and phrases. "
            "Notice how the cloud of points shifts as each character gets its own "
            "token embedding. Position is encoded via RoPE inside the attention "
            "mechanism, not added to the embedding itself — the widget shows the "
            "pure token embeddings before attention applies position-dependent rotation."
        ),
        "widget": "embedding",
    },
]

ATTENTION_STEPS = [
    {
        "key": "what-is-attention",
        "title": "What is Attention?",
        "body": (
            "Attention helps each token build a representation by looking at itself "
            "and every token that came before it. Type some text, then use the left and right "
            "arrow keys to pick a token. The heatmap will show how strongly that token "
            "focuses on each earlier token. Brighter means stronger attention."
        ),
        "widget": "attention",
    },
    {
        "key": "how-attention-is-computed",
        "title": "How Attention is Computed",
        "body": (
            "At each position, the model computes three vectors: Query (what am I looking for), "
            "Key (what do I contain), and Value (what info do I carry). "
            "Position is encoded via RoPE: the Query and Key vectors are rotated by an "
            "angle proportional to their position before the dot product. "
            "It takes the dot product of the current token's Query with every earlier token's Key. "
            "Those scores go through softmax to become attention weights (0 to 1, summing to 1)."
        ),
        "widget": "attention",
    },
    {
        "key": "lower-triangular-pattern",
        "title": "Lower-Triangular Pattern",
        "body": (
            "Notice the heatmap is lower-triangular: each token only attends to itself "
            "and tokens before it. The model never looks at future tokens that would leak "
            "information it should predict. Navigate between tokens with arrow keys and watch "
            "how each row only covers positions <= its own index."
        ),
        "widget": "attention",
    },
    {
        "key": "multi-head-attention",
        "title": "Multi-Head Attention",
        "body": (
            "This model has 4 attention heads running in parallel (n_head = 4). "
            "Each head learns a different relationship pattern. "
            "One head might focus on the previous character, another on the start of a word. "
            "Use the head selector to switch between heads and compare patterns."
        ),
        "widget": "attention",
    },
    {
        "key": "explore-different-input",
        "title": "Explore Different Input",
        "body": (
            "Type completely different text and watch the attention patterns change. "
            "The weights reflect what the model has learned from its training data. "
            "Experiment with short words, repeated characters, and punctuation. "
            "Each input produces a unique attention signature."
        ),
        "widget": "attention",
    },
    {
        "key": "residual-connections",
        "title": "Residual Connections",
        "body": (
            "After attention, the original input is added back to the output: "
            'output = attention(x) + x. This "add-back" pattern creates a gradient highway '
            "that lets signals flow directly through the network without vanishing or exploding. "
            "Without residuals, deeper models would struggle to learn because gradients "
            "would decay to zero through many layers."
        ),
    },
    {
        "key": "rmsnorm",
        "title": "RMSNorm Explained",
        "body": (
            "Before attention, the model normalises activations with RMSNorm. "
            "Given input values x, it computes RMS = sqrt(mean(x squared)), then scales by "
            "a learned parameter: output = x / RMS. Unlike LayerNorm, RMSNorm does not "
            "subtract the mean — it only divides by the root-mean-square. This is simpler, "
            "faster, and works well for transformer training."
        ),
    },
    {
        "key": "kv-cache-mechanics",
        "title": "KV Cache Mechanics",
        "body": (
            "During autoregressive generation, the model caches Key and Value vectors "
            "for every previous position instead of recomputing them. At each new position, "
            "it computes Q, K, V for the current token, appends K and V to per-layer lists, "
            "then attends to all cached positions. This turns O(n) into O(n) per step. "
            "An important detail: Keys are rotated by RoPE BEFORE caching — each key is "
            "rotated exactly once at its position and never double-rotated. Values are "
            "not rotated (they carry absolute content, not relative position)."
        ),
    },
]

SAMPLING_STEPS = [
    {
        "key": "from-logits-to-probabilities",
        "title": "From Logits to Probabilities",
        "body": (
            "After processing all tokens, the model outputs logits: raw scores for every "
            "character in the vocabulary. Higher logit = the model thinks that character "
            "is more likely next. The widget shows these as a bar chart. "
            "Softmax converts logits into probabilities that sum to 1."
        ),
        "widget": "sampling",
    },
    {
        "key": "temperature",
        "title": "Temperature",
        "body": (
            "Temperature scales the logits before softmax. Low temperature (near 0) "
            "makes the distribution peaky: the most likely character dominates. "
            "High temperature (1.0+) flattens the distribution: all characters become "
            "more equally likely. Move the temperature slider and watch the bars reshape."
        ),
        "widget": "sampling",
    },
    {
        "key": "top-k-sampling",
        "title": "Top-K Sampling",
        "body": (
            "Top-K restricts sampling to the K most probable characters. "
            "The probability mass is redistributed only among those K. "
            "K = 1 is greedy decoding (always pick the most likely). "
            "K = vocab_size uses the full distribution. "
            "Adjust the top-K slider and see which characters get cut off."
        ),
        "widget": "sampling",
    },
    {
        "key": "reading-the-distribution",
        "title": "Reading the Distribution",
        "body": (
            "Each bar is one character from the vocabulary. "
            "Tall bar = the model is confident that character comes next. "
            "Short or missing bar = the model considers that unlikely. "
            "The widget labels each bar with the character and its probability. "
            "Notice how only a handful of characters get meaningful probability."
        ),
        "widget": "sampling",
    },
    {
        "key": "sampling-in-practice",
        "title": "Sampling in Practice",
        "body": (
            "Temperature and top-K work together. Try temperature 0.5 with top-K 5 "
            "for moderately focused sampling. Then try temperature 1.5 with top-K 20 "
            "for more diverse outputs. The bars update in real time as you adjust. "
            "This is the same sampling used when generating text in the Playground."
        ),
        "widget": "sampling",
    },
]

TRAINING_LOOP_STEPS = [
    {
        "key": "what-is-training",
        "title": "What is Training?",
        "body": (
            "Training adjusts all model parameters to make better predictions. "
            "At each step: the model reads a sequence, predicts tokens one by one, "
            "measures how wrong it was (loss), and nudges every parameter to reduce that error. "
            "The widget below shows the loss curve from your training runs. "
            "If you haven't trained a model yet, head to the "
            '<a href="/v1/training-page" class="action-link">Training Dashboard</a> '
            "first — then come back here to inspect the results."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "the-loss-curve",
        "title": "The Loss Curve",
        "body": (
            "Loss quantifies prediction error: how surprised the model is by the actual next "
            "character. A decreasing curve means the model is learning patterns in the data. "
            "Early steps have high loss (the model is guessing blindly). "
            "Later steps have lower loss as the model picks up character-level patterns. "
            "Select a finished experiment above and drag the scrubber to see loss at any point."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "what-loss-tells-you",
        "title": "What Loss Tells You",
        "body": (
            "The shape of the curve reveals training quality. A smooth downward slope "
            "means stable learning. Plateaus suggest the model needs more capacity or "
            "different hyperparameters. Spikes or oscillations may mean the learning rate "
            "is too high. Compare curves from different experiments using the selector above."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "gradient-descent",
        "title": "Gradient Descent",
        "body": (
            "The optimizer (Adam) computes gradients for every parameter and updates them "
            "in the direction that reduces loss. The learning rate controls step size: "
            "too small = painfully slow progress, too big = overshooting and divergence. "
            "This model uses linear learning rate decay: lr_t = lr * (1 - step/num_steps). "
            "The scrubber below lets you step through the gradient updates at each point."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "training-to-generation",
        "title": "Training to Generation",
        "body": (
            "A trained model generates new text character by character: "
            "it predicts the next char, samples it (using the sampling lesson's techniques), "
            "feeds it back as input, and repeats. Better loss = more coherent output. "
            "No experiments yet? "
            '<a href="/v1/training-page" class="action-link">Go train a model</a> '
            "to populate the loss curve above — then use the selector to switch between runs."
        ),
        "widget": "trainingLoop",
    },
    {
        "key": "dual-backend",
        "title": "CPU vs GPU Training",
        "body": (
            "anvil has two training backends with identical Llama architecture. "
            "The CPU backend uses pure Python (zero dependencies) with a custom "
            "Value autograd graph. The GPU backend uses PyTorch tensors for "
            "10-100x speed on CUDA or MPS. Switching between them is transparent: "
            "TrainingService resolves the device and dispatches automatically. "
            "GPU-trained weights are bridged back into a CPU LlamaModel via "
            "_load_weights_into_model(), so downstream code never knows which "
            "backend ran. See the Architecture reference for details."
        ),
        "widget": "trainingLoop",
    },
]

LOSS_STEPS = [
    {
        "key": "what-is-loss",
        "title": "What is Loss?",
        "body": (
            "Loss measures how wrong the model's predictions are. For each token, "
            "the model outputs a probability distribution over the vocabulary. "
            "If the correct next token gets probability 0.1, the loss is higher "
            "than if it gets 0.9. The widget shows the running loss as training progresses."
        ),
        "widget": "loss",
    },
    {
        "key": "cross-entropy",
        "title": "Cross-Entropy",
        "body": (
            "Cross-entropy loss is defined as -log(p(target)), where p(target) is "
            "the probability the model assigned to the correct next token. "
            "If p(target) = 1.0 (perfect prediction), loss = 0. "
            "If p(target) = 0.5, loss ≈ 0.69. The widget shows this value "
            "for the current training step."
        ),
        "widget": "loss",
    },
    {
        "key": "softmax-connection",
        "title": "Softmax Connection",
        "body": (
            "The model's raw output is logits — unnormalised scores. Softmax converts "
            "them into probabilities that sum to 1.0. The loss is computed from those "
            "probabilities, not from the logits directly. The widget shows the softmax "
            "output for the current batch and highlights p(target)."
        ),
        "widget": "loss",
    },
    {
        "key": "reading-the-curve",
        "title": "Reading the Curve",
        "body": (
            "A smooth downward slope means stable learning — the model is consistently "
            "making better predictions. Plateaus suggest the model needs more capacity "
            "(more parameters) or a different learning rate regime. "
            "The widget annotates each region of the curve with what it indicates."
        ),
        "widget": "loss",
    },
    {
        "key": "the-baseline",
        "title": "The Baseline",
        "body": (
            "Random guessing for a vocabulary of 27 characters (26 letters + BOS) "
            "gives p = 1/27 for each token, so loss = -log(1/27) ≈ 3.3. "
            "If your training loss is above 3.3, the model hasn't even reached "
            "random guessing yet. The widget marks the baseline on the loss curve."
        ),
        "widget": "loss",
    },
]

PARAMS_STEPS = [
    {
        "key": "where-params-live",
        "title": "Where Parameters Live",
        "body": (
            "All model parameters live in a state_dict: a dictionary of PyTorch-like "
            "tensors accessible via model.state_dict(). Each key is a layer name, "
            "each value is a weight matrix. The widget loads the most recent model's "
            "state_dict and shows every parameter with its shape and value range."
        ),
        "widget": "params",
    },
    {
        "key": "token-embeddings",
        "title": "Token Embeddings (WTE)",
        "body": (
            "WTE (Weight Token Embedding) is a matrix of shape vocab_size x n_embd. "
            "Each of the 27 tokens gets one 16-dimensional vector. "
            "These are the learned representations that turn token IDs into dense vectors. "
            "The widget highlights the WTE entry and shows a few rows of values."
        ),
        "widget": "params",
    },
    {
        "key": "rope-position",
        "title": "RoPE (Position Encoding)",
        "body": (
            "This model uses Rotary Position Embedding (RoPE) instead of learned "
            "position embeddings. Precomputed cos and sin tables rotate the Query "
            "and Key vectors by an angle proportional to position. There are no "
            "learned position parameters — position encoding is baked into the "
            "attention computation itself via a rotation matrix."
        ),
        "widget": "params",
    },
    {
        "key": "attention-weights",
        "title": "Attention Weights (Q/K/V/O)",
        "body": (
            "Each attention head has four projection matrices: Query (Q), Key (K), "
            "Value (V), and Output (O). Each is shape n_embd x n_embd (16 x 16). "
            "With 4 heads, that is 4 x 4 x 16 x 16 = 4,096 attention parameters. "
            "The widget breaks down each projection and shows sample values."
        ),
        "widget": "params",
    },
    {
        "key": "mlp-and-output",
        "title": "MLP and Output Head",
        "body": (
            "After attention, a SwiGLU MLP projects through gate, up, and down "
            "matrices. The gate (16 x ~42) is activated by SiLU then multiplied "
            "element-wise with up (16 x ~42). The result projects through down "
            "(~42 x 16). The lm_head (16 x 27) produces logits over the vocabulary. "
            "Total: the widget sums all parameters and verifies the count."
        ),
        "widget": "params",
    },
    {
        "key": "export-mapping",
        "title": "Safetensors Export Names",
        "body": (
            "When exported to safetensors (HF-compatible format), each anvil "
            "parameter maps to a HuggingFace LlamaForCausalLM tensor name. "
            "For example, layer0.attn_wq becomes "
            "model.layers.0.self_attn.q_proj.weight. "
            "layer{i}.rms_1 maps to input_layernorm.weight, and "
            "layer{i}.rms_2 maps to post_attention_layernorm.weight. "
            "No biases are exported (Llama uses bias-free linear layers). "
            "See the Safetensors Export reference for the full mapping table."
        ),
        "widget": "params",
    },
]

ADAM_STEPS = [
    {
        "key": "what-is-adam",
        "title": "What is Adam?",
        "body": (
            "Plain SGD uses a single learning rate for every parameter. "
            "Adam (Adaptive Moment Estimation) maintains two per-parameter values: "
            "m (momentum) and v (adaptive learning rate). This makes training faster "
            "and more stable, especially for transformers with diverse parameter scales."
        ),
        "widget": "adam",
    },
    {
        "key": "momentum",
        "title": "Momentum (m)",
        "body": (
            "Momentum tracks a rolling average of past gradients: "
            "m_t = beta1 * m_{t-1} + (1 - beta1) * g_t. "
            "This smooths out noisy gradients and accelerates progress in consistent "
            "directions. The widget shows how m evolves step by step for a sample parameter."
        ),
        "widget": "adam",
    },
    {
        "key": "adaptive-lr",
        "title": "Adaptive LR (v)",
        "body": (
            "The v term tracks the squared gradient magnitude: "
            "v_t = beta2 * v_{t-1} + (1 - beta2) * g_t^2. "
            "Parameters with large gradients get smaller updates (they are sensitive), "
            "while parameters with small gradients get larger updates. "
            "The widget visualises this per-parameter scaling effect."
        ),
        "widget": "adam",
    },
    {
        "key": "bias-correction",
        "title": "Bias Correction",
        "body": (
            "At the first step, m and v are initialised to zero, so they are biased "
            "toward zero. Adam corrects this: m_hat = m / (1 - beta1^t), "
            "v_hat = v / (1 - beta2^t). Early in training, this correction is large; "
            "it decays toward 1 as t increases. The widget shows the correction curve."
        ),
        "widget": "adam",
    },
    {
        "key": "lr-decay",
        "title": "LR Decay",
        "body": (
            "This model uses a linear learning rate decay schedule: "
            "lr_t = lr * (1 - step / num_steps). The learning rate starts at the "
            "configured value and decreases linearly to zero. This lets the model "
            "make large updates early when it is far from optimal, then fine-tune "
            "with smaller updates later. The widget shows the decay curve."
        ),
        "widget": "adam",
    },
    {
        "key": "weight-decay",
        "title": "Weight Decay (AdamW)",
        "body": (
            "The optimizer in anvil's core engine is technically Adam, not AdamW — "
            "there is no explicit weight decay term. In full AdamW, each parameter "
            "has its own learning rate and a small decay factor that gently pulls "
            "weights toward zero (L2 regularization). This prevents weights from "
            "growing unbounded. For anvil's small educational models, the effect "
            "is negligible. The GPU backend uses torch.optim.Adam (also without "
            "weight decay). Adding weight_decay to the config is a natural "
            "extension for more serious training runs."
        ),
        "widget": "adam",
    },
]

AUTOGRAD_STEPS = [
    {
        "key": "what-is-autograd",
        "title": "What is Autograd?",
        "body": (
            "Autograd is automatic differentiation: it tracks every mathematical operation "
            "to build a computation graph, then walks it backward to compute gradients. "
            "In anvil, each number is wrapped in a Value object that records how it was "
            "computed. Type some text into the widget and watch the computation graph build."
        ),
        "widget": "autograd",
    },
    {
        "key": "building-the-graph",
        "title": "Building the Graph",
        "body": (
            "Every operation (add, multiply, log, exp, relu) creates a new Value node "
            "that points back to its inputs (children). The graph grows from parameters "
            "and input tokens up through embeddings, attention, and finally to the loss. "
            "Each node stores its data value and the local gradient of the operation."
        ),
        "widget": "autograd",
    },
    {
        "key": "topological-sort",
        "title": "Topological Sort",
        "body": (
            "Before backpropagation, the graph must be topologically sorted: ordered so "
            "that every node comes after all nodes it depends on. This ensures gradients "
            "flow in the correct direction — from the loss (output) back to the parameters "
            "(inputs). The widget shows the node depth, with depth 0 at the output."
        ),
        "widget": "autograd",
    },
    {
        "key": "chain-rule",
        "title": "Chain Rule",
        "body": (
            "Backpropagation applies the chain rule: the gradient at each node is the sum "
            "of (local gradient x parent gradient) for all paths to the loss. Each edge in "
            "the graph shows the local gradient contribution. Green values mean positive "
            "influence on the loss, red means negative."
        ),
        "widget": "autograd",
    },
    {
        "key": "gradient-accumulation",
        "title": "Gradient Accumulation",
        "body": (
            "When a Value is used in multiple places (the graph branches), its gradient "
            "is the sum of contributions from each path. This is why the backward pass "
            "uses += (accumulation) rather than simple assignment. The widget shows the "
            "final accumulated gradient (g) at each node."
        ),
        "widget": "autograd",
    },
]

ARCHITECTURE_STEPS = [
    {
        "key": "the-big-picture",
        "title": "The Big Picture",
        "body": (
            "anvil is a Llama-style decoder-only transformer. Text flows in as token "
            "IDs, through a token embedding, then through one or more identical "
            "transformer blocks, and finally through a normalization + output head "
            "that produces logits over the vocabulary. The diagram shows the full "
            "stack — use it as a map for the components you learned in earlier lessons."
        ),
        "widget": "architecture",
    },
    {
        "key": "token-embedding-input",
        "title": "Token Embedding (Input)",
        "body": (
            "Each token ID indexes a row of the wte matrix to produce a dense vector "
            "of size n_embd. Unlike GPT-2, there is NO learned position embedding "
            "added here — position is injected later via RoPE inside attention. The "
            "embedding is the only thing fed into the first transformer block."
        ),
        "widget": "architecture",
    },
    {
        "key": "the-transformer-block",
        "title": "The Transformer Block",
        "body": (
            "The heart of the model is the transformer block, repeated n_layer times. "
            "Each block has two sublayers: a self-attention sublayer and a SwiGLU MLP "
            "sublayer. Both use pre-normalization (RMSNorm before the sublayer) and a "
            "residual connection (the input is added back to the output). Highlighted "
            "in the diagram, this block is where nearly all the parameters live."
        ),
        "widget": "architecture",
    },
    {
        "key": "attention-sublayer",
        "title": "Attention Sublayer",
        "body": (
            "First sublayer: RMSNorm (scaled by rms_1) → Q/K/V projections → RoPE "
            "rotation applied to Q and K → multi-head causal attention → output "
            "projection (Wo) → add residual. RoPE is what encodes position, by "
            "rotating the query and key vectors by an angle proportional to their "
            "position before the attention dot-product."
        ),
        "widget": "architecture",
    },
    {
        "key": "swiglu-sublayer",
        "title": "SwiGLU MLP Sublayer",
        "body": (
            "Second sublayer: RMSNorm (scaled by rms_2) → SwiGLU MLP → add residual. "
            "SwiGLU computes gate = SiLU(x·Wgate), up = x·Wup, then (gate ⊙ up)·Wdown. "
            "The intermediate size is int(8·n_embd/3), preserving parameter parity "
            "with the classic 4x ReLU MLP it replaces. SiLU (Swish) is x·sigmoid(x)."
        ),
        "widget": "architecture",
    },
    {
        "key": "output-head",
        "title": "Output Head",
        "body": (
            "After the final transformer block, one more RMSNorm (rms_final) "
            "normalizes the representation, then the lm_head linear projection maps "
            "it from n_embd back to vocab_size — producing one logit per possible "
            "next character. Softmax turns those logits into probabilities. The lm_head "
            "is a separate matrix from wte (no weight tying)."
        ),
        "widget": "architecture",
    },
]

EXPORT_STEPS = [
    {
        "key": "why-export",
        "title": "Why Export?",
        "body": (
            "After training, the model is stored as model.json — a Python-serializable "
            "dict of Value objects. This format is anvil-native: it preserves autograd "
            "state and is loadable by LlamaModel.load(). But other tools don't understand "
            "anvil's format. The export pipeline converts the trained weights into "
            "safetensors, the standard format for HuggingFace transformers. This lets "
            "you load your trained model in Llama.cpp, vLLM, or any Llama-compatible "
            "inference server."
        ),
    },
    {
        "key": "tensor-mapping",
        "title": "Tensor Name Mapping",
        "body": (
            "The critical bridge is export_state_dict() in anvil/services/export.py. "
            "Every anvil internal key maps to a HuggingFace LlamaForCausalLM tensor name. "
            "For example, layer0.attn_wq becomes model.layers.0.self_attn.q_proj.weight. "
            "layer0.rms_1 maps to input_layernorm.weight. rms_final maps to model.norm.weight. "
            "No biases are exported — Llama uses bias-free linear layers. No wpe is exported "
            " RoPE is a computation, not a parameter. See the Safetensors Export reference "
            "for the full mapping table."
        ),
    },
    {
        "key": "config-generation",
        "title": "Config Generation",
        "body": (
            "Alongside the weights, the export generates a config.json compatible with "
            "HuggingFace LlamaConfig. Key fields: model_type=llama, hidden_size=n_embd, "
            "intermediate_size=int(8*n_embd/3), num_hidden_layers=n_layer, "
            "num_attention_heads=n_head, hidden_act=silu, rms_norm_eps=1e-5, "
            "rope_theta=10000.0. The config also marks tie_word_embeddings=false "
            "(wte and lm_head are separate) and attention_bias=false."
        ),
    },
    {
        "key": "tokenizer-export",
        "title": "Tokenizer Export",
        "body": (
            "The character-level tokenizer is exported as tokenizer.json with: "
            "the sorted character list, char-to-ID mapping, BOS token ID, and "
            "tokenizer type flag. This ensures the same encoding is used at "
            "inference time as during training. The exported tokenizer is not "
            "compatible with HuggingFace tokenizers (which use BPE/WordPiece), "
            "but the format is self-documenting for anvil's use case."
        ),
    },
    {
        "key": "mlflow-pyfunc",
        "title": "MLflow Pyfunc Model",
        "body": (
            "The export also generates MLmodel and conda.yaml for MLflow's pyfunc "
            "loading path. The MLmodel points to anvil._pyfunc_model.AnvilPyfuncModel "
            "as the loader module. The conda.yaml lists anvil, transformers, torch, "
            "safetensors, and numpy as dependencies. This enables MLflow Model Registry "
            "to deploy the model as a REST endpoint or load it in Python for inference. "
            "The demo model at data/models/demo/ is the canonical example."
        ),
    },
]

CLOUD_COMPUTE_STEPS = [
    {
        "key": "why-cloud-compute",
        "title": "Why Cloud Compute?",
        "body": (
            "Local training is limited by your hardware. A 16-parameter model fits anywhere, "
            "but serious models need more memory and faster computation. Cloud compute (Modal) "
            "lets you train on powerful remote GPUs without buying hardware. The workflow "
            "stays the same: config→submit→poll→artifacts. The widget below walks through "
            "each stage of a remote training run."
        ),
        "widget": "cloudCompute",
    },
    {
        "key": "backend-selector",
        "title": "Backend Selector",
        "body": (
            "The Training Dashboard now shows a Compute Backend selector instead of a simple "
            "GPU toggle. Options: Auto (best available), Local (CPU), Local (GPU), and "
            "Modal (cloud GPU). Unavailable options are greyed out with an explanation. "
            "The endpoint /v1/compute/backends returns availability from the compute registry."
        ),
    },
    {
        "key": "submitted-event",
        "title": "The 'submitted' SSE Event",
        "body": (
            'When training is dispatched to Modal, the server sends a new "submitted" '
            "SSE event to the browser with the remote_job_id. This tells the dashboard "
            "the job was accepted by Modal and is waiting in the queue. "
            "The connection state changes to 'submitted' and shows the remote job ID."
        ),
    },
    {
        "key": "status-event",
        "title": "The 'status' SSE Event",
        "body": (
            "As Modal runs the job, the server polls for state transitions and emits "
            '"status" SSE events. These carry the current lifecycle phase: '
            "RUNNING (training started), with step/loss metrics when available, "
            "and COMPLETED (training finished). The dashboard updates the loss chart "
            "and metrics in real time, exactly like local training."
        ),
    },
    {
        "key": "artifact-flow",
        "title": "Artifact Flow",
        "body": (
            "On remote completion, Modal logs artifacts directly to the shared MLflow "
            "server: model.safetensors, config.json, samples.txt, and MLmodel metadata. "
            "The anvil server picks up the completion, records the experiment in the "
            "local SQLite DB, and registers the model in MLflow Model Registry with "
            "a runs:/ URI. No local model download — the artifact stays in MLflow."
        ),
    },
    {
        "key": "d4-failure-mode",
        "title": "D4 Failure Mode",
        "body": (
            "If you select Modal but the modal package is missing or unauthenticated, "
            "the server returns a 422 error with a clear message: "
            '"Modal selected but not available. Install via: pip install anvil[compute] '
            'and authenticate via: modal token new". This follows the D4 rule: '
            "implicit backends (auto, local-cpu/gpu) silently fall back; "
            "explicit selection of an unavailable backend raises an error."
        ),
    },
    {
        "key": "polling-lifecycle",
        "title": "Polling Lifecycle",
        "body": (
            "The polling loop uses exponential backoff: starts at 1-second intervals "
            "during SUBMITTED, extends to 5 seconds during RUNNING, and switches to "
            "15-second intervals once COMPLETED (waiting for artifact sync). "
            "The loop has a configurable timeout (default 30 minutes). "
            "If the timeout expires, the experiment is marked failed."
        ),
    },
]


CHUNKING_STEPS = [
    {
        "key": "why-chunking",
        "title": "Why Chunk at All?",
        "body": (
            "The model has a fixed context window (<code>block_size</code>, default 16 "
            "characters). A raw document is almost always longer than that. Chunking is "
            "the step that turns one long text into many bite-sized training documents, "
            "each short enough to fit the window. anvil ships three strategies, all "
            "implementing one tiny interface: <code>Chunker.chunk(text) -> list[str]</code> "
            "in <code>anvil/services/chunking/base.py</code>. A chunker is stateless — the "
            "same input always yields the same chunks."
        ),
        "widget": "chunking",
    },
    {
        "key": "file-as-doc",
        "title": "Strategy 1: File-as-Document",
        "body": (
            "<code>FileAsDocChunker</code> is the identity strategy: it returns the whole "
            "text as a single chunk (<code>[text]</code>), or an empty list if the text is "
            "empty. Use it when each file is already a coherent unit you want kept intact, "
            "or as a baseline to compare the other strategies against. It is the "
            '<code>ChunkingStrategy.FILE</code> = <code>"file"</code> option.'
        ),
    },
    {
        "key": "line-as-doc",
        "title": "Strategy 2: Line-as-Document",
        "body": (
            "<code>LineAsDocChunker</code> splits on newlines and returns one chunk per "
            "<b>non-empty</b> line, each stripped of surrounding whitespace "
            "(<code>line.strip() for line in text.splitlines() if line.strip()</code>). "
            "Perfect for line-oriented records: name lists, logs, CSV rows. This is "
            '<code>ChunkingStrategy.LINE</code> = <code>"line"</code>. anvil\'s bundled '
            "demo name corpus uses exactly this shape — one name per line, one training "
            "sample per name."
        ),
    },
    {
        "key": "windowed",
        "title": "Strategy 3: Fixed-Size Window",
        "body": (
            "<code>FixedSizeWindowChunker(block_size, overlap)</code> slides a fixed-width "
            "window across the text. The stride between windows is "
            "<code>max(1, int(block_size * (1 - overlap)))</code> — so "
            "<code>overlap=0.0</code> gives disjoint windows and <code>overlap=0.5</code> "
            "(the default) advances by half a window each step, covering the text densely. "
            "The final window may be shorter than <code>block_size</code>. This is the "
            "default strategy (<code>ChunkingStrategy.WINDOWED</code> = "
            '<code>"windowed"</code>) and the right choice for continuous prose.'
        ),
    },
    {
        "key": "overlap-tradeoff",
        "title": "The Overlap Trade-off",
        "body": (
            "Overlap is validated to the half-open range <code>[0.0, 1.0)</code> — exactly "
            "<code>1.0</code> is rejected because it would produce zero stride and loop "
            "forever. More overlap means more chunks (more training examples) and fewer "
            "boundaries where a pattern gets split across two windows — but also more "
            "duplicated text and slower training. Less overlap is leaner but risks cutting "
            "a recurring sequence exactly at a window edge. The 50% default is a balanced "
            "starting point."
        ),
    },
    {
        "key": "chunking-feeds-training",
        "title": "From Chunks to Training",
        "body": (
            "When you train from a corpus, <code>TrainingService._load_docs</code> picks "
            "the chunker named in the corpus's chunk config, runs every file through it, "
            "and the resulting list of strings becomes the training documents — each one "
            "BOS-wrapped and fed through the loop you saw in the Training Loop lesson. The "
            "auto-detection on the Datasets page is just choosing which of these three "
            "<code>Chunker</code> subclasses to instantiate."
        ),
    },
]

CONTENT_VERSIONING_STEPS = [
    {
        "key": "why-version-data",
        "title": "Why Version Your Data?",
        "body": (
            "Reproducibility in ML is impossible if the data can silently change. anvil's "
            "content repository is a Git-like substrate for training data: every "
            "byte is content-addressed, every snapshot is an immutable version, and every "
            "training run records exactly which version it consumed. It is pure-Python and "
            "local-first, living under <code>anvil/services/content/</code>."
        ),
        "widget": "contentVersioning",
    },
    {
        "key": "content-addressing",
        "title": "Content-Addressed Blobs",
        "body": (
            "Every piece of content is stored as a <b>blob</b> keyed by its SHA-256 hash. "
            "The store computes <code>hashlib.sha256(raw).hexdigest()</code> and writes the "
            "bytes to <code>blobs/&lt;first-2-hex-chars&gt;/&lt;full-sha256&gt;</code>. "
            "Because the address <i>is</i> the hash, identical content is automatically "
            "deduplicated — if the blob already exists on disk, the write is skipped. The "
            "<code>content_hash</code> (64 hex chars) is the primary key of the "
            "<code>ContentBlob</code> table, enforcing uniqueness at the database level too."
        ),
    },
    {
        "key": "manifest",
        "title": "The Manifest",
        "body": (
            "A <b>manifest</b> describes one version of a corpus: its "
            "<code>corpus_slug</code>, <code>version_number</code>, the chunking config "
            "(<code>strategy</code>, <code>block_size</code>, <code>chunk_overlap</code>), "
            "and an ordered list of entries. Each <code>ManifestEntry</code> carries a "
            "<code>path</code>, the blob's <code>content_hash</code>, and a "
            "<code>weight</code> (default 1.0). The manifest is then itself hashed: entries "
            "are sorted, serialized to canonical JSON, and SHA-256'd into a "
            "<code>manifest_digest</code> — an immutable fingerprint of the entire snapshot."
        ),
    },
    {
        "key": "versions-and-refs",
        "title": "Versions and VersionRefs",
        "body": (
            "A <code>VersionRef</code> pins a snapshot by combining the human-facing "
            "<code>version_number</code> and optional <code>label</code> with the "
            "content-addressed <code>manifest_digest</code> and internal "
            "<code>version_id</code>. New versions increment monotonically: "
            "<code>max(existing version_numbers) + 1</code>, starting at 1. Because the "
            "digest is derived from content, you can never confuse two different snapshots "
            "that happen to share a version number — the hash always disambiguates."
        ),
    },
    {
        "key": "weight-replication",
        "title": "Weight-Based Replication",
        "body": (
            "Each entry has a <code>weight</code> that controls how much it contributes to "
            "training. The rule is deliberately simple integer replication: "
            "<code>factor = max(1, round(weight))</code>, and each entry's chunks are added "
            "to the training set <code>factor</code> times. So a weight of 3 triples an "
            "entry's presence; a weight of 0.4 still contributes once (the floor of 1). "
            "This is replication, not probabilistic sampling — predictable and "
            "reproducible."
        ),
    },
    {
        "key": "lineage-and-locks",
        "title": "Lineage and Locks",
        "body": (
            "When a run trains on a version, <code>LineageService</code> records a "
            "<code>VersionRunRef</code> row linking the <code>version_id</code> to the "
            "MLflow run UUID and a <code>corpus_ref</code>. That join table is the audit "
            "trail: from any trained model you can trace the MLflow run back to the exact "
            "<code>manifest_digest</code> of the data it learned from. <code>LockService</code> "
            "adds advisory checkout locks (acquire / release / list) scoped like "
            '<code>"corpus:42"</code>, so collaborators can coordinate edits without '
            "clobbering each other."
        ),
    },
]

EXPERIMENT_TRACKING_STEPS = [
    {
        "key": "what-is-a-run",
        "title": "What is an Experiment Run?",
        "body": (
            "Every time you train, anvil opens an <b>MLflow run</b> — a record that "
            "captures the hyperparameters, the loss curve, the final samples, and the "
            "exported model artifacts in one place. The <code>TrackingService</code> "
            "(<code>anvil/services/tracking/tracking.py</code>) is the thin async wrapper "
            "around the MLflow client that anvil uses for all of this. Runs live in the "
            '"anvil" experiment so the Experiments page can list and compare them.'
        ),
        "widget": "experimentTracking",
    },
    {
        "key": "params-logged",
        "title": "Logging Hyperparameters",
        "body": (
            "At the start of a run, <code>start_run</code> logs every hyperparameter as an "
            "MLflow <i>param</i>: <code>n_layer</code>, <code>n_embd</code>, "
            "<code>n_head</code>, <code>block_size</code>, <code>num_steps</code>, "
            "<code>learning_rate</code>, <code>beta1</code>, <code>beta2</code>, "
            "<code>temperature</code>, plus the resolved <code>engine_backend</code> "
            "(STDLIB/TORCH) and <code>device</code> (cpu/cuda:0/mps). Params are immutable "
            "for the life of the run — they describe the experiment's configuration."
        ),
    },
    {
        "key": "metrics-logged",
        "title": "Logging Metrics",
        "body": (
            "Unlike params, <i>metrics</i> are time series. Every training step calls "
            '<code>log_metric(run_id, "loss", value, step=step)</code>, building the loss '
            "curve you scrub through in the Training Loop lesson. At completion, "
            '<code>log_final_metric("final_loss", ...)</code> records the terminal value '
            "with no step. Tags like <code>anvil.status</code>, "
            "<code>architectures=LlamaForCausalLM</code>, and an "
            "<code>anvil.input_digest</code> (the SHA-256 of the dataset/corpus that fed "
            "the run) round out the record."
        ),
    },
    {
        "key": "artifacts-and-registry",
        "title": "Artifacts and the Model Registry",
        "body": (
            "When a run finishes, its artifacts are uploaded: <code>samples.txt</code>, "
            "<code>model.safetensors</code>, <code>config.json</code>, "
            "<code>tokenizer.json</code>, plus the MLflow <code>MLmodel</code> and "
            "<code>conda.yaml</code> descriptors. Then the model is registered in the "
            "<b>Model Registry</b> under a sanitized name — <code>dataset-{id}</code>, "
            "<code>corpus-{id}</code>, or <code>demo</code> — with the source pinned as a "
            "<code>runs:/{run_id}/</code> URI. Each registration auto-increments the "
            "model's version number."
        ),
    },
    {
        "key": "primary-lineage",
        "title": "MLflow as Primary Lineage",
        "body": (
            "anvil treats MLflow as the source of truth for trained models. At "
            "inference time, <code>InferenceService</code> resolves a model first from the "
            "local artifact cache, then from the MLflow Model Registry — downloading the "
            "registered artifacts on demand. The exported model is MLflow-pyfunc compliant: "
            "the <code>MLmodel</code> file names "
            "<code>anvil._pyfunc_model.AnvilPyfuncModel</code> as its loader, so "
            '<code>mlflow.pyfunc.load_model("models:/dataset-42/3")</code> works in any '
            "MLflow-aware tool."
        ),
    },
    {
        "key": "degraded-mode",
        "title": "Fire-and-Forget by Design",
        "body": (
            "Tracking must never break training. The <code>TrackingService</code> is "
            "deliberately <b>fire-and-forget</b>: if MLflow is unreachable, it sets an "
            "internal <code>_degraded</code> flag and every logging call becomes a silent "
            "no-op. Training continues, the model still trains and exports — only the "
            "experiment record is skipped. This is the opposite of the governance "
            "<code>AuditService</code>, which deliberately <i>raises</i> on failure because "
            "an audit trail with silent gaps would be worthless. Two subsystems, two "
            "opposite error philosophies, each correct for its job."
        ),
    },
]

GOVERNANCE_STEPS = [
    {
        "key": "why-governance",
        "title": "Why Data Governance?",
        "body": (
            "A model is only as trustworthy as the data it learned from. anvil ships a "
            "governance layer so that data inclusion is lawful, attributed, and "
            "auditable. It rests on three pillars: machine-readable <b>provenance</b>, a "
            "tamper-evident <b>audit trail</b>, and an <b>acceptable-use gate</b> on every "
            "submission. The code lives in <code>anvil/services/governance/</code>."
        ),
        "widget": "governance",
    },
    {
        "key": "provenance",
        "title": "Provenance: Where Data Came From",
        "body": (
            "Bundled sample data carries a <code>provenance.json</code> manifest shipped "
            "inside the wheel. Each item records its <code>source</code>, "
            "<code>license</code>, and <code>attribution</code> — for example, Alice in "
            'Wonderland is tagged <code>license: "Public Domain"</code> with its Project '
            "Gutenberg source. The <code>Dataset</code> and <code>Corpus</code> tables "
            "gained five provenance columns: <code>source_description</code>, "
            "<code>license_id</code> (a foreign key into the license catalog), "
            "<code>attribution_text</code>, <code>origin</code> "
            '(<code>"bundled"</code> or <code>"user"</code>), and '
            "<code>parent_provenance_ref</code> for derived data."
        ),
    },
    {
        "key": "license-catalog",
        "title": "The License Catalog",
        "body": (
            "An approved-license catalog (<code>license_catalog</code> table) is seeded at "
            "startup with a broad permissive set: Public Domain, CC0-1.0, MIT, "
            "BSD-2-Clause, BSD-3-Clause, Apache-2.0, CC-BY-4.0, CC-BY-SA-4.0, and "
            "Generated/Original. Attribution-required licenses (the CC-BY family) are "
            "flagged <code>requires_attribution=True</code>. A special "
            '<code>"own-content"</code> sentinel covers private/proprietary user data — '
            "it is marked non-redistributable, exempting it from the approved-license "
            "requirement while still being recorded."
        ),
    },
    {
        "key": "acceptable-use-gate",
        "title": "The Acceptable-Use Gate",
        "body": (
            "Every upload and import must pass a gate. The submitter declares a "
            "<code>declared_source</code>, picks a <code>license_identifier</code> (an "
            'approved license or <code>"own-content"</code>), and sets '
            "<code>acceptable_use_affirmed=true</code>. The gate is "
            "<b>declaration-only</b> — there is deliberately no keyword, PII, or ML content "
            "scanning; it is an honest-affirmation model. Missing a source, a license, or "
            "the affirmation yields a rejection (HTTP 422) with a clear, respectful "
            "explanation rather than a cryptic error."
        ),
    },
    {
        "key": "hash-chained-audit",
        "title": "The Hash-Chained Audit Trail",
        "body": (
            "Every consequential event — seed, upload, import, curate, delete, takedown, "
            "policy accept/reject — is appended to an <code>audit_events</code> table. Each "
            "entry stores a SHA-256 <code>entry_hash</code> computed over its canonical "
            "fields <b>including the previous entry's hash</b>. The genesis entry uses 64 "
            "zeros as its <code>prev_hash</code>. This is the same blockchain-style linkage "
            "you may know from Git commits: change any past entry and every subsequent hash "
            "stops matching."
        ),
    },
    {
        "key": "chain-verification",
        "title": "Verifying Integrity",
        "body": (
            "<code>AuditService.verify_chain()</code> recomputes every entry's hash and "
            "checks each <code>prev_hash</code> linkage, returning a "
            "<code>ChainVerifyResult</code> with <code>valid</code>, the first "
            "<code>break_at_sequence</code> if broken, and <code>entries_checked</code>. "
            "Crucially, unlike the fire-and-forget MLflow tracker, <code>AuditService</code> "
            "<b>raises</b> on any write failure so the transaction rolls back — a gap in the "
            "audit trail is never silently tolerated. Tamper detection beats convenience "
            "when the whole point is accountability."
        ),
    },
]


MEMORY_DIVERGENCE_STEPS = [
    {
        "key": "why-pre-flight",
        "title": "Knowing Before You Train",
        "body": (
            "Two things can ruin a training run: running out of memory before it even "
            "starts, and the loss exploding to infinity once it does. anvil guards both. "
            "A pre-flight <b>memory estimator</b> predicts the footprint of a config "
            "before launch, and a runtime <b>divergence detector</b> halts the run the "
            "instant the loss goes non-finite. This lesson covers both safety nets."
        ),
        "widget": "memoryDivergence",
    },
    {
        "key": "memory-breakdown",
        "title": "What Uses Memory",
        "body": (
            "<code>estimate_training_memory</code> counts parameters with the same formula "
            "the model uses, then sizes four FP32 (4-byte) buffers: <b>weights</b> "
            "(1x params), <b>gradients</b> (1x params), the <b>Adam optimizer</b> state "
            "(2x params, for the m and v moments), and the <b>KV cache</b> "
            "(<code>n_layer x 2 x block_size x n_embd x 4</code> bytes). Their sum is the "
            "<code>total</code>; the optimizer alone is the single largest consumer at "
            "twice the model's own weight footprint."
        ),
    },
    {
        "key": "peak-and-headroom",
        "title": "Peak vs Total",
        "body": (
            "Total isn't the whole story — the backward pass holds activations alive too. "
            "The estimator applies a conservative 2x headroom factor: "
            "<code>peak = total * 2</code>. That peak is what gets compared against "
            "available memory, because peak is what actually triggers an "
            "out-of-memory error."
        ),
    },
    {
        "key": "oom-prediction",
        "title": "Predicting OOM",
        "body": (
            "The estimator detects the device (CUDA reports free VRAM; MPS uses total "
            "system memory as the ceiling) and computes <code>peak / available</code>. "
            "Above 90% it sets <code>would_oom=True</code> and warns the run will likely "
            "fail; above 75% it warns you are close to the limit; below that it is clear. "
            "On CPU it never hard-blocks — system RAM and virtual memory absorb the "
            "overflow, just slowly. This is why the tiny defaults "
            "(<code>n_embd=16</code>, <code>n_layer=1</code>) always fit anywhere."
        ),
    },
    {
        "key": "what-is-divergence",
        "title": "When Training Diverges",
        "body": (
            "Sometimes the loss doesn't just plateau — it blows up. A learning rate that's "
            "too high, or pathological data, can push the loss to <code>NaN</code> "
            "(not-a-number) or <code>Inf</code> (infinity). Once that happens, every "
            "subsequent gradient is poisoned and the run is unrecoverable. anvil classifies "
            "this with <code>classify_divergence(loss)</code>, which returns "
            "<code>DivergenceReason.LOSS_NAN</code>, <code>LOSS_INF</code>, or "
            "<code>None</code> if the loss is still finite."
        ),
    },
    {
        "key": "divergence-handling",
        "title": "Halting on Divergence",
        "body": (
            "The training progress callback checks every step. The moment "
            "<code>classify_divergence</code> returns a reason, it emits a "
            "<code>divergence</code> SSE event to the dashboard and raises "
            "<code>DivergenceError</code> to stop the loop immediately — no point burning "
            "compute on a dead run. The run is flagged as diverged so the UI can explain "
            "what happened. Stopping fast and loudly beats silently producing a broken "
            "model, the same accountability instinct behind the audit trail."
        ),
    },
]


@router.get("/learn", response_class=HTMLResponse)
async def learn_index(request: Request) -> HTMLResponse:
    """Render the learning hub index page with ordered lessons and additional sections."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]  # type: ignore[no-any-return]
        request,
        "archetypes/learn-index.html",
        {"lessons": LEARNING_ARC_LESSONS, "additional": LEARNING_ARC_ADDITIONAL},
    )


@router.get("/learn/data-fundamentals", response_class=HTMLResponse)
async def data_fundamentals_page(request: Request) -> HTMLResponse:
    """Render the data fundamentals walkthrough with pipeline diagram and steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/data-fundamentals.html",
        {"steps": DATA_FUNDAMENTALS_STEPS, **_arc_context("data-fundamentals")},
    )


@router.get("/learn/attention", response_class=HTMLResponse)
async def attention_concept_page(request: Request) -> HTMLResponse:
    """Render the attention mechanism walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": ATTENTION_STEPS, **_arc_context("attention")},
    )


@router.get("/learn/tokenization", response_class=HTMLResponse)
async def tokenization_concept_page(request: Request) -> HTMLResponse:
    """Render the tokenization walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": TOKENIZATION_STEPS, **_arc_context("tokenization")},
    )


@router.get("/learn/embeddings", response_class=HTMLResponse)
async def embeddings_concept_page(request: Request) -> HTMLResponse:
    """Render the embeddings walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": EMBEDDING_STEPS, **_arc_context("embeddings")},
    )


@router.get("/learn/sampling", response_class=HTMLResponse)
async def sampling_concept_page(request: Request) -> HTMLResponse:
    """Render the sampling walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": SAMPLING_STEPS, **_arc_context("sampling")},
    )


@router.get("/learn/training-loop", response_class=HTMLResponse)
async def training_loop_concept_page(request: Request) -> HTMLResponse:
    """Render the training loop walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": TRAINING_LOOP_STEPS, **_arc_context("training-loop")},
    )


@router.get("/learn/autograd", response_class=HTMLResponse)
async def autograd_concept_page(request: Request) -> HTMLResponse:
    """Render the autograd walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": AUTOGRAD_STEPS, **_arc_context("autograd")},
    )


@router.get("/learn/loss", response_class=HTMLResponse)
async def loss_concept_page(request: Request) -> HTMLResponse:
    """Render the loss functions walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": LOSS_STEPS, **_arc_context("loss")},
    )


@router.get("/learn/parameters", response_class=HTMLResponse)
async def params_concept_page(request: Request) -> HTMLResponse:
    """Render the model parameters walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": PARAMS_STEPS, **_arc_context("parameters")},
    )


@router.get("/learn/adam", response_class=HTMLResponse)
async def adam_concept_page(request: Request) -> HTMLResponse:
    """Render the Adam optimizer walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": ADAM_STEPS, **_arc_context("adam")},
    )


@router.get("/learn/architecture", response_class=HTMLResponse)
async def architecture_concept_page(request: Request) -> HTMLResponse:
    """Render the transformer architecture walkthrough page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/architecture.html",
        {"steps": ARCHITECTURE_STEPS, **_arc_context("architecture")},
    )


@router.get("/learn/export", response_class=HTMLResponse)
async def export_concept_page(request: Request) -> HTMLResponse:
    """Render the model export walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": EXPORT_STEPS, **_arc_context("export")},
    )


@router.get("/learn/chunking", response_class=HTMLResponse)
async def chunking_concept_page(request: Request) -> HTMLResponse:
    """Render the chunking strategies walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": CHUNKING_STEPS, **_arc_context("chunking")},
    )


@router.get("/learn/content-versioning", response_class=HTMLResponse)
async def content_versioning_concept_page(request: Request) -> HTMLResponse:
    """Render the content versioning walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": CONTENT_VERSIONING_STEPS, **_arc_context("content-versioning")},
    )


@router.get("/learn/experiment-tracking", response_class=HTMLResponse)
async def experiment_tracking_concept_page(request: Request) -> HTMLResponse:
    """Render the experiment tracking walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": EXPERIMENT_TRACKING_STEPS, **_arc_context("experiment-tracking")},
    )


@router.get("/learn/governance", response_class=HTMLResponse)
async def governance_concept_page(request: Request) -> HTMLResponse:
    """Render the data governance walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": GOVERNANCE_STEPS, **_arc_context("governance")},
    )


@router.get("/learn/memory-divergence", response_class=HTMLResponse)
async def memory_divergence_concept_page(request: Request) -> HTMLResponse:
    """Render the memory and divergence walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": MEMORY_DIVERGENCE_STEPS, **_arc_context("memory-divergence")},
    )


GLOSSARY_TERMS = [
    {
        "name": "anvil (core engine)",
        "definition": "The core Llama training engine — ~200 lines of pure Python, zero dependencies.",
    },
    {
        "name": "God Class",
        "definition": "<code>AnvilWorkbench</code> — single entry point exposing all service methods to routes/CLI/tests.",
    },
    {
        "name": "FileStore",
        "definition": "Pluggable async file storage abstraction (local filesystem or S3).",
    },
    {
        "name": "Repository",
        "definition": "Data access class encapsulating all DB operations for a single entity.",
    },
    {
        "name": "SSE",
        "definition": "Server-Sent Events — unidirectional HTTP streaming for real-time updates.",
    },
    {
        "name": "UoW",
        "definition": "Unit of Work — transaction boundary spanning multiple repository operations.",
    },
    {
        "name": "ADR",
        "definition": "Architecture Decision Record — documents significant architecture decisions.",
    },
    {
        "name": "Vault",
        "definition": "Obsidian-compatible documentation directory for internal project knowledge.",
    },
    {
        "name": "Constitution",
        "definition": "Project governance document defining non-negotiable principles for codebase work.",
    },
    {
        "name": "Value",
        "definition": "Autograd scalar node in <code>anvil/core/autograd.py</code> — stores <code>data</code>, <code>grad</code>, children and local partial derivatives for reverse-mode AD.",
    },
    {
        "name": "Autograd",
        "definition": "Automatic differentiation via computation graph — forward pass builds DAG, <code>.backward()</code> traverses in topological order applying chain rule.",
    },
    {
        "name": "KV Cache",
        "definition": "Key-Value cache for causal self-attention — per-layer lists appended at each autoregressive step, avoids recomputing previous positions.",
    },
    {
        "name": "RMSNorm",
        "definition": "Root Mean Square Layer Normalization — <code>x / sqrt(mean(x\u00b2) + \u03b5)</code> — the base computation is stateless; learned scale parameters (<code>rms_1</code>, <code>rms_2</code>, <code>rms_final</code>) are applied elementwise after normalization.",
    },
    {
        "name": "Adam",
        "definition": "Adaptive Moment Estimation optimizer — bias-corrected first/second moment estimates (m, v) + linear LR decay, implemented manually in <code>train()</code>. Plain Adam, NOT AdamW.",
    },
    {
        "name": "BOS",
        "definition": "Begin-of-Sequence sentinel token — always <code>len(uchars)</code> (last index in vocabulary), used to delimit documents and stop sampling.",
    },
    {
        "name": "Autoregressive",
        "definition": "Generating one token at a time, conditioning each prediction on all previous tokens via the KV cache.",
    },
    {
        "name": "Softmax",
        "definition": "Normalized exponential function — <code>e^x_i / \u03a3 e^x_j</code> — converts logits to probability distribution over vocabulary.",
    },
    {
        "name": "Cross-Entropy",
        "definition": "Loss function for classification — <code>-log(p_target)</code> — negative log probability of the correct next token.",
    },
    {
        "name": "State Dict",
        "definition": "The model's parameter dictionary — maps weight names (wte, lm_head, rms_final, layer.N.{attn_wq/wk/wv/wo, mlp_gate/up/down, rms_1/rms_2}) to lists of Value objects.",
    },
    {
        "name": "Safetensors",
        "definition": "Safe serialization format for neural network tensors. anvil exports trained models to safetensors with HuggingFace-compatible tensor names.",
    },
    {
        "name": "RoPE",
        "definition": "Rotary Position Embedding — encodes token position by rotating Query and Key vectors by an angle proportional to position. Half-split (rotate_half) convention: dim i paired with dim i + head_dim/2.",
    },
    {
        "name": "SwiGLU",
        "definition": "SiLU-gated gated MLP — replaces ReLU with <code>(SiLU(x\u00b7Wgate) \u2299 x\u00b7Wup)\u00b7Wdown</code>. Three projections (gate, up, down) with <code>intermediate_size = int(8 \u00d7 n_embd / 3)</code>.",
    },
    {
        "name": "Dual Backend",
        "definition": "anvil's CPU and GPU training backends. CPU (<code>train()</code>) uses pure Python with Value autograd. GPU (<code>train_torch()</code>) uses PyTorch tensors.",
    },
    {
        "name": "GPU Bridge",
        "definition": "<code>_load_weights_into_model()</code> — copies GPU-trained weight lists into a CPU LlamaModel for downstream compatibility.",
    },
    {
        "name": "Dataset",
        "definition": "Static collection of text samples where each line in a <code>.txt</code> file becomes one training sample. Supports inline editing, curation (dedup, filter, replace), and export.",
    },
    {
        "name": "Corpus",
        "definition": "Dynamic directory source scanned with glob patterns and chunking strategies (windowed/file/line). Supports gitignore-style include/exclude filtering.",
    },
    {
        "name": "Run-in-Executor",
        "definition": "Python asyncio pattern for offloading blocking/sync code to a thread pool thread, used by <code>TrainingService</code> to run the core engine.",
    },
    {
        "name": "Commitizen",
        "definition": "CLI tool for conventional commit enforcement and semantic version bump management (<code>cz commit</code>, <code>cz bump</code>, <code>cz check</code>).",
    },
    {
        "name": "Conventional Commits",
        "definition": "Structured commit message format: <code>&lt;type&gt;(&lt;scope&gt;): &lt;description&gt;</code>.",
    },
    {
        "name": "SemVer",
        "definition": "Semantic Versioning (<code>MAJOR.MINOR.PATCH</code>) — bump rules: fix\u2192PATCH, feat\u2192MINOR, BREAKING CHANGE\u2192MAJOR.",
    },
    {
        "name": "BUMP_PAT",
        "definition": "Fine-grained GitHub Personal Access Token used by CI workflows to create auto-merge PRs (Contents+PRs+Workflows: write).",
    },
    {
        "name": "ANVIL_MODE",
        "definition": "Env var selecting operating mode (<code>local</code> or <code>saas</code>). Never auto-detected.",
    },
    {
        "name": "Three-Mode Model",
        "definition": "anvil's operating modes: Local User (pip install, SQLite), SaaS User (hosted multi-tenant on AWS), SaaS Developer (docker compose / dev AWS / cdk).",
    },
    {
        "name": "EventBus",
        "definition": "Pluggable async pub/sub abstraction for live training metrics. Local = <code>InProcessEventBus</code> (asyncio.Queue); SaaS = <code>RedisEventBus</code> (ElastiCache).",
    },
    {
        "name": "JobQueue",
        "definition": "Pluggable training-job dispatch abstraction. Local = <code>InProcessJobQueue</code> (immediate task); SaaS = <code>BatchJobQueue</code> (AWS Batch submit).",
    },
    {
        "name": "ComputeBackend",
        "definition": "Pluggable training execution abstraction. Local = stdlib/torch in-process; SaaS = <code>BatchComputeBackend</code> (Batch on EC2).",
    },
    {
        "name": "ResourceSpec",
        "definition": "Structured compute requirement <code>{node_count, gpus_per_node, vcpus, memory_mb, instance_class}</code>.",
    },
    {
        "name": "Organization",
        "definition": "Top-level tenant and billing boundary in SaaS mode. Owns all resources; no query crosses <code>org_id</code>.",
    },
    {
        "name": "Team",
        "definition": "A group of users within an Organization; resources may be team-scoped. Users may belong to multiple teams.",
    },
    {
        "name": "Role",
        "definition": "RBAC role — <code>owner</code>/<code>admin</code>/<code>member</code>/<code>viewer</code>. Assigned at org level, optionally overridden per team.",
    },
    {
        "name": "JobEvent",
        "definition": "Append-only lifecycle event <code>(job_id, sequence)</code> in PostgreSQL — the authoritative record of training-job state.",
    },
    {
        "name": "Reconciler",
        "definition": "Scheduled task that compares Batch/DB/MLflow/S3 state and repairs jobs stuck in non-terminal states beyond a grace period.",
    },
    {
        "name": "UsageRecord",
        "definition": "Per-job billback record (GPU-seconds, instance-hours) attributed to <code>org_id</code>/<code>team_id</code>/<code>user_id</code>, derived from terminal <code>JobEvent</code>.",
    },
    {
        "name": "Cognito",
        "definition": "Amazon Cognito User Pools — the SaaS identity provider. App-managed OIDC/JWT validated via <code>aws-jwt-verify</code> + JWKS.",
    },
    {
        "name": "RDS Proxy + IAM Auth",
        "definition": "DB access pattern for SaaS — pods generate short-lived (\u226415 min) IAM tokens from their role; no static DB password ever reaches a pod.",
    },
    {
        "name": "anvil deploy",
        "definition": "Turnkey CLI deploying the full SaaS stack into any AWS account via pre-synthesized, digest-pinned CloudFormation through boto3.",
    },
    {
        "name": "Compute Shape",
        "definition": "One of <code>cpu</code>/<code>gpu</code>/<code>multi-gpu</code>/<code>multi-node</code> — selects the pre-registered Batch job definition and queue.",
    },
    {
        "name": "Chunker",
        "definition": "Strategy that splits text into context-window-sized documents via <code>chunk(text) -> list[str]</code>. Three implementations: <code>FixedSizeWindowChunker</code> (windowed), <code>LineAsDocChunker</code> (line), <code>FileAsDocChunker</code> (file).",
    },
    {
        "name": "Overlap",
        "definition": "Fraction of adjacent windows that overlap in <code>FixedSizeWindowChunker</code>, in <code>[0.0, 1.0)</code>. Stride = <code>max(1, int(block_size * (1 - overlap)))</code>. Default 0.5.",
    },
    {
        "name": "Content Blob",
        "definition": "Content-addressed bytes in the versioned store, keyed by SHA-256 and written to <code>blobs/&lt;hash[:2]&gt;/&lt;hash&gt;</code>. Identical content is deduplicated automatically.",
    },
    {
        "name": "Manifest",
        "definition": "Immutable description of one content version — corpus slug, version number, chunk config, and ordered entries — hashed to a <code>manifest_digest</code> (SHA-256 of canonical JSON).",
    },
    {
        "name": "VersionRef",
        "definition": "Pins a content snapshot by combining <code>version_number</code> and <code>label</code> with the content-addressed <code>manifest_digest</code> and internal <code>version_id</code>.",
    },
    {
        "name": "Weight Replication",
        "definition": "Training-data weighting rule <code>factor = max(1, round(weight))</code>; each content entry's chunks are repeated <code>factor</code> times. Replication, not probabilistic sampling.",
    },
    {
        "name": "MLflow Run",
        "definition": "Experiment record holding a training run's params (hyperparameters), metrics (per-step loss), tags, and artifacts. Logged by <code>TrackingService</code>.",
    },
    {
        "name": "Model Registry",
        "definition": "MLflow registry of trained models, named <code>dataset-{id}</code>/<code>corpus-{id}</code>/<code>demo</code>, source-pinned via a <code>runs:/{run_id}/</code> URI, auto-incrementing versions.",
    },
    {
        "name": "Fire-and-Forget",
        "definition": "<code>TrackingService</code> error policy: if MLflow is unreachable it sets <code>_degraded</code> and silently no-ops, so tracking never breaks training. Opposite of <code>AuditService</code>, which raises.",
    },
    {
        "name": "Provenance",
        "definition": "Machine-readable record of data origin — <code>source</code>, <code>license</code>, <code>attribution</code> — in <code>provenance.json</code> for bundled data and five provenance columns on Dataset/Corpus.",
    },
    {
        "name": "Acceptable-Use Gate",
        "definition": "Declaration-only check on upload/import requiring <code>declared_source</code>, an approved <code>license</code> (or <code>own-content</code>), and <code>acceptable_use_affirmed=true</code>. Rejections return HTTP 422. No content scanning.",
    },
    {
        "name": "Audit Chain",
        "definition": "Append-only <code>audit_events</code> log where each entry's SHA-256 <code>entry_hash</code> covers the previous entry's hash (genesis <code>prev_hash</code> = 64 zeros). <code>verify_chain()</code> detects tampering.",
    },
    {
        "name": "Memory Estimate",
        "definition": "Pre-flight footprint = weights + gradients + Adam (2x params) + KV cache, in FP32, with <code>peak = total x 2</code> for backward-pass activations. Flags likely OOM above 90% of available memory.",
    },
    {
        "name": "Divergence",
        "definition": "Non-finite training loss. <code>classify_divergence(loss)</code> returns <code>DivergenceReason.LOSS_NAN</code> or <code>LOSS_INF</code>; the run emits a <code>divergence</code> SSE event and raises <code>DivergenceError</code> to halt.",
    },
]


@router.get("/learn/faq", response_class=HTMLResponse)
async def faq_page(request: Request) -> HTMLResponse:
    """Render the FAQ walkthrough page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/faq.html",
        {"arc": LEARNING_ARC},
    )


@router.get("/learn/glossary", response_class=HTMLResponse)
async def glossary_page(request: Request) -> HTMLResponse:
    """Render the glossary page with definitions for all technical terms."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/glossary.html",
        {"terms": GLOSSARY_TERMS, "arc": LEARNING_ARC},
    )


@router.get("/learn/cloud-compute", response_class=HTMLResponse)
async def cloud_compute_concept_page(request: Request) -> HTMLResponse:
    """Render the cloud compute walkthrough page with interactive steps."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/concept.html",
        {"steps": CLOUD_COMPUTE_STEPS, **_arc_context("cloud-compute")},
    )


@router.get("/models-page", response_class=HTMLResponse)
async def models_page(request: Request) -> HTMLResponse:
    """Render the model registry page."""
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/models.html",
        {
            "related_lessons": related_lessons("export", "architecture", "graph"),
        },
    )


@router.get("/model-detail/{model_id}", response_class=HTMLResponse)
async def model_detail_page(request: Request, model_id: str) -> HTMLResponse:
    """Render the model detail page for a given model ID.

    Parameters
    ----------
    request : Request
        FastAPI request object.
    model_id : str
        The model ID to display (parsed as integer).

    Returns
    -------
    TemplateResponse
        Model detail page or a 404 response for invalid IDs.
    """
    try:
        parsed = int(model_id)
        if parsed <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
            request,
            "archetypes/model_detail.html",
            {"model_id": 0, "error": f"Invalid model ID: {model_id}"},
            status_code=404,
        )
    return request.app.state.templates.TemplateResponse(  # type: ignore[no-any-return]
        request,
        "archetypes/model_detail.html",
        {"model_id": parsed},
    )


@router.get("/inference/models")
async def list_inference_models() -> dict[str, Any]:
    """List all registered models available for inference.

    Returns
    -------
    dict
        Dict with ``models`` (list of model dicts) and optionally a
        ``message`` if no models are registered.
    """
    from anvil.services.tracking.tracking import TrackingService

    tracking_svc = TrackingService()
    models = await tracking_svc.list_registered_models()
    if not models:
        return {
            "models": [],
            "message": "No models registered. Train an experiment and register it first.",
        }
    return {"models": models}


def _validate_sampling_params(
    body: InferenceSampleBody,
) -> tuple[int | None, float | None]:
    """Validate ``top_k`` and ``top_p`` sampling parameters.

    Parameters
    ----------
    body : InferenceSampleBody
        Request body containing ``top_k`` and ``top_p`` fields.

    Returns
    -------
    tuple of int | None and float | None
        The validated ``top_k`` and ``top_p`` values.

    Raises
    ------
    HTTPException
        If ``top_k`` is not a positive integer, or ``top_p`` is not a
        float in ``(0.0, 1.0]``.
    """
    top_k = body.top_k
    top_p = body.top_p

    if top_k is not None:
        if top_k <= 0:
            raise HTTPException(
                status_code=400, detail="top_k must be a positive integer"
            )

    if top_p is not None:
        if top_p <= 0.0 or top_p > 1.0:
            raise HTTPException(
                status_code=400,
                detail="top_p must be a float in the range (0.0, 1.0]",
            )

    return top_k, top_p


def _build_prompt_ids(
    prompt: str,
    chars: list[str],
    model: LlamaModel,
) -> list[int]:
    """Build prompt token IDs from a prompt string.

    Parameters
    ----------
    prompt : str
        Input prompt text. May be empty.
    chars : list of str
        Vocabulary character list from the loaded model.
    model : object
        Loaded model instance with ``block_size`` attribute.

    Returns
    -------
    list of int
        Prompt token IDs (``BOS`` + character indices), or an empty
        list if no valid prompt is provided. Truncated to
        ``model.block_size``.

    Raises
    ------
    HTTPException
        If ``prompt`` contains a character not in the vocabulary.
    """
    BOS = len(chars)
    if not prompt:
        return []

    try:
        prompt_ids = [BOS] + [chars.index(ch) for ch in prompt]
    except ValueError as err:
        bad_char = next(ch for ch in prompt if ch not in chars)
        raise HTTPException(
            status_code=400,
            detail=f"Character {bad_char!r} not in model vocabulary",
        ) from err

    return prompt_ids[: model.block_size]


def _sample_next_token(
    logits: list[Value],
    temperature: float,
    top_k: int | None,
    top_p: float | None,
    model: LlamaModel,
) -> int:
    """Sample a single token from logits with optional filtering.

    Applies temperature scaling, optional Top-K truncation, optional
    Top-P (nucleus) truncation, then softmax and weighted random
    selection.

    Parameters
    ----------
    logits : list of Value
        Raw logits from the model forward pass.
    temperature : float
        Sampling temperature (divides all logits).
    top_k : int | None
        If set, keep only the top-K highest logits.
    top_p : float | None
        If set, keep the smallest set of logits whose cumulative
        probability exceeds ``top_p``.
    model : object
        Loaded model instance with ``vocab_size`` attribute.

    Returns
    -------
    int
        Sampled token index.
    """
    from anvil.core.autograd import Value

    scaled = [logit / temperature for logit in logits]

    if top_k is not None and 0 < top_k < model.vocab_size:
        sorted_vals = sorted(scaled, key=lambda v: v.data, reverse=True)
        threshold = sorted_vals[top_k - 1].data
        scaled = [v if v.data >= threshold else Value(-1e10) for v in scaled]

    if top_p is not None and 0.0 < top_p < 1.0:
        sorted_vals = sorted(scaled, key=lambda v: v.data, reverse=True)
        sorted_probs = softmax(sorted_vals)
        cumsum = 0.0
        cutoff_idx = 0
        for i, p in enumerate(sorted_probs):
            cumsum += p.data
            if cumsum >= top_p:
                cutoff_idx = i
                break
        else:
            cutoff_idx = len(sorted_vals) - 1
        threshold = sorted_vals[cutoff_idx].data
        scaled = [v if v.data >= threshold else Value(-1e10) for v in scaled]

    probs = softmax(scaled)
    token_id = random.choices(range(model.vocab_size), weights=[p.data for p in probs])[
        0
    ]
    return token_id


def _generate_with_prompt(
    model: LlamaModel,
    prompt_ids: list[int],
    temperature: float,
    top_k: int | None,
    top_p: float | None,
    chars: list[str],
    BOS: int,
    keys: list[list[list[Value]]],
    values: list[list[list[Value]]],
) -> str:
    """Generate a text sample conditioned on a prompt.

    Runs the prompt through the model to warm up the KV cache, then
    auto-regressively samples subsequent tokens until ``BOS`` or
    ``block_size`` is reached.

    Parameters
    ----------
    model : object
        Loaded model instance with ``forward``, ``block_size``, and
        ``vocab_size`` attributes.
    prompt_ids : list of int
        Token IDs for the prompt (including leading ``BOS``).
    temperature : float
        Sampling temperature.
    top_k : int | None
        Top-K filter parameter.
    top_p : float | None
        Top-P filter parameter.
    chars : list of str
        Vocabulary character list.
    BOS : int
        Beginning-of-sequence token ID.
    keys : list of list
        KV-cache key arrays (one per layer).
    values : list of list
        KV-cache value arrays (one per layer).

    Returns
    -------
    str
        Generated text sample (prompt continuation).
    """
    logits = model.forward(prompt_ids[0], 0, keys, values)
    for pos_id in range(1, len(prompt_ids)):
        logits = model.forward(prompt_ids[pos_id], pos_id, keys, values)

    sample = [chars[idx] for idx in prompt_ids[1:]]

    for pos_id in range(len(prompt_ids), model.block_size):
        token_id = _sample_next_token(logits, temperature, top_k, top_p, model)
        if token_id == BOS:
            break
        sample.append(chars[token_id])
        if pos_id < model.block_size - 1:
            logits = model.forward(token_id, pos_id, keys, values)

    return "".join(sample)


def _generate_without_prompt(
    model: LlamaModel,
    temperature: float,
    top_k: int | None,
    top_p: float | None,
    chars: list[str],
    BOS: int,
    keys: list[list[list[Value]]],
    values: list[list[list[Value]]],
) -> str:
    """Generate a text sample from scratch (no prompt).

    Starts with the ``BOS`` token and auto-regressively samples tokens
    until ``BOS`` is re-encountered or ``block_size`` is reached.

    Parameters
    ----------
    model : object
        Loaded model instance with ``forward``, ``block_size``, and
        ``vocab_size`` attributes.
    temperature : float
        Sampling temperature.
    top_k : int | None
        Top-K filter parameter.
    top_p : float | None
        Top-P filter parameter.
    chars : list of str
        Vocabulary character list.
    BOS : int
        Beginning-of-sequence token ID.
    keys : list of list
        KV-cache key arrays (one per layer).
    values : list of list
        KV-cache value arrays (one per layer).

    Returns
    -------
    str
        Generated text sample.
    """
    token_id = BOS
    sample: list[str] = []

    for pos_id in range(model.block_size):
        logits = model.forward(token_id, pos_id, keys, values)
        token_id = _sample_next_token(logits, temperature, top_k, top_p, model)
        if token_id == BOS:
            break
        sample.append(chars[token_id])

    return "".join(sample)


def _sample_tokens(
    model: LlamaModel,
    prompt_ids: list[int],
    temperature: float,
    top_k: int | None,
    top_p: float | None,
    num_samples: int,
    chars: list[str],
    BOS: int,
) -> list[str]:
    """Generate multiple text samples from a model.

    Parameters
    ----------
    model : object
        Loaded model instance with ``n_layer``, ``block_size``, and
        ``vocab_size`` attributes.
    prompt_ids : list of int
        Prompt token IDs (may be empty for unconditional generation).
    temperature : float
        Sampling temperature.
    top_k : int | None
        Top-K filter parameter.
    top_p : float | None
        Top-P filter parameter.
    num_samples : int
        Number of samples to generate.
    chars : list of str
        Vocabulary character list.
    BOS : int
        Beginning-of-sequence token ID.

    Returns
    -------
    list of str
        Generated text samples.
    """
    samples: list[str] = []
    for _ in range(num_samples):
        keys: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]
        values: list[list[list[Value]]] = [[] for _ in range(model.n_layer)]

        if prompt_ids:
            sample = _generate_with_prompt(
                model,
                prompt_ids,
                temperature,
                top_k,
                top_p,
                chars,
                BOS,
                keys,
                values,
            )
        else:
            sample = _generate_without_prompt(
                model,
                temperature,
                top_k,
                top_p,
                chars,
                BOS,
                keys,
                values,
            )

        samples.append(sample)

    return samples


@router.post("/inference/sample")
async def inference_sample(body: InferenceSampleBody) -> dict[str, Any]:
    """Generate text samples from a registered model.

    Parameters
    ----------
    body : InferenceSampleBody
        Request body with ``model_id``, ``version``, and optional
        sampling parameters.

    Returns
    -------
    dict
        Generated text samples from the model.

    Raises
    ------
    HTTPException
        If ``model_id`` or ``version`` are missing, or parameters are
        invalid.
    """
    top_k, top_p = _validate_sampling_params(body)

    from anvil.services.inference.inference import InferenceService

    inf_svc = InferenceService()
    try:
        loaded = await inf_svc.load_model(body.model_id, body.version)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    model = loaded.model
    chars = loaded.chars
    BOS = len(chars)

    prompt_ids = _build_prompt_ids(body.prompt, chars, model)
    samples = _sample_tokens(
        model,
        prompt_ids,
        body.temperature,
        top_k,
        top_p,
        body.num_samples,
        chars,
        BOS,
    )

    return {"samples": samples}
