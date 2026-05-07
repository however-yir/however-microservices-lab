.PHONY: up down restart logs ps topics schema-register build-jobs build-realtime build-enrich build-anomaly submit-realtime submit-enrich submit-anomaly produce-events produce-rag smoke cdc-check load-test

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

topics:
	bash data-storage/kafka-config/create-topics.sh

schema-register:
	docker compose up --no-deps schema-registry-init

build-jobs: build-realtime build-enrich build-anomaly

build-realtime:
	cd stream-processing/flink-jobs/realtime-stats && mvn clean package -DskipTests

build-enrich:
	cd stream-processing/flink-jobs/data-enrich && mvn clean package

build-anomaly:
	cd stream-processing/flink-jobs/anomaly-detect && mvn clean package -DskipTests

submit-realtime:
	docker cp stream-processing/flink-jobs/realtime-stats/target/realtime-stats-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/realtime-stats.jar
	docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/realtime-stats.jar

submit-enrich:
	docker cp stream-processing/flink-jobs/data-enrich/target/data-enrich-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/data-enrich.jar
	docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/data-enrich.jar --source.starting.offsets latest

submit-anomaly:
	docker cp stream-processing/flink-jobs/anomaly-detect/target/anomaly-detect-1.0.0.jar rdp-flink-jobmanager:/opt/flink/usrlib/anomaly-detect.jar
	docker exec -it rdp-flink-jobmanager flink run /opt/flink/usrlib/anomaly-detect.jar --source.starting.offsets latest

produce-events:
	cd data-collector/api-collector && python3 producer.py

produce-rag:
	cd data-collector/api-collector && python3 rag_document_producer.py

smoke:
	bash scripts/smoke_check.sh

cdc-check:
	curl -s http://localhost:8083/connectors

load-test:
	python3 scripts/load_test.py --bootstrap localhost:9092 --topic user_behavior_events --duration 60 --rps 200
