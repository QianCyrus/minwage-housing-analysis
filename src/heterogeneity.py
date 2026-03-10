from __future__ import annotations

import pandas as pd

from src.config import CONTROL_VARS, FIRST_TREAT_START_YEAR, PANEL_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import (
    available_controls,
    baseline_sample,
    run_clustered_ols,
    save_dataframe,
    tidy_model,
    tidy_summary,
)


def estimation_sample(
    df: pd.DataFrame,
    *,
    outcome: str,
    treatment: str,
    controls: list[str],
) -> pd.DataFrame:
    needed = [outcome, treatment, "state", "year", *controls]
    return df.dropna(subset=needed).copy()


def compute_subgroup_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add high_burden and high_rent indicators based on pre-treatment medians."""
    pre = df.loc[df["year"] < FIRST_TREAT_START_YEAR]

    burden_by_state = pre.groupby("state")["median_rent_pct_income"].mean()
    rent_by_state = pre.groupby("state")["median_gross_rent"].mean()

    cutoff_burden = burden_by_state.median()
    cutoff_rent = rent_by_state.median()

    out = df.copy()
    out["high_burden"] = out["state"].map(burden_by_state >= cutoff_burden).astype(int)
    out["high_rent"] = out["state"].map(rent_by_state >= cutoff_rent).astype(int)
    out["post_x_high_burden"] = out["post"] * out["high_burden"]
    out["post_x_high_rent"] = out["post"] * out["high_rent"]
    return out


def run_passthrough(sample: pd.DataFrame, controls: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estimate rent pass-through rate: how much does rent rise per $1 of MW gap."""
    outcome = "median_gross_rent"
    treatment = "mw_gap"
    frame = estimation_sample(sample, outcome=outcome, treatment=treatment, controls=controls)
    rhs = [treatment, *controls, "C(state)", "C(year)"]
    formula = f"{outcome} ~ " + " + ".join(rhs)
    model = run_clustered_ols(frame, formula=formula, cluster_col="state")

    name = "passthrough_mw_gap"
    full = tidy_model(model, model_name=name, outcome=outcome, treatment=treatment)
    summ = tidy_summary(model, model_name=name, outcome=outcome, treatment=treatment,
                        terms_of_interest=[treatment, *controls])
    return full, summ


def run_interaction_models(sample: pd.DataFrame, controls: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run 4 interaction regressions (2 outcomes x 2 moderators)."""
    specs = [
        ("interact_burden_rentshare", "median_rent_pct_income", "post", "post_x_high_burden"),
        ("interact_burden_rentlevel", "median_gross_rent", "post", "post_x_high_burden"),
        ("interact_rent_rentshare", "median_rent_pct_income", "post", "post_x_high_rent"),
        ("interact_rent_rentlevel", "median_gross_rent", "post", "post_x_high_rent"),
    ]
    full_results: list[pd.DataFrame] = []
    summary_results: list[pd.DataFrame] = []

    for model_name, outcome, treatment, interaction in specs:
        frame = estimation_sample(sample, outcome=outcome, treatment=treatment, controls=controls)
        rhs = [treatment, interaction, *controls, "C(state)", "C(year)"]
        formula = f"{outcome} ~ " + " + ".join(rhs)
        model = run_clustered_ols(frame, formula=formula, cluster_col="state")

        full_results.append(tidy_model(model, model_name=model_name, outcome=outcome, treatment=treatment))
        terms = [treatment, interaction, *controls]
        summary_results.append(tidy_summary(model, model_name=model_name, outcome=outcome,
                                            treatment=treatment, terms_of_interest=terms))

    return pd.concat(full_results, ignore_index=True), pd.concat(summary_results, ignore_index=True)


def run_subgroup_models(sample: pd.DataFrame, controls: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run DiD separately for each subgroup (8 regressions)."""
    specs = [
        ("high_burden_rentshare", "high_burden", 1, "median_rent_pct_income", "post"),
        ("low_burden_rentshare", "high_burden", 0, "median_rent_pct_income", "post"),
        ("high_burden_rentlevel", "high_burden", 1, "median_gross_rent", "post"),
        ("low_burden_rentlevel", "high_burden", 0, "median_gross_rent", "post"),
        ("high_rent_rentshare", "high_rent", 1, "median_rent_pct_income", "post"),
        ("low_rent_rentshare", "high_rent", 0, "median_rent_pct_income", "post"),
        ("high_rent_rentlevel", "high_rent", 1, "median_gross_rent", "post"),
        ("low_rent_rentlevel", "high_rent", 0, "median_gross_rent", "post"),
    ]
    full_results: list[pd.DataFrame] = []
    summary_results: list[pd.DataFrame] = []

    for model_name, group_col, group_val, outcome, treatment in specs:
        sub = sample.loc[sample[group_col] == group_val]
        frame = estimation_sample(sub, outcome=outcome, treatment=treatment, controls=controls)
        rhs = [treatment, *controls, "C(state)", "C(year)"]
        formula = f"{outcome} ~ " + " + ".join(rhs)
        model = run_clustered_ols(frame, formula=formula, cluster_col="state")

        full_results.append(tidy_model(model, model_name=model_name, outcome=outcome, treatment=treatment))
        terms = [treatment, *controls]
        summary_results.append(tidy_summary(model, model_name=model_name, outcome=outcome,
                                            treatment=treatment, terms_of_interest=terms))

    return pd.concat(full_results, ignore_index=True), pd.concat(summary_results, ignore_index=True)


def main() -> None:
    ensure_project_dirs()
    if not PANEL_FILE.exists():
        raise FileNotFoundError(f"Missing panel file: {PANEL_FILE}")

    panel = pd.read_csv(PANEL_FILE)
    sample = baseline_sample(panel)
    sample = compute_subgroup_indicators(sample)
    controls = available_controls(sample, CONTROL_VARS)

    # Pass-through elasticity
    pt_full, pt_summ = run_passthrough(sample, controls)
    save_dataframe(pt_full, TABLES_DIR / "passthrough_elasticity.csv")
    save_dataframe(pt_summ, TABLES_DIR / "passthrough_elasticity_summary.csv")
    pt_coef = pt_summ.loc[pt_summ["term"] == "mw_gap", "coef"].iloc[0]
    pt_p = pt_summ.loc[pt_summ["term"] == "mw_gap", "p_value"].iloc[0]
    print(f"Pass-through: +${pt_coef:.1f}/month per $1 MW gap (p={pt_p:.4f})")

    # Interaction models
    int_full, int_summ = run_interaction_models(sample, controls)
    save_dataframe(int_full, TABLES_DIR / "heterogeneity_interaction.csv")
    save_dataframe(int_summ, TABLES_DIR / "heterogeneity_interaction_summary.csv")

    # Subgroup models
    sub_full, sub_summ = run_subgroup_models(sample, controls)
    save_dataframe(sub_full, TABLES_DIR / "heterogeneity_subgroups.csv")
    save_dataframe(sub_summ, TABLES_DIR / "heterogeneity_subgroups_summary.csv")

    print("Heterogeneity and pass-through results written to outputs/tables/.")


if __name__ == "__main__":
    main()
