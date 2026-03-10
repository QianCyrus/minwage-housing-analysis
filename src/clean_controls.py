from __future__ import annotations

import pandas as pd

from src.config import INTERIM_CONTROLS_FILE, RAW_LAUS_FILE, RAW_QCEW_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import log_if_positive, save_dataframe, to_numeric, validate_unique_keys


def clean_controls(
    laus_path=RAW_LAUS_FILE,
    qcew_path=RAW_QCEW_FILE,
    output_path=INTERIM_CONTROLS_FILE,
) -> pd.DataFrame:
    if not laus_path.exists():
        raise FileNotFoundError(f"Missing LAUS raw file: {laus_path}")

    laus = pd.read_csv(laus_path, dtype={"state_fips": str})

    laus["year"] = pd.to_numeric(laus["year"], errors="coerce").astype("Int64")
    laus["unemployment_rate"] = to_numeric(laus["unemployment_rate"])

    qcew_available = qcew_path.exists()
    if qcew_available:
        qcew = pd.read_csv(qcew_path, dtype={"state_fips": str})
        qcew["year"] = pd.to_numeric(qcew["year"], errors="coerce").astype("Int64")
        qcew["avg_weekly_wage"] = to_numeric(qcew["avg_weekly_wage"])
        if "annual_employment" in qcew:
            qcew["annual_employment"] = to_numeric(qcew["annual_employment"])
        out = laus.merge(
            qcew,
            on=["state", "state_abbr", "state_fips", "year"],
            how="outer",
            validate="one_to_one",
        )
    else:
        out = laus.copy()
        out["avg_weekly_wage"] = pd.NA
        out["annual_employment"] = pd.NA
        print("  WARNING: QCEW wage data not found. avg_weekly_wage will be entirely missing.")
        print("           This means log_avg_weekly_wage cannot be used as a control variable.")

    out["log_avg_weekly_wage"] = log_if_positive(out["avg_weekly_wage"])
    out = out.sort_values(["state_abbr", "year"]).reset_index(drop=True)
    validate_unique_keys(out, ["state_abbr", "year"], name="controls_state_year")
    save_dataframe(out, output_path)

    # -- data quality report --
    _write_controls_quality(out, qcew_available)
    return out


def _write_controls_quality(df: pd.DataFrame, qcew_available: bool) -> None:
    """Write a quality report for control variables."""
    rows = []
    for col in ["unemployment_rate", "avg_weekly_wage", "log_avg_weekly_wage", "annual_employment"]:
        if col not in df.columns:
            rows.append({"variable": col, "total": len(df), "non_missing": 0,
                         "missing": len(df), "missing_pct": 100.0, "status": "NOT IN DATA"})
            continue
        n_miss = int(df[col].isna().sum())
        n_valid = len(df) - n_miss
        rows.append({
            "variable": col,
            "total": len(df),
            "non_missing": n_valid,
            "missing": n_miss,
            "missing_pct": round(n_miss / len(df) * 100, 1),
            "status": "OK" if n_valid > 0 else "ALL MISSING",
        })
    quality = pd.DataFrame(rows)
    quality["qcew_file_found"] = qcew_available
    save_dataframe(quality, TABLES_DIR / "controls_quality.csv")
    print(f"  Controls quality report written ({quality.loc[quality['status']=='OK', 'variable'].tolist()} available).")


def main() -> None:
    ensure_project_dirs()
    out = clean_controls()
    print(f"Wrote cleaned controls to {INTERIM_CONTROLS_FILE} ({len(out)} rows).")


if __name__ == "__main__":
    main()
