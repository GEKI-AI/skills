#!/bin/sh
# Tools for one CI job on the runner (Python, uv and Node are already there).
# Usage, from the repo root: sh ci/setup.sh [venv] [skills-ref] [pi] [prism] [gitleaks]
#
#   venv         .cache/venv with the packages of ci/requirements.txt, put on PATH
#   skills-ref   the Agent Skills validator, at the commit in ci/pins.env
#   pi           Pi in .cache/pi, its path in PI_BIN
#   prism        Prism in .cache/prism
#   gitleaks     gitleaks in .cache/gitleaks, put on PATH
#
# The versions are in ci/pins.env. The workflow caches .cache/pi, .cache/prism and
# .cache/gitleaks, so a download happens only when a version changes.
set -eu
set -a
. ./ci/pins.env
set +a
path_add() { if [ -n "${GITHUB_PATH:-}" ]; then echo "$1" >> "$GITHUB_PATH"; fi; PATH="$1:$PATH"; export PATH; }
env_add() { if [ -n "${GITHUB_ENV:-}" ]; then echo "$1=$2" >> "$GITHUB_ENV"; fi; }

for tool in "$@"; do
  case "$tool" in
    venv)
      uv venv --quiet --python 3.12 .cache/venv
      uv pip install --quiet --python .cache/venv/bin/python -r ci/requirements.txt
      path_add "$PWD/.cache/venv/bin"
      ;;
    skills-ref)
      uv pip install --quiet --python .cache/venv/bin/python "$SKILLS_REF"
      ;;
    pi)
      if [ ! -x .cache/pi/node_modules/.bin/pi ]; then
        npm install --prefix .cache/pi --no-audit --no-fund --silent \
          "@earendil-works/pi-coding-agent@${PI_VERSION}"
      fi
      env_add PI_BIN "$PWD/.cache/pi/node_modules/.bin/pi"
      ;;
    prism)
      if [ ! -x .cache/prism/node_modules/.bin/prism ]; then
        npm install --prefix .cache/prism --no-audit --no-fund --silent \
          "@stoplight/prism-cli@${PRISM_VERSION}"
      fi
      ;;
    gitleaks)
      if [ ! -x .cache/gitleaks/gitleaks ]; then
        mkdir -p .cache/gitleaks
        base="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}"
        archive="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
        curl -sSfL -o ".cache/gitleaks/$archive" "$base/$archive"
        curl -sSfL -o .cache/gitleaks/checksums.txt "$base/gitleaks_${GITLEAKS_VERSION}_checksums.txt"
        (cd .cache/gitleaks && grep " $archive\$" checksums.txt | sha256sum -c - && tar xzf "$archive" gitleaks)
      fi
      path_add "$PWD/.cache/gitleaks"
      ;;
    *)
      echo "unknown tool: $tool" >&2
      exit 2
      ;;
  esac
done
