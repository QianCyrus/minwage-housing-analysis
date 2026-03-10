from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    INTERIM_OUTCOMES_FILE,
    RAW_ACS_RENT_FILE,
    RAW_ACS_RENT_SHARE_FILE,
    ensure_project_dirs,
)
from src.utils import log_if_positive, save_dataframe, to_numeric, validate_unique_keys


def load_acs_table(raw_path, *, value_col: str, output_col: str) -> pd.DataFrame:
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing ACS raw file: {raw_path}")
    df = pd.read_csv(raw_path, dtype={"state_fips": str})
    required = {"state", "state_abbr", "state_fips", "year", value_col}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"ACS file missing columns: {sorted(missing)}")
    out = df[["state", "state_abbr", "state_fips", "year", value_col]].copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out[output_col] = to_numeric(out[value_col])
    return out.drop(columns=[value_col])


def clean_outcomes(
    rent_share_path=RAW_ACS_RENT_SHARE_FILE,
    rent_path=RAW_ACS_RENT_FILE,
    output_path=INTERIM_OUTCOMES_FILE,
) -> pd.DataFrame:
    rent_share = load_acs_table(
        rent_share_path,
        value_col="B25071_001E",
        output_col="median_rent_pct_income",
    )
    rent = load_acs_table(
        rent_path,
        value_col="B25064_001E",
        output_col="median_gross_rent",
    )

    out = rent_share.merge(rent, on=["state", "state_abbr", "state_fips", "year"], how="outer")
    out["acs_comparable"] = (out["year"] != 2020).astype(int)
    out["rent_burden_high"] = np.where(
        out["median_rent_pct_income"].notna(),
        (out["median_rent_pct_income"] >= 30).astype(int),
        np.nan,
    )
    out["log_median_gross_rent"] = log_if_positive(out["median_gross_rent"])
    out = out.sort_values(["state_abbr", "year"]).reset_index(drop=True)
    validate_unique_keys(out, ["state_abbr", "year"], name="outcomes_state_year")
    save_dataframe(out, output_path)
    return out


def main() -> None:
    ensure_project_dirs()
    out = clean_outcomes()
    print(f"Wrote cleaned outcomes to {INTERIM_OUTCOMES_FILE} ({len(out)} rows).")


if __name__ == "__main__":
    main()
