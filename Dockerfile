FROM python:3.12-slim

WORKDIR /app

# git é necessário só para o pip install do agent_framework abaixo (via
# git+https) — não publicado no PyPI (ver STATE.md, B-007).
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Dependências do projeto
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# agent_framework — instalado direto do repositório público, pinado num
# commit específico para reprodutibilidade (mesmo mecanismo do CI, ver
# .github/workflows/ci.yml). --no-deps: a PoC só usa channels/routing/
# observability, que não requerem as dependências pesadas do
# pyproject.toml completo (oracledb, oci, pymongo, redis, motor,
# google-cloud-pubsub, mcp, langfuse).
ARG AGENT_FRAMEWORK_REF=f9c66b4792ac9fd63d7397dbab3bcac310e4d780
RUN pip install --no-cache-dir --no-deps \
    "git+https://github.com/hoshikawa2/agent_platform_oci.git@${AGENT_FRAMEWORK_REF}#subdirectory=libs/agent_framework"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
