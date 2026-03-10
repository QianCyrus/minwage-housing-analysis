from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import FIGURES_DIR, PANEL_FILE, TABLES_DIR, ensure_project_dirs


def coefficient_plot(frame: pd.DataFrame, *, title: str, output_name: str) -> None:
    fig, ax = plt.subplots(figsize=(10, max(4, len(frame) * 0.8 + 1)))
    plotted = frame.sort_values("coef").reset_index(drop=True)
    positions = range(len(plotted))
    ax.axvline(0, color="black", linewidth=1)
    ax.errorbar(
        plotted["coef"],
        positions,
        xerr=[plotted["coef"] - plotted["ci_low"], plotted["ci_high"] - plotted["coef"]],
        fmt="o",
        capsize=4,
    )
    ax.set_yticks(list(positions))
    ax.set_yticklabels(plotted["label"])
    ax.set_xlabel("Coefficient")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / output_name, dpi=200)
    plt.close(fig)


def robustness_split_plot(rob_terms: pd.DataFrame) -> None:
    """Split robustness results by outcome unit to avoid mixed-scale issues."""
    # Separate: % income outcomes vs dollar outcomes
    pct_mask = rob_terms["outcome"] != "median_gross_rent"
    dollar_mask = rob_terms["outcome"] == "median_gross_rent"

    pct_df = rob_terms.loc[pct_mask].copy()
    dollar_df = rob_terms.loc[dollar_mask].copy()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                              gridspec_kw={"width_ratios": [max(len(pct_df), 1), max(len(dollar_df), 1)]})

    # Left panel: percentage-point coefficients
    ax = axes[0]
    if not pct_df.empty:
        plotted = pct_df.sort_values("coef").reset_index(drop=True)
        positions = range(len(plotted))
        ax.axvline(0, color="black", linewidth=1)
        ax.errorbar(plotted["coef"], positions,
                     xerr=[plotted["coef"] - plotted["ci_low"], plotted["ci_high"] - plotted["coef"]],
                     fmt="o", capsize=4)
        ax.set_yticks(list(positions))
        ax.set_yticklabels(plotted["label"])
    ax.set_xlabel("Coefficient (pp)")
    ax.set_title("Rent burden (% income)")
    ax.grid(axis="x", alpha=0.25)

    # Right panel: dollar coefficients
    ax = axes[1]
    if not dollar_df.empty:
        plotted = dollar_df.sort_values("coef").reset_index(drop=True)
        positions = range(len(plotted))
        ax.axvline(0, color="black", linewidth=1)
        ax.errorbar(plotted["coef"], positions,
                     xerr=[plotted["coef"] - plotted["ci_low"], plotted["ci_high"] - plotted["coef"]],
                     fmt="o", capsize=4, color="darkorange")
        ax.set_yticks(list(positions))
        ax.set_yticklabels(plotted["label"])
    ax.set_xlabel("Coefficient ($)")
    ax.set_title("Rent level (dollars)")
    ax.grid(axis="x", alpha=0.25)

    fig.suptitle("Robustness treatment effects", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "robustness_treatment_effects.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def placebo_histogram(placebo_path, actual_coef: float) -> None:
    """Plot distribution of placebo coefficients vs actual estimate."""
    if not placebo_path.exists():
        return
    df = pd.read_csv(placebo_path)
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(df["placebo_coef"], bins=25, edgecolor="black", alpha=0.7, color="lightsteelblue",
            label="Placebo estimates")
    ax.axvline(actual_coef, color="red", linewidth=2, linestyle="--",
               label=f"Actual estimate = {actual_coef:.3f}")
    ax.set_xlabel("Coefficient on post")
    ax.set_ylabel("Frequency")
    ax.set_title("Placebo test: randomly reassigned treatment (100 iterations)")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "placebo_distribution.png", dpi=200)
    plt.close(fig)


def main() -> None:
    ensure_project_dirs()

    did_path = TABLES_DIR / "did_baseline.csv"
    rob_path = TABLES_DIR / "robustness_checks.csv"
    if not did_path.exists() or not rob_path.exists():
        raise FileNotFoundError("Run did_baseline.py and robustness.py before make_figures.py.")

    did = pd.read_csv(did_path)
    rob = pd.read_csv(rob_path)

    # -- Baseline coefficient plot --
    did_terms = did.loc[did["term"].isin(["post", "mw_gap"]), [
        "model_name", "term", "coef", "ci_low", "ci_high",
    ]].copy()
    did_terms["label"] = did_terms["model_name"] + ": " + did_terms["term"]
    coefficient_plot(
        did_terms,
        title="Baseline treatment effects",
        output_name="baseline_treatment_effects.png",
    )

    # -- Robustness coefficient plot (FIXED: separate panels for different units) --
    rob_terms = rob.loc[rob["term"].isin(["post", "mw_gap", "post_any"]), [
        "model_name", "outcome", "term", "coef", "ci_low", "ci_high",
    ]].copy()
    rob_terms["label"] = rob_terms["model_name"] + ": " + rob_terms["term"]
    robustness_split_plot(rob_terms)

    # -- Treatment timing histogram --
    if PANEL_FILE.exists():
        panel = pd.read_csv(PANEL_FILE)
        timing = (
            panel.loc[panel["treat_ever"] == 1, ["state_abbr", "first_treat_year"]]
            .drop_duplicates()
            .dropna()
        )
        if not timing.empty:
            fig, ax = plt.subplots(figsize=(9, 5))
            ax.hist(timing["first_treat_year"],
                    bins=range(int(timing["first_treat_year"].min()),
                               int(timing["first_treat_year"].max()) + 2),
                    edgecolor="black")
            ax.set_xlabel("First treatment year")
            ax.set_ylabel("Number of states")
            ax.set_title("Distribution of first minimum-wage increases (>=$0.50)")
            fig.tight_layout()
            fig.savefig(FIGURES_DIR / "first_treat_year_histogram.png", dpi=200)
            plt.close(fig)

    # -- Placebo distribution plot --
    placebo_path = TABLES_DIR / "placebo_test.csv"
    actual_coef = did.loc[(did["model_name"] == "twfe_post_rent_share") & (did["term"] == "post"), "coef"]
    if not actual_coef.empty:
        placebo_histogram(placebo_path, float(actual_coef.iloc[0]))

    print("Publication-style figures written to outputs/figures.")


if __name__ == "__main__":
    main()
