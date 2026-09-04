#!/usr/bin/env bash
# astock-ime 一键刷新（Git-Bash / Linux / macOS）
#   ./run.sh                       # 等价于 python build.py all
#   ./run.sh build --no-imewl      # 只出文本词库
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
[ $# -eq 0 ] && set -- all

if [ -z "${PGPASSWORD:-}" ]; then
  echo "提示：未设置 PGPASSWORD，direct 连库会失败；" \
       "配置了 docker_container 时会自动回退到 docker exec psql。" >&2
fi

"$PY" -X utf8 build.py "$@"
