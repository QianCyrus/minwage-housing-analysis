from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import FIGURES_DIR, FIRST_TREAT_START_YEAR, PANEL_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import baseline_sample, save_dataframe, summarize_missingness


def plot_group_trend(
    df: pd.DataFrame,
    *,
    value_col: str,
    output_name: str,
    ylabel: str,
) -> None:
    trend = (
        df.groupby(["year", "treat_ever"], as_index=False)[value_col]
        .mean()
        .sort_values(["treat_ever", "year"])
    )
    labels = {0: "Never treated", 1: "Ever treated"}

    fig, ax = plt.subplots(figsize=(9, 5))
    for group, frame in trend.groupby("treat_ever"):
        ax.plot(frame["year"], frame[value_col], marker="o", label=labels.get(group, str(group)))
    ax.set_xlabel("Year")
    ax.set_ylabel(ylabel)
    ax.set_title(ylabel)
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / output_name, dpi=200)
    plt.close(fig)


def balance_table(df: pd.DataFrame) -> pd.DataFrame:
    """Compare pre-treatment covariate means between treated and never-treated."""
    pre = df.loc[df["year"] < FIRST_TREAT_START_YEAR].copy()
    covars = [c for c in [
        "median_rent_pct_income", "median_gross_rent", "state_min_wage",
        "mw_gap", "unemployment_rate",
    ] if c in pre.columns]

    rows = []
    for var in covars:
        treated = pre.loc[pre["treat_ever"] == 1, var].dropna()
        control = pre.loc[pre["treat_ever"] == 0, var].dropna()
        diff = treated.mean() - control.mean()
        pooled_se = np.sqrt(treated.var() / max(len(treated), 1) + control.var() / max(len(control), 1))
        rows.append({
            "variable": var,
            "treated_mean": round(treated.mean(), 3) if len(treated) else np.nan,
            "treated_n": len(treated),
            "control_mean": round(control.mean(), 3) if len(control) else np.nan,
            "control_n": len(control),
            "difference": round(diff, 3) if len(treated) and len(control) else np.nan,
            "diff_se": round(pooled_se, 3) if pooled_se > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def plot_outcome_distributions(df: pd.DataFrame) -> None:
    """Histogram of main outcome variables."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax = axes[0]
    vals = df["median_rent_pct_income"].dropna()
    ax.hist(vals, bins=30, edgecolor="black", alpha=0.7)
    ax.axvline(30, color="red", linestyle="--", label="30% threshold")
    ax.set_xlabel("Median rent as % of income")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of rent burden")
    ax.legend()

    ax = axes[1]
    vals = df["median_gross_rent"].dropna()
    ax.hist(vals, bins=30, edgecolor="black", alpha=0.7, color="orange")
    ax.set_xlabel("Median gross rent ($)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of median rent")

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "outcome_distributions.png", dpi=200)
    plt.close(fig)


def plot_mw_gap_distribution(df: pd.DataFrame) -> None:
    """Histogram of mw_gap across all state-years."""
    fig, ax = plt.subplots(figsize=(9, 5))
    vals = df["mw_gap"].dropna()
    ax.hist(vals, bins=40, edgecolor="black", alpha=0.7, color="steelblue")
    ax.set_xlabel("State MW - Federal MW ($)")
    ax.set_ylabel("Frequency (state-years)")
    ax.set_title("Distribution of minimum wage gap (mw_gap)")
    ax.axvline(0, color="red", linestyle="--", alpha=0.6)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "mw_gap_distribution.png", dpi=200)
    plt.close(fig)


def main() -> None:
    ensure_project_dirs()
    if not PANEL_FILE.exists():
        raise FileNotFoundError(f"Missing panel file: {PANEL_FILE}")

    panel = pd.read_csv(PANEL_FILE)
    baseline = baseline_sample(panel)

    # 1. Summary statistics
    summary = baseline[
        [
            "median_rent_pct_income",
            "median_gross_rent",
            "state_min_wage",
            "mw_gap",
            "unemployment_rate",
            "avg_weekly_wage",
            "zhvi",
        ]
    ].describe().T
    summary.to_csv(TABLES_DIR / "summary_stats.csv")

    # 2. Missingness report
    summarize_missingness(panel).to_csv(TABLES_DIR / "missingness.csv", index=False)

    # 3. Policy timing table
    policy_timing = (
        panel.loc[panel["treat_ever"] == 1, ["state", "state_abbr", "first_treat_year"]]
        .drop_duplicates()
        .sort_values(["first_treat_year", "state_abbr"])
    )
    policy_timing.to_csv(TABLES_DIR / "policy_timing.csv", index=False)

    # 4. Balance table (NEW)
    bal = balance_table(baseline)
    save_dataframe(bal, TABLES_DIR / "balance_table.csv")
    print("  Balance table written.")

    # 5. Trend plots
    plot_group_trend(
        baseline,
        value_col="median_rent_pct_income",
        output_name="rent_burden_trend.png",
        ylabel="Median gross rent as % of income",
    )
    plot_group_trend(
        baseline,
        value_col="state_min_wage",
        output_name="minimum_wage_trend.png",
        ylabel="Applicable minimum wage",
    )

    # 6. Outcome distributions (NEW)
    plot_outcome_distributions(baseline)
    print("  Outcome distribution plots written.")

    # 7. MW gap distribution (NEW)
    plot_mw_gap_distribution(baseline)
    print("  MW gap distribution plot written.")

    print("EDA outputs written to outputs/tables and outputs/figures.")


if __name__ == "__main__":
    main()
