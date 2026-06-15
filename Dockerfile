# anvil — Docker image
#
# Build:  docker build -t anvil .
# Run:    docker run -p 8080:8080 -p 5001:5001 anvil

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY shared/ shared/
COPY scripts/ scripts/
COPY anvil/ anvil/
COPY migrations/ migrations/
COPY alembic.ini .
COPY data/demo/ data/demo/

RUN make setup

EXPOSE 8080 5001

CMD ["make", "run"]