# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""E2E render-smoke tests for all HTML page routes."""

import pytest


@pytest.mark.asyncio
async def test_root(client):
    """GET / returns the training dashboard page (200, HTML)."""
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Forging intelligence" in r.text


@pytest.mark.asyncio
async def test_root_with_slash(client):
    """GET '' (root with trailing slash) returns the training dashboard."""
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_acceptable_use_page(client):
    """GET /v1/acceptable-use renders the acceptable-use policy page."""
    r = await client.get("/v1/acceptable-use")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Acceptable Use Policy" in r.text


@pytest.mark.asyncio
async def test_training_page(client):
    """GET /v1/training-page renders the training configuration page."""
    r = await client.get("/v1/training-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Active Training Runs" in r.text


@pytest.mark.asyncio
async def test_experiments_page(client):
    """GET /v1/experiments-page renders the experiment history page."""
    r = await client.get("/v1/experiments-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Experiment History" in r.text


@pytest.mark.asyncio
async def test_datasets_page(client):
    """GET /v1/datasets-page renders the dataset management page."""
    r = await client.get("/v1/datasets-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Add Data" in r.text


@pytest.mark.asyncio
async def test_operations_page(client):
    """GET /v1/operations-page renders the operations dashboard."""
    r = await client.get("/v1/operations-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "System Resources" in r.text


@pytest.mark.asyncio
async def test_inference_page(client):
    """GET /v1/inference-page renders the inference/playground page."""
    r = await client.get("/v1/inference-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Inference" in r.text
    assert "Sample from a Model" in r.text


@pytest.mark.asyncio
async def test_content_page(client):
    """GET /v1/content-page renders the content library page."""
    r = await client.get("/v1/content-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Corpus Library" in r.text


@pytest.mark.asyncio
async def test_about_page(client):
    """GET /v1/about renders the about page with version and all sections."""
    from anvil import __version__

    r = await client.get("/v1/about")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "About anvil" in r.text
    assert f"v{__version__}" in r.text
    assert "MIT License" in r.text
    assert "Technology Stack" in r.text
    assert "Architecture Overview" in r.text
    assert "Governance" in r.text
    assert "Resources" in r.text
    assert "Version" in r.text


@pytest.mark.asyncio
async def test_learn_index(client):
    """GET /v1/learn renders the learning hub index with all lessons listed."""
    r = await client.get("/v1/learn")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Learning Path" in r.text
    assert "/v1/learn/chunking" in r.text
    assert "/v1/learn/content-versioning" in r.text
    assert "/v1/learn/experiment-tracking" in r.text
    assert "/v1/learn/governance" in r.text
    assert "/v1/learn/memory-divergence" in r.text


@pytest.mark.asyncio
async def test_learn_graph(client):
    """GET /v1/learn/graph renders the forward pass computation graph page."""
    r = await client.get("/v1/learn/graph")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Forward Pass Explorer" in r.text


@pytest.mark.asyncio
async def test_learn_data_fundamentals(client):
    """GET /v1/learn/data-fundamentals renders the data fundamentals lesson."""
    r = await client.get("/v1/learn/data-fundamentals")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Data Fundamentals" in r.text


@pytest.mark.asyncio
async def test_learn_tokenization(client):
    """GET /v1/learn/tokenization renders the tokenization lesson."""
    r = await client.get("/v1/learn/tokenization")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Tokenization" in r.text


@pytest.mark.asyncio
async def test_learn_embeddings(client):
    """GET /v1/learn/embeddings renders the embeddings lesson."""
    r = await client.get("/v1/learn/embeddings")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Embeddings" in r.text


@pytest.mark.asyncio
async def test_learn_sampling(client):
    """GET /v1/learn/sampling renders the sampling lesson."""
    r = await client.get("/v1/learn/sampling")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Sampling" in r.text


@pytest.mark.asyncio
async def test_learn_training_loop(client):
    """GET /v1/learn/training-loop renders the training loop lesson."""
    r = await client.get("/v1/learn/training-loop")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Training Loop" in r.text


@pytest.mark.asyncio
async def test_learn_autograd(client):
    """GET /v1/learn/autograd renders the autograd lesson."""
    r = await client.get("/v1/learn/autograd")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Autograd" in r.text


@pytest.mark.asyncio
async def test_learn_loss(client):
    """GET /v1/learn/loss renders the cross-entropy loss lesson."""
    r = await client.get("/v1/learn/loss")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Cross-Entropy Loss" in r.text


@pytest.mark.asyncio
async def test_learn_parameters(client):
    """GET /v1/learn/parameters renders the model parameters lesson."""
    r = await client.get("/v1/learn/parameters")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Parameters" in r.text


@pytest.mark.asyncio
async def test_learn_adam(client):
    """GET /v1/learn/adam renders the Adam optimizer lesson."""
    r = await client.get("/v1/learn/adam")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Adam Optimizer" in r.text


@pytest.mark.asyncio
async def test_learn_architecture(client):
    """GET /v1/learn/architecture renders the transformer architecture lesson."""
    r = await client.get("/v1/learn/architecture")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Architecture" in r.text


@pytest.mark.asyncio
async def test_learn_export(client):
    """GET /v1/learn/export renders the model export lesson."""
    r = await client.get("/v1/learn/export")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Model Export" in r.text


@pytest.mark.asyncio
async def test_learn_chunking(client):
    """GET /v1/learn/chunking renders the chunking strategies lesson."""
    r = await client.get("/v1/learn/chunking")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Chunking Strategies" in r.text
    assert "FixedSizeWindowChunker" in r.text
    assert 'data-widget="chunking"' in r.text


@pytest.mark.asyncio
async def test_learn_content_versioning(client):
    """GET /v1/learn/content-versioning renders the content versioning lesson."""
    r = await client.get("/v1/learn/content-versioning")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Content Versioning" in r.text
    assert "manifest_digest" in r.text
    assert 'data-widget="contentVersioning"' in r.text


@pytest.mark.asyncio
async def test_learn_experiment_tracking(client):
    """GET /v1/learn/experiment-tracking renders the experiment tracking lesson."""
    r = await client.get("/v1/learn/experiment-tracking")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Experiment Tracking" in r.text
    assert "Model Registry" in r.text
    assert 'data-widget="experimentTracking"' in r.text


@pytest.mark.asyncio
async def test_learn_governance(client):
    """GET /v1/learn/governance renders the data governance lesson."""
    r = await client.get("/v1/learn/governance")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Data Governance" in r.text
    assert "Acceptable-Use Gate" in r.text
    assert 'data-widget="governance"' in r.text


@pytest.mark.asyncio
async def test_learn_memory_divergence(client):
    """GET /v1/learn/memory-divergence renders the memory and divergence lesson."""
    r = await client.get("/v1/learn/memory-divergence")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Memory &amp; Divergence" in r.text
    assert "DivergenceError" in r.text
    assert 'data-widget="memoryDivergence"' in r.text


@pytest.mark.asyncio
async def test_learn_faq(client):
    """GET /v1/learn/faq renders the FAQ page."""
    r = await client.get("/v1/learn/faq")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Frequently Asked Questions" in r.text


@pytest.mark.asyncio
async def test_learn_glossary(client):
    """GET /v1/learn/glossary renders the glossary page."""
    r = await client.get("/v1/learn/glossary")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Glossary" in r.text


@pytest.mark.asyncio
async def test_learn_cloud_compute(client):
    """GET /v1/learn/cloud-compute renders the cloud compute lesson."""
    r = await client.get("/v1/learn/cloud-compute")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Training in the Cloud" in r.text


@pytest.mark.asyncio
async def test_learn_fine_tuning_intro(client):
    """GET /v1/learn/fine-tuning-intro renders the fine-tuning introduction lesson."""
    r = await client.get("/v1/learn/fine-tuning-intro")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "What Is Fine-Tuning?" in r.text
    assert "coming-soon-badge" in r.text


@pytest.mark.asyncio
async def test_learn_warmstart_vs_lora(client):
    """GET /v1/learn/warmstart-vs-lora renders the warm-start vs LoRA lesson."""
    r = await client.get("/v1/learn/warmstart-vs-lora")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert (
        "Warm-Start vs LoRA" in r.text
        or "Warm-Start vs PEFT" in r.text
        or "Parameter-Efficient" in r.text
    )
    assert 'data-widget="lora"' in r.text
    assert "/static/js/widgets/lora.js" in r.text
    assert "coming-soon-badge" in r.text


@pytest.mark.asyncio
async def test_learn_finetune_vs_prompt_vs_rag(client):
    """GET /v1/learn/finetune-vs-prompt-vs-rag renders the decision comparison lesson."""
    r = await client.get("/v1/learn/finetune-vs-prompt-vs-rag")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Side-by-Side Comparison" in r.text
    assert "learn-comparison-table" in r.text
    assert "Strengths" in r.text
    assert "Weaknesses" in r.text
    assert "Best For" in r.text


@pytest.mark.asyncio
async def test_models_page(client):
    """GET /v1/models-page renders the model registry page."""
    r = await client.get("/v1/models-page")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Model Registry" in r.text


@pytest.mark.asyncio
async def test_model_detail_page(client):
    """GET /v1/model-detail/999 renders the model detail page (no error)."""
    r = await client.get("/v1/model-detail/999")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Model Detail" in r.text
