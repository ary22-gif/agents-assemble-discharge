.PHONY: install run-fhir run-agents run-orchestrator run-medrecon run-careplan run-followup test demo deploy lint clean

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	uv sync
	uv run pre-commit install
	@echo "✓ Dependencies installed. Copy .env.example → .env and fill in your keys."

# ── FHIR mock server ───────────────────────────────────────────────────────────
run-fhir:
	uv run uvicorn fhir_server.main:app --host 0.0.0.0 --port $${FHIR_SERVER_PORT:-8000} --reload

# ── Individual agents ─────────────────────────────────────────────────────────
run-orchestrator:
	uv run uvicorn agents.orchestrator.app:a2a_app --host 0.0.0.0 --port $${ORCHESTRATOR_PORT:-8001}

run-medrecon:
	uv run uvicorn agents.medrecon.app:a2a_app --host 0.0.0.0 --port $${MEDRECON_PORT:-8002}

run-careplan:
	uv run uvicorn agents.careplan.app:a2a_app --host 0.0.0.0 --port $${CAREPLAN_PORT:-8003}

run-followup:
	uv run uvicorn agents.followup.app:a2a_app --host 0.0.0.0 --port $${FOLLOWUP_PORT:-8004}

# ── Run all agents in background (use run-fhir separately) ────────────────────
run-agents:
	@echo "Starting all agents in background..."
	uv run uvicorn agents.medrecon.app:a2a_app --host 0.0.0.0 --port $${MEDRECON_PORT:-8002} &
	uv run uvicorn agents.careplan.app:a2a_app --host 0.0.0.0 --port $${CAREPLAN_PORT:-8003} &
	uv run uvicorn agents.followup.app:a2a_app --host 0.0.0.0 --port $${FOLLOWUP_PORT:-8004} &
	uv run uvicorn agents.orchestrator.app:a2a_app --host 0.0.0.0 --port $${ORCHESTRATOR_PORT:-8001}

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	uv run pytest tests/ -v

test-e2e:
	uv run python scripts/test_e2e.py

# ── Demo ───────────────────────────────────────────────────────────────────────
demo:
	uv run python scripts/simulate_promptopinion.py

# ── Deployment ────────────────────────────────────────────────────────────────
deploy:
	@echo "Running Cloud Run deploy..."
	bash scripts/deploy.sh

# ── Lint / pre-commit ─────────────────────────────────────────────────────────
lint:
	uv run pre-commit run --all-files

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache
