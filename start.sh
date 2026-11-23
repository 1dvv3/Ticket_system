#!/usr/bin/env bash

set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────
# Graduation Ticket System — Offline Launcher
# Run this from anywhere. Once the venv is set up, no internet is used.
#   ./start.sh              start the app
#   SETUP=1 ./start.sh      set up the venv first (needs internet once)
#   START_APP=0 ./start.sh  only check, print the manual start command
# Env overrides: HOST, PORT, PYTHON_VERSION
# ─────────────────────────────────────────────────────────────

APP_NAME="ticket-webapp"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-3389}"
START_APP="${START_APP:-1}"
SETUP="${SETUP:-0}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
VENV_DIR=".venv"

# Resolve the directory this script lives in, and work from there.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Error reporting ──────────────────────────────────────────

log()  { printf '[%s] %s\n' "$APP_NAME" "$*"; }
warn() { printf '[%s] WARNING: %s\n' "$APP_NAME" "$*" >&2; }

die() {
  local message="$1"
  local fix="$2"
  local internet="${3:-no}"
  printf '\n[%s] ERROR: %s\n' "$APP_NAME" "$message" >&2
  printf '[%s] Fix:\n%s\n' "$APP_NAME" "$fix" >&2
  printf '[%s] Internet required: %s\n\n' "$APP_NAME" "$internet" >&2
  exit 1
}

on_error() {
  die "unexpected error on line $1" "Check the output above. If this keeps happening, re-run with SETUP=1 ./start.sh (needs internet once)." "maybe"
}
trap 'on_error "$LINENO"' ERR

# ── Validation ───────────────────────────────────────────────

check_required_files() {
  local -a missing=()
  local f
  for f in app.py requirements.txt templates/index.html fonts/Perandory.ttf ticket_bg.jpg; do
    [[ -f "$f" ]] || missing+=("$f")
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    printf -v joined '  - %s\n' "${missing[@]}"
    die "required app files are missing:
$joined" "Re-download the app (this needs internet once):
  curl -LsSf https://github.com/1dvv3/Ticket_system/archive/refs/heads/main.tar.gz | tar -xz
  cd Ticket_system-main
Then run ./start.sh again." "yes"
  fi

  grep -qi '^[[:space:]]*Flask' requirements.txt || \
    die "requirements.txt exists but does not list Flask" "Restore it from the repo:
  curl -LsSf https://raw.githubusercontent.com/1dvv3/Ticket_system/main/requirements.txt -o requirements.txt" "yes"

  log "All required app files present"
}

check_port() {
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
      die "port $PORT is already in use" "Choose another port:
  PORT=4000 ./start.sh
Or stop whatever is using port $PORT." "no"
    fi
  fi
}

venv_ready() {
  [[ -x "$VENV_DIR/bin/python" ]] && \
    "$VENV_DIR/bin/python" -c 'import flask, reportlab' >/dev/null 2>&1
}

ensure_uv() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 && return 0

  die "uv is not installed and the virtual environment is not ready" "Install uv (needs internet once):
  curl -LsSf https://astral.sh/uv/install.sh | sh
Then run:
  SETUP=1 ./start.sh" "yes"
}

setup_venv() {
  ensure_uv

  log "Installing Python $PYTHON_VERSION via uv (needs internet once)"
  uv python install "$PYTHON_VERSION" || \
    die "could not install Python $PYTHON_VERSION" "Run manually and check the error:
  uv python install $PYTHON_VERSION" "yes"

  log "Creating virtual environment ($VENV_DIR)"
  uv venv --python "$PYTHON_VERSION" --allow-existing "$VENV_DIR" || \
    die "could not create the virtual environment" "Remove it and retry:
  rm -rf $VENV_DIR
  SETUP=1 ./start.sh" "yes"

  log "Installing Flask and reportlab (needs internet once)"
  uv pip install --python "$VENV_DIR/bin/python" -r requirements.txt || \
    die "could not install dependencies" "Run manually and check the error:
  uv pip install --python $VENV_DIR/bin/python -r requirements.txt" "yes"

  uv pip check --python "$VENV_DIR/bin/python" || \
    die "dependency check failed" "Reinstall dependencies:
  uv pip install --python $VENV_DIR/bin/python --reinstall -r requirements.txt" "yes"

  venv_ready || die "virtual environment still cannot import flask and reportlab" "Inspect the error:
  $VENV_DIR/bin/python -c 'import flask, reportlab'
Then reinstall:
  uv pip install --python $VENV_DIR/bin/python --reinstall -r requirements.txt" "yes"

  log "Setup complete — the app will now run fully offline"
}

start_app() {
  check_port

  local url="http://$HOST:$PORT"
  local cmd=(env UV_OFFLINE=1 "$VENV_DIR/bin/python" -m flask --app app run --host "$HOST" --port "$PORT" --no-debug)

  if [[ "$START_APP" != "1" ]]; then
    log "Checks passed. To start the app later (fully offline):"
    log "  cd \"$SCRIPT_DIR\" && ${cmd[*]}"
    return 0
  fi

  log "Starting ticket system at $url (offline)"
  log "Press Ctrl+C to stop"
  # UV_OFFLINE=1 guarantees uv cannot reach the network at runtime.
  "${cmd[@]}"
}

main() {
  log "=== Graduation Ticket System ==="
  log "Folder: $SCRIPT_DIR"
  check_required_files

  if ! venv_ready; then
    if [[ "$SETUP" == "1" ]]; then
      setup_venv
    else
      die "virtual environment is missing or broken (cannot import flask and reportlab)" "Set it up once (needs internet once):
  SETUP=1 ./start.sh
Or manually:
  uv python install $PYTHON_VERSION
  uv venv --python $PYTHON_VERSION $VENV_DIR
  uv pip install --python $VENV_DIR/bin/python -r requirements.txt
After setup, ./start.sh runs fully offline." "yes"
    fi
  else
    log "Virtual environment is ready — no internet needed"
  fi

  start_app
}

main "$@"
