# --- Build stage -------------------------------------------------------------
# We use a slim Python base, install deps in their own layer for cache reuse,
# then copy the app source. Running as a non-root user is a small but real
# security hardening for production deployments.
FROM python:3.11-slim AS runtime

# Set a stable working directory for everything that follows.
WORKDIR /app

# System deps: build-essential for any C-extension wheels, libpq-dev for
# psycopg, curl for the healthcheck. Cleaning apt cache keeps the image small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first — pip cache mounts make rebuilds fast.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

# Create and switch to a non-root user — containers should never run as root.
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Streamlit's default port. Render and docker-compose will both map this.
EXPOSE 8501

# Healthcheck against Streamlit's built-in health endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Entrypoint: run any pending Alembic migrations, then start Streamlit.
# This means schema changes auto-apply on container start in any environment.
CMD ["bash", "-c", "alembic upgrade head && streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"]
