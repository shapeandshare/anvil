"""Tests for HubClient — caching HTTP client for HuggingFace Hub.

Covers the full HubClient API including:
- Construction with/without huggingface_hub installed
- search_models with caching, cache misses, API errors, rate limits
- get_model_info with caching, cache misses, errors, stale fallback
- _is_expired TTL calculation
- _serialize_models and _serialize_model_info conversion helpers
- _safe_get attribute access helper
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from anvil.services.inference_hub.hub_client import (
    HubClient,
    _safe_get,
    _serialize_model_info,
    _serialize_models,
)


def _make_mock_model(
    model_id: str = "test/model",
    license_val: str = "mit",
    architectures: list[str] | None = None,
    safetensors_params: dict[str, int] | None = None,
) -> MagicMock:
    """Build a MagicMock that resembles a HuggingFace ModelInfo object."""
    model = MagicMock()
    model.modelId = model_id
    model.cardData = {"license": license_val}
    model.config = (
        {"architectures": architectures} if architectures else {"architectures": []}
    )

    if safetensors_params is not None:
        st = MagicMock()
        st.parameters = safetensors_params
        model.safetensors = st
    else:
        model.safetensors = None

    return model


def _make_mock_model_info(
    model_id: str = "test/model",
    license_val: str = "mit",
    architectures: list[str] | None = None,
    safetensors_params: dict[str, int] | None = None,
    pipeline_tag: str | None = None,
    library_name: str | None = None,
    downloads: int = 0,
) -> MagicMock:
    """Build a MagicMock that resembles a HuggingFace ModelInfo (full) object."""
    info = _make_mock_model(model_id, license_val, architectures, safetensors_params)
    info.pipeline_tag = pipeline_tag
    info.library_name = library_name
    info.downloads = downloads
    return info


##############################################################################
# Construction
##############################################################################


class TestHubClientConstruction:
    """HubClient instantiation — installed vs. not installed."""

    def test_constructor_raises_runtime_error_when_hf_not_installed(self) -> None:
        """Raises RuntimeError when huggingface_hub is not available."""
        with patch("anvil.services.inference_hub.hub_client.HfApi", None):
            with pytest.raises(RuntimeError, match="huggingface_hub is required"):
                HubClient(token="test")

    def test_constructor_initializes_hf_api_when_available(self) -> None:
        """Initializes HfApi and caches when huggingface_hub is installed."""
        mock_hf_api_cls = MagicMock()
        mock_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_instance

        with patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls):
            client = HubClient(token="test_token")

        mock_hf_api_cls.assert_called_once_with(token="test_token")
        assert client._api is mock_instance
        assert client._search_cache == {}
        assert client._info_cache == {}
        assert client._search_ttl == 300
        assert client._info_ttl == 1800

    def test_constructor_defaults_token_to_none(self) -> None:
        """Defaults token to None when not provided."""
        mock_hf_api_cls = MagicMock()
        with patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls):
            HubClient()

        mock_hf_api_cls.assert_called_once_with(token=None)


##############################################################################
# _is_expired
##############################################################################


class TestIsExpired:
    """_is_expired static method — TTL boundary conditions."""

    def test_is_expired_returns_true_when_ttl_exceeded(self) -> None:
        """Returns True when current time exceeds timestamp + TTL."""
        mock_hf_api_cls = MagicMock()
        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=200.0),
        ):
            client = HubClient()
            assert client._is_expired(timestamp=100.0, ttl=10) is True

    def test_is_expired_returns_false_when_within_ttl(self) -> None:
        """Returns False when current time is within timestamp + TTL."""
        mock_hf_api_cls = MagicMock()
        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=105.0),
        ):
            client = HubClient()
            assert client._is_expired(timestamp=100.0, ttl=10) is False

    def test_is_expired_returns_false_at_exact_boundary(self) -> None:
        """Returns False when current time exactly equals timestamp + TTL."""
        mock_hf_api_cls = MagicMock()
        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=110.0),
        ):
            client = HubClient()
            assert client._is_expired(timestamp=100.0, ttl=10) is False


##############################################################################
# search_models
##############################################################################


class TestSearchModels:
    """search_models — caching, API calls, error handling."""

    def test_search_models_returns_cached_results_when_ttl_not_expired(
        self,
    ) -> None:
        """Returns cached results without calling API when TTL is fresh."""
        mock_hf_api_cls = MagicMock()
        cached_results = [{"hf_id": "cached/model"}]

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client._search_cache["bert:20"] = (50.0, cached_results)

        with patch("time.time", return_value=100.0):
            result = client.search_models("bert")

        assert result == {"results": cached_results, "cached": True, "error": None}
        client._api.list_models.assert_not_called()

    def test_search_models_calls_list_models_on_cache_miss(self) -> None:
        """Calls HfApi.list_models and serializes results on cache miss."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance

        mock_model = _make_mock_model(
            model_id="test/model",
            license_val="apache-2.0",
            architectures=["LlamaForCausalLM"],
            safetensors_params={"float32": 100},
        )
        mock_api_instance.list_models.return_value = [mock_model]

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=500.0),
        ):
            client = HubClient()
            result = client.search_models("test", limit=10)

        mock_api_instance.list_models.assert_called_once_with(search="test")
        assert result["cached"] is False
        assert result["error"] is None
        assert len(result["results"]) == 1
        assert result["results"][0]["hf_id"] == "test/model"
        assert result["results"][0]["license"] == "apache-2.0"
        assert result["results"][0]["architecture"] == "LlamaForCausalLM"
        assert result["results"][0]["params"] == 100

    def test_search_models_cache_key_includes_limit(self) -> None:
        """Uses a cache key that distinguishes different limits."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.return_value = []

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client.search_models("test", limit=5)
            client.search_models("test", limit=20)

        assert mock_api_instance.list_models.call_count == 2

    def test_search_models_handles_api_error_gracefully(self) -> None:
        """Returns error dict when HfApi.list_models raises."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.side_effect = ValueError("API failure")

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            result = client.search_models("test")

        assert result == {
            "results": [],
            "cached": False,
            "error": "API failure",
        }

    def test_search_models_serves_stale_cache_on_429_rate_limit(self) -> None:
        """Serves stale cache when API raises a 429 rate-limit error."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.side_effect = ValueError(
            "429 rate limit exceeded"
        )

        cached_results = [{"hf_id": "stale/model"}]

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client._search_ttl = 0
            client._search_cache["test:20"] = (1.0, cached_results)
            result = client.search_models("test")

        assert result == {"results": cached_results, "cached": True, "error": None}

    def test_search_models_returns_rate_limit_error_without_stale_cache(
        self,
    ) -> None:
        """Returns rate-limit error message when no stale cache is available."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.side_effect = ValueError("429 Too Many Requests")

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            result = client.search_models("test")

        assert result == {
            "results": [],
            "cached": False,
            "error": "Rate limited. Retry in N seconds.",
        }

    def test_search_models_non_429_error_with_stale_cache_returns_error(
        self,
    ) -> None:
        """Returns error (not stale cache) for non-429 exceptions."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.side_effect = ValueError("connection error")

        cached_results = [{"hf_id": "stale/model"}]

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client._search_ttl = 0
            client._search_cache["test:20"] = (1.0, cached_results)
            result = client.search_models("test")

        assert result == {
            "results": [],
            "cached": False,
            "error": "connection error",
        }

    def test_search_models_stores_result_in_cache_after_api_call(self) -> None:
        """Stores serialized results in cache after a successful API call."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.list_models.return_value = []

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=200.0),
        ):
            client = HubClient()
            client.search_models("newquery", limit=5)

        cache_key = "newquery:5"
        assert cache_key in client._search_cache
        timestamp, cached_results = client._search_cache[cache_key]
        assert timestamp == 200.0
        assert cached_results == []


##############################################################################
# get_model_info
##############################################################################


class TestGetModelInfo:
    """get_model_info — caching, API calls, error handling, stale fallback."""

    def test_get_model_info_returns_cached_info_when_ttl_not_expired(
        self,
    ) -> None:
        """Returns cached info without calling API when TTL is fresh."""
        mock_hf_api_cls = MagicMock()
        cached_info = {"hf_id": "cached/model", "downloads": 42}

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client._info_cache["test/model"] = (50.0, cached_info)

        with patch("time.time", return_value=100.0):
            result = client.get_model_info("test/model")

        assert result == cached_info
        client._api.model_info.assert_not_called()

    def test_get_model_info_calls_model_info_on_cache_miss(self) -> None:
        """Calls HfApi.model_info and serializes result on cache miss."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance

        mock_info = _make_mock_model_info(
            model_id="test/model",
            license_val="mit",
            architectures=["LlamaForCausalLM"],
            safetensors_params={"bfloat16": 200},
            pipeline_tag="text-generation",
            library_name="transformers",
            downloads=1500,
        )
        mock_api_instance.model_info.return_value = mock_info

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=500.0),
        ):
            client = HubClient()
            result = client.get_model_info("test/model")

        mock_api_instance.model_info.assert_called_once_with("test/model")
        assert result is not None
        assert result["hf_id"] == "test/model"
        assert result["license"] == "mit"
        assert result["architecture"] == "LlamaForCausalLM"
        assert result["params"] == 200
        assert result["pipeline_tag"] == "text-generation"
        assert result["library_name"] == "transformers"
        assert result["downloads"] == 1500

    def test_get_model_info_returns_none_on_error(self) -> None:
        """Returns None when API raises and no stale cache exists."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.model_info.side_effect = ValueError("not found")

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            result = client.get_model_info("unknown/model")

        assert result is None

    def test_get_model_info_returns_stale_cache_on_error_when_available(
        self,
    ) -> None:
        """Returns stale cached info when API raises and stale cache exists."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.model_info.side_effect = ValueError("API down")

        stale_info = {"hf_id": "test/model", "downloads": 99}

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=100.0),
        ):
            client = HubClient()
            client._info_ttl = 0
            client._info_cache["test/model"] = (1.0, stale_info)
            result = client.get_model_info("test/model")

        assert result == stale_info

    def test_get_model_info_stores_result_in_cache_after_api_call(self) -> None:
        """Stores serialized info in cache after a successful API call."""
        mock_hf_api_cls = MagicMock()
        mock_api_instance = MagicMock()
        mock_hf_api_cls.return_value = mock_api_instance
        mock_api_instance.model_info.return_value = _make_mock_model_info(
            model_id="new/model"
        )

        with (
            patch("anvil.services.inference_hub.hub_client.HfApi", mock_hf_api_cls),
            patch("time.time", return_value=300.0),
        ):
            client = HubClient()
            client.get_model_info("new/model")

        assert "new/model" in client._info_cache
        timestamp, cached_info = client._info_cache["new/model"]
        assert timestamp == 300.0
        assert cached_info["hf_id"] == "new/model"


##############################################################################
# _serialize_models (module-level helper)
##############################################################################


class TestSerializeModels:
    """_serialize_models — conversion from ModelInfo list to dict list."""

    def test_serialize_models_converts_model_info_objects_to_dicts(self) -> None:
        """Converts ModelInfo-like objects to plain dicts with expected keys."""
        models = [
            _make_mock_model(
                model_id="org/model-a",
                license_val="mit",
                architectures=["LlamaForCausalLM"],
                safetensors_params={"float32": 100, "float16": 50},
            )
        ]
        result = _serialize_models(models, limit=10)

        assert len(result) == 1
        entry = result[0]
        assert entry["hf_id"] == "org/model-a"
        assert entry["display_name"] == "org/model-a"
        assert entry["params"] == 150
        assert entry["license"] == "mit"
        assert entry["architecture"] == "LlamaForCausalLM"
        assert entry["is_curated"] is False

    def test_serialize_models_honours_limit_parameter(self) -> None:
        """Limits output to the specified number of models."""
        models = [_make_mock_model(model_id=f"model/{i}") for i in range(5)]
        result = _serialize_models(models, limit=3)

        assert len(result) == 3
        assert result[0]["hf_id"] == "model/0"
        assert result[1]["hf_id"] == "model/1"
        assert result[2]["hf_id"] == "model/2"

    def test_serialize_models_without_safetensors_sets_params_to_zero(
        self,
    ) -> None:
        """Sets params to 0 when safetensors is None."""
        model = _make_mock_model(model_id="no/st", safetensors_params=None)
        result = _serialize_models([model], limit=10)

        assert result[0]["params"] == 0

    def test_serialize_models_handles_non_dict_card_data(self) -> None:
        """Defaults license to 'unknown' when cardData is not a dict."""
        model = MagicMock()
        model.modelId = "no/card"
        model.cardData = "not_a_dict"
        model.config = None
        model.safetensors = None

        result = _serialize_models([model], limit=10)

        assert result[0]["license"] == "unknown"
        assert result[0]["architecture"] == "unknown"

    def test_serialize_models_handles_empty_architectures_list(self) -> None:
        """Defaults architecture to 'unknown' when architectures list is empty."""
        model = _make_mock_model(model_id="no/arch", architectures=[])
        result = _serialize_models([model], limit=10)

        assert result[0]["architecture"] == "unknown"

    def test_serialize_models_handles_non_dict_config(self) -> None:
        """Defaults architecture to 'unknown' when config is not a dict."""
        model = MagicMock()
        model.modelId = "no/config"
        model.cardData = {"license": "mit"}
        model.config = "not_a_dict"
        model.safetensors = None

        result = _serialize_models([model], limit=10)

        assert result[0]["architecture"] == "unknown"
        assert result[0]["license"] == "mit"

    def test_serialize_models_handles_empty_input(self) -> None:
        """Returns empty list when given an empty list."""
        result = _serialize_models([], limit=10)
        assert result == []

    def test_serialize_models_handles_safetensors_without_parameters(self) -> None:
        """Sets params to 0 when safetensors has no parameters attribute."""
        model = MagicMock()
        model.modelId = "no/safetensors-params"
        model.cardData = {"license": "mit"}
        model.config = {"architectures": ["LlamaForCausalLM"]}
        st = MagicMock(spec=[])
        model.safetensors = st

        result = _serialize_models([model], limit=10)

        assert result[0]["params"] == 0
        assert result[0]["architecture"] == "LlamaForCausalLM"


##############################################################################
# _serialize_model_info (module-level helper)
##############################################################################


class TestSerializeModelInfo:
    """_serialize_model_info — single ModelInfo to dict conversion."""

    def test_serialize_model_info_includes_all_fields(self) -> None:
        """Includes all expected keys in serialized output."""
        info = _make_mock_model_info(
            model_id="org/full",
            license_val="apache-2.0",
            architectures=["LlamaForCausalLM"],
            safetensors_params={"float32": 300},
            pipeline_tag="text-generation",
            library_name="transformers",
            downloads=5000,
        )
        result = _serialize_model_info(info)

        assert result["hf_id"] == "org/full"
        assert result["display_name"] == "org/full"
        assert result["params"] == 300
        assert result["license"] == "apache-2.0"
        assert result["architecture"] == "LlamaForCausalLM"
        assert result["pipeline_tag"] == "text-generation"
        assert result["library_name"] == "transformers"
        assert result["downloads"] == 5000
        assert result["is_curated"] is False

    def test_serialize_model_info_missing_optional_fields_defaults_to_none(
        self,
    ) -> None:
        """Defaults pipeline_tag and library_name to None when absent."""
        info = _make_mock_model_info(model_id="org/minimal")
        del info.pipeline_tag
        del info.library_name

        result = _serialize_model_info(info)

        assert result["pipeline_tag"] is None
        assert result["library_name"] is None
        assert result["downloads"] == 0

    def test_serialize_model_info_handles_non_dict_card_data(self) -> None:
        """Defaults license to 'unknown' when cardData is not a dict."""
        info = _make_mock_model_info(model_id="org/nocard")
        info.cardData = "string_card"

        result = _serialize_model_info(info)

        assert result["license"] == "unknown"

    def test_serialize_model_info_handles_empty_architectures(self) -> None:
        """Defaults architecture to 'unknown' when architectures list is empty."""
        info = _make_mock_model_info(model_id="org/noarch", architectures=[])
        result = _serialize_model_info(info)

        assert result["architecture"] == "unknown"

    def test_serialize_model_info_handles_non_dict_config(self) -> None:
        """Defaults architecture to 'unknown' when config is not a dict."""
        info = _make_mock_model_info(model_id="org/noconfig")
        info.config = "invalid"

        result = _serialize_model_info(info)

        assert result["architecture"] == "unknown"

    def test_serialize_model_info_without_safetensors(self) -> None:
        """Sets params to 0 when safetensors is None."""
        info = _make_mock_model_info(model_id="org/nosafe", safetensors_params=None)
        result = _serialize_model_info(info)

        assert result["params"] == 0


##############################################################################
# _safe_get (module-level helper)
##############################################################################


class TestSafeGet:
    """_safe_get — safe attribute access with default."""

    def test_safe_get_returns_attribute_value_when_exists(self) -> None:
        """Returns the attribute value when the attribute exists."""
        obj = MagicMock()
        obj.name = "test_value"

        result = _safe_get(obj, "name")
        assert result == "test_value"

    def test_safe_get_returns_default_when_attribute_missing(self) -> None:
        """Returns the default value when the attribute does not exist."""
        obj = object()

        result = _safe_get(obj, "nonexistent")
        assert result is None

    def test_safe_get_uses_custom_default(self) -> None:
        """Uses the provided default value when attribute is missing."""
        obj = object()

        result = _safe_get(obj, "missing", "fallback")
        assert result == "fallback"

    def test_safe_get_works_with_none_value(self) -> None:
        """Returns None when attribute exists but is set to None."""
        obj = MagicMock()
        obj.null_attr = None

        result = _safe_get(obj, "null_attr", "default")
        assert result is None
