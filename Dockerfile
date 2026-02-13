# Stage 1: Build Vue.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + compiled frontend
FROM python:3.11-slim AS runtime

# Install Rust toolchain for building gpredomicspy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Install Python dependencies
COPY backend/pyproject.toml backend/
RUN pip install --no-cache-dir -e backend/

# Install gpredomicspy from source (requires Rust)
# For now, this is optional — the app works in mock mode without it
# COPY gpredomicspy/ gpredomicspy/
# RUN cd gpredomicspy && pip install maturin && maturin develop --release

# Copy backend code
COPY backend/ backend/

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist backend/static/

# Copy sample data
COPY data/sample/ data/sample/

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
