#!/usr/bin/env bash
#
# Start PaperPrism on http://localhost:8000
#
# Installs whatever is missing, builds the frontend if it is stale, then runs
# the server. Safe to re-run: everything it does is skipped when already done.
#
#   ./run.sh              start on port 8000
#   ./run.sh 9000         start on another port
#   ./run.sh --rebuild    force a fresh frontend build

set -euo pipefail

cd "$(dirname "$0")"

VENV=.venv
PORT=8000
REBUILD=0

for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    ''|*[!0-9]*) echo "Unrecognised argument: $arg" >&2; exit 2 ;;
    *) PORT="$arg" ;;
  esac
done

say()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[33m!\033[0m   %s\n' "$1"; }
die()  { printf '\033[31mx\033[0m   %s\n' "$1" >&2; exit 1; }

# --- prerequisites ---------------------------------------------------------

# Node is needed to build the frontend once; after that it is only needed
# again when the frontend source changes. Tell people how to get it on the
# machine they are actually sitting at rather than pointing at a download page.
# The package name differs from the command name and from one package manager
# to the next: on Debian `node` is an unrelated ham-radio program, and the one
# you want is `nodejs`. Getting this wrong sends people to install the wrong
# thing, so each manager gets its own name.
#
#   how_to_install <brew-name> <deb/rpm-name> <arch-name> <download-url>
how_to_install() {
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null; then
        echo "Install it with:  brew install $1"
      else
        echo "Install Homebrew from https://brew.sh, then:  brew install $1"
        echo "Or download the macOS installer from $4"
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null; then
        echo "Install it with:  sudo apt install $2"
      elif command -v dnf >/dev/null; then
        echo "Install it with:  sudo dnf install $2"
      elif command -v pacman >/dev/null; then
        echo "Install it with:  sudo pacman -S $3"
      else
        echo "Get it from $4"
      fi
      ;;
    *) echo "Get it from $4" ;;
  esac
}

missing() {
  printf '\033[31mx\033[0m   %s is not installed.\n' "$1" >&2
  shift
  how_to_install "$@" | while IFS= read -r line; do printf '    %s\n' "$line" >&2; done
  printf '    Then run ./run.sh again.\n' >&2
  exit 1
}

NODE_URL=https://nodejs.org
PY_URL=https://www.python.org/downloads/

command -v python3 >/dev/null || missing "python3" python3 python3 python "$PY_URL"
command -v node    >/dev/null || missing "node" node nodejs nodejs "$NODE_URL"
command -v npm     >/dev/null || missing "npm (it ships with node)" node npm nodejs "$NODE_URL"

python3 - <<'PY' || die "PaperPrism needs Python 3.10 or newer. You have $(python3 -V 2>&1)."
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY

# --- backend ---------------------------------------------------------------

if [ ! -d "$VENV" ]; then
  say "Creating the Python virtualenv"
  python3 -m venv "$VENV" 2>/dev/null || die \
    "Could not create a virtualenv. On Debian or Ubuntu: sudo apt install python3-venv"
fi

PY_BIN="$VENV/bin/python"
[ -x "$PY_BIN" ] || PY_BIN="$VENV/Scripts/python.exe"   # git-bash on Windows
[ -x "$PY_BIN" ] || die "The virtualenv at $VENV looks broken. Delete it and re-run."

if ! "$PY_BIN" -c "import fastapi, pypdf, anthropic" 2>/dev/null; then
  say "Installing backend dependencies"
  "$PY_BIN" -m pip install --quiet --upgrade pip
  "$PY_BIN" -m pip install --quiet -r backend/requirements.txt
fi

# --- frontend --------------------------------------------------------------

if [ ! -d frontend/node_modules ]; then
  say "Installing frontend dependencies (this one takes a minute)"
  (cd frontend && npm install --silent)
fi

needs_build=$REBUILD
[ -f frontend/dist/index.html ] || needs_build=1
if [ "$needs_build" -eq 0 ]; then
  # Rebuild when any source file is newer than the built entry point.
  if [ -n "$(find frontend/src frontend/index.html -newer frontend/dist/index.html 2>/dev/null | head -1)" ]; then
    needs_build=1
  fi
fi

if [ "$needs_build" -eq 1 ]; then
  say "Building the frontend"
  (cd frontend && npm run build >/dev/null)
fi

# --- configuration ---------------------------------------------------------

if [ ! -f .env ]; then
  warn "No .env file, so PaperPrism will start in demo mode."
  warn "To analyse real papers:  cp .env.example .env   and add your key."
elif ! grep -qE '^\s*(export\s+)?ANTHROPIC_API_KEY\s*=\s*\S' .env; then
  warn "ANTHROPIC_API_KEY is empty in .env, so PaperPrism will start in demo mode."
fi

# --- go --------------------------------------------------------------------

echo
say "PaperPrism is starting on http://localhost:$PORT"
say "Press Ctrl-C to stop."
echo

cd backend
exec "../$PY_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
