from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import CONTROL_VARS, PANEL_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import available_controls, baseline_sample, save_dataframe, run_clustered_ols, tidy_model, tidy_summary


def main() -> None:
    ensure_project_dirs()
    if not PANEL_FILE.exists():
        raise FileNotFoundError(f"Missing panel file: {PANEL_FILE}")

    panel = pd.read_csv(PANEL_FILE)
    baseline = baseline_sample(panel)
    baseline["year_centered"] = baseline["year"] - baseline["year"].min()

    specs = [
        (
            "continuous_gap",
            baseline,
            "median_rent_pct_income",
            "mw_gap",
            False,
        ),
        (
            "state_trends",
            baseline,
            "median_rent_pct_income",
            "post",
            True,
        ),
        (
            "pre_2020_only",
            baseline.loc[baseline["year"] <= 2019].copy(),
            "median_rent_pct_income",
            "post",
            False,
        ),
        (
            "alt_outcome_level_rent",
            baseline,
            "median_gross_rent",
            "post",
            False,
        ),
    ]

    # -- add "any_increase" specification (old treatment definition, no threshold) --
    if "post_any" in baseline.columns:
        specs.append((
            "any_increase",
            baseline,
            "median_rent_pct_income",
            "post_any",
            False,
        ))

    full_results: list[pd.DataFrame] = []
    summary_results: list[pd.DataFrame] = []

    for model_name, frame, outcome, treatment, add_state_trends in specs:
        controls = available_controls(frame, CONTROL_VARS)
        needed = [outcome, treatment, "state", "year", *controls]
        if add_state_trends:
            needed.append("year_centered")
        sample = frame.dropna(subset=needed).copy()
        rhs = [treatment, *controls, "C(state)", "C(year)"]
        formula = f"{outcome} ~ " + " + ".join(rhs)
        if add_state_trends:
            formula += " + C(state):year_centered"
        model = run_clustered_ols(sample, formula=formula, cluster_col="state")
        full_results.append(tidy_model(model, model_name=model_name, outcome=outcome, treatment=treatment))
        terms_of_interest = [treatment, *controls]
        summary_results.append(
            tidy_summary(model, model_name=model_name, outcome=outcome,
                         treatment=treatment, terms_of_interest=terms_of_interest)
        )

    # -- Placebo test: random permutation of treatment assignment --
    print("  Running placebo test (100 permutations)...")
    placebo_coefs = _run_placebo(baseline, n_iter=100)
    save_dataframe(placebo_coefs, TABLES_DIR / "placebo_test.csv")

    out = pd.concat(full_results, ignore_index=True)
    save_dataframe(out, TABLES_DIR / "robustness_checks.csv")

    summary = pd.concat(summary_results, ignore_index=True)
    save_dataframe(summary, TABLES_DIR / "robustness_summary.csv")

    print("Robustness checks written to outputs/tables/robustness_checks.csv.")
    print("Robustness summary written to outputs/tables/robustness_summary.csv.")


def _run_placebo(baseline: pd.DataFrame, n_iter: int = 100) -> pd.DataFrame:
    """Randomly reassign treatment across states and re-estimate, collecting placebo coefficients."""
    controls = available_controls(baseline, CONTROL_VARS)
    needed = ["median_rent_pct_income", "state", "year", *controls]
    sample = baseline.dropna(subset=needed).copy()

    states = sample["state"].unique()
    n_treated = int(sample.drop_duplicates("state")["treat_ever"].sum())

    rng = np.random.default_rng(42)
    coefs = []
    for i in range(n_iter):
        fake_treated = set(rng.choice(states, size=n_treated, replace=False))
        sample["placebo_post"] = sample["state"].isin(fake_treated).astype(int)
        rhs = ["placebo_post", *controls, "C(state)", "C(year)"]
        formula = "median_rent_pct_income ~ " + " + ".join(rhs)
        try:
            model = run_clustered_ols(sample, formula=formula, cluster_col="state")
            coefs.append({"iteration": i, "placebo_coef": model.params["placebo_post"],
                          "placebo_pval": model.pvalues["placebo_post"]})
        except Exception:
            pass

    return pd.DataFrame(coefs)


if __name__ == "__main__":
    main()
