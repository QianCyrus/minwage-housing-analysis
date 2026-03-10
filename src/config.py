from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
TABLES_DIR = OUTPUTS_DIR / "tables"
REPORT_DIR = ROOT / "report"

START_YEAR = 2010
END_YEAR = 2024
FIRST_TREAT_START_YEAR = 2015
BASELINE_YEARS = [year for year in range(START_YEAR, END_YEAR + 1) if year != 2020]
MIN_MW_INCREASE = 0.50  # dollar threshold to filter CPI micro-adjustments

RAW_POLICY_FILE = RAW_DIR / "fred_state_min_wage.csv"
RAW_ACS_RENT_SHARE_FILE = RAW_DIR / "acs_b25071_state_2010_2024.csv"
RAW_ACS_RENT_FILE = RAW_DIR / "acs_b25064_state_2010_2024.csv"
RAW_LAUS_FILE = RAW_DIR / "laus_state_unemployment_2010_2024.csv"
RAW_QCEW_FILE = RAW_DIR / "qcew_state_avg_weekly_wage_2010_2024.csv"
RAW_ZHVI_FILE = RAW_DIR / "zillow_zhvi_state_monthly.csv"

INTERIM_POLICY_FILE = INTERIM_DIR / "policy_state_year.csv"
INTERIM_OUTCOMES_FILE = INTERIM_DIR / "outcomes_state_year.csv"
INTERIM_CONTROLS_FILE = INTERIM_DIR / "controls_state_year.csv"
INTERIM_ZHVI_FILE = INTERIM_DIR / "zhvi_state_year.csv"

PANEL_FILE = PROCESSED_DIR / "state_year_panel.csv"

CENSUS_API_BASE = "https://api.census.gov/data"
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
FRED_GRAPH_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"
QCEW_API_BASE = "https://data.bls.gov/cew/data/api"
DEFAULT_ZILLOW_ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "State_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

CONTROL_VARS = ["unemployment_rate", "log_avg_weekly_wage"]
OUTCOME_VARS = [
    "median_rent_pct_income",
    "median_gross_rent",
    "log_median_gross_rent",
    "zhvi",
    "log_zhvi",
]

STATE_ROWS = [
    ("Alabama", "AL", "01"),
    ("Alaska", "AK", "02"),
    ("Arizona", "AZ", "04"),
    ("Arkansas", "AR", "05"),
    ("California", "CA", "06"),
    ("Colorado", "CO", "08"),
    ("Connecticut", "CT", "09"),
    ("Delaware", "DE", "10"),
    ("District of Columbia", "DC", "11"),
    ("Florida", "FL", "12"),
    ("Georgia", "GA", "13"),
    ("Hawaii", "HI", "15"),
    ("Idaho", "ID", "16"),
    ("Illinois", "IL", "17"),
    ("Indiana", "IN", "18"),
    ("Iowa", "IA", "19"),
    ("Kansas", "KS", "20"),
    ("Kentucky", "KY", "21"),
    ("Louisiana", "LA", "22"),
    ("Maine", "ME", "23"),
    ("Maryland", "MD", "24"),
    ("Massachusetts", "MA", "25"),
    ("Michigan", "MI", "26"),
    ("Minnesota", "MN", "27"),
    ("Mississippi", "MS", "28"),
    ("Missouri", "MO", "29"),
    ("Montana", "MT", "30"),
    ("Nebraska", "NE", "31"),
    ("Nevada", "NV", "32"),
    ("New Hampshire", "NH", "33"),
    ("New Jersey", "NJ", "34"),
    ("New Mexico", "NM", "35"),
    ("New York", "NY", "36"),
    ("North Carolina", "NC", "37"),
    ("North Dakota", "ND", "38"),
    ("Ohio", "OH", "39"),
    ("Oklahoma", "OK", "40"),
    ("Oregon", "OR", "41"),
    ("Pennsylvania", "PA", "42"),
    ("Rhode Island", "RI", "44"),
    ("South Carolina", "SC", "45"),
    ("South Dakota", "SD", "46"),
    ("Tennessee", "TN", "47"),
    ("Texas", "TX", "48"),
    ("Utah", "UT", "49"),
    ("Vermont", "VT", "50"),
    ("Virginia", "VA", "51"),
    ("Washington", "WA", "53"),
    ("West Virginia", "WV", "54"),
    ("Wisconsin", "WI", "55"),
    ("Wyoming", "WY", "56"),
]


def state_metadata() -> pd.DataFrame:
    return pd.DataFrame(STATE_ROWS, columns=["state", "state_abbr", "state_fips"])


def census_api_key() -> str | None:
    return os.environ.get("CENSUS_API_KEY")


def bls_api_key() -> str | None:
    return os.environ.get("BLS_API_KEY")


def zillow_url() -> str:
    return os.environ.get("ZILLOW_ZHVI_URL", DEFAULT_ZILLOW_ZHVI_URL)


def ensure_project_dirs() -> None:
    for path in [
        RAW_DIR,
        INTERIM_DIR,
        PROCESSED_DIR,
        FIGURES_DIR,
        TABLES_DIR,
        REPORT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
