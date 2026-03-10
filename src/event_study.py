from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from src.config import CONTROL_VARS, FIGURES_DIR, PANEL_FILE, TABLES_DIR, ensure_project_dirs
from src.utils import (
    available_controls,
    baseline_sample,
    event_term_name,
    run_clustered_ols,
    save_dataframe,
    tidy_model,
)

MIN_EVENT = -5
MAX_EVENT = 5
REFERENCE_EVENT = -1


def prepare_event_study_sample(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    out = baseline_sample(df).copy()
    treated = out["treat_ever"] == 1
    out.loc[treated, "event_window"] = out.loc[treated, "event_time"].clip(MIN_EVENT, MAX_EVENT)
    terms: list[str] = []
    for event_time in range(MIN_EVENT, MAX_EVENT + 1):
        if event_time == REFERENCE_EVENT:
            continue
        term = event_term_name(event_time)
        out[term] = ((out["treat_ever"] == 1) & (out["event_window"] == event_time)).astype(int)
        terms.append(term)
    return out, terms


def parse_event_time(term: str) -> int:
    raw = term.removeprefix("event_")
    sign = -1 if raw.startswith("m") else 1
    return sign * int(raw[1:])


def plot_event_study(frame: pd.DataFrame, output_path, *, title: str = "Event study: median rent burden") -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axhline(0, color="black", linewidth=1)
    ax.axvline(-1, color="gray", linestyle="--", linewidth=1)
    ax.errorbar(
        frame["event_time"],
        frame["coef"],
        yerr=[frame["coef"] - frame["ci_low"], frame["ci_high"] - frame["coef"]],
        fmt="o-",
        capsize=4,
    )
    ax.set_xlabel("Event time")
    ax.set_ylabel("Coefficient")
    ax.set_title(title)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def run_one_event_study(
    sample: pd.DataFrame,
    event_terms: list[str],
    controls: list[str],
    outcome: str,
    model_label: str,
) -> pd.DataFrame:
    """Run one event study specification and return tidy results."""
    needed = [outcome, "state", "year", *controls, *event_terms]
    est = sample.dropna(subset=needed).copy()

    terms_str = " + ".join(event_terms)
    rhs = [terms_str, *controls, "C(state)", "C(year)"]
    formula = f"{outcome} ~ " + " + ".join(rhs)
    model = run_clustered_ols(est, formula=formula, cluster_col="state")

    results = tidy_model(
        model,
        model_name=model_label,
        outcome=outcome,
        treatment="event_time_dummies",
    )
    results = results.loc[results["term"].isin(event_terms)].copy()
    results["event_time"] = results["term"].map(parse_event_time)
    results = results.sort_values("event_time").reset_index(drop=True)
    return results


def main() -> None:
    ensure_project_dirs()
    if not PANEL_FILE.exists():
        raise FileNotFoundError(f"Missing panel file: {PANEL_FILE}")

    panel = pd.read_csv(PANEL_FILE)
    sample, event_terms = prepare_event_study_sample(panel)
    controls = available_controls(sample, CONTROL_VARS)

    # 1. Event study: median rent burden (primary)
    res_burden = run_one_event_study(
        sample, event_terms, controls,
        outcome="median_rent_pct_income",
        model_label="event_study_twfe",
    )
    save_dataframe(res_burden, TABLES_DIR / "event_study_median_rent_pct_income.csv")
    plot_event_study(res_burden, FIGURES_DIR / "event_study_median_rent_pct_income.png",
                     title="Event study: median rent burden (% income)")

    # 2. Event study: log median gross rent (NEW)
    res_rent = run_one_event_study(
        sample, event_terms, controls,
        outcome="log_median_gross_rent",
        model_label="event_study_log_rent",
    )
    save_dataframe(res_rent, TABLES_DIR / "event_study_log_median_gross_rent.csv")
    plot_event_study(res_rent, FIGURES_DIR / "event_study_log_median_gross_rent.png",
                     title="Event study: log median gross rent")

    print("Event-study outputs written to outputs/tables and outputs/figures.")


if __name__ == "__main__":
    main()
