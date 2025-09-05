@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION

REM ==============================================
REM Start Qwen service and backend (Windows .bat)
REM - Supports llama.cpp (default) or Ollama
REM - Uses local venv if present: .venv\Scripts\activate.bat
REM - Backend runs via python -m backend.app (gevent WSGIServer)
REM ==============================================

REM Repo root (folder of this script)
set "REPO_ROOT=%~dp0"
pushd "%REPO_ROOT%" >nul 2>&1

REM ---- Activate venv if exists ----
if exist "%REPO_ROOT%\.venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\.venv\Scripts\activate.bat"
)

REM ---- Common env (backend + frontend expectations) ----
set "FLASK_ENV=development"
set "API_BASE_URL=http://localhost:5000"
set "FRONTEND_ORIGINS=http://localhost:5000"
set "PYTHONIOENCODING=utf-8"

REM ---- LLM client settings (backend -> OpenAI-compatible server) ----
REM Default to llama.cpp server on 127.0.0.1:8080
if not defined LLM_BASE_URL set "LLM_BASE_URL=http://127.0.0.1:8080/v1"
if not defined LLM_API_KEY  set "LLM_API_KEY=sk-noauth"
if not defined LLM_MODEL    set "LLM_MODEL=qwen2.5-3b-instruct-q5_k_m"
if not defined LLM_CHAT_FORMAT set "LLM_CHAT_FORMAT=qwen"
if not defined LLM_MAX_RETRIES set "LLM_MAX_RETRIES=0"

REM ---- Qwen backend choice: llama.cpp (default) or Ollama ----
REM Set QWEN_MODE=ollama to use Ollama; otherwise uses llama.cpp
if /I "%QWEN_MODE%"=="ollama" goto :START_OLLAMA
goto :START_LLAMA

:START_LLAMA
echo [QWEN] Starting llama.cpp OpenAI server on 127.0.0.1:8080 ...
REM Adjust the path below to your local GGUF model file if different
if not defined QWEN_MODEL_PATH set "QWEN_MODEL_PATH=%REPO_ROOT%models\qwen2.5-3b-instruct-q5_k_m.gguf"

if not exist "%QWEN_MODEL_PATH%" (
  echo [WARN] GGUF model not found: "%QWEN_MODEL_PATH%"
  echo        Please set QWEN_MODEL_PATH to your local Qwen GGUF model.
  echo        Will still try to start backend; Qwen API may be unavailable.
  goto :START_BACKEND
)

REM Try to start llama.cpp server in a new window
REM Common flags: change as needed (ctx-size, threads, etc.)
where llama-server >nul 2>&1
if errorlevel 1 (
  echo [ERROR] llama-server not found in PATH. Install llama.cpp server or add it to PATH.
  goto :START_BACKEND
)

start "qwen-server" cmd /k ^
  llama-server ^
    -m "%QWEN_MODEL_PATH%" ^
    --host 127.0.0.1 --port 8080 ^
    -c 4096 --parallel 2

goto :START_BACKEND

:START_OLLAMA
echo [QWEN] Using Ollama on 127.0.0.1:11434 ...
set "LLM_BASE_URL=http://127.0.0.1:11434/v1"
REM Choose your model tag that exists locally, e.g. qwen2.5:3b-instruct
if not defined LLM_MODEL set "LLM_MODEL=qwen2.5:3b-instruct"

where ollama >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Ollama not found in PATH. Install Ollama or switch to llama.cpp (unset QWEN_MODE).
  goto :START_BACKEND
)

REM Start Ollama server
start "ollama-serve" cmd /k ollama serve

REM Optional: ensure the model is warmed up if already pulled (no network pull here)
REM timeout /t 3 >nul
REM start "ollama-warmup" cmd /k ollama run %LLM_MODEL% "你好"

goto :START_BACKEND

:START_BACKEND
echo [BACKEND] Starting Flask+Socket.IO server on http://localhost:5000 ...
start "backend" cmd /k python -m backend.app

echo.
echo ==============================================
echo Started processes (each in its own window):
echo - Qwen service (llama.cpp or Ollama)
echo - Backend server (Flask+Socket.IO)
echo Environment:
echo   LLM_BASE_URL=%LLM_BASE_URL%
echo   LLM_MODEL=%LLM_MODEL%
echo   LLM_CHAT_FORMAT=%LLM_CHAT_FORMAT%
echo   API_BASE_URL=%API_BASE_URL%
echo Open http://localhost:5000 in your browser.
echo ==============================================

popd >nul 2>&1
exit /b 0

