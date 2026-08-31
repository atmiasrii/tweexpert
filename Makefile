# Quill — developer commands.
PY ?= python
VENV := .venv
ifeq ($(OS),Windows_NT)
  BIN := $(VENV)/Scripts
else
  BIN := $(VENV)/bin
endif

.PHONY: help venv install doctor seed test api worker browser fe fe-build up down clean

help:
	@echo "Quill make targets:"
	@echo "  make install    create venv + install backend deps + frontend deps"
	@echo "  make doctor     check deps, GPU, model endpoint, session, selectors, db (O-07)"
	@echo "  make seed       create schema + populate the fixture queue/shadow log (T-01)"
	@echo "  make test       run the acceptance suite (§25)"
	@echo "  make api        run the API (uvicorn) on 127.0.0.1:8000"
	@echo "  make worker     run the worker (scheduler + pipeline)"
	@echo "  make browser    run the browser process (engine owner)"
	@echo "  make fe         run the Vite dev server"
	@echo "  make fe-build   build the dashboard into frontend/dist"
	@echo "  make up / down  docker compose up -d / down"

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(BIN)/python -m pip install -r backend/requirements.txt
	cd frontend && npm install

doctor:
	cd backend && ../$(BIN)/python -m quill.ops.doctor

seed:
	cd backend && ../$(BIN)/python -m quill.seed

test:
	cd backend && ../$(BIN)/python -m pytest tests/ -q

api:
	cd backend && ../$(BIN)/python -m uvicorn quill.api.app:app --host 127.0.0.1 --port 8000 --reload

worker:
	cd backend && ../$(BIN)/python -m quill.worker

browser:
	cd backend && ../$(BIN)/python -m quill.browser_proc

fe:
	cd frontend && npm run dev

fe-build:
	cd frontend && npm run build

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	rm -rf backend/data/quill.db* backend/data/debug/* frontend/dist
