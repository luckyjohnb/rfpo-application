.PHONY: install test test-unit test-integration test-changed test-coverage lint format docker-up docker-build deploy smoke

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:
	python -m pytest tests/unit/ tests/integration/ -v --tb=short

test-unit:
	python -m pytest tests/unit/ -v --tb=short

test-integration:
	python -m pytest tests/integration/ -v --tb=short

test-changed:
	python -m pytest tests/ -v --tb=short --last-failed

test-coverage:
	python -m pytest tests/unit/ tests/integration/ --cov=. --cov-report=term-missing --cov-report=html

lint:
	python -m black --check .
	python -m flake8 . --max-line-length=120
	python -m isort --check .

format:
	python -m black .
	python -m isort .

docker-up:
	docker-compose up -d

docker-build:
	docker-compose build

deploy:
	./redeploy-phase1.sh

smoke:
	python -m pytest tests/smoke/ -v --tb=short
