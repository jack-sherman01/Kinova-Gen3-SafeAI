#!/usr/bin/env bash
# Run a Kortex Python example (or any script) with the workspace venv.
# Usage:
#   ./run.sh list                                   # list available examples
#   ./run.sh check [--ip 192.168.1.10]              # read-only connection check
#   ./run.sh 102-Movement_high_level/01-move_angular_and_cartesian.py [--ip ...] [-u admin -p admin]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$ROOT/.venv/bin/python"
EXAMPLES="$ROOT/Kinova-kortex2_Gen3_G3L/api_python/examples"

case "${1:-}" in
    ""|-h|--help)
        sed -n '2,6p' "$0"; exit 0 ;;
    list)
        cd "$EXAMPLES" && find . -mindepth 2 -name '[0-9]*.py' | sed 's|^\./||' | sort; exit 0 ;;
    check)
        shift; exec "$PY" "$ROOT/check_connection.py" "$@" ;;
esac

TARGET="$1"; shift
[[ -f "$TARGET" ]] || TARGET="$EXAMPLES/$TARGET"
[[ -f "$TARGET" ]] || { echo "Not found: $TARGET (try ./run.sh list)"; exit 1; }
cd "$(dirname "$TARGET")"
exec "$PY" "$(basename "$TARGET")" "$@"
