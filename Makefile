.PHONY: ingest up down infra-up infra-down

PYTHON ?= python3

ingest:
	$(PYTHON) scripts/run_ingestao.py

up:
	docker compose --profile infra --profile app up -d --build

down:
	docker compose --profile infra --profile app down

infra-up:
	docker compose --profile infra up -d

infra-down:
	docker compose --profile infra down
