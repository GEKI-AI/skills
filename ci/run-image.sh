#!/bin/sh
# Script tests of one tool in the GEKI sandbox image. The image has its Python
# libraries preinstalled. Declared packages that it lacks are installed here, as
# they are at every session start, and reported.
# Usage (from the repo root, inside the image): sh ci/run-image.sh TOOL
set -eu
tool="$1"
export PYTHONDONTWRITEBYTECODE=1
pip install --user --quiet pytest pyyaml
for package in $(python ci/declared.py packages "$tool"); do
  if ! python -c "import importlib.metadata as m; m.version('$package')" 2>/dev/null; then
    echo "::warning::$package is declared by a $tool skill and not in the GEKI image"
    pip install --user --quiet "$package"
  fi
done
# shellcheck disable=SC2046
python -m pytest -p no:cacheprovider -q $(python ci/declared.py paths "$tool")
