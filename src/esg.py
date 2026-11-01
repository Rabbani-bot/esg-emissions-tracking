"""TCFD-aligned emissions tracking: data generation, validation and metrics.

All inputs are generated with a fixed seed for a modelled four-unit company, so every number
in outputs/ can be regenerated exactly. Carbon prices are user-set scenario assumptions,
not forecasts.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

SEED = 2021
UNITS = {"Textiles": 0.40, "Packaging": 0.25, "Logistics": 0.20, "Offices": 0.15}  # revenue share
YEARS = range(2021, 2026)
GRID_EF = 0.45        # t CO2e per MWh, location-based (representative grid average)
RESIDUAL_EF = 0.55    # t CO2e per MWh, market-based residual mix
BASE_YEAR, TARGET_YEAR, TARGET_CUT = 2021, 2030, 0.42   # 42% absolute S1+2 cut (1.5C-aligned rate)
CARBON_PRICE = {"Current policies": 30, "Delayed transition": 90, "Net zero 2050": 150}  # USD/t, 2030 assumption


def generate(seed: int = SEED) -> pd.DataFrame:
    """Quarterly activity data per business unit, 2021-2025."""
    rng = np.random.default_rng(seed)
    rows = []
    for y in YEARS:
        t = y - BASE_YEAR
        for q in range(1, 5):
            for u, share in UNITS.items():
                revenue = 60 * share * 1.05 ** t * (1 + 0.04 * np.sin(q)) * rng.normal(1, 0.02)   # USD m
                mwh = revenue * {"Textiles": 95, "Packaging": 70, "Logistics": 25, "Offices": 12}[u] * 0.96 ** t
                fuel_t = revenue * {"Textiles": 30, "Packaging": 22, "Logistics": 85, "Offices": 2}[u] * 0.95 ** t
                re_share = min(0.08 + 0.12 * t, 0.9) if u != "Logistics" else min(0.05 + 0.05 * t, 0.9)
                rows.append(dict(year=y, quarter=q, unit=u, revenue_musd=revenue,
                                 electricity_mwh=mwh * rng.normal(1, 0.03),
                                 scope1_t=fuel_t * rng.normal(1, 0.04), re_share=re_share))
    df = pd.DataFrame(rows)
    # realistic reporting gaps: two missing meter readings to be caught by validation
    df.loc[(df.year == 2023) & (df.quarter == 2) & (df.unit == "Offices"), "electricity_mwh"] = np.nan
    df.loc[(df.year == 2024) & (df.quarter == 4) & (df.unit == "Logistics"), "scope1_t"] = np.nan
    return df


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Flag gaps and impute them from the same unit's same quarter in the previous year (documented method)."""
    out = df.copy()
    gaps = out[out[["electricity_mwh", "scope1_t"]].isna().any(axis=1)][["year", "quarter", "unit"]]
    for col in ["electricity_mwh", "scope1_t"]:
        miss = out[col].isna()
        for i in out.index[miss]:
            r = out.loc[i]
            prev = out[(out.year == r.year - 1) & (out.quarter == r.quarter) & (out.unit == r.unit)][col]
            out.loc[i, col] = float(prev.iloc[0])
            out.loc[i, "imputed"] = col
    report = {"records": len(df), "gaps": len(gaps), "completeness_pct": 100 * (1 - df[["electricity_mwh", "scope1_t"]].isna().mean().mean()),
              "gap_list": gaps.to_dict("records")}
    return out, report


def metrics(df: pd.DataFrame) -> pd.DataFrame:
    d = df.assign(scope2_location_t=df.electricity_mwh * GRID_EF,
                  scope2_market_t=df.electricity_mwh * (1 - df.re_share) * RESIDUAL_EF)
    a = d.groupby("year")[["revenue_musd", "electricity_mwh", "scope1_t", "scope2_location_t", "scope2_market_t"]].sum()
    a["re_share_pct"] = 100 * (d.electricity_mwh * d.re_share).groupby(d.year).sum() / a.electricity_mwh
    a["s12_market_t"] = a.scope1_t + a.scope2_market_t
    a["intensity_t_per_musd"] = a.s12_market_t / a.revenue_musd
    a["yoy_pct"] = a.s12_market_t.pct_change() * 100
    a["target_path_t"] = target_path(a.s12_market_t.loc[BASE_YEAR], a.index)
    a["vs_target_pct"] = 100 * (a.s12_market_t / a.target_path_t - 1)
    return a


def target_path(base: float, years) -> np.ndarray:
    """Linear path from the base year to TARGET_CUT below base in TARGET_YEAR."""
    yrs = np.asarray(list(years), float)
    return base * (1 - TARGET_CUT * (yrs - BASE_YEAR) / (TARGET_YEAR - BASE_YEAR))


def carbon_exposure(emissions_t: float, ebitda_musd: float) -> pd.DataFrame:
    """Annual cost if S1+2 emissions were priced at each scenario price; share of EBITDA."""
    rows = [{"scenario": s, "price_usd_t": p, "cost_musd": emissions_t * p / 1e6,
             "pct_of_ebitda": 100 * emissions_t * p / 1e6 / ebitda_musd} for s, p in CARBON_PRICE.items()]
    return pd.DataFrame(rows)
