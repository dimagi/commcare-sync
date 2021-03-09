start: ## Start the docker containers
	@echo "Starting the docker containers"
	@docker-compose up -d
	@echo "Containers started - http://localhost:8000"

stop: ## Stop Containers
	@docker-compose down

build: ## Build Containers
	@docker-compose build

ssh: ## SSH into running web container
	docker-compose exec web ash

migrations: ## Create DB migrations in the container
	@docker-compose exec web python manage.py makemigrations

migrate: ## Run DB migrations in the container
	@docker-compose exec web python manage.py migrate

init: start migrate

.PHONY: help
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
