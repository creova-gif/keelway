.PHONY: test test-verbose m1 bench studio desktop demo serve runner init-demo docker-up docker-down clean help infra-local infra-aws infra-k8s tier2-status tier2-verify package

PYTHON ?= python3

help:
	@echo "Keelway by Sorvex Labs — local tasks in a kora clone"
	@echo "  Studio, the governance server, and website/ are three different surfaces."
	@echo "  This help text does not print a test pass count."
	@echo "  make test          Run pytest on tests/ (PYTHONPATH=. python3 -m pytest tests -q)"
	@echo "  make test-verbose  Run pytest with verbose output"
	@echo "  make m1            Run: python3 cli.py m1"
	@echo "  make bench         Run: python3 cli.py bench"
	@echo "  make studio        Local Studio web UI: python3 cli.py dev (127.0.0.1:7420)"
	@echo "  make desktop       Local Studio browser-app window: python3 cli.py desktop"
	@echo "  make demo          Run examples/run_developer_demo.py"
	@echo "  make tier2-status  Run: python3 cli.py tier2 status"
	@echo "  make tier2-verify  Run: python3 cli.py tier2 verify"
	@echo "  make serve         Governance server only: python3 -m keelway.cli.main serve on 127.0.0.1:8000"
	@echo "                     Same CLI as keelway-core serve. The keelway script has no serve command."
	@echo "  make runner        Run keelway.cli.main runner against http://127.0.0.1:8000"
	@echo "  make infra-local   Run deploy/scripts/deploy-local.sh"
	@echo "  make infra-aws     Run deploy/scripts/deploy-aws.sh"
	@echo "  make infra-k8s     Run: kubectl apply -f deploy/k8s/"
	@echo "  make docker-up     docker compose up -d"
	@echo "                     Image ENTRYPOINT: python3 -m keelway.cli.main serve --host 0.0.0.0 --port 8000"
	@echo "                     That bind is 0.0.0.0, unlike make serve on 127.0.0.1. Compose also starts keelway-runner and ollama."
	@echo "  make docker-down   docker compose down"
	@echo "  make package       Run: python3 cli.py package --out dist/"
	@echo "  make clean         Remove caches and local keelway_audit.db files"

package:
	PYTHONPATH=. $(PYTHON) cli.py package --out dist/

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
