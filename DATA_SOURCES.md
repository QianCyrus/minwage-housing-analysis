# Data Sources

All raw data is downloaded programmatically by `python -m src.download_data`.
No manual download is required. This document records the exact sources for reproducibility.

## 1. State Minimum Wage (FRED)

| Item | Detail |
|------|--------|
| Provider | Federal Reserve Economic Data (FRED), St. Louis Fed |
| Series | `STTMINWG{XX}` (one per state) and `STTMINWGFG` (federal) |
| Endpoint | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` |
| Frequency | Monthly, collapsed to annual (last observation of the year) |
| Coverage | 2010–2024, 51 states + DC |
| Auth | None required |
| Output | `data/raw/fred_state_min_wage.csv` |

## 2. ACS Median Gross Rent as % of Income (Census Bureau)

| Item | Detail |
|------|--------|
| Provider | U.S. Census Bureau, American Community Survey 1-Year |
| Table | B25071, variable `B25071_001E` |
| Endpoint | `https://api.census.gov/data/{year}/acs/acs1` |
| Coverage | 2010–2024 (2020 uses experimental methodology; excluded from regressions) |
| Auth | Optional `CENSUS_API_KEY` (raises rate limit) |
| Output | `data/raw/acs_b25071_state_2010_2024.csv` |

## 3. ACS Median Gross Rent (Census Bureau)

| Item | Detail |
|------|--------|
| Provider | U.S. Census Bureau, American Community Survey 1-Year |
| Table | B25064, variable `B25064_001E` |
| Endpoint | `https://api.census.gov/data/{year}/acs/acs1` |
| Coverage | 2010–2024 |
| Auth | Optional `CENSUS_API_KEY` |
| Output | `data/raw/acs_b25064_state_2010_2024.csv` |

## 4. State Unemployment Rate (BLS LAUS)

| Item | Detail |
|------|--------|
| Provider | Bureau of Labor Statistics, Local Area Unemployment Statistics |
| Series | `LASST{FIPS}0000000000003` (one per state) |
| Endpoint | `https://api.bls.gov/publicAPI/v2/timeseries/data/` |
| Frequency | Monthly, averaged to annual |
| Coverage | 2010–2024, 51 states + DC |
| Auth | Optional `BLS_API_KEY` (raises rate limit from 25 to 500 queries/day) |
| Output | `data/raw/laus_state_unemployment_2010_2024.csv` |

## 5. Average Weekly Wage (BLS QCEW)

| Item | Detail |
|------|--------|
| Provider | Bureau of Labor Statistics, Quarterly Census of Employment & Wages |
| Endpoint | ZIP bulk files (pre-2020) / CSV API (2020+) |
| Filter | `agglvl_code=50`, `own_code=0` (statewide, all ownerships, total covered) |
| Coverage | 2010–2024 (coverage depends on API availability; ~7% in current download) |
| Auth | None |
| Output | `data/raw/qcew_state_avg_weekly_wage_2010_2024.csv` |
| Note | QCEW endpoints may reject automated requests. If download fails, the pipeline continues without this variable. See README for manual fallback. |

## 6. Zillow Home Value Index (Optional)

| Item | Detail |
|------|--------|
| Provider | Zillow Research |
| Series | ZHVI, Single-Family + Condo, middle tier (33rd–67th percentile) |
| URL | `https://files.zillowstatic.com/research/public_csvs/zhvi/State_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv` |
| Coverage | Monthly, melted to state-month level |
| Auth | None |
| Output | `data/raw/zillow_zhvi_state_monthly.csv` |
| Note | Not included in default pipeline. Use `--with-zillow` flag to download. |

## Downloading

```bash
# Download all default datasets (FRED, ACS, LAUS, QCEW)
python -m src.download_data

# Download specific datasets
python -m src.download_data --datasets minimum_wage acs laus

# Include Zillow
python -m src.download_data --datasets all
```

## API Keys (Optional)

Set as environment variables before running:

```bash
export CENSUS_API_KEY="your_key"   # https://api.census.gov/data/key_signup.html
export BLS_API_KEY="your_key"      # https://data.bls.gov/registrationEngine/
```
