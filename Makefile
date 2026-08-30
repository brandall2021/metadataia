.PHONY: help dev-up dev-down up down build migrate seed test lint logs ps \
        prod-config prod-up prod-down prod-logs prod-seed prod-backup

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
	@echo "  make prod-config Valida el compose de produccion"
	@echo "  make prod-up    Levanta el stack de produccion (requiere .env)"
	@echo "  make prod-down  Detiene el stack de produccion"
	@echo "  make prod-logs  Logs del stack de produccion"
	@echo "  make prod-seed  Carga datos iniciales en produccion (una vez)"
	@echo "  make prod-backup Genera backup de PostgreSQL y MinIO (./backups)"

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

prod-config:
	docker compose -f docker-compose.prod.yml config

prod-up:
	docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

prod-seed:
	docker compose -f docker-compose.prod.yml run --rm api python -m app.seed

prod-backup:
	./deploy/backup.sh