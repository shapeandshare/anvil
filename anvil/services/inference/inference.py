# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Inference service — connects educational widgets to real model data.

Follows layer discipline: services consume repositories, routes call services.
"""

# pylint: disable=protected-access

from __future__ import annotations

import asyncio
import logging
import math
from pathlib import Path
from typing import Any

from mlflow.tracking import MlflowClient

from ...config import get_mlflow_uri
from ...core._tokenizer_base import Tokenizer
from ...core.autograd import Value
from ...core.engine import LlamaModel, softmax
from ..tracking.tracking import TrackingService
from .loaded_model import LoadedModel
from .tokenizer_factory import create_tokenizer

logger = logging.getLogger("anvil.services.inference.tokenizer")


def _is_bos(token_id: int, bos_id: int | None) -> bool:
    """Check if a token ID is the BOS token, handling ``None`` safely."""
    return bos_id is not None and token_id == bos_id


def _token_label(token_id: int, chars: list[str], bos_id: int | None) -> str:
    """Return a human-readable label for a token ID."""
    if _is_bos(token_id, bos_id):
        return "<BOS>"
    if 0 <= token_id < len(chars):
        return chars[token_id]
    return "<?>"


def _top_k_logits(logits: list[float], k: int | None) -> list[float]:
    """Apply top-k filtering to logit values.

    Sets logits below the k-th highest value to a large negative
    number (``-1e10``), effectively zeroing their softmax probability.

    Parameters
    ----------
    logits : list[float]
        Raw logit values from the model output layer.
    k : int or None
        Number of highest logits to keep. ``None`` or ``<=0``
        disables filtering.

    Returns
    -------
    list[float]
        Filtered logits where low-ranking values are suppressed.
    """
    if k is None or k <= 0:
        return logits
    sorted_vals = sorted(logits, reverse=True)
    threshold = sorted_vals[min(k - 1, len(sorted_vals) - 1)]
    return [v if v >= threshold else -1e10 for v in logits]


def _project_to_2d(vectors: list[list[float]]) -> list[dict[str, float]]:
    """Project high-dimensional vectors to 2D using power-iteration PCA.

    Implements a zero-dependency PCA via power iteration: computes
    the top principal component, projects it out, then computes the
    second component from the residual.

    Parameters
    ----------
    vectors : list[list[float]]
        Input vectors, each of equal dimension.

    Returns
    -------
    list[dict[str, float]]
        Projected coordinates as ``{"x": ..., "y": ...}`` dicts.
    """
    if not vectors:
        return []
    n_dim = len(vectors[0])
    if n_dim <= 2:
        return [
            {"x": v[0] if n_dim > 0 else 0.0, "y": v[1] if n_dim > 1 else 0.0}
            for v in vectors
        ]

    n_pts = len(vectors)
    means = [sum(v[d] for v in vectors) / n_pts for d in range(n_dim)]
    centered = [[v[d] - means[d] for d in range(n_dim)] for v in vectors]

    def power_iterate(data: list[list[float]], num_iters: int = 20) -> list[float]:
        vec = [1.0 / (n_dim**0.5)] * n_dim
        for _ in range(num_iters):
            # v = data^T @ (data @ vec)
            tmp = [sum(row[d] * vec[d] for d in range(n_dim)) for row in data]
            new_vec = [
                sum(data[i][d] * tmp[i] for i in range(n_pts)) for d in range(n_dim)
            ]
            norm = sum(x * x for x in new_vec) ** 0.5
            if norm > 1e-12:
                new_vec = [x / norm for x in new_vec]
            vec = new_vec
        return vec

    pc1 = power_iterate(centered)
    # Project out PC1
    residual = [
        [v[d] - pc1[d] * sum(v[j] * pc1[j] for j in range(n_dim)) for d in range(n_dim)]
        for v in centered
    ]
    pc2 = power_iterate(residual)

    projections = []
    for v in centered:
        projections.append(
            {
                "x": sum(v[d] * pc1[d] for d in range(n_dim)),
                "y": sum(v[d] * pc2[d] for d in range(n_dim)),
            }
        )
    return projections


class InferenceService:
    """Business logic for inference endpoints.

    Methods are async when they touch DB; sync for pure computation.
    Supports tokenization, embedding extraction, attention visualisation,
    sampling distribution computation, forward/backward computation
    graph traversal, and model parameter introspection.
    """

    def __init__(self) -> None:
        """Initialise the inference service with an empty model cache."""
        self._cache: dict[tuple[int, int], tuple[LlamaModel, Tokenizer]] = {}
        self._default_id: int | None = None

    async def load_model(
        self,
        model_id: int | None = None,
        version: int | None = None,
    ) -> LoadedModel:
        """Load a model by experiment ID and optional version.

        Resolution order: in-memory cache, experiment artifact file
        (``data/models/experiment_{id}.json``), then MLflow Model Registry.
        When ``model_id`` is ``None``, resolves to the demo model via
        :meth:`_resolve_default_id`.

        Parameters
        ----------
        model_id : int, optional
            The experiment ID. ``None`` resolves a default (demo model).
        version : int, optional
            Model version in the registry. Defaults to ``1``.

        Returns
        -------
        LoadedModel
            Container with the loaded model, vocabulary, and metadata.

        Raises
        ------
        ValueError
            If no model is found for the given ID and version.
        """
        if model_id is None:
            model_id = await self._resolve_default_id()

        version = version if version is not None else 1
        cache_key = (model_id, version)
        if cache_key in self._cache:
            gpt_model, tokenizer = self._cache[cache_key]
            return LoadedModel(gpt_model, tokenizer, model_id, version, "cached")

        # Primary path: load from saved experiment artifact
        model_path = Path(f"data/models/experiment_{model_id}.json")
        if model_path.exists():
            gpt_model = LlamaModel.load(str(model_path))
            if gpt_model.chars is None:
                raise ValueError("Model has no character mapping")
            name = f"experiment-{model_id}"
            tokenizer = create_tokenizer(
                tokenizer_family=gpt_model.tokenizer_family,
                serialization_type=gpt_model.serialization_type,
                chars=gpt_model.chars,
                artifact_dir=str(model_path.parent),
            )
            self._cache[cache_key] = (gpt_model, tokenizer)
            return LoadedModel(gpt_model, tokenizer, model_id, version, name)

        # Fallback: try loading from MLflow Model Registry
        tracking_svc = TrackingService()
        models = await tracking_svc.list_registered_models()
        model_name: str | None = None
        candidates = {f"dataset-{model_id}", f"corpus-{model_id}", "demo"}
        for m in models:
            if m.get("name") in candidates:
                model_name = m["name"]
                break

        if model_name:
            loop = asyncio.get_event_loop()
            client = MlflowClient(get_mlflow_uri())
            try:
                all_versions = await loop.run_in_executor(
                    None,
                    lambda: client.search_model_versions(f"name='{model_name}'"),
                )
                if all_versions:
                    sorted_versions = sorted(
                        all_versions, key=lambda v: int(v.version), reverse=True
                    )
                    run_id = sorted_versions[0].run_id
                    if run_id is None:
                        raise ValueError("MLflow run_id is None")
                    local_dir = await loop.run_in_executor(
                        None,
                        lambda: client.download_artifacts(
                            run_id=run_id, path="", dst_path=None
                        ),
                    )
                    model_file = Path(local_dir) / "model.json"
                    if model_file.exists():
                        gpt_model = LlamaModel.load(str(model_file))
                        if gpt_model.chars is None:
                            raise ValueError("Model has no character mapping")
                        local_dir_path = Path(local_dir)
                        tokenizer = create_tokenizer(
                            tokenizer_family=gpt_model.tokenizer_family,
                            serialization_type=gpt_model.serialization_type,
                            chars=gpt_model.chars,
                            artifact_dir=str(local_dir_path),
                        )
                        self._cache[cache_key] = (gpt_model, tokenizer)
                        return LoadedModel(
                            gpt_model, tokenizer, model_id, version, model_name
                        )
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        raise ValueError(f"Model not found: model_id={model_id}, version={version}")

    async def _resolve_default_id(self) -> int:
        """Resolve the default model (demo) to its numeric experiment ID.

        Resolution order: in-memory cache, MLflow Model Registry (preferring
        a model named ``"demo"``), then the filesystem for
        ``data/models/experiment_1.json`` (the inline fallback path).
        Raises ``ValueError`` when no model is found.

        Returns
        -------
        int
            The experiment ID of the default model.
        """
        if self._default_id is not None:
            return self._default_id

        tracking_svc = TrackingService()
        models = await tracking_svc.list_registered_models()

        if models:
            for m in models:
                if m.get("name") == "demo" and m.get("id") is not None:
                    mid = m["id"]
                    assert isinstance(mid, int)
                    self._default_id = mid
                    return mid
            for m in models:
                mid = m.get("id")
                if isinstance(mid, int):
                    self._default_id = mid
                    return mid

        # Filesystem fallback: scan for any experiment_<N>.json artifact that
        # the warmup pipeline or seed script may have created.
        models_dir = Path("data/models")
        fallback = models_dir / "experiment_1.json"
        if not fallback.exists() and models_dir.is_dir():
            candidates = sorted(models_dir.glob("experiment_*.json"))
            if candidates:
                fallback = candidates[0]
        if fallback.exists():
            try:
                model_id = int(fallback.stem.split("_")[1])
            except (IndexError, ValueError):
                model_id = 1
            self._default_id = model_id
            return model_id

        raise ValueError("No models available. Train or bootstrap a model first.")

    def tokenize(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        """Tokenise text and return token metadata.

        Parameters
        ----------
        text : str
            Input text to tokenise.
        loaded : LoadedModel
            The loaded model and tokenizer.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"tokens"`` (list of char/ID
            pairs), ``"vocab_size"``, and ``"bos_id"``.
        """
        logger.info(
            "Encode: model=%s, family=%s, text_len=%d",
            loaded.name,
            getattr(loaded.model, "tokenizer_family", "?"),
            len(text),
        )
        ids = loaded.tokenizer.encode(text)
        return {
            "model": loaded.info(),
            "tokens": [
                {
                    "char": _token_label(i, loaded.chars, loaded.bos_id),
                    "id": i,
                }
                for i in ids
            ],
            "vocab_size": loaded.tokenizer.vocab_size,
            "bos_id": loaded.bos_id,
        }

    def embeddings(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        """Compute embedding vectors for each token in the input text.

        Projects embeddings to 2D for visualisation via PCA.

        Parameters
        ----------
        text : str
            Input text.
        loaded : LoadedModel
            The loaded model and vocabulary.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"tokens"``, ``"vectors"``,
            ``"n_embd"``, and ``"projection"`` (2D coordinates).
        """
        ids = loaded.tokenizer.encode(text)
        wte = loaded.model._get_matrix("wte")
        vectors = []
        labels = []
        for _i, tid in enumerate(ids):
            row = [v.data for v in wte[tid]]
            vectors.append(row)
            label = _token_label(tid, loaded.chars, loaded.bos_id)
            labels.append({"char": label, "id": tid})

        projection = _project_to_2d(vectors)

        return {
            "model": loaded.info(),
            "tokens": labels,
            "vectors": vectors,
            "n_embd": loaded.model.n_embd,
            "projection": [
                {"x": p["x"], "y": p["y"], "label": labels[i]["char"]}
                for i, p in enumerate(projection)
            ],
        }

    def attention(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        """Compute attention weights for input text.

        Runs a forward-introspect pass to extract per-layer, per-head
        attention weight matrices.

        Parameters
        ----------
        text : str
            Input text.
        loaded : LoadedModel
            The loaded model and vocabulary.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"tokens"``, ``"n_layer"``,
            ``"n_head"``, ``"weights"``, and ``"rope"`` (cos/sin
            tables and head dimension).
        """
        ids = loaded.tokenizer.encode(text)
        max_len = min(loaded.model.block_size, 256)
        ids = ids[:max_len]

        result = loaded.model.forward_introspect(ids)
        weights = result["attention"]

        token_labels = [
            {"char": _token_label(i, loaded.chars, loaded.bos_id), "id": i} for i in ids
        ]

        return {
            "model": loaded.info(),
            "tokens": token_labels,
            "n_layer": loaded.model.n_layer,
            "n_head": loaded.model.n_head,
            "weights": weights,
            "rope": {
                "cos_table": loaded.model._cos_table[:max_len],
                "sin_table": loaded.model._sin_table[:max_len],
                "head_dim": loaded.model.head_dim,
            },
        }

    def sampling_distribution(
        self,
        prompt: str,
        temperature: float,
        top_k: int | None,
        loaded: LoadedModel,
    ) -> dict[str, Any]:
        """Compute the full next-token sampling distribution.

        Runs a forward pass on the prompt, applies temperature scaling
        and top-k filtering, and returns per-token probabilities.

        Parameters
        ----------
        prompt : str
            Input prompt text.
        temperature : float
            Sampling temperature (higher = more random).
        top_k : int or None
            Top-k filter count. ``None`` or ``<=0`` disables filtering.
        loaded : LoadedModel
            The loaded model and vocabulary.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"tokens"`` (per-token details
            including raw logits, scaled logits, probabilities),
            ``"temperature"``, ``"prompt"``, ``"vocab_size"``,
            ``"top_k"``, and ``"top_k_effective"``.
        """
        ids = loaded.tokenizer.encode(prompt)
        n_layers = loaded.model.n_layer
        keys: list[list[list[Value]]] = [[] for _ in range(n_layers)]
        values: list[list[list[Value]]] = [[] for _ in range(n_layers)]
        for pos_id, tid in enumerate(ids):
            loaded.model.forward(tid, pos_id, keys, values)

        last_pos = len(ids)
        fallback_id = loaded.bos_id if loaded.bos_id is not None else 0
        dummy_tid = ids[-1] if ids else fallback_id
        logits = loaded.model.forward(dummy_tid, last_pos - 1, keys, values)

        raw_logits: list[float] = [logit.data for logit in logits]
        scaled: list[float] = [r / temperature for r in raw_logits]
        vocab_size = loaded.tokenizer.vocab_size

        # Determine top-k threshold and compute in_top_k / truncated
        resolved_top_k: int = vocab_size if top_k is None or top_k <= 0 else top_k
        if top_k is None or top_k <= 0:
            in_top_k: list[bool] = [True] * vocab_size
            truncated: list[float] = list(scaled)
        else:
            sorted_vals = sorted(scaled, reverse=True)
            threshold = sorted_vals[min(resolved_top_k - 1, vocab_size - 1)]
            in_top_k = [s >= threshold for s in scaled]
            truncated = [
                s if ok else -1e10 for s, ok in zip(scaled, in_top_k, strict=True)
            ]

        top_k_effective = sum(in_top_k)

        # Softmax over all scaled logits → prob_pre_top_k
        max_pre = max(scaled)
        exps_pre = [math.exp(s - max_pre) for s in scaled]
        total_pre = sum(exps_pre)
        prob_pre_top_k = [e / total_pre for e in exps_pre]

        # Softmax over truncated logits → prob_final
        max_final = max(truncated)
        exps_final = [math.exp(v - max_final) for v in truncated]
        total_final = sum(exps_final)
        probs_final = [e / total_final for e in exps_final]

        all_tokens = []
        for i in range(vocab_size):
            char = _token_label(i, loaded.chars, loaded.bos_id)
            all_tokens.append(
                {
                    "char": char,
                    "id": i,
                    "raw_logit": raw_logits[i],
                    "scaled_logit": scaled[i],
                    "prob_pre_top_k": prob_pre_top_k[i],
                    "prob_final": probs_final[i],
                    "prob": probs_final[i],
                    "in_top_k": in_top_k[i],
                }
            )

        return {
            "model": loaded.info(),
            "tokens": all_tokens,
            "temperature": temperature,
            "prompt": prompt,
            "vocab_size": vocab_size,
            "top_k": resolved_top_k,
            "top_k_effective": top_k_effective,
        }

    def forward_graph(
        self, loaded: LoadedModel, max_nodes: int = 400
    ) -> dict[str, Any]:
        """Compute the forward computation graph (nodes and edges) for the model.

        Runs a single forward pass on the BOS token and traverses the
        ``Value`` graph to extract node operations and their connections.

        Parameters
        ----------
        loaded : LoadedModel
            The loaded model and vocabulary.
        max_nodes : int
            Maximum number of graph nodes to collect. Defaults to ``400``.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"nodes"`` (operation type, value,
            depth), and ``"edges"`` (parent-child relationships).
        """
        n_layers = loaded.model.n_layer
        keys: list[list[list[Value]]] = [[] for _ in range(n_layers)]
        values: list[list[list[Value]]] = [[] for _ in range(n_layers)]
        tid = loaded.bos_id if loaded.bos_id is not None else 0
        logits = loaded.model.forward(tid, 0, keys, values)

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[int] = set()
        node_counter: list[int] = [0]

        def assign_op(val: Value) -> str:
            """Infer operation type from Value structure."""
            n_children = len(val._children)
            if n_children == 0:
                return "input"
            if n_children == 1:
                child = val._children[0]
                if hasattr(child, "_local_grads") and child._local_grads:
                    lg = child._local_grads
                    if len(lg) == 1 and lg[0] != 1.0:
                        return "pow"
                return "silu"
            if n_children == 2:
                parent_types = [type(c).__name__ for c in val._children[:2]]
                if "Value" in parent_types:
                    return "add"
                return "mul"
            return "combine"

        def traverse(v: Value, depth: int = 0) -> str | None:
            if len(nodes) >= max_nodes:
                return None
            v_id = id(v)
            if v_id in visited:
                for n in nodes:
                    if n["id"] == str(v_id):
                        return str(n["id"])
                return str(v_id)
            visited.add(v_id)

            node_id = str(v_id)
            op = assign_op(v)
            label = f"{op}[{depth}]"
            node_counter[0] += 1

            nodes.append(
                {
                    "id": node_id,
                    "op": op,
                    "label": label,
                    "value": round(v.data, 4),
                    "depth": depth,
                }
            )

            for child in v._children:
                child_id = traverse(child, depth + 1)
                if child_id is not None:
                    edges.append({"from": node_id, "to": child_id})

            return node_id

        logit_val = logits[-1]
        traverse(logit_val, depth=0)

        return {
            "model": loaded.info(),
            "nodes": nodes,
            "edges": edges,
        }

    def backward_graph(
        self, text: str, loaded: LoadedModel, max_nodes: int = 400
    ) -> dict[str, Any]:
        """Run forward + backward pass on input text, return computation graph with gradients.

        Runs a forward pass over the input sequence, computes
        cross-entropy loss, runs backpropagation, and traverses the
        ``Value`` graph to extract nodes with gradients.

        Parameters
        ----------
        text : str
            Input text for the forward/backward pass.
        loaded : LoadedModel
            The loaded model and vocabulary.
        max_nodes : int
            Maximum number of graph nodes to collect. Defaults to ``400``.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"nodes"`` (value, gradient,
            local grads, depth), ``"edges"``, and ``"metadata"``
            (total nodes/edges, max depth, input tokens, loss value).
        """
        ids = loaded.tokenizer.encode(text)
        n = min(len(ids) - 1, loaded.model.block_size)
        ids = ids[: n + 1]

        # Forward pass over the sequence
        keys: list[list[list[Value]]] = [[] for _ in range(loaded.model.n_layer)]
        values: list[list[list[Value]]] = [[] for _ in range(loaded.model.n_layer)]
        losses: list[Value] = []
        logits: list[Value] | None = None
        for pos_id in range(n):
            token_id, target_id = ids[pos_id], ids[pos_id + 1]
            logits = loaded.model.forward(token_id, pos_id, keys, values)
            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(loss_t)
        loss = (1.0 / n) * sum(losses)

        # Backward pass
        assert isinstance(loss, Value)
        loss.backward()

        # Traverse graph from the last logit Value
        assert logits is not None
        logit_val = logits[-1]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[int] = set()

        def assign_op(val: Value) -> str:
            n_children = len(val._children)
            if n_children == 0:
                return "input"
            if n_children == 1:
                child = val._children[0]
                if hasattr(child, "_local_grads") and child._local_grads:
                    lg = child._local_grads
                    if len(lg) == 1 and lg[0] != 1.0:
                        return "pow"
                return "silu"
            if n_children == 2:
                parent_types = [type(c).__name__ for c in val._children[:2]]
                if "Value" in parent_types:
                    return "add"
                return "mul"
            return "combine"

        def traverse(v: Value, depth: int = 0) -> str | None:
            if len(nodes) >= max_nodes:
                return None
            v_id = id(v)
            if v_id in visited:
                for n in nodes:
                    if n["id"] == str(v_id):
                        return str(n["id"])
                return str(v_id)
            visited.add(v_id)

            node_id = str(v_id)
            op = assign_op(v)
            label = f"{op}[{depth}]"

            local_grads: list[float] = []
            for lg in v._local_grads:
                if isinstance(lg, (int, float)):
                    local_grads.append(round(float(lg), 6))
                else:
                    local_grads.append(round(lg.data, 6))

            nodes.append(
                {
                    "id": node_id,
                    "op": op,
                    "label": label,
                    "value": round(v.data, 6),
                    "grad": round(v.grad, 6),
                    "local_grads": local_grads,
                    "depth": depth,
                }
            )

            for child in v._children:
                child_id = traverse(child, depth + 1)
                if child_id is not None:
                    edges.append({"from": node_id, "to": child_id})

            return node_id

        traverse(logit_val, depth=0)

        max_depth = max((n.get("depth", 0) for n in nodes), default=0)
        token_labels = [
            {"char": _token_label(i, loaded.chars, loaded.bos_id), "id": i} for i in ids
        ]

        return {
            "model": loaded.info(),
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "max_depth": max_depth,
                "input_tokens": token_labels,
                "loss_value": round(loss.data, 6),
            },
        }

    def autograd_example_graph(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        """Return a small, complete teaching graph computed by the real Value engine.

        Companion to :meth:`backward_graph`: the full model graph is hundreds of
        nodes deep, so the lesson's concepts (SiLU, gradient accumulation) are
        unreadable there. This builds a tiny single-neuron-with-loss expression
        seeded with genuine embedding scalars from ``text`` and runs an authentic
        forward + backward pass, so every value and gradient is real at a legible
        scale. Same response schema as :meth:`backward_graph`.
        """
        ids = loaded.tokenizer.encode(text)
        seed_fallback = loaded.bos_id if loaded.bos_id is not None else 0
        seed_id = next(
            (t for t in ids if not _is_bos(t, loaded.bos_id)),
            ids[0] if ids else seed_fallback,
        )
        wte = loaded.model._get_matrix("wte")
        row = [v.data for v in wte[seed_id]]

        def _seed(i: int, fallback: float) -> float:
            return round(float(row[i]), 4) if i < len(row) else fallback

        x_val = _seed(0, 0.5)
        w1_val = _seed(1, 0.8)
        w2_val = _seed(2, -0.4)
        b_val = _seed(3, 0.1)
        target = 1.0

        op_by_id: dict[int, str] = {}

        def reg(value: Value, op: str) -> Value:
            op_by_id[id(value)] = op
            return value

        x = reg(Value(x_val), "input")
        w1 = reg(Value(w1_val), "input")
        w2 = reg(Value(w2_val), "input")
        b = reg(Value(b_val), "input")
        neg_target = reg(Value(-target), "input")

        weighted_1 = reg(x * w1, "mul")
        weighted_2 = reg(x * w2, "mul")  # x reused -> its gradient accumulates here
        summed = reg(weighted_1 + weighted_2, "add")
        pre_activation = reg(summed + b, "add")
        activation = reg(pre_activation.silu(), "silu")
        prediction_error = reg(activation + neg_target, "add")
        loss = reg(prediction_error**2, "pow")

        loss.backward()

        order: list[Value] = []
        visited_ids: set[int] = set()
        edges: list[dict[str, Any]] = []
        stack: list[Value] = [loss]
        while stack:
            v = stack.pop()
            v_id = id(v)
            if v_id in visited_ids:
                continue
            visited_ids.add(v_id)
            order.append(v)
            for child in v._children:
                edges.append({"from": str(v_id), "to": str(id(child))})
                stack.append(child)

        # Longest path from the loss (root=0) so edges always flow downward and a
        # reused input settles at its deepest layer (Bellman-Ford relaxation on a DAG).
        depth: dict[int, int] = {id(loss): 0}
        children_ids = {id(v): [id(c) for c in v._children] for v in order}
        for _ in range(len(order)):
            for v in order:
                d = depth.get(id(v), 0)
                for child_id in children_ids[id(v)]:
                    if depth.get(child_id, -1) < d + 1:
                        depth[child_id] = d + 1

        nodes: list[dict[str, Any]] = []
        for v in order:
            v_id = id(v)
            op = op_by_id.get(v_id, "combine")
            local_grads = [round(float(lg), 6) for lg in v._local_grads]
            nodes.append(
                {
                    "id": str(v_id),
                    "op": op,
                    "label": f"{op}[{depth[v_id]}]",
                    "value": round(v.data, 6),
                    "grad": round(v.grad, 6),
                    "local_grads": local_grads,
                    "depth": depth[v_id],
                }
            )

        max_depth = max(depth.values(), default=0)
        token_labels = [
            {"char": _token_label(i, loaded.chars, loaded.bos_id), "id": i} for i in ids
        ]

        return {
            "model": loaded.info(),
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "max_depth": max_depth,
                "input_tokens": token_labels,
                "loss_value": round(loss.data, 6),
            },
        }

    def loss_breakdown(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        """Compute per-token cross-entropy loss for input text.

        Runs a forward pass for each position in the sequence and
        computes the negative log-likelihood loss for each predicted
        token. Also reports the random-guess baseline for comparison.

        Parameters
        ----------
        text : str
            Input text.
        loaded : LoadedModel
            The loaded model and vocabulary.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"tokens"`` (with character labels),
            ``"losses"`` (per-token loss values), ``"average_loss"``,
            ``"random_baseline"``, and ``"vocab_size"``.
        """
        ids = loaded.tokenizer.encode(text)
        n = min(len(ids) - 1, loaded.model.block_size)
        ids = ids[: n + 1]

        keys: list[list[list[Value]]] = [[] for _ in range(loaded.model.n_layer)]
        values: list[list[list[Value]]] = [[] for _ in range(loaded.model.n_layer)]
        losses: list[float] = []
        for pos_id in range(n):
            token_id, target_id = ids[pos_id], ids[pos_id + 1]
            logits = loaded.model.forward(token_id, pos_id, keys, values)
            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(round(loss_t.data, 6))

        average_loss = round(sum(losses) / n, 6) if n > 0 else 0.0
        random_baseline = round(-math.log(1.0 / loaded.tokenizer.vocab_size), 6)

        token_labels = [
            {"char": _token_label(i, loaded.chars, loaded.bos_id), "id": i} for i in ids
        ]

        return {
            "model": loaded.info(),
            "tokens": token_labels,
            "losses": losses,
            "average_loss": average_loss,
            "random_baseline": random_baseline,
            "vocab_size": loaded.tokenizer.vocab_size,
        }

    def model_params(self, loaded: LoadedModel) -> dict[str, Any]:
        """Return named parameter breakdown with shapes and counts.

        Iterates over all parameters in the model state dict,
        categorises them (embedding, attention, MLP, RMSNorm, etc.),
        and computes per-group and total parameter counts.

        Parameters
        ----------
        loaded : LoadedModel
            The loaded model and vocabulary.

        Returns
        -------
        dict[str, Any]
            Dict with ``"model"``, ``"total_params"``, model
            hyperparameters (``n_embd``, ``n_layer``, etc.), and
            ``"groups"`` (each with name, category, shape, count,
            and percentage).
        """
        groups: list[dict[str, Any]] = []
        total_params = 0

        for name, mat in loaded.model.state_dict.items():
            if mat and isinstance(mat[0], list):
                rows = len(mat)
                cols = len(mat[0]) if rows > 0 else 0
                num_params = rows * cols
            else:
                rows = len(mat)
                cols = 1
                num_params = rows
            total_params += num_params

            if name == "wte":
                category = "embedding"
            elif name == "lm_head":
                category = "output"
            elif ".attn_" in name:
                category = "attention projections"
            elif ".mlp_" in name:
                category = "SwiGLU MLP"
            elif name == "rms_final" or ".rms_" in name:
                category = "RMSNorm scales"
            else:
                category = "other"

            groups.append(
                {
                    "name": name,
                    "category": category,
                    "shape": [rows, cols],
                    "num_params": num_params,
                }
            )

        for g in groups:
            g["percentage"] = (
                round(g["num_params"] / total_params * 100, 2)
                if total_params > 0
                else 0.0
            )

        return {
            "model": loaded.info(),
            "total_params": total_params,
            "n_embd": loaded.model.n_embd,
            "n_layer": loaded.model.n_layer,
            "n_head": loaded.model.n_head,
            "block_size": loaded.model.block_size,
            "vocab_size": loaded.model.vocab_size,
            "groups": groups,
        }
