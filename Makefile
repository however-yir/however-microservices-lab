SHELL := /bin/bash

.PHONY: check-all check-java check-node check-python check-e2e

check-all:
	bash scripts/checks/run_all_checks.sh

check-java:
	cd src/adservice && chmod +x gradlew && ./gradlew test pmdMain

check-node:
	cd src/currencyservice && npm ci && npm test
	cd src/paymentservice && npm ci && npm test

check-python:
	cd src/shoppingassistantservice && python3 -m pip install -r requirements.txt
	cd src/shoppingassistantservice && python3 -m ruff check .
	cd src/shoppingassistantservice && python3 -m mypy shoppingassistantservice.py config.py metrics.py resilience.py retriever.py model_client.py
	cd src/shoppingassistantservice && python3 -m pytest

check-e2e:
	bash tests/e2e/kind_skaffold_smoke.sh
