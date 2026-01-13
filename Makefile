.PHONY: help build up down logs test test-idempotency test-retry clean

help:
	@echo "Available commands:"
	@echo "  make build              - Build all Docker images"
	@echo "  make up                 - Start all services"
	@echo "  make down               - Stop all services"
	@echo "  make logs               - Follow logs from all services"
	@echo "  make test               - Run all tests"
	@echo "  make test-idempotency   - Run idempotency test"
	@echo "  make test-retry         - Run retry->DLQ test"
	@echo "  make clean              - Clean up everything (including volumes)"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Services are ready!"
	@echo "API: http://localhost:3000"
	@echo "Health: http://localhost:3000/health"
	@echo "Metrics: http://localhost:3000/metrics"

down:
	docker-compose down

logs:
	docker-compose logs -f

test: up
	@echo "Running tests..."
	@cd tests && pip install -q -r requirements.txt
	@cd tests && python test_idempotency.py
	@cd tests && python test_retry_dlq.py

test-idempotency: up
	@cd tests && pip install -q -r requirements.txt
	@cd tests && python test_idempotency.py

test-retry: up
	@cd tests && pip install -q -r requirements.txt
	@cd tests && python test_retry_dlq.py

clean:
	docker-compose down -v
	@echo "Cleaned up all containers and volumes"
