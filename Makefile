.PHONY: help up down logs clean build restart test lint seed backup restore

# Default target
help:
	@echo "Minimee - Makefile Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  make up       - Start all Docker services"
	@echo "  make down     - Stop all Docker services"
	@echo "  make logs     - Show logs from all services"
	@echo "  make build    - Build all Docker images"
	@echo "  make restart  - Restart all services"
	@echo "  make clean    - Stop services and remove volumes"
	@echo "  make test     - Run all tests (backend + frontend)"
	@echo "  make lint     - Run linting (backend + frontend)"
	@echo "  make seed     - Seed database with default data"
	@echo "  make backup   - Create database backup"
	@echo "  make restore  - Restore database from backup (requires FILE=path)"
	@echo "  make help     - Show this help message"

# Start all services
up:
	@echo "Starting Minimee services..."
	cd infra/docker && docker-compose up -d

# Stop all services
down:
	@echo "Stopping Minimee services..."
	cd infra/docker && docker-compose down

# Show logs
logs:
	cd infra/docker && docker-compose logs -f

# Build images
build:
	@echo "Building Docker images..."
	cd infra/docker && docker-compose build

# Restart services
restart:
	@echo "Restarting services..."
	cd infra/docker && docker-compose restart

# Clean up (stop and remove volumes)
clean:
	@echo "Cleaning up..."
	cd infra/docker && docker-compose down -v

# Run tests
test:
	@echo "Running tests..."
	@echo "Backend tests..."
	cd apps/backend && pytest tests/ -v
	@echo "Frontend type check..."
	cd apps/dashboard && npm run type-check

# Run linting
lint:
	@echo "Running linters..."
	@echo "Backend lint..."
	cd apps/backend && flake8 . --count --max-line-length=127 --statistics || echo "Linting completed"
	@echo "Frontend lint..."
	cd apps/dashboard && npm run lint

# Seed database
seed:
	@echo "Seeding database..."
	python3 scripts/seed_data.py

# Backup database
backup:
	@echo "Creating database backup..."
	bash scripts/backup_db.sh

# Restore database
restore:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter required"; \
		echo "Usage: make restore FILE=./backups/minimee_backup_20240101_120000.sql.gz"; \
		exit 1; \
	fi
	@echo "Restoring database from $(FILE)..."
	bash scripts/restore_db.sh $(FILE)

