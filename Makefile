.PHONY: test test-verbose m1 bench studio desktop demo serve runner init-demo docker-up docker-down clean help infra-local infra-aws infra-k8s tier2-status tier2-verify

PYTHON ?= python3

help:
	@echo "Keelway by Sorvex Labs — Developer Tasks"
	@echo "  make test          Run full automated test suite (513 tests)"
	@echo "  make test-verbose  Run pytest with verbose output"
	@echo "  make m1            Validate Milestone M1 10-stage end-to-end developer workflow"
	@echo "  make bench         Run golden 10-task evaluation benchmark panel"
	@echo "  make studio        Launch Keelway Studio Web & Desktop developer environment"
	@echo "  make demo          Run interactive developer walkthrough & tamper detection demo"
	@echo "  make tier2-status  Show live Tier 2 Hardware Security status"
	@echo "  make tier2-verify  Cryptographically verify all Tier 2 hardware claims"
	@echo "  make serve         Start local control plane & operator dashboard (http://127.0.0.1:8000)"
	@echo "  make runner        Start outbound customer runner daemon"
	@echo "  make infra-local   Deploy complete containerized stack locally with healthchecks"
	@echo "  make infra-aws     Deploy enterprise AWS infrastructure (ECS, RDS, S3 Object Lock, KMS)"
	@echo "  make infra-k8s     Apply production Kubernetes manifests (deploy/k8s/)"
	@echo "  make docker-up     Start multi-container stack via Docker Compose"
	@echo "  make docker-down   Stop Docker Compose services"
	@echo "  make clean         Remove cache files, databases, and temporary artifacts"

test:
	PYTHONPATH=. $(PYTHON) -m pytest tests -q

test-verbose:
	PYTHONPATH=. $(PYTHON) -m pytest tests -v

m1:
	PYTHONPATH=. $(PYTHON) cli.py m1

bench:
	PYTHONPATH=. $(PYTHON) cli.py bench

studio:
	PYTHONPATH=. $(PYTHON) cli.py dev

desktop:
	PYTHONPATH=. $(PYTHON) cli.py desktop

demo:
	PYTHONPATH=. $(PYTHON) examples/run_developer_demo.py

tier2-status:
	PYTHONPATH=. $(PYTHON) cli.py tier2 status

tier2-verify:
	PYTHONPATH=. $(PYTHON) cli.py tier2 verify

serve:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main serve --host 127.0.0.1 --port 8000

init-demo:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main init-demo --dir examples/demo_service

runner:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main runner --runner-id node-01 --org org_sorvex_demo --server http://127.0.0.1:8000

infra-local:
	./deploy/scripts/deploy-local.sh

infra-aws:
	./deploy/scripts/deploy-aws.sh

infra-k8s:
	kubectl apply -f deploy/k8s/

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f keelway_audit.db keelway_audit.db-shm keelway_audit.db-wal
