from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import (
    FIRST_TREAT_START_YEAR,
    INTERIM_POLICY_FILE,
    MIN_MW_INCREASE,
    RAW_POLICY_FILE,
    TABLES_DIR,
    ensure_project_dirs,
)
from src.utils import build_state_year_scaffold, save_dataframe, to_numeric, validate_unique_keys


def clean_policy_data(raw_path=RAW_POLICY_FILE, output_path=INTERIM_POLICY_FILE) -> pd.DataFrame:
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw policy file: {raw_path}")

    df = pd.read_csv(raw_path, dtype={"state_fips": str})
    required = {"state", "state_abbr", "state_fips", "year", "observed_state_min_wage", "federal_min_wage"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Policy file missing columns: {sorted(missing)}")

    scaffold = build_state_year_scaffold()[["state", "state_abbr", "state_fips", "year"]]
    df = scaffold.merge(
        df,
        on=["state", "state_abbr", "state_fips", "year"],
        how="left",
        validate="one_to_one",
    )

    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["observed_state_min_wage"] = to_numeric(df["observed_state_min_wage"])
    df["federal_min_wage"] = to_numeric(df["federal_min_wage"])
    federal_by_year = df.groupby("year")["federal_min_wage"].transform("max")
    df["federal_min_wage"] = df["federal_min_wage"].fillna(federal_by_year)
    df["observed_state_min_wage"] = df.groupby("state_abbr")["observed_state_min_wage"].ffill()
    df["state_min_wage"] = df[["observed_state_min_wage", "federal_min_wage"]].max(axis=1, skipna=True)
    df["mw_gap"] = df["state_min_wage"] - df["federal_min_wage"]

    df = df.sort_values(["state_abbr", "year"]).reset_index(drop=True)
    df["lag_state_min_wage"] = df.groupby("state_abbr")["state_min_wage"].shift()
    df["state_min_wage_change"] = df["state_min_wage"] - df["lag_state_min_wage"]

    # -- substantive increase: >= MIN_MW_INCREASE threshold (filters CPI micro-adjustments) --
    df["state_min_wage_increase"] = (
        (df["year"] >= FIRST_TREAT_START_YEAR)
        & (df["state_min_wage_change"] >= MIN_MW_INCREASE)
    ).astype(int)

    first_treat = (
        df.loc[df["state_min_wage_increase"] == 1, ["state_abbr", "year"]]
        .groupby("state_abbr", as_index=False)["year"]
        .min()
        .rename(columns={"year": "first_treat_year"})
    )
    df = df.merge(first_treat, on="state_abbr", how="left")
    df["first_treat_year"] = df["first_treat_year"].astype("Int64")
    df["treat_ever"] = df["first_treat_year"].notna().astype(int)
    df["post"] = ((df["treat_ever"] == 1) & (df["year"] >= df["first_treat_year"])).astype(int)
    df["event_time"] = np.where(
        df["treat_ever"] == 1,
        df["year"] - df["first_treat_year"],
        np.nan,
    )

    # -- also keep "any increase" version for robustness --
    df["any_mw_increase"] = (
        (df["year"] >= FIRST_TREAT_START_YEAR) & (df["state_min_wage_change"] > 0)
    ).astype(int)
    first_any = (
        df.loc[df["any_mw_increase"] == 1, ["state_abbr", "year"]]
        .groupby("state_abbr", as_index=False)["year"]
        .min()
        .rename(columns={"year": "first_treat_year_any"})
    )
    df = df.merge(first_any, on="state_abbr", how="left")
    df["first_treat_year_any"] = df["first_treat_year_any"].astype("Int64")
    df["treat_ever_any"] = df["first_treat_year_any"].notna().astype(int)
    df["post_any"] = (
        (df["treat_ever_any"] == 1) & (df["year"] >= df["first_treat_year_any"])
    ).astype(int)

    out = df[
        [
            "state",
            "state_abbr",
            "state_fips",
            "year",
            "observed_state_min_wage",
            "state_min_wage",
            "federal_min_wage",
            "mw_gap",
            "state_min_wage_change",
            "state_min_wage_increase",
            "treat_ever",
            "first_treat_year",
            "post",
            "event_time",
            "treat_ever_any",
            "first_treat_year_any",
            "post_any",
        ]
    ].copy()
    validate_unique_keys(out, ["state_abbr", "year"], name="policy_state_year")
    save_dataframe(out, output_path)

    # -- diagnostics table --
    _write_policy_diagnostics(out)
    return out


def _write_policy_diagnostics(df: pd.DataFrame) -> None:
    """Write per-state treatment diagnostics."""
    states = df[["state", "state_abbr"]].drop_duplicates()
    diag = states.copy()

    # substantive treatment info
    treat_info = (
        df.loc[df["treat_ever"] == 1, ["state_abbr", "first_treat_year"]]
        .drop_duplicates()
    )
    diag = diag.merge(treat_info, on="state_abbr", how="left")
    diag["treat_ever"] = diag["first_treat_year"].notna().astype(int)

    # any-increase info
    any_info = (
        df.loc[df["treat_ever_any"] == 1, ["state_abbr", "first_treat_year_any"]]
        .drop_duplicates()
    )
    diag = diag.merge(any_info, on="state_abbr", how="left")
    diag["treat_ever_any"] = diag["first_treat_year_any"].notna().astype(int)

    # max mw_gap for each state
    max_gap = df.groupby("state_abbr")["mw_gap"].max().reset_index()
    max_gap.columns = ["state_abbr", "max_mw_gap"]
    diag = diag.merge(max_gap, on="state_abbr", how="left")

    # max single-year change
    max_chg = (
        df.loc[df["year"] >= FIRST_TREAT_START_YEAR]
        .groupby("state_abbr")["state_min_wage_change"]
        .max()
        .reset_index()
    )
    max_chg.columns = ["state_abbr", "max_annual_increase"]
    diag = diag.merge(max_chg, on="state_abbr", how="left")

    diag = diag.sort_values(["treat_ever", "first_treat_year", "state_abbr"],
                            ascending=[False, True, True])
    save_dataframe(diag, TABLES_DIR / "policy_diagnostics.csv")

    n_treat = diag["treat_ever"].sum()
    n_any = diag["treat_ever_any"].sum()
    print(f"  Policy diagnostics: {n_treat} states treated (>=${MIN_MW_INCREASE}), "
          f"{n_any} with any increase (>$0).")


def main() -> None:
    ensure_project_dirs()
    out = clean_policy_data()
    print(f"Wrote cleaned policy data to {INTERIM_POLICY_FILE} ({len(out)} rows).")


if __name__ == "__main__":
    main()
