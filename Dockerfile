# anvil — pip-installable multi-stage Docker image
#
# Builder stage:  build the wheel from source
# Runtime stage:  pip install the wheel ONLY (no source tree)
#                 genuinely exercises "pip install anvil"
#
# Build:  docker build --target runtime -t anvil .
# Run:    docker run -p 8080:8080 -p 5001:5001 anvil

# ---- Stage 1: builder — build the wheel ----
FROM python:3.11-slim AS builder

WORKDIR /src

# Install uv (fast Python package/resolver) for wheel building
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy only what's needed to build the wheel
COPY pyproject.toml ./
COPY anvil/ anvil/

# Build the PEP 517 wheel
RUN uv build --wheel --out-dir /dist .

# ---- Stage 2: runtime — install ONLY the wheel (no source tree) ----
FROM python:3.11-slim AS runtime

# Create a non-root user for security
RUN useradd --create-home --uid 1000 anvil

# Copy the pre-built wheel from the builder stage
COPY --from=builder /dist/*.whl /tmp/wheels/

# Install the wheel + its dependencies.
# This pulls dependencies from PyPI (no source tree is present,
# so this genuinely exercises "pip install <wheel>").
RUN pip install --no-cache-dir /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

# Switch to non-root user
USER anvil

# Writable runtime workspace (data/, logs/, mlruns/ created by anvil on first run)
WORKDIR /workspace

# Ports: 8080 (web), 5001 (in-process MLflow)
EXPOSE 8080 5001

# Launch via the installed console script (no Make needed)
CMD ["anvil"]
