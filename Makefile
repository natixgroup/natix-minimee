.PHONY: help up down logs clean build restart

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

