from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
import re
import tempfile
import zipfile

import pandas as pd
import requests

from src.config import (
    BLS_API_URL,
    CENSUS_API_BASE,
    END_YEAR,
    FRED_GRAPH_CSV,
    RAW_ACS_RENT_FILE,
    RAW_ACS_RENT_SHARE_FILE,
    RAW_LAUS_FILE,
    RAW_POLICY_FILE,
    RAW_QCEW_FILE,
    RAW_ZHVI_FILE,
    START_YEAR,
    bls_api_key,
    census_api_key,
    ensure_project_dirs,
    state_metadata,
    zillow_url,
)
from src.utils import clean_numeric, save_dataframe, standardize_state_name, to_numeric

REQUEST_TIMEOUT = 60
QCEW_API_FIRST_YEAR = 2020
DOWNLOAD_RETRIES = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download raw project data.")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["minimum_wage", "acs", "laus", "qcew"],
        choices=["all", "minimum_wage", "acs", "laus", "qcew", "zillow"],
        help="Datasets to download.",
    )
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    return parser.parse_args()


def fetch_csv(session: requests.Session, url: str, *, params: dict | None = None) -> pd.DataFrame:
    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text))


def fetch_json(
    session: requests.Session,
    url: str,
    *,
    method: str = "get",
    params: dict | None = None,
    payload: dict | None = None,
) -> dict:
    if method.lower() == "post":
        response = session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    else:
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def collapse_fred_series(frame: pd.DataFrame, *, value_name: str) -> pd.DataFrame:
    date_col = frame.columns[0]
    value_col = frame.columns[1]
    out = frame.rename(columns={date_col: "date", value_col: value_name}).copy()
    out["date"] = pd.to_datetime(out["date"])
    out["year"] = out["date"].dt.year
    out[value_name] = clean_numeric(out[value_name])
    out = out.sort_values("date").groupby("year", as_index=False).last()
    return out[["year", value_name]]


def download_minimum_wage(session: requests.Session, start_year: int, end_year: int) -> None:
    states = state_metadata()
    federal = fetch_csv(session, FRED_GRAPH_CSV, params={"id": "STTMINWGFG"})
    federal = collapse_fred_series(federal, value_name="federal_min_wage")

    records: list[pd.DataFrame] = []
    for row in states.itertuples(index=False):
        series_id = f"STTMINWG{row.state_abbr}"
        try:
            frame = fetch_csv(session, FRED_GRAPH_CSV, params={"id": series_id})
            frame = collapse_fred_series(frame, value_name="observed_state_min_wage")
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            frame = pd.DataFrame(
                {
                    "year": list(range(start_year, end_year + 1)),
                    "observed_state_min_wage": pd.NA,
                }
            )
        frame["state"] = row.state
        frame["state_abbr"] = row.state_abbr
        frame["state_fips"] = row.state_fips
        frame["fred_series_id"] = series_id
        records.append(frame)

    combined = pd.concat(records, ignore_index=True)
    combined = combined.merge(federal, on="year", how="left")
    combined = combined.loc[combined["year"].between(start_year, end_year)].sort_values(
        ["state_abbr", "year"]
    )
    save_dataframe(combined, RAW_POLICY_FILE)


def download_acs_table(
    session: requests.Session,
    *,
    start_year: int,
    end_year: int,
    variable: str,
    output_path,
) -> None:
    meta = state_metadata()
    valid_fips = set(meta["state_fips"])
    fips_to_abbr = dict(zip(meta["state_fips"], meta["state_abbr"]))
    records: list[pd.DataFrame] = []

    for year in range(start_year, end_year + 1):
        params = {"get": f"NAME,{variable}", "for": "state:*"}
        api_key = census_api_key()
        if api_key:
            params["key"] = api_key
        try:
            payload = fetch_json(
                session,
                f"{CENSUS_API_BASE}/{year}/acs/acs1",
                params=params,
            )
            frame = pd.DataFrame(payload[1:], columns=payload[0])
            frame = frame.rename(columns={"NAME": "state", "state": "state_fips"})
            frame["state"] = frame["state"].map(standardize_state_name)
            frame["state_abbr"] = frame["state_fips"].map(fips_to_abbr)
            frame = frame.loc[frame["state_fips"].isin(valid_fips)].copy()
            frame["year"] = year
            frame[variable] = to_numeric(frame[variable])
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            frame = meta.copy()
            frame["year"] = year
            frame[variable] = pd.NA
        records.append(frame[["state", "state_abbr", "state_fips", "year", variable]])

    save_dataframe(pd.concat(records, ignore_index=True), output_path)


def year_windows(start_year: int, end_year: int, window_size: int = 10) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    current = start_year
    while current <= end_year:
        windows.append((current, min(current + window_size - 1, end_year)))
        current += window_size
    return windows


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def download_laus(session: requests.Session, start_year: int, end_year: int) -> None:
    meta = state_metadata().copy()
    meta["laus_series_id"] = meta["state_fips"].map(lambda code: f"LASST{code}0000000000003")
    id_to_row = {row.laus_series_id: row for row in meta.itertuples(index=False)}
    records: list[dict] = []

    for window_start, window_end in year_windows(start_year, end_year):
        for series_group in chunked(meta["laus_series_id"].tolist(), 25):
            payload = {
                "seriesid": series_group,
                "startyear": str(window_start),
                "endyear": str(window_end),
            }
            api_key = bls_api_key()
            if api_key:
                payload["registrationKey"] = api_key
            response = fetch_json(
                session,
                BLS_API_URL,
                method="post",
                payload=payload,
            )
            if response.get("status") != "REQUEST_SUCCEEDED":
                raise RuntimeError(f"BLS LAUS request failed: {response}")

            for series in response["Results"]["series"]:
                row = id_to_row[series["seriesID"]]
                for obs in series["data"]:
                    period = obs["period"]
                    if not re.fullmatch(r"M(0[1-9]|1[0-2])", period):
                        continue
                    records.append(
                        {
                            "state": row.state,
                            "state_abbr": row.state_abbr,
                            "state_fips": row.state_fips,
                            "year": int(obs["year"]),
                            "month": int(period[1:]),
                            "unemployment_rate": float(obs["value"]),
                        }
                    )

    if not records:
        raise ValueError("BLS LAUS download returned no monthly observations.")
    monthly = pd.DataFrame(records)
    annual = (
        monthly.groupby(["state", "state_abbr", "state_fips", "year"], as_index=False)[
            "unemployment_rate"
        ]
        .mean()
        .sort_values(["state_abbr", "year"])
    )
    save_dataframe(annual, RAW_LAUS_FILE)


def pick_qcew_row(frame: pd.DataFrame) -> pd.Series:
    standardized = frame.copy()
    standardized.columns = [str(col).strip().lower() for col in standardized.columns]
    for col in ["agglvl_code", "own_code", "industry_code", "size_code"]:
        if col in standardized:
            standardized[col] = standardized[col].astype(str).str.strip()

    subset = standardized.loc[
        (standardized["agglvl_code"] == "50") & (standardized["own_code"] == "0")
    ].copy()
    if "industry_code" in subset and subset["industry_code"].isin({"10", "10-----"}).any():
        subset = subset.loc[subset["industry_code"].isin({"10", "10-----"})].copy()
    if "size_code" in subset and subset["size_code"].isin({"0", "00"}).any():
        subset = subset.loc[subset["size_code"].isin({"0", "00"})].copy()
    if subset.empty:
        raise ValueError("No statewide total-covered QCEW row found.")
    return subset.iloc[0]


def qcew_annual_by_area_zip_url(year: int) -> str:
    return f"https://data.bls.gov/cew/data/files/{year}/csv/{year}_annual_by_area.zip"


def qcew_api_area_url(year: int, area_code: str) -> str:
    return f"https://data.bls.gov/cew/data/api/{year}/a/area/{area_code}.csv"


def remote_file_size(session: requests.Session, url: str) -> int | None:
    response = session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    size = response.headers.get("content-length")
    return int(size) if size else None


def download_file(session: requests.Session, url: str, destination: Path) -> None:
    expected_size = remote_file_size(session, url)
    if destination.exists():
        destination.unlink()

    attempts = 0
    downloaded = 0
    while expected_size is None or downloaded < expected_size:
        headers = {}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"
        try:
            with session.get(url, stream=True, timeout=REQUEST_TIMEOUT, headers=headers) as response:
                response.raise_for_status()
                if downloaded > 0 and response.status_code == 200:
                    destination.unlink(missing_ok=True)
                    downloaded = 0
                with destination.open("ab" if downloaded > 0 else "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                            downloaded += len(chunk)
            attempts = 0
        except requests.exceptions.RequestException:
            attempts += 1
            if attempts > DOWNLOAD_RETRIES:
                raise

    if expected_size is not None and destination.stat().st_size != expected_size:
        raise IOError(
            f"Downloaded file size mismatch for {url}: "
            f"{destination.stat().st_size} != {expected_size}"
        )


def find_qcew_statewide_member(zf: zipfile.ZipFile, *, year: int, area_code: str) -> str:
    prefix = f"{year}.annual {area_code} "
    matches = [
        name
        for name in zf.namelist()
        if name.endswith(".csv") and prefix in Path(name).name and "Statewide" in Path(name).name
    ]
    if not matches:
        raise FileNotFoundError(f"Statewide QCEW member not found for year={year}, area_code={area_code}")
    return matches[0]


def extract_qcew_statewide_rows_from_zip(
    session: requests.Session,
    *,
    year: int,
    meta: pd.DataFrame,
) -> list[dict]:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / f"{year}_annual_by_area.zip"
        download_file(session, qcew_annual_by_area_zip_url(year), zip_path)
        with zipfile.ZipFile(zip_path) as zf:
            for row in meta.itertuples(index=False):
                area_code = f"{row.state_fips}000"
                member = find_qcew_statewide_member(zf, year=year, area_code=area_code)
                with zf.open(member) as handle:
                    frame = pd.read_csv(handle)
                selected = pick_qcew_row(frame)
                rows.append(
                    {
                        "state": row.state,
                        "state_abbr": row.state_abbr,
                        "state_fips": row.state_fips,
                        "year": year,
                        "avg_weekly_wage": pd.to_numeric(
                            selected["annual_avg_wkly_wage"], errors="coerce"
                        ),
                        "annual_employment": pd.to_numeric(
                            selected["annual_avg_emplvl"], errors="coerce"
                        ),
                    }
                )
    return rows


def extract_qcew_statewide_rows_from_api(*, session: requests.Session, year: int, meta: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    for row in meta.itertuples(index=False):
        area_code = f"{row.state_fips}000"
        frame = fetch_csv(session, qcew_api_area_url(year, area_code))
        selected = pick_qcew_row(frame)
        rows.append(
            {
                "state": row.state,
                "state_abbr": row.state_abbr,
                "state_fips": row.state_fips,
                "year": year,
                "avg_weekly_wage": pd.to_numeric(selected["annual_avg_wkly_wage"], errors="coerce"),
                "annual_employment": pd.to_numeric(selected["annual_avg_emplvl"], errors="coerce"),
            }
        )
    return rows


def download_qcew(session: requests.Session, start_year: int, end_year: int) -> None:
    records: list[dict] = []
    meta = state_metadata()
    for year in range(start_year, end_year + 1):
        print(f"  QCEW year {year}...")
        if year >= QCEW_API_FIRST_YEAR:
            records.extend(extract_qcew_statewide_rows_from_api(session=session, year=year, meta=meta))
        else:
            records.extend(extract_qcew_statewide_rows_from_zip(session=session, year=year, meta=meta))

    out = pd.DataFrame(records).sort_values(["state_abbr", "year"])
    save_dataframe(out, RAW_QCEW_FILE)


def download_zillow(session: requests.Session, start_year: int, end_year: int) -> None:
    frame = fetch_csv(session, zillow_url())
    date_cols = [col for col in frame.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(col))]
    if "RegionName" not in frame.columns or not date_cols:
        raise ValueError("Unexpected Zillow schema. Expected RegionName and monthly date columns.")

    meta = state_metadata()
    out = frame.copy()
    out["state"] = out["RegionName"].map(standardize_state_name)
    out = out.loc[out["state"].isin(set(meta["state"]))].copy()
    out = out.merge(meta, on="state", how="left")
    out = out[["state", "state_abbr", "state_fips", *date_cols]]
    out = out.melt(
        id_vars=["state", "state_abbr", "state_fips"],
        value_vars=date_cols,
        var_name="date",
        value_name="zhvi",
    )
    out["date"] = pd.to_datetime(out["date"])
    out = out.loc[out["date"].dt.year.between(start_year, end_year)].copy()
    out["zhvi"] = to_numeric(out["zhvi"])
    save_dataframe(out.sort_values(["state_abbr", "date"]), RAW_ZHVI_FILE)


def main() -> None:
    args = parse_args()
    ensure_project_dirs()
    datasets = set(args.datasets)
    if "all" in datasets:
        datasets = {"minimum_wage", "acs", "laus", "qcew", "zillow"}

    session = requests.Session()
    session.headers.update({"User-Agent": "minimum-wage-housing-affordability/1.0"})

    if "minimum_wage" in datasets:
        print("Downloading state minimum wage data...")
        download_minimum_wage(session, args.start_year, args.end_year)

    if "acs" in datasets:
        print("Downloading ACS rent burden table B25071...")
        download_acs_table(
            session,
            start_year=args.start_year,
            end_year=args.end_year,
            variable="B25071_001E",
            output_path=RAW_ACS_RENT_SHARE_FILE,
        )
        print("Downloading ACS gross rent table B25064...")
        download_acs_table(
            session,
            start_year=args.start_year,
            end_year=args.end_year,
            variable="B25064_001E",
            output_path=RAW_ACS_RENT_FILE,
        )

    if "laus" in datasets:
        print("Downloading LAUS unemployment data...")
        download_laus(session, args.start_year, args.end_year)

    if "qcew" in datasets:
        print("Downloading QCEW wage data...")
        try:
            download_qcew(session, args.start_year, args.end_year)
        except Exception as exc:
            print(
                "WARNING: QCEW download failed. "
                "Proceeding without the wage control file for now."
            )
            print(f"Reason: {exc}")

    if "zillow" in datasets:
        print("Downloading Zillow ZHVI data...")
        download_zillow(session, args.start_year, args.end_year)

    print("Download step completed.")


if __name__ == "__main__":
    main()
