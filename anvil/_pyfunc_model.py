# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow pyfunc model wrapper for anvil-trained Llama models.

This module is the ``loader_module`` target in the ``MLmodel`` file.
It must be importable at inference time (the ``anvil`` package must be installed).
"""
# pylint: disable=attribute-defined-outside-init

import json
from pathlib import Path

import mlflow.pyfunc
import pandas as pd


class AnvilPyfuncModel(mlflow.pyfunc.PythonModel):  # type: ignore[name-defined, misc]
    """Pyfunc wrapper that loads an anvil-trained Llama model via HuggingFace transformers.

    Usage::

        model = mlflow.pyfunc.load_model("models:/dataset-1/1")
        model.predict(pd.DataFrame({"text": ["hello"]}))
    """

    def load_context(self, context: object) -> None:
        """Load model artifacts from an MLflow model directory.

        Reads the HuggingFace ``config.json`` from the artifact URI,
        instantiates a ``LlamaForCausalLM``, loads safetensors weights,
        and initialises the character-level tokenizer metadata.

        Parameters
        ----------
        context : mlflow.pyfunc.PythonModelContext
            MLflow model context providing ``artifact_uri`` pointing to
            the directory containing ``config.json``,
            ``model.safetensors``, and ``tokenizer.json``.
        """
        import torch
        from safetensors.torch import load_file
        from transformers import LlamaConfig, LlamaForCausalLM

        model_dir = Path(context.artifact_uri)  # type: ignore[attr-defined]

        # Load model architecture and weights
        self.config = LlamaConfig.from_pretrained(str(model_dir))
        self.model = LlamaForCausalLM(self.config)
        safetensors_path = model_dir / "model.safetensors"
        if safetensors_path.exists():
            state_dict = load_file(str(safetensors_path))
            self.model.load_state_dict(state_dict, strict=False)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self._torch = torch

        # Load character-level tokenizer metadata
        tokenizer_path = model_dir / "tokenizer.json"
        if tokenizer_path.exists():
            with open(tokenizer_path, encoding="utf-8") as f:
                tokenizer_data = json.load(f)
            self.vocab = tokenizer_data.get("vocab", {})
            self.chars = tokenizer_data.get("chars", [])
            self.bos_token_id = tokenizer_data.get("bos_token_id")
            self._reverse_vocab = {v: k for k, v in self.vocab.items()}
        else:
            self.vocab = {}
            self.chars = []
            self.bos_token_id = None
            self._reverse_vocab = {}

    def predict(self, _context: object, model_input: pd.DataFrame) -> pd.DataFrame:
        """Generate text continuations for each input string.

        Parameters
        ----------
        model_input : pd.DataFrame
            A DataFrame whose first column contains input text strings.

        Returns
        -------
        pd.DataFrame
            DataFrame with a single column ``generated`` containing the
            model's continuation for each input.
        """
        texts = (
            model_input.iloc[:, 0].tolist()
            if isinstance(model_input, pd.DataFrame)
            else [str(model_input)]
        )
        results = []
        for text in texts:
            result = self._generate(text, max_new_tokens=50)
            results.append(result)
        return pd.DataFrame({"generated": results})

    def _generate(self, prompt: str, max_new_tokens: int = 50) -> str:
        """Generate a continuation for a single prompt string.

        Encodes the prompt using the character-level vocabulary, runs
        autoregressive decoding with argmax sampling, and decodes only
        the newly generated tokens (prompt is stripped from output).

        Parameters
        ----------
        prompt : str
            Input text string to generate a continuation for.
        max_new_tokens : int, optional
            Maximum number of tokens to generate. Defaults to ``50``.

        Returns
        -------
        str
            The generated continuation text (prompt excluded).
        """
        # Encode via character-level vocab
        input_ids = [self.vocab.get(c, 0) for c in prompt]
        if self.bos_token_id is not None:
            input_ids = [self.bos_token_id, *input_ids]

        input_tensor = self._torch.tensor([input_ids]).to(self.device)
        generated_ids = input_ids[:]

        for _ in range(max_new_tokens):
            with self._torch.no_grad():
                outputs = self.model(input_tensor)
                logits = outputs.logits
            next_token_logits = logits[0, -1, :]
            next_token = int(self._torch.argmax(next_token_logits).item())
            generated_ids.append(next_token)
            input_tensor = self._torch.tensor([generated_ids]).to(self.device)

        # Decode only the new tokens (skip the prompt)
        new_ids = generated_ids[len(input_ids) :]
        return "".join(self._reverse_vocab.get(tok, "") for tok in new_ids)
