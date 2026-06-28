# Tokenizer Dispatch Contract

## INFO Logging (FR-015b)

Every encode/decode dispatch MUST log:

```
INFO  anvil.services.inference.tokenizer  Model {model_id} v{version}: tokenizer_family={family}, serialization_type={type}, vocab_size={size}
INFO  anvil.services.inference.tokenizer  Encode: model={model_id}, family={family}, text_len={n_chars}, tokens_len={n_tokens}
INFO  anvil.services.inference.tokenizer  Decode: model={model_id}, family={family}, tokens_len={n_tokens}, text_len={n_chars}
```

## API Response Shape

Model info endpoint response includes tokenizer metadata:

```json
{
    "id": 1,
    "version": 1,
    "name": "demo",
    "is_demo": true,
    "tokenizer": {
        "family": "char",
        "serialization_type": "char_json",
        "vocab_size": 65
    }
}
```

## Error Responses

All tokenizer load failures return:

```json
{
    "detail": {
        "type": "tokenizer_load_error",
        "message": "Failed to load tokenizer for model {id}: {cause}",
        "file": "data/models/experiment_1/tokenizer.json"
    }
}
```

HTTP status: 422 for loadable-but-invalid, 500 for unexpected errors.

## Load-Time Dispatch

When model is loaded:

1. Check `config.json` for `tokenizer_family` + `serialization_type`
2. Log the resolved values at INFO level
3. Attempt to load tokenizer artifact from `FileStore`
4. On failure → `TokenizerLoadError` (422 response)
5. Valid tokenizer → wrap in appropriate implementation class
6. Store as `loaded_model.tokenizer` for inference methods