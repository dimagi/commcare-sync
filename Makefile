start: ## Start the Docker containers
	@echo "Starting the Docker containers"
	@docker-compose up -d
	@echo "Containers started - http://localhost:8000"

services: ## Start Docker containers excl. "web"
	@docker-compose up db redis celery -d

stop: ## Stop Containers
	@docker-compose down

build: ## Build Containers
	@docker-compose build

ssh: ## SSH into running web container
	docker-compose exec web bash

migrations: ## Create DB migrations in the container
	@docker-compose exec web uv run manage.py makemigrations

migrate: ## Run DB migrations in the container
	@docker-compose exec web uv run manage.py migrate

shell: ## Get a Django shell
	@docker-compose exec web uv run manage.py shell

init: start migrate  ## Quickly get up and running (start containers and migrate DB)

npm-install: ## Runs npm install in the container
	@docker-compose exec web npm install

npm-build: ## Bundle JS files for production in the container
	@docker-compose exec web npm run build

npm-watch: ## Bundle JS files and watch for changes in the container
	@docker-compose exec web npm run dev-watch

.PHONY: help
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
