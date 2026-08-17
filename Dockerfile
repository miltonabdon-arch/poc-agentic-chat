FROM python:3.12-slim

WORKDIR /app

# Dependências do projeto
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# agent_framework (vendored localmente - não publicado em PyPI)
COPY vendor/agent_framework /app/vendor/agent_framework
RUN pip install --no-cache-dir /app/vendor/agent_framework

COPY . .

EXPOSE 8000

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
