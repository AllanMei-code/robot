#!/usr/bin/env bash
set -euo pipefail

# ==============================================
# Start Qwen service and backend (Ubuntu/Linux)
# - Supports llama.cpp (default) or Ollama
# - Uses local venv if present: .venv/bin/activate
# - Backend via Gunicorn (start.sh), logs under ./logs
# ==============================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

mkdir -p logs

# ---- Activate venv if exists ----
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# ---- Common env (backend + frontend expectations) ----
export PYTHONIOENCODING="utf-8"
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:5000}"
export FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-http://127.0.0.1:5000}"

# ---- LLM client settings (backend -> OpenAI-compatible server) ----
# Default to llama.cpp server on 127.0.0.1:8080
export LLM_BASE_URL="${LLM_BASE_URL:-http://127.0.0.1:8080/v1}"
export LLM_API_KEY="${LLM_API_KEY:-sk-noauth}"
export LLM_MODEL="${LLM_MODEL:-qwen2.5-3b-instruct-q5_k_m}"
export LLM_CHAT_FORMAT="${LLM_CHAT_FORMAT:-qwen}"
export LLM_MAX_RETRIES="${LLM_MAX_RETRIES:-0}"

# ---- Qwen backend choice: llama.cpp (default) or Ollama ----
QWEN_MODE="${QWEN_MODE:-llama}"

start_llama() {
  echo "[QWEN] Starting llama.cpp OpenAI server on 127.0.0.1:8080 ..."
  : "${QWEN_MODEL_PATH:="${REPO_ROOT}/models/qwen2.5-3b-instruct-q5_k_m.gguf"}"
  if [[ ! -f "$QWEN_MODEL_PATH" ]]; then
    echo "[WARN] GGUF model not found: $QWEN_MODEL_PATH"
    echo "       Set QWEN_MODEL_PATH to your local Qwen GGUF model."
    echo "       Skipping Qwen start; backend will still start."
    return 0
  fi
  if ! command -v llama-server >/dev/null 2>&1; then
    echo "[ERROR] llama-server not found in PATH. Install llama.cpp server or add it to PATH."
    echo "        Skipping Qwen start; backend will still start."
    return 0
  fi
  nohup llama-server \
    -m "$QWEN_MODEL_PATH" \
    --host 127.0.0.1 --port 8080 \
    -c 4096 --parallel 2 \
    > "${REPO_ROOT}/logs/qwen.log" 2>&1 & echo $! > "${REPO_ROOT}/qwen.pid"
}

start_ollama() {
  echo "[QWEN] Using Ollama on 127.0.0.1:11434 ..."
  export LLM_BASE_URL="http://127.0.0.1:11434/v1"
  : "${LLM_MODEL:="qwen2.5:3b-instruct"}"
  if ! command -v ollama >/dev/null 2>&1; then
    echo "[ERROR] Ollama not found in PATH. Install Ollama or set QWEN_MODE=llama."
    echo "        Skipping Qwen start; backend will still start."
    return 0
  fi
  # Start Ollama daemon
  nohup ollama serve > "${REPO_ROOT}/logs/ollama.log" 2>&1 & echo $! > "${REPO_ROOT}/ollama.pid"
  # Optional: warmup (disabled to avoid network pulls)
  # nohup bash -lc "sleep 3; ollama run ${LLM_MODEL} 'hello'" > logs/ollama-warmup.log 2>&1 &
}

start_backend() {
  echo "[BACKEND] Starting Flask+Socket.IO (Gunicorn) on http://127.0.0.1:5000 ..."
  # start.sh execs gunicorn; keep it in background and capture PID
  nohup bash -lc "bash start.sh" > "${REPO_ROOT}/logs/backend.log" 2>&1 & echo $! > "${REPO_ROOT}/backend.pid"
}

case "$QWEN_MODE" in
  ollama) start_ollama ;;
  *)      start_llama ;;
esac

start_backend

echo
echo "=============================================="
echo "Started in background with logs under ./logs:"
echo "- Qwen service:    logs/qwen.log or logs/ollama.log"
echo "- Backend server:  logs/backend.log (gunicorn.log also used)"
echo "Environment:"
echo "  LLM_BASE_URL=$LLM_BASE_URL"
echo "  LLM_MODEL=$LLM_MODEL"
echo "  LLM_CHAT_FORMAT=$LLM_CHAT_FORMAT"
echo "  API_BASE_URL=$API_BASE_URL"
echo "Open http://127.0.0.1:5000 in your browser."
echo "PID files: backend.pid, qwen.pid/ollama.pid"
echo "To stop: xargs kill < backend.pid (and qwen.pid/ollama.pid)"
echo "=============================================="

