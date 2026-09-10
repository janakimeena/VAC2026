# Workshop image: Python, the retrieval stack, and the embedding model baked in.
#
# The model is downloaded AT BUILD TIME on purpose. A classroom of students all
# pulling 130 MB from Hugging Face over shared wifi is a reliable way to lose the
# first twenty minutes of a session. Built once, it works offline afterwards.

FROM python:3.12-slim

# HOME and the Jupyter dirs point at /tmp because the container runs as the HOST
# user (see docker-compose.yml), who owns no home directory inside the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    HOME=/tmp \
    JUPYTER_CONFIG_DIR=/tmp/.jupyter \
    JUPYTER_DATA_DIR=/tmp/.jupyter/data \
    JUPYTER_RUNTIME_DIR=/tmp/.jupyter/runtime \
    TOKENIZERS_PARALLELISM=false

WORKDIR /workshop

# Build tools some wheels still need, removed again to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch: the GPU build is several gigabytes and buys nothing here.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.13.0

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')" \
    && chmod -R a+rX /opt/hf

COPY . .

# Writable by whichever uid docker compose runs as.
RUN mkdir -p /tmp/.jupyter && chmod -R 777 /tmp/.jupyter

ENV PYTHONPATH=/workshop/src

EXPOSE 8888
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", \
     "--allow-root", "--ServerApp.token=''", "--ServerApp.password=''", \
     "--notebook-dir=/workshop"]
