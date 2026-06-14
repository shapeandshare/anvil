from dataclasses import dataclass


@dataclass
class TrackingCapabilities:
    genai_datasets: bool
    server_backed: bool
    mlflow_version: str


def detect_capabilities(tracking_uri: str) -> TrackingCapabilities:
    import mlflow

    version = mlflow.__version__

    try:
        import mlflow.genai.datasets

        genai_ok = True
    except ImportError:
        genai_ok = False

    server_backed = tracking_uri.startswith("http://") or tracking_uri.startswith(
        "https://"
    )

    return TrackingCapabilities(
        genai_datasets=genai_ok and server_backed,
        server_backed=server_backed,
        mlflow_version=version,
    )
