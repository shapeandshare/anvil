"""Inference service — connects educational widgets to real model data.

Follows layer discipline: services consume repositories, routes call services.
"""

import threading
from pathlib import Path
from typing import Any

from microgpt.core.engine import GPT
from microgpt.core.tokenizer import Vocabulary


DEMO_MODEL_PATH = Path("data/models/demo/model.json")
DEMO_CORPUS = [
    "the quick brown fox jumps over the lazy dog",
    "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG",
    "emma",
    "olivia",
    "ava",
    "isabella",
    "sophia",
    "mia",
    "charlotte",
    "amelia",
    "GPT demo 42",
]
_DEMO_TRAIN_LOCK = threading.Lock()


def _train_demo_model() -> GPT:
    from microgpt.core.engine import train

    model, _loss, _samples, uchars = train(
        DEMO_CORPUS,
        num_steps=400,
        n_embd=16,
        n_head=4,
        n_layer=1,
        block_size=16,
    )
    DEMO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(DEMO_MODEL_PATH), uchars)
    model.chars = uchars
    return model


class DemoModelProvider:
    """Provisions a tiny demo model on first request.

    The demo model is a real trained model — all data returned is genuine.
    """

    def __init__(self) -> None:
        self._model: GPT | None = None
        self._chars: list[str] | None = None

    def get_model(self) -> tuple[GPT, list[str]]:
        if self._model is not None:
            chars_list = self._chars if self._chars is not None else []
            return self._model, chars_list

        with _DEMO_TRAIN_LOCK:
            if self._model is not None:
                chars_list = self._chars if self._chars is not None else []
                return self._model, chars_list

            if DEMO_MODEL_PATH.exists():
                model = GPT.load(str(DEMO_MODEL_PATH))
                if model.chars is not None:
                    self._model = model
                    self._chars = model.chars
                    return model, model.chars

            model = _train_demo_model()
            self._model = model
            self._chars = model.chars
            chars_list = self._chars if self._chars is not None else []
            return model, chars_list

    def info(self) -> dict[str, Any]:
        return {"id": None, "version": None, "name": "demo", "is_demo": True}


_demo_provider = DemoModelProvider()


class LoadedModel:
    """Container for a loaded GPT model with its vocabulary and metadata."""

    def __init__(
        self,
        model: GPT,
        chars: list[str],
        model_id: int | None,
        version: int | None,
        name: str,
        is_demo: bool = False,
    ):
        self.model = model
        self.chars = chars
        self.vocab = Vocabulary.from_chars(chars)
        self.model_id = model_id
        self.version = version
        self.name = name
        self.is_demo = is_demo

    def info(self) -> dict[str, Any]:
        return {
            "id": self.model_id,
            "version": self.version,
            "name": self.name,
            "is_demo": self.is_demo,
        }


def _top_k_logits(logits: list[float], k: int | None) -> list[float]:
    if k is None or k <= 0:
        return logits
    sorted_vals = sorted(logits, reverse=True)
    threshold = sorted_vals[min(k - 1, len(sorted_vals) - 1)]
    return [v if v >= threshold else -1e10 for v in logits]


def _project_to_2d(vectors: list[list[float]]) -> list[dict[str, float]]:
    """Project high-dim vectors to 2D using top-2 PCA via power iteration.

    Zero-dependency pure-python implementation.
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
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int], tuple[GPT, list[str]]] = {}
        self._demo_provider = _demo_provider

    async def load_model(
        self,
        model_id: int | None = None,
        version: int | None = None,
    ) -> LoadedModel:
        if model_id is None:
            gpt_model, chars = self._demo_provider.get_model()
            return LoadedModel(gpt_model, chars, None, None, "demo", is_demo=True)

        cache_key = (model_id, version if version is not None else 1)
        if cache_key in self._cache:
            gpt_model, chars = self._cache[cache_key]
            name = "cached"
            return LoadedModel(gpt_model, chars, model_id, cache_key[1], name)

        from microgpt.db.session import AsyncSessionLocal
        from microgpt.db.repositories.models import ModelRepository
        from microgpt.services.models import ModelRegistryService

        async with AsyncSessionLocal() as session:
            repo = ModelRepository(session)
            svc = ModelRegistryService(repo)
            v = await svc.get_version(model_id, version if version is not None else 1)

        if v is None:
            raise ValueError(
                f"Model version not found: model_id={model_id}, version={version}"
            )

        model_path = Path(v["artifact_path"])
        if not model_path.exists():
            raise FileNotFoundError(f"Model artifact not found: {model_path}")

        gpt_model = GPT.load(str(model_path))
        if gpt_model.chars is None:
            raise ValueError("Model has no character mapping")

        name = v.get("hyperparameters", {}).get("name", f"model-{model_id}")
        self._cache[cache_key] = (gpt_model, gpt_model.chars)
        return LoadedModel(gpt_model, gpt_model.chars, model_id, cache_key[1], name)

    def tokenize(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        ids = loaded.vocab.encode(text)
        return {
            "model": loaded.info(),
            "tokens": [
                {
                    "char": loaded.chars[i] if i != loaded.vocab.bos_id else "<BOS>",
                    "id": i,
                }
                for i in ids
            ],
            "vocab_size": loaded.vocab.vocab_size,
            "bos_id": loaded.vocab.bos_id,
        }

    def embeddings(self, text: str, loaded: LoadedModel) -> dict[str, Any]:
        ids = loaded.vocab.encode(text)
        vectors = []
        labels = []
        for _i, tid in enumerate(ids):
            row = [v.data for v in loaded.model.state_dict["wte"][tid]]
            vectors.append(row)
            label = loaded.chars[tid] if tid != loaded.vocab.bos_id else "<BOS>"
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
        ids = loaded.vocab.encode(text)
        max_len = min(loaded.model.block_size, 32)
        ids = ids[:max_len]

        result = loaded.model.forward_introspect(ids)
        weights = result["attention"]

        token_labels = [
            {"char": loaded.chars[i] if i != loaded.vocab.bos_id else "<BOS>", "id": i}
            for i in ids
        ]

        return {
            "model": loaded.info(),
            "tokens": token_labels,
            "n_layer": loaded.model.n_layer,
            "n_head": loaded.model.n_head,
            "weights": weights,
        }

    def sampling_distribution(
        self,
        prompt: str,
        temperature: float,
        top_k: int | None,
        loaded: LoadedModel,
    ) -> dict[str, Any]:
        ids = loaded.vocab.encode(prompt)
        n_layers = loaded.model.n_layer
        keys: list[list[Any]] = [[] for _ in range(n_layers)]
        values: list[list[Any]] = [[] for _ in range(n_layers)]
        for pos_id, tid in enumerate(ids):
            loaded.model.forward(tid, pos_id, keys, values)

        last_pos = len(ids)
        dummy_tid = ids[-1] if ids else loaded.vocab.bos_id
        logits = loaded.model.forward(dummy_tid, last_pos - 1, keys, values)
        scaled = [logit.data / temperature for logit in logits]
        truncated = _top_k_logits(scaled, top_k)

        import math

        max_val = max(truncated)
        exps = [math.exp(v - max_val) for v in truncated]
        total = sum(exps)
        probs = [e / total for e in exps]

        all_tokens = []
        for i in range(loaded.vocab.vocab_size):
            char = loaded.chars[i] if i != loaded.vocab.bos_id else "<BOS>"
            all_tokens.append(
                {
                    "char": char,
                    "id": i,
                    "prob": probs[i],
                }
            )

        return {
            "model": loaded.info(),
            "tokens": all_tokens,
            "temperature": temperature,
        }

    def forward_graph(
        self, loaded: LoadedModel, max_nodes: int = 400
    ) -> dict[str, Any]:
        n_layers = loaded.model.n_layer
        keys: list[list[Any]] = [[] for _ in range(n_layers)]
        values: list[list[Any]] = [[] for _ in range(n_layers)]
        tid = loaded.vocab.bos_id
        logits = loaded.model.forward(tid, 0, keys, values)

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[int] = set()
        node_counter: list[int] = [0]

        def assign_op(val: Any) -> str:
            """Infer operation type from Value structure."""
            n_children = len(val._children)
            if n_children == 0:
                return "input"
            if n_children == 1:
                child = val._children[0]
                if hasattr(child, "_local_grads") and child._local_grads:
                    lg = child._local_grads
                    if len(lg) == 1 and lg[0] != 1.0:
                        if isinstance(lg[0], (int, float)) and lg[0] != 1.0:
                            return "pow"
                return "relu"
            if n_children == 2:
                parent_types = [type(c).__name__ for c in val._children[:2]]
                if "Value" in parent_types:
                    return "add"
                return "mul"
            return "combine"

        def traverse(v: Any, depth: int = 0) -> str | None:
            if len(nodes) >= max_nodes:
                return None
            v_id = id(v)
            if v_id in visited:
                for n in nodes:
                    if n["id"] == str(v_id):
                        return n["id"]
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
        """Run forward + backward pass on input text, return computation graph with gradients."""

        ids = loaded.vocab.encode(text)
        n = min(len(ids) - 1, loaded.model.block_size)
        ids = ids[: n + 1]

        # Forward pass over the sequence
        keys: list[list[Any]] = [[] for _ in range(loaded.model.n_layer)]
        values: list[list[Any]] = [[] for _ in range(loaded.model.n_layer)]
        losses: list[Any] = []
        for pos_id in range(n):
            token_id, target_id = ids[pos_id], ids[pos_id + 1]
            logits = loaded.model.forward(token_id, pos_id, keys, values)
            from microgpt.core.engine import softmax

            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(loss_t)
        loss = (1.0 / n) * sum(losses)

        # Backward pass
        loss.backward()

        # Traverse graph from the last logit Value
        logit_val = logits[-1]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        visited: set[int] = set()

        def assign_op(val: Any) -> str:
            n_children = len(val._children)
            if n_children == 0:
                return "input"
            if n_children == 1:
                child = val._children[0]
                if hasattr(child, "_local_grads") and child._local_grads:
                    lg = child._local_grads
                    if len(lg) == 1 and lg[0] != 1.0:
                        if isinstance(lg[0], (int, float)) and lg[0] != 1.0:
                            return "pow"
                return "relu"
            if n_children == 2:
                parent_types = [type(c).__name__ for c in val._children[:2]]
                if "Value" in parent_types:
                    return "add"
                return "mul"
            return "combine"

        def traverse(v: Any, depth: int = 0) -> str | None:
            if len(nodes) >= max_nodes:
                return None
            v_id = id(v)
            if v_id in visited:
                for n in nodes:
                    if n["id"] == str(v_id):
                        return n["id"]
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
            {"char": loaded.chars[i] if i != loaded.vocab.bos_id else "<BOS>", "id": i}
            for i in ids
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
        """Compute per-token cross-entropy loss for input text."""
        import math

        ids = loaded.vocab.encode(text)
        n = min(len(ids) - 1, loaded.model.block_size)
        ids = ids[: n + 1]

        from microgpt.core.engine import softmax

        keys: list[list[Any]] = [[] for _ in range(loaded.model.n_layer)]
        values: list[list[Any]] = [[] for _ in range(loaded.model.n_layer)]
        losses: list[float] = []
        for pos_id in range(n):
            token_id, target_id = ids[pos_id], ids[pos_id + 1]
            logits = loaded.model.forward(token_id, pos_id, keys, values)
            probs = softmax(logits)
            loss_t = -probs[target_id].log()
            losses.append(round(loss_t.data, 6))

        average_loss = round(sum(losses) / n, 6) if n > 0 else 0.0
        random_baseline = round(-math.log(1.0 / loaded.vocab.vocab_size), 6)

        token_labels = [
            {"char": loaded.chars[i] if i != loaded.vocab.bos_id else "<BOS>", "id": i}
            for i in ids
        ]

        return {
            "model": loaded.info(),
            "tokens": token_labels,
            "losses": losses,
            "average_loss": average_loss,
            "random_baseline": random_baseline,
            "vocab_size": loaded.vocab.vocab_size,
        }

    def model_params(self, loaded: LoadedModel) -> dict[str, Any]:
        """Return named parameter breakdown with shapes and counts."""
        groups: list[dict[str, Any]] = []
        total_params = 0

        for name, mat in loaded.model.state_dict.items():
            rows = len(mat)
            cols = len(mat[0]) if mat and len(mat) > 0 else 0
            num_params = rows * cols
            total_params += num_params

            if name == "wte" or name == "wpe":
                category = "embedding"
            elif name == "lm_head":
                category = "output"
            elif ".attn_" in name:
                category = "attention"
            elif ".mlp_" in name:
                category = "mlp"
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
