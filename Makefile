SHELL := /bin/bash

.PHONY: check-all check-java check-node check-python

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
	cd src/shoppingassistantservice && python3 -m mypy shoppingassistantservice.py
	cd src/shoppingassistantservice && python3 -m pytest
