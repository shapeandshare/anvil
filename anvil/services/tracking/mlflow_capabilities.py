# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""MLflow tracking capabilities detection — probes a tracking URI for features.

Provides ``detect_capabilities()`` to determine whether the configured
MLflow server supports genai datasets, is server-backed, and what
version of MLflow is running.
"""

from pydantic import BaseModel


class TrackingCapabilities(BaseModel):
    """Capabilities detected for the MLflow tracking server.

    Attributes
    ----------
    genai_datasets : bool
        Whether MLflow 3.x genai dataset features are available and
        the server is backend-backed.
    server_backed : bool
        Whether the tracking URI points to an HTTP/HTTPS server.
    mlflow_version : str
        The installed MLflow version string.
    """

    genai_datasets: bool
    server_backed: bool
    mlflow_version: str


def detect_capabilities(tracking_uri: str) -> TrackingCapabilities:
    """Detect MLflow tracking server capabilities from a URI.

    Checks the MLflow version, whether ``mlflow.genai.datasets`` is
    importable, and whether the URI points to a remote server.

    Parameters
    ----------
    tracking_uri : str
        The MLflow tracking URI to probe.

    Returns
    -------
    TrackingCapabilities
        Detected capabilities including genai dataset support, server
        backend flag, and MLflow version.
    """
    try:
        # import-placement:allow -- version-dependent sub-module probe
        import mlflow.genai.datasets

        genai_ok = True
    except ImportError:
        genai_ok = False

    version = mlflow.__version__

    server_backed = tracking_uri.startswith("http://") or tracking_uri.startswith(
        "https://"
    )

    return TrackingCapabilities(
        genai_datasets=genai_ok and server_backed,
        server_backed=server_backed,
        mlflow_version=version,
    )
