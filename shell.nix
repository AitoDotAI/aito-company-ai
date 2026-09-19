# aito-company-ai development shell
#
# Provides Python + uv for the loaders, MCP server, FastAPI backend, and
# booktests, plus Node for the React frontend (frontend/, built to
# src/company_ai/web_dist). The Aito instance runs outside this shell:
#   docker pull ghcr.io/aitohq/aito && docker run -p 8080:8080 ghcr.io/aitohq/aito
#
# Usage: nix-shell  (or direnv with `use nix`)

{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "aito-company-ai";

  buildInputs = with pkgs; [
    python312
    uv          # package and venv management; deps live in pyproject.toml
    nodejs_22   # React frontend build (frontend/, deps in package.json)
    jq          # poking Aito API responses on the command line
    curl
  ];

  shellHook = ''
    export UV_PYTHON=${pkgs.python312}/bin/python3
    # nix can leak a py3.11 PYTHONPATH into the 3.12 venv, breaking `import mcp`
    # (cannot import name 'Sentinel' from typing_extensions). Drop it here; for
    # the MCP server Claude Code spawns outside this shell, register it with
    # `env -u PYTHONPATH` (see README, Side 1).
    unset PYTHONPATH

    # Load instance config if present; never committed (see .gitignore).
    if [ -f .env ]; then
      set -a; source .env; set +a
    fi

    echo "aito-company-ai dev shell"
    echo "  python: $(python3 --version 2>&1)"
    echo "  uv:     $(uv --version 2>&1)"
    echo "  node:   $(node --version 2>&1)"
    if [ -n "''${AITO_INSTANCE_URL:-}" ]; then
      echo "  aito:   $AITO_INSTANCE_URL"
    else
      echo "  aito:   not configured. cp .env.example .env and edit."
    fi
  '';
}
