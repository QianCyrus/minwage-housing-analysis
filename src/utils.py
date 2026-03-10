from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.config import BASELINE_YEARS, END_YEAR, START_YEAR, ensure_project_dirs, state_metadata


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_dataframe(df: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    ensure_parent(path)
    df.to_csv(path, index=index)


def clean_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.replace(r"[^\d\.-]", "", regex=True),
        errors="coerce",
    )


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def log_if_positive(series: pd.Series) -> pd.Series:
    values = to_numeric(series)
    return pd.Series(np.where(values > 0, np.log(values), np.nan), index=series.index)


def build_state_year_scaffold(
    start_year: int = START_YEAR,
    end_year: int = END_YEAR,
) -> pd.DataFrame:
    states = state_metadata()
    years = pd.DataFrame({"year": list(range(start_year, end_year + 1))})
    scaffold = states.merge(years, how="cross")
    return scaffold.sort_values(["state_abbr", "year"]).reset_index(drop=True)


def state_maps() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    meta = state_metadata()
    abbr_to_name = dict(zip(meta["state_abbr"], meta["state"]))
    fips_to_name = dict(zip(meta["state_fips"], meta["state"]))
    fips_to_abbr = dict(zip(meta["state_fips"], meta["state_abbr"]))
    return abbr_to_name, fips_to_name, fips_to_abbr


def standardize_state_name(value: str) -> str | None:
    if pd.isna(value):
        return None
    raw = str(value).strip()
    normalized = " ".join(raw.split())
    abbr_to_name, _, _ = state_maps()
    if normalized.upper() in abbr_to_name:
        return abbr_to_name[normalized.upper()]
    aliases = {
        "Washington, DC": "District of Columbia",
        "Washington DC": "District of Columbia",
        "D.C.": "District of Columbia",
        "DC": "District of Columbia",
    }
    return aliases.get(normalized, normalized)


def add_state_identifiers(df: pd.DataFrame, *, state_col: str = "state") -> pd.DataFrame:
    meta = state_metadata()
    out = df.copy()
    out[state_col] = out[state_col].map(standardize_state_name)
    out = out.merge(meta, on=state_col, how="left", suffixes=("", "_meta"))
    if "state_abbr_meta" in out:
        out["state_abbr"] = out["state_abbr"].fillna(out["state_abbr_meta"])
        out = out.drop(columns=["state_abbr_meta"])
    if "state_fips_meta" in out:
        out["state_fips"] = out["state_fips"].fillna(out["state_fips_meta"])
        out = out.drop(columns=["state_fips_meta"])
    return out


def validate_unique_keys(df: pd.DataFrame, key_cols: Iterable[str], *, name: str) -> None:
    duplicates = df.duplicated(list(key_cols), keep=False)
    if duplicates.any():
        sample = df.loc[duplicates, list(key_cols)].head()
        raise ValueError(f"{name} has duplicate keys for {list(key_cols)}:\n{sample}")


def baseline_sample(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df["year"].isin(BASELINE_YEARS)].copy()


def available_controls(df: pd.DataFrame, requested_controls: Iterable[str],
                       min_coverage: float = 0.5) -> list[str]:
    """Return controls that have at least `min_coverage` fraction of non-missing values."""
    controls: list[str] = []
    for control in requested_controls:
        if control in df.columns and df[control].notna().mean() >= min_coverage:
            controls.append(control)
    return controls


def run_clustered_ols(
    df: pd.DataFrame,
    *,
    formula: str,
    cluster_col: str = "state",
):
    import statsmodels.formula.api as smf

    required_columns = [cluster_col]
    if cluster_col not in df:
        raise KeyError(f"Cluster column '{cluster_col}' is missing.")
    model = smf.ols(formula=formula, data=df).fit(
        cov_type="cluster",
        cov_kwds={"groups": df[cluster_col]},
    )
    return model


def tidy_model(model, *, model_name: str, outcome: str, treatment: str) -> pd.DataFrame:
    conf_int = model.conf_int()
    frame = pd.DataFrame(
        {
            "term": model.params.index,
            "coef": model.params.values,
            "std_err": model.bse.values,
            "t_stat": model.tvalues.values,
            "p_value": model.pvalues.values,
            "ci_low": conf_int[0].values,
            "ci_high": conf_int[1].values,
        }
    )
    frame["model_name"] = model_name
    frame["outcome"] = outcome
    frame["treatment"] = treatment
    frame["nobs"] = int(model.nobs)
    frame["r_squared"] = model.rsquared
    return frame[
        [
            "model_name",
            "outcome",
            "treatment",
            "term",
            "coef",
            "std_err",
            "t_stat",
            "p_value",
            "ci_low",
            "ci_high",
            "nobs",
            "r_squared",
        ]
    ]


def tidy_summary(
    model,
    *,
    model_name: str,
    outcome: str,
    treatment: str,
    terms_of_interest: list[str] | None = None,
) -> pd.DataFrame:
    """Extract key coefficients only (no fixed-effect dummies)."""
    full = tidy_model(model, model_name=model_name, outcome=outcome, treatment=treatment)
    if terms_of_interest is None:
        # keep everything except state/year FE dummies and Intercept
        mask = ~full["term"].str.startswith("C(") & (full["term"] != "Intercept")
        out = full.loc[mask].copy()
    else:
        out = full.loc[full["term"].isin(terms_of_interest)].copy()
    try:
        out["r_squared_adj"] = model.rsquared_adj
    except Exception:
        out["r_squared_adj"] = np.nan
    # count clusters from the groups array used for clustering
    try:
        groups = model.cov_kwds.get("groups", None) if hasattr(model, "cov_kwds") else None
        out["n_clusters"] = int(groups.nunique()) if groups is not None else np.nan
    except Exception:
        out["n_clusters"] = np.nan
    return out


def event_term_name(event_time: int) -> str:
    prefix = "m" if event_time < 0 else "p"
    return f"event_{prefix}{abs(event_time)}"


def summarize_missingness(df: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "column": df.columns,
            "missing_count": df.isna().sum().values,
            "missing_share": df.isna().mean().values,
        }
    )
    return summary.sort_values(["missing_share", "column"], ascending=[False, True]).reset_index(
        drop=True
    )


def initialize_project() -> None:
    ensure_project_dirs()
