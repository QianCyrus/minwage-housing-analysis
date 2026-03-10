from __future__ import annotations

import re

import pandas as pd

from src.config import (
    INTERIM_CONTROLS_FILE,
    INTERIM_OUTCOMES_FILE,
    INTERIM_POLICY_FILE,
    INTERIM_ZHVI_FILE,
    PANEL_FILE,
    RAW_ZHVI_FILE,
    TABLES_DIR,
    ensure_project_dirs,
)
from src.utils import (
    build_state_year_scaffold,
    log_if_positive,
    save_dataframe,
    standardize_state_name,
    to_numeric,
    validate_unique_keys,
)


def load_zhvi_state_year(raw_path=RAW_ZHVI_FILE, output_path=INTERIM_ZHVI_FILE) -> pd.DataFrame | None:
    if not raw_path.exists():
        return None

    raw = pd.read_csv(raw_path, dtype={"state_fips": str})
    if {"state", "state_abbr", "state_fips", "date", "zhvi"}.issubset(raw.columns):
        long = raw.copy()
    else:
        date_cols = [col for col in raw.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(col))]
        if "RegionName" not in raw.columns or not date_cols:
            raise ValueError("Unsupported Zillow schema.")
        long = raw.copy()
        long["state"] = long["RegionName"].map(standardize_state_name)
        long = long.melt(
            id_vars=["state"],
            value_vars=date_cols,
            var_name="date",
            value_name="zhvi",
        )

    long["date"] = pd.to_datetime(long["date"])
    long["year"] = long["date"].dt.year.astype("Int64")
    long["zhvi"] = to_numeric(long["zhvi"])
    group_cols = ["state", "year"]
    if "state_abbr" in long.columns:
        group_cols.insert(1, "state_abbr")
    if "state_fips" in long.columns:
        group_cols.insert(2, "state_fips")
    annual = (
        long.groupby(group_cols, as_index=False)["zhvi"]
        .mean()
        .sort_values([col for col in group_cols if col != "year"] + ["year"])
    )
    save_dataframe(annual, output_path)
    return annual


def build_panel(
    policy_path=INTERIM_POLICY_FILE,
    outcomes_path=INTERIM_OUTCOMES_FILE,
    controls_path=INTERIM_CONTROLS_FILE,
    output_path=PANEL_FILE,
) -> pd.DataFrame:
    for path in [policy_path, outcomes_path, controls_path]:
        if not path.exists():
            raise FileNotFoundError(f"Missing cleaned input file: {path}")

    scaffold = build_state_year_scaffold()
    policy = pd.read_csv(policy_path, dtype={"state_fips": str})
    outcomes = pd.read_csv(outcomes_path, dtype={"state_fips": str})
    controls = pd.read_csv(controls_path, dtype={"state_fips": str})
    zhvi = load_zhvi_state_year()

    merge_log = []

    panel = scaffold.merge(
        policy,
        on=["state", "state_abbr", "state_fips", "year"],
        how="left",
        validate="one_to_one",
    )
    merge_log.append({"step": "scaffold + policy", "rows_after": len(panel),
                       "new_cols": len(policy.columns) - 4})

    panel = panel.merge(
        outcomes,
        on=["state", "state_abbr", "state_fips", "year"],
        how="left",
        validate="one_to_one",
    )
    merge_log.append({"step": "+ outcomes", "rows_after": len(panel),
                       "new_cols": len(outcomes.columns) - 4})

    panel = panel.merge(
        controls,
        on=["state", "state_abbr", "state_fips", "year"],
        how="left",
        validate="one_to_one",
    )
    merge_log.append({"step": "+ controls", "rows_after": len(panel),
                       "new_cols": len(controls.columns) - 4})

    if zhvi is not None:
        join_keys = [key for key in ["state", "state_abbr", "state_fips", "year"] if key in zhvi.columns]
        panel = panel.merge(zhvi, on=join_keys, how="left")
        merge_log.append({"step": "+ zhvi", "rows_after": len(panel), "new_cols": 1})
    else:
        panel["zhvi"] = pd.NA
        merge_log.append({"step": "+ zhvi (missing)", "rows_after": len(panel), "new_cols": 1})

    panel["is_2020"] = (panel["year"] == 2020).astype(int)
    panel["in_baseline_sample"] = (panel["year"] != 2020).astype(int)
    panel["log_state_min_wage"] = log_if_positive(panel["state_min_wage"])
    panel["log_median_gross_rent"] = log_if_positive(panel["median_gross_rent"])
    panel["log_zhvi"] = log_if_positive(panel["zhvi"])

    validate_unique_keys(panel, ["state_abbr", "year"], name="state_year_panel")
    panel = panel.sort_values(["state_abbr", "year"]).reset_index(drop=True)
    save_dataframe(panel, output_path)

    # -- merge diagnostics --
    merge_diag = pd.DataFrame(merge_log)
    merge_diag["total_cols"] = merge_diag["new_cols"].cumsum() + 4
    save_dataframe(merge_diag, TABLES_DIR / "merge_diagnostics.csv")

    # -- panel completeness --
    n_states = panel["state_abbr"].nunique()
    n_years = panel["year"].nunique()
    n_baseline = panel.loc[panel["in_baseline_sample"] == 1].shape[0]
    completeness = pd.DataFrame([{
        "n_states": n_states,
        "n_years": n_years,
        "expected_rows": n_states * n_years,
        "actual_rows": len(panel),
        "balanced": n_states * n_years == len(panel),
        "baseline_rows": n_baseline,
        "total_columns": len(panel.columns),
    }])
    save_dataframe(completeness, TABLES_DIR / "panel_completeness.csv")
    print(f"  Panel: {n_states} states x {n_years} years = {len(panel)} rows, "
          f"{len(panel.columns)} columns.")

    return panel


def main() -> None:
    ensure_project_dirs()
    panel = build_panel()
    print(f"Wrote merged panel to {PANEL_FILE} ({len(panel)} rows).")


if __name__ == "__main__":
    main()
