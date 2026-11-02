#!/bin/sh
# Script tests of one tool in an empty environment: python:3.11-slim with only the
# packages that the skills declare. The tests run in the container Python (pytest,
# pyyaml). The scripts run in a separate venv that holds only the declared packages,
# so an undeclared import fails.
# Usage (from the repo root, inside the container): sh ci/run-empty.sh TOOL
set -eu
tool="$1"
export PYTHONDONTWRITEBYTECODE=1
pip install --quiet --no-cache-dir -r ci/requirements.txt
packages="$(python ci/declared.py packages "$tool")"
if [ -n "$packages" ]; then
  python -m venv /tmp/skillenv
  # shellcheck disable=SC2086
  /tmp/skillenv/bin/pip install --quiet --no-cache-dir $packages
else
  python -m venv --without-pip /tmp/skillenv
fi
export SKILL_PYTHON=/tmp/skillenv/bin/python
echo "scripts run with: $($SKILL_PYTHON --version), packages: ${packages:-none}"
# shellcheck disable=SC2046
python -m pytest -p no:cacheprovider -q $(python ci/declared.py paths "$tool")
