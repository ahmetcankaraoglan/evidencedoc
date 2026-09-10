FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY evidencedoc ./evidencedoc
RUN pip install --no-cache-dir .
RUN useradd --create-home app && mkdir /app/data && chown app:app /app/data
USER app
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "evidencedoc.app:app", "--host", "0.0.0.0", "--port", "8765"]
