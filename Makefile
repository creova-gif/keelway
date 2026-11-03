.PHONY: test test-verbose demo serve runner init-demo docker-up docker-down clean help

PYTHON ?= python3

help:
	@echo "Keelway by Sorvex Labs — Developer Tasks"
	@echo "  make test          Run full automated test suite (79 tests)"
	@echo "  make test-verbose  Run pytest with verbose output"
	@echo "  make demo          Run interactive developer walkthrough & tamper detection demo"
	@echo "  make serve         Start local control plane & operator dashboard (http://127.0.0.1:8000)"
	@echo "  make init-demo     Scaffold demo Git repository in examples/demo_service"
	@echo "  make runner        Start outbound customer runner daemon"
	@echo "  make docker-up     Start multi-container stack via Docker Compose"
	@echo "  make docker-down   Stop Docker Compose services"
	@echo "  make clean         Remove cache files, databases, and temporary artifacts"

test:
	PYTHONPATH=. $(PYTHON) -m pytest tests -q

test-verbose:
	PYTHONPATH=. $(PYTHON) -m pytest tests -v

demo:
	PYTHONPATH=. $(PYTHON) examples/run_developer_demo.py

serve:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main serve --host 127.0.0.1 --port 8000

init-demo:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main init-demo --dir examples/demo_service

runner:
	PYTHONPATH=. $(PYTHON) -m keelway.cli.main runner --runner-id node-01 --org org_sorvex_demo --server http://127.0.0.1:8000

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f keelway_audit.db keelway_audit.db-shm keelway_audit.db-wal
