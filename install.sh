#!/usr/bin/env bash

set -Eeuo pipefail

# ─────────────────────────────────────────────────────────────
# Graduation Ticket System — Installer / Updater
# First run (internet needed once): downloads the app, sets up Python.
# After that use start.sh — running the app needs no internet.
#   ./install.sh              fresh install into ~/Applications/ticket-webapp
#   UPDATE=1 ./install.sh     refresh app files, keep data.json and .venv
# Env overrides: TICKET_APP_DIR, HOST, PORT, PYTHON_VERSION, START_APP, UPDATE
# ─────────────────────────────────────────────────────────────

APP_NAME="ticket-webapp"
DEFAULT_APP_DIR="$HOME/Applications/$APP_NAME"
APP_DIR="${TICKET_APP_DIR:-$DEFAULT_APP_DIR}"
ARCHIVE_URL="${TICKET_APP_ARCHIVE_URL:-https://github.com/1dvv3/Ticket_system/archive/refs/heads/main.tar.gz}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-3389}"
START_APP="${START_APP:-1}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
UPDATE="${UPDATE:-0}"
VENV_DIR=".venv"

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
  die "unexpected error on line $1" "Check the output above, then retry. If the problem persists, re-download the app (needs internet once)." "maybe"
}
trap 'on_error "$LINENO"' ERR

# ── Tool checks ──────────────────────────────────────────────

check_tools() {
  local missing=()
  command -v curl >/dev/null 2>&1 || missing+=("curl")
  command -v tar  >/dev/null 2>&1 || missing+=("tar")

  if [[ ${#missing[@]} -gt 0 ]]; then
    printf -v joined '  - %s\n' "${missing[@]}"
    die "missing required tools:
$joined" "Install them first. On macOS: xcode-select --install
On Debian/Ubuntu: sudo apt install curl tar
On Arch: sudo pacman -S curl tar" "yes"
  fi
}

ensure_uv() {
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 && { log "uv already installed: $(uv --version)"; return 0; }

  log "Installing uv (needs internet once)"
  curl -LsSf https://astral.sh/uv/install.sh | sh || \
    die "could not install uv" "Run manually and check the error:
  curl -LsSf https://astral.sh/uv/install.sh | sh" "yes"

  command -v uv >/dev/null 2>&1 || \
    die "uv was installed but is not on PATH" "Add it to your PATH and open a new terminal:
  export PATH=\"\$HOME/.local/bin:\$PATH\"
Then re-run this script." "no"
  log "uv installed: $(uv --version)"
}

# ── App download / update ────────────────────────────────────

validate_app_files() {
  local -a missing=()
  local f
  for f in app.py requirements.txt templates/index.html fonts/Perandory.ttf ticket_bg.jpg start.sh; do
    [[ -f "$APP_DIR/$f" ]] || missing+=("$f")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    printf -v joined '  - %s\n' "${missing[@]}"
    die "downloaded app is missing files:
$joined" "Try downloading again:
  rm -rf \"$APP_DIR\"
  TICKET_APP_DIR=\"$APP_DIR\" ./install.sh" "yes"
  fi
  log "All required app files present"
}

prepare_app_dir() {
  # Fresh install: use a copy already in cwd if we're inside the repo.
  if [[ "$UPDATE" != "1" && -z "${TICKET_APP_DIR:-}" && \
        -f "$PWD/app.py" && -f "$PWD/templates/index.html" ]]; then
    APP_DIR="$PWD"
    log "Using current directory: $APP_DIR"
    return
  fi

  mkdir -p "$(dirname "$APP_DIR")" || \
    die "cannot create parent directory of $APP_DIR" "Choose a writable location:
  TICKET_APP_DIR=~/ticket-app ./install.sh" "no"

  if [[ "$UPDATE" != "1" && -e "$APP_DIR" && -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
    log "App directory already exists at $APP_DIR — skipping download"
    log "To refresh app files while keeping data.json and .venv, run: UPDATE=1 ./install.sh"
    return
  fi

  local tmp_dir source_dir
  tmp_dir="$(mktemp -d)"
  log "Downloading app from $ARCHIVE_URL (needs internet)"
  if ! curl -fsSL "$ARCHIVE_URL" -o "$tmp_dir/app.tar.gz"; then
    die "could not download the app archive from $ARCHIVE_URL" "Check your internet connection, then retry:
  UPDATE=1 ./install.sh
Or use a local archive:
  TICKET_APP_ARCHIVE_URL=file:///path/to/archive.tar.gz ./install.sh" "yes"
  fi

  if ! tar -xzf "$tmp_dir/app.tar.gz" -C "$tmp_dir"; then
    die "downloaded archive could not be extracted" "Try again; if it keeps failing, download manually and set TICKET_APP_ARCHIVE_URL." "yes"
  fi

  source_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [[ -n "$source_dir" ]] || die "archive contained no app directory" "Check the archive URL:
  $ARCHIVE_URL" "yes"

  if [[ "$UPDATE" == "1" && -e "$APP_DIR" ]]; then
    local backup_dir entry name
    backup_dir="$(mktemp -d)"
    [[ -f "$APP_DIR/data.json" ]] && cp -p "$APP_DIR/data.json" "$backup_dir/data.json"
    [[ -d "$APP_DIR/$VENV_DIR" ]] && mv "$APP_DIR/$VENV_DIR" "$backup_dir/$VENV_DIR"

    for entry in "$source_dir"/* "$source_dir"/.[!.]* "$source_dir"/..?*; do
      [[ -e "$entry" ]] || continue
      name="$(basename "$entry")"
      [[ "$name" == "data.json" ]] && continue
      rm -rf "$APP_DIR/$name"
      cp -R "$entry" "$APP_DIR/$name"
    done

    [[ -f "$backup_dir/data.json" ]] && cp -p "$backup_dir/data.json" "$APP_DIR/data.json"
    [[ -d "$backup_dir/$VENV_DIR" ]] && mv "$backup_dir/$VENV_DIR" "$APP_DIR/$VENV_DIR"
    rm -rf "$backup_dir"
    log "App updated in place — data.json and .venv preserved"
  else
    if [[ -e "$APP_DIR" ]]; then
      die "$APP_DIR already exists and is not empty" "Choose a different directory:
  TICKET_APP_DIR=~/my-tickets ./install.sh
Or refresh it:
  UPDATE=1 ./install.sh" "no"
    fi
    mv "$source_dir" "$APP_DIR" || die "could not move app into $APP_DIR" "Check permissions on the parent directory." "no"
    log "App installed to $APP_DIR"
  fi

  rm -rf "$tmp_dir"
}

# ── Python / dependencies ────────────────────────────────────

venv_ready() {
  [[ -x "$APP_DIR/$VENV_DIR/bin/python" ]] && \
    "$APP_DIR/$VENV_DIR/bin/python" -c 'import flask, reportlab' >/dev/null 2>&1
}

ensure_requirements() {
  if [[ -f "$APP_DIR/requirements.txt" ]]; then
    grep -qi '^[[:space:]]*Flask' "$APP_DIR/requirements.txt" || \
      die "requirements.txt exists but does not list Flask" "Restore it from the repo:
  curl -LsSf https://raw.githubusercontent.com/1dvv3/Ticket_system/main/requirements.txt -o \"$APP_DIR/requirements.txt\"" "yes"
    log "requirements.txt present and valid"
    return
  fi
  cat > "$APP_DIR/requirements.txt" <<'EOF'
Flask>=3.0,<4.0
reportlab>=4.0,<5.0
EOF
  log "Created requirements.txt"
}

install_python_packages() {
  cd "$APP_DIR"
  if venv_ready; then
    log "Virtual environment is ready — skipping Python/dependency install"
    return
  fi

  ensure_uv
  log "Installing Python $PYTHON_VERSION (needs internet once)"
  uv python install "$PYTHON_VERSION" || \
    die "could not install Python $PYTHON_VERSION" "Run manually:
  uv python install $PYTHON_VERSION" "yes"

  log "Creating virtual environment"
  uv venv --python "$PYTHON_VERSION" --allow-existing "$VENV_DIR" || \
    die "could not create virtual environment" "Remove it and retry:
  rm -rf \"$APP_DIR/$VENV_DIR\"
  ./install.sh" "yes"

  ensure_requirements
  log "Installing dependencies (needs internet once)"
  uv pip install --python "$VENV_DIR/bin/python" -r requirements.txt || \
    die "could not install dependencies" "Run manually and check the error:
  cd \"$APP_DIR\" && uv pip install --python $VENV_DIR/bin/python -r requirements.txt" "yes"

  uv pip check --python "$VENV_DIR/bin/python" || \
    die "dependency check failed" "Reinstall:
  cd \"$APP_DIR\" && uv pip install --python $VENV_DIR/bin/python --reinstall -r requirements.txt" "yes"

  venv_ready || die "virtual environment still cannot import flask and reportlab" "Inspect the problem:
  \"$APP_DIR/$VENV_DIR/bin/python\" -c 'import flask, reportlab'" "yes"
  log "Python environment ready — running the app will need no internet"
}

# ── Launch ───────────────────────────────────────────────────

check_port() {
  if command -v lsof >/dev/null 2>&1; then
    if lsof -i ":$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
      die "port $PORT is already in use" "Use another port:
  PORT=4000 ./install.sh" "no"
    fi
  fi
}

launch() {
  cd "$APP_DIR"
  if [[ "$START_APP" != "1" ]]; then
    log "Install complete. Start the app any time (offline) with:"
    log "  cd \"$APP_DIR\" && ./start.sh"
    return
  fi

  check_port
  local url="http://$HOST:$PORT"
  log "Starting ticket system at $url"
  log "Press Ctrl+C to stop"

  # start.sh uses UV_OFFLINE=1 so the running app never touches the network.
  SETUP=0 HOST="$HOST" PORT="$PORT" "$APP_DIR/$VENV_DIR/bin/python" -m flask \
    --app app run --host "$HOST" --port "$PORT" --no-debug &
  local server_pid=$!
  trap "kill $server_pid 2>/dev/null; wait $server_pid 2>/dev/null; exit 0" INT TERM

  log "Waiting for server at $url ..."
  for i in $(seq 1 15); do
    if curl -sf "$url" >/dev/null 2>&1; then
      log "Server is ready"
      break
    fi
    [[ $i -eq 15 ]] && { log "Server did not respond — open $url manually"; break; }
    sleep 1
  done

  if command -v open >/dev/null 2>&1; then
    open "$url" || warn "could not open browser — navigate to $url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" || warn "could not open browser — navigate to $url"
  else
    log "Open $url in your browser"
  fi

  wait "$server_pid" || true
}

main() {
  log "=== Graduation Ticket System Installer ==="
  [[ "$UPDATE" == "1" ]] && log "Mode: UPDATE (app files refreshed, data.json and .venv preserved)"
  log "Target: $APP_DIR"
  check_tools
  prepare_app_dir
  validate_app_files
  chmod +x "$APP_DIR/start.sh" 2>/dev/null || warn "could not mark start.sh executable; run: chmod +x \"$APP_DIR/start.sh\""
  install_python_packages
  launch
}

main "$@"
