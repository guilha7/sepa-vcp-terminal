#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "========================================================================"
echo "  SEPA/VCP TRADING TERMINAL (Mark Minervini) — 100% Gratuito / Local"
echo "========================================================================"

if [ ! -f ".env" ]; then
  echo "[INFO] A criar .env a partir de .env.example..."
  cp .env.example .env
fi

# 1. Backend Python venv
if [ ! -x "backend/.venv/bin/python" ]; then
  echo "[1/4] A criar ambiente virtual Python..."
  python3 -m venv backend/.venv
  echo "[2/4] A instalar dependências Python..."
  backend/.venv/bin/pip install --upgrade pip
  backend/.venv/bin/pip install -r backend/requirements.txt
else
  echo "[1/4] Ambiente Python encontrado."
fi

# 2. Frontend Node dependencies
if [ ! -d "frontend/node_modules" ]; then
  echo "[2/4] A instalar dependências do frontend..."
  (cd frontend && npm install)
else
  echo "[2/4] Dependências do frontend encontradas."
fi

cleanup() {
  echo ""
  echo "A encerrar Backend e Frontend..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[3/4] A iniciar Backend FastAPI em http://127.0.0.1:8000 ..."
(cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

sleep 2

echo "[4/4] A iniciar Frontend React em http://127.0.0.1:5173 ..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "========================================================================"
echo "  TERMINAL ATIVO EM LOCALHOST!"
echo "  Dashboard : http://127.0.0.1:5173"
echo "  API Docs  : http://127.0.0.1:8000/docs"
echo "  Prime Ctrl+C para encerrar ambos os servidores."
echo "========================================================================"

wait
