#!/usr/bin/env bash
# Local-dev wrapper for aito-company-ai.
#
# Most commands take an optional <config> that selects the dotenv file
# .env.<config> (and thus the Aito instance + port). e.g. `./do dev aito`
# uses .env.aito. With no <config>, .env.local is used when present, else
# .env. The port comes from COMPANY_AI_PORT in the chosen file (else 8770),
# so an instance's endpoint and port travel together; the PORT env var still
# overrides. Each instance is managed on its own port independently.
#
#   ./do install              uv sync + npm install (one-time)
#   ./do build                build the React frontend (vite → src/company_ai/web_dist)
#   ./do seed [config]        create schema + load every table from data/seed
#   ./do seed-tiny [config]   same, from data/seed_tiny (cold-start dataset)
#   ./do migrate [config]     diagnose + apply the non-destructive schema migration
#   ./do doctor [config]      read-only schema/drift + build report
#   ./do start [config]       start the dashboard in the background (PID-managed)
#   ./do stop [config]        stop the background dashboard
#   ./do restart [config]     rebuild + restart the background dashboard
#   ./do status [config]      is the dashboard up? which instance, which port
#   ./do serve [config]       run the dashboard in the foreground (logs to terminal)
#   ./do dev [config]         vite dev (:5173, hot reload) + backend on its port
#   ./do logs [config]        tail the background dashboard log
#   ./do test [sel]           run the booktest suite (book/), or a selector
#   ./do test-ui              run the frontend unit tests (vitest)
#   ./do mcp [config]         run the MCP server in the foreground (stdio)
#   ./do image                build the deployable container (app + synthetic seed)
#   ./do smoke [config]       build + boot the image locally, check it serves
#   ./do clean                wipe build artifacts and PID/log files
#
# Examples:
#   ./do dev                  hot-reload dev on the default/local instance
#   ./do dev aito             dev against .env.aito (its own endpoint + port)
#   ./do start aito           background dashboard for the aito instance

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

die() { echo "✗ $*" >&2; exit 1; }
say() { echo "→ $*"; }

# resolve <config>: choose the dotenv file (COMPANY_AI_ENV) and the port, then
# derive the per-port PID/log/health so instances don't collide. A given
# <config> wins; else a pre-set COMPANY_AI_ENV; else .env.local if present;
# else .env. PORT (env) > COMPANY_AI_PORT in the file > 8770.
resolve() {
  local cfg="${1:-}"
  if [ -n "$cfg" ]; then
    [ -f ".env.$cfg" ] || die ".env.$cfg not found (configs: $(ls .env.* 2>/dev/null | sed 's/^.env.//' | grep -v example | tr '\n' ' '))"
    export COMPANY_AI_ENV=".env.$cfg"
  elif [ -z "${COMPANY_AI_ENV:-}" ] && [ -f .env.local ]; then
    export COMPANY_AI_ENV=.env.local
  fi
  local file="${COMPANY_AI_ENV:-.env}"
  if [ -z "${PORT:-}" ]; then
    # COMPANY_AI_PORT from the chosen file (digits only; missing is fine)
    local p=""
    [ -f "$file" ] && p=$(sed -n 's/^COMPANY_AI_PORT=//p' "$file" | tr -dc '0-9')
    PORT="${p:-8770}"
  fi
  PIDFILE=".dashboard.${PORT}.pid"
  LOGFILE=".dashboard.${PORT}.log"
  HEALTH="http://127.0.0.1:${PORT}/api/score-options"  # static, needs no Aito
}

env_label() { echo "${COMPANY_AI_ENV:-.env}"; }

ensure_built() {
  [ -f src/company_ai/web_dist/index.html ] || cmd_build
}

running() {
  [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

cmd_install() {
  command -v uv >/dev/null 2>&1 || die "uv not found (see https://docs.astral.sh/uv/)"
  command -v npm >/dev/null 2>&1 || die "npm not found"
  say "uv sync"
  uv sync
  say "npm install (frontend)"
  ( cd frontend && npm install --no-audit --no-fund )
}

cmd_build() {
  [ -d frontend/node_modules ] || ( cd frontend && npm install --no-audit --no-fund )
  ( cd frontend && npm run build )
  say "web_dist ready"
}

IMAGE="${COMPANY_AI_IMAGE:-aito-company-ai:local}"

# Build the deployable container (app + synthetic seed only; see Dockerfile).
cmd_image() {
  say "building image $IMAGE"
  docker build -t "$IMAGE" .
  say "built $IMAGE"
}

# Boot the image locally and check it serves — the reversible pre-deploy smoke.
# Points at whatever Aito your chosen .env names (dashboard reads it at runtime).
cmd_smoke() {
  cmd_image
  local port="${SMOKE_PORT:-8899}"
  say "running $IMAGE on :$port (Ctrl-C stops)"
  docker rm -f company-ai-smoke >/dev/null 2>&1 || true
  # liveness/SPA don't call Aito; a placeholder URL just gets the app past its
  # config assert. Set AITO_INSTANCE_URL/AITO_API_KEY to exercise data too.
  docker run -d --name company-ai-smoke -p "$port:8770" \
    -e "AITO_INSTANCE_URL=${AITO_INSTANCE_URL:-http://placeholder:9005}" \
    -e "AITO_API_KEY=${AITO_API_KEY:-smoke}" "$IMAGE" >/dev/null
  sleep 3
  if curl -fsS "http://localhost:$port/api/health" >/dev/null; then
    say "health OK; SPA: $(curl -fsS -o /dev/null -w '%{http_code}' http://localhost:$port/)"
  else
    say "health FAILED — logs:"; docker logs company-ai-smoke | tail -20
  fi
  say "stop with: docker rm -f company-ai-smoke"
}

cmd_seed() {
  resolve "${1:-}"
  local dir="${SEED_DIR:-data/seed}"
  say "seeding via $(env_label) from $dir"
  uv run company-ai create-schema
  uv run company-ai load-companies --dir "$dir"   # link target; load before contacts/deals
  for cmd in load-rolodex load-touches load-sessions load-materials load-channels load-posts load-todos load-deals load-decisions load-experiments load-events load-documents; do
    uv run company-ai "$cmd" --dir "$dir"
  done
}

cmd_seed_tiny() { SEED_DIR=data/seed_tiny cmd_seed "${1:-}"; }

cmd_doctor() { resolve "${1:-}"; uv run company-ai doctor; }

# bring an instance's schema up to the code, non-destructively: diagnose,
# add any missing tables/columns (create-schema; never drops data), re-check.
cmd_migrate() {
  resolve "${1:-}"
  say "migrating $(env_label) — diagnosing first"
  uv run company-ai doctor
  echo
  uv run company-ai create-schema
  echo
  say "after migration:"
  uv run company-ai doctor
}

cmd_start() {
  resolve "${1:-}"
  ensure_built
  if running; then say "already running (pid $(cat "$PIDFILE")) on :$PORT"; return; fi
  say "starting dashboard on :$PORT via $(env_label)"
  nohup uv run company-ai dashboard --port "$PORT" >"$LOGFILE" 2>&1 &
  echo $! >"$PIDFILE"
  for _ in $(seq 1 30); do
    if curl -sf -o /dev/null "$HEALTH"; then
      say "up → http://localhost:${PORT}  (logs: ./do logs, stop: ./do stop)"
      return
    fi
    sleep 0.5
  done
  die "did not come up in 15s — see $LOGFILE"
}

cmd_stop() {
  resolve "${1:-}"
  if running; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
  fi
  # also sweep any stragglers from this repo's dashboard on this port
  pkill -f "company-ai dashboard --port ${PORT}" 2>/dev/null || true
  rm -f "$PIDFILE"
  say "stopped (:$PORT)"
}

cmd_restart() { cmd_stop "${1:-}"; cmd_build; cmd_start "${1:-}"; }

cmd_status() {
  resolve "${1:-}"
  if running && curl -sf -o /dev/null "$HEALTH"; then
    say "running: pid $(cat "$PIDFILE"), http://localhost:${PORT}, instance $(env_label)"
  elif running; then
    say "process up (pid $(cat "$PIDFILE")) but not answering on :$PORT — see ./do logs"
  else
    say "not running (:$PORT, $(env_label))"
  fi
}

cmd_serve() {
  resolve "${1:-}"
  ensure_built
  say "serving on :$PORT via $(env_label) (Ctrl-C to stop)"
  exec uv run company-ai dashboard --port "$PORT"
}

cmd_dev() {
  resolve "${1:-}"
  [ -d frontend/node_modules ] || cmd_install
  # you always open PORT (as in prod); the dev backend sits at PORT+1, so an
  # instance keeps to its own slice of the port range (2000 → UI 2000, API 2001).
  local backend=$((PORT + 1))
  say "frontend → http://localhost:${PORT} (vite dev, hot reload)"
  say "backend  → http://localhost:${backend} (uvicorn, via $(env_label))"
  ( uv run company-ai dashboard --port "$backend" ) &
  local back=$!
  trap 'kill $back 2>/dev/null || true' EXIT INT TERM
  ( cd frontend && VITE_PORT="$PORT" VITE_API_PORT="$backend" npm run dev )
}

cmd_logs() { resolve "${1:-}"; tail -f "$LOGFILE"; }

cmd_test() { exec uv run booktest "${@:-book}"; }

cmd_test_ui() {
  [ -d frontend/node_modules ] || ( cd frontend && npm install --no-audit --no-fund )
  ( cd frontend && exec npm test )
}

cmd_mcp() { resolve "${1:-}"; exec uv run company-ai-mcp; }

cmd_clean() {
  cmd_stop 2>/dev/null || true
  rm -rf src/company_ai/web_dist frontend/.vite "$PIDFILE" "$LOGFILE"
  find . -type d -name __pycache__ -not -path './.venv/*' -prune -exec rm -rf {} + 2>/dev/null || true
  say "cleaned"
}

cmd_help() { sed -n '2,/^set -/p' "$0" | sed -n '/^#/p' | sed 's/^# \{0,1\}//'; }

case "${1:-help}" in
  install)        shift; cmd_install "$@" ;;
  build)          shift; cmd_build "$@" ;;
  seed)           shift; cmd_seed "$@" ;;
  seed-tiny)      shift; cmd_seed_tiny "$@" ;;
  migrate)        shift; cmd_migrate "$@" ;;
  doctor)         shift; cmd_doctor "$@" ;;
  start)          shift; cmd_start "$@" ;;
  stop)           shift; cmd_stop "$@" ;;
  restart)        shift; cmd_restart "$@" ;;
  status)         shift; cmd_status "$@" ;;
  serve)          shift; cmd_serve "$@" ;;
  dev)            shift; cmd_dev "$@" ;;
  logs)           shift; cmd_logs "$@" ;;
  test)           shift; cmd_test "$@" ;;
  test-ui)        shift; cmd_test_ui "$@" ;;
  mcp)            shift; cmd_mcp "$@" ;;
  image)          shift; cmd_image "$@" ;;
  smoke)          shift; cmd_smoke "$@" ;;
  clean)          shift; cmd_clean "$@" ;;
  help|-h|--help) cmd_help ;;
  *) die "unknown command: $1 (run './do help')" ;;
esac
