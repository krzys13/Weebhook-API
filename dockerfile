FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml ./
COPY README.md* ./

RUN uv sync --no-dev

COPY . .

CMD ["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]