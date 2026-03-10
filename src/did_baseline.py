from __future__ import annotations

import pandas as pd

from src.config import CONTROL_VARS, PANEL_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import available_controls, baseline_sample, run_clustered_ols, save_dataframe, tidy_model, tidy_summary


def estimation_sample(
    df: pd.DataFrame,
    *,
    outcome: str,
    treatment: str,
    controls: list[str],
) -> pd.DataFrame:
    needed = [outcome, treatment, "state", "year", *controls]
    return df.dropna(subset=needed).copy()


def main() -> None:
    ensure_project_dirs()
    if not PANEL_FILE.exists():
        raise FileNotFoundError(f"Missing panel file: {PANEL_FILE}")

    panel = pd.read_csv(PANEL_FILE)
    sample = baseline_sample(panel)

    specs = [
        ("twfe_post_rent_share", "median_rent_pct_income", "post"),
        ("twfe_post_log_rent", "log_median_gross_rent", "post"),
        ("twfe_gap_rent_share", "median_rent_pct_income", "mw_gap"),
    ]
    full_results: list[pd.DataFrame] = []
    summary_results: list[pd.DataFrame] = []

    for model_name, outcome, treatment in specs:
        controls = available_controls(sample, CONTROL_VARS)
        frame = estimation_sample(sample, outcome=outcome, treatment=treatment, controls=controls)
        rhs = [treatment, *controls, "C(state)", "C(year)"]
        formula = f"{outcome} ~ " + " + ".join(rhs)
        model = run_clustered_ols(frame, formula=formula, cluster_col="state")
        full_results.append(tidy_model(model, model_name=model_name, outcome=outcome, treatment=treatment))

        # clean summary: only treatment + controls
        terms_of_interest = [treatment, *controls]
        summ = tidy_summary(model, model_name=model_name, outcome=outcome,
                            treatment=treatment, terms_of_interest=terms_of_interest)
        summary_results.append(summ)

    out = pd.concat(full_results, ignore_index=True)
    save_dataframe(out, TABLES_DIR / "did_baseline.csv")

    summary = pd.concat(summary_results, ignore_index=True)
    save_dataframe(summary, TABLES_DIR / "did_summary.csv")

    print("Baseline DiD results written to outputs/tables/did_baseline.csv.")
    print("Summary table written to outputs/tables/did_summary.csv.")


if __name__ == "__main__":
    main()
