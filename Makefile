# Growth Garden — top-level plumbing
# Most work happens inside agent containers; these are the shared host commands.

.PHONY: help sync-contracts check check-backend check-frontend services-up services-down build-images

help:
	@echo "sync-contracts  regenerate contracts/openapi.json + api_types.ts from the backend app"
	@echo "check           run all checks (backend + frontend lint/tests)"
	@echo "services-up     start dev services (mongo + backend + web) for integration/E2E"
	@echo "services-down   stop dev services"
	@echo "build-images    build the three agent Docker images"

# Regenerate the contract from the live FastAPI schema, then derive TS types.
sync-contracts:
	cd backend && uv run python -c "import json, main; print(json.dumps(main.app.openapi(), ensure_ascii=False, indent=2))" > ../contracts/openapi.json
	npx --yes openapi-typescript contracts/openapi.json -o contracts/api_types.ts
	@echo "contracts/ regenerated"

check: check-backend check-frontend

check-backend:
	cd backend && uv run ruff check . && uv run pytest -q

check-frontend:
	gdtoolkit --version >/dev/null 2>&1 && gdformat --check godot/scripts/ || echo "gdtoolkit not on host; lint runs in container/CI"

services-up:
	docker compose -f docker/docker-compose.dev.yml up -d --build

services-down:
	docker compose -f docker/docker-compose.dev.yml down

build-images:
	docker build -f docker/Dockerfile.backend  -t growth-garden-backend  .
	docker build -f docker/Dockerfile.frontend -t growth-garden-frontend .
	docker build -f docker/Dockerfile.test     -t growth-garden-test     .
