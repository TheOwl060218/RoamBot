#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export ROAMBOT_PROVIDER_MODE="${ROAMBOT_PROVIDER_MODE:-mock}"
export ROAMBOT_DEMO_MODE="${ROAMBOT_DEMO_MODE:-true}"
export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost}"

if [[ "$ROAMBOT_PROVIDER_MODE" != "mock" || "$ROAMBOT_DEMO_MODE" != "true" ]]; then
  echo 'Automated tests require mock provider mode with demo data.' >&2
  exit 1
fi

if [[ -x .venv/bin/python ]]; then
  python=.venv/bin/python
elif [[ -x .venv/Scripts/python.exe ]]; then
  python=.venv/Scripts/python.exe
else
  echo 'Python virtual environment not found. Create .venv first.' >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo 'Node.js 24 LTS was not found on PATH.' >&2
  exit 1
fi

"$python" -m pytest backend/tests -q -W error
"$python" -m ruff check backend/src backend/tests

pushd frontend >/dev/null
node node_modules/vitest/vitest.mjs run
node node_modules/eslint/bin/eslint.js .
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
node node_modules/@playwright/test/cli.js test
popd >/dev/null
