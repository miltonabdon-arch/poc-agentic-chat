# Critérios de Aceite — Demo Final

Checklist usado na demonstração ao final das 2 semanas. Todos os itens devem
passar rodando exclusivamente `docker compose up` + os comandos indicados —
sem qualquer dependência de nuvem ou credencial de produção.

## 1. Ambiente sobe do zero

- [ ] `python scripts/run_ingestao.py` processa `data/catalogo/` sem erro
      (Chroma embutido, sem serviço externo)
- [ ] `docker compose up -d` sobe o serviço FastAPI sem erro
- [ ] `curl localhost:8000/health` retorna 200

## 2. Ingestão

- [ ] `python scripts/run_ingestao.py` processa todos os documentos de
      `data/catalogo/` sem erro
- [ ] Resumo impresso mostra número de documentos e chunks consistente com o
      volume de `data/catalogo/`

## 3. Perguntas fundamentadas em RAG (devem responder corretamente, com fonte)

- [ ] "Quais franquias de dados o Plano Turbo 40GB inclui?" → resposta cita
      o valor correto de franquia e referencia o documento de origem
- [ ] "Existe fidelidade no Plano Família Prime?" → resposta correta
      (sim/não conforme o documento sintético) com fonte
- [ ] "Qual o valor da multa de cancelamento do Plano Controle 20GB?" →
      resposta correta com fonte

## 4. Perguntas fora de escopo (sem chunk correspondente)

- [ ] Uma pergunta sobre um plano que não existe no catálogo sintético
      retorna explicitamente "não encontrei essa informação" — nunca uma
      resposta inventada

## 5. Guardrails

- [ ] Uma entrada contendo um CPF de teste é mascarada antes de qualquer
      chamada ao LLM (verificável no log/trace de observabilidade)
- [ ] Uma pergunta pedindo comparação nominal com concorrente é bloqueada
      ou reformulada sem citar o nome do concorrente

## 6. Observabilidade

- [ ] Cada interação das seções 3-5 aparece no trace/log de observabilidade
      com: latência total, guardrails acionados (se algum), `chunk_id`
      usado (quando aplicável)

## 7. Pipeline CI

- [ ] Último push na branch principal do repositório mostra pipeline verde
      no Bitbucket (lint + testes)

## 8. Separação de papéis

- [ ] Cada pasta (`rag_pipeline/`, `agent/`, `gateway/`, `orchestrator/`) tem
      testes próprios que passam isoladamente (`pytest tests/test_<papel>.py`)
      sem precisar do ambiente integrado completo

## 9. Relatório de achados

- [ ] Documento curto (1-2 páginas) entregue junto com a demo, cobrindo: o
      que funcionou como esperado no `agent_platform_oci`, o que exigiu
      adaptação, e qualquer gap encontrado — ver `PROPOSTA-POC.md`, seção 10
