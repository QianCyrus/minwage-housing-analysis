#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SKIP_DOWNLOAD=0
WITH_ZILLOW=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-download)
      SKIP_DOWNLOAD=1
      shift
      ;;
    --with-zillow)
      WITH_ZILLOW=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: bash scripts/run_pipeline.sh [--skip-download] [--with-zillow]" >&2
      exit 1
      ;;
  esac
done

if [[ $SKIP_DOWNLOAD -eq 0 ]]; then
  DATASETS=(minimum_wage acs laus qcew)
  if [[ $WITH_ZILLOW -eq 1 ]]; then
    DATASETS+=(zillow)
  fi
  python -m src.download_data --datasets "${DATASETS[@]}"
fi

python -m src.clean_policy
python -m src.clean_outcomes
python -m src.clean_controls
python -m src.build_panel
python -m src.eda
python -m src.did_baseline
python -m src.event_study
python -m src.robustness
python -m src.heterogeneity
python -m src.make_figures

echo "Pipeline finished. Key output: data/processed/state_year_panel.csv"
