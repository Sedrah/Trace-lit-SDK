COMPOSE = docker compose -f infra/docker-compose.yml --env-file .env
COMPOSE_CTX = COMPOSE_CONTEXT=/opt/trace-lit

.PHONY: up down restart logs ps build deploy

## Start all services (build images if changed)
up:
	$(COMPOSE_CTX) $(COMPOSE) up -d --build

## Stop all services
down:
	$(COMPOSE) down

## Restart a single service: make restart svc=nginx
restart:
	$(COMPOSE) restart $(svc)

## Tail logs for a service: make logs svc=ingestion
logs:
	$(COMPOSE) logs $(svc) --tail 50 -f

## Show container status
ps:
	$(COMPOSE) ps

## Build images without starting
build:
	$(COMPOSE_CTX) $(COMPOSE) build

## Pull latest code and redeploy (same as CI)
deploy:
	git pull origin main
	$(COMPOSE_CTX) $(COMPOSE) up -d --build
	docker image prune -f
