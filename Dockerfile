FROM python:3.12-slim

WORKDIR /app

# git e necessario para o pip instalar agent-framework via git+subdirectory
# (ver requirements.txt) a partir do repositorio publico agent_platform_oci.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
