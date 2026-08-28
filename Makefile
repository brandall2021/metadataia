.PHONY: help dev-up dev-down up down build migrate seed test lint logs ps

help:
	@echo "METADATAIA - comandos utiles"
	@echo ""
	@echo "  make dev-up     Levanta todos los servicios (docker compose up -d)"
	@echo "  make dev-down   Detiene todos los servicios"
	@echo "  make build      Reconstruye las imagenes"
	@echo "  make migrate    Aplica migraciones de base de datos (alembic upgrade head)"
	@echo "  make seed       Carga datos iniciales (usuarios/roles/permisos)"
	@echo "  make test       Ejecuta los tests del backend dentro del contenedor"
	@echo "  make logs       Sigue los logs de todos los servicios"

dev-up:
	docker compose up -d --build

dev-down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m app.seed

test:
	docker compose exec api /bin/sh -c 'python -c "import pytest" 2>/dev/null || pip install -q ".[dev]"; pytest'

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps