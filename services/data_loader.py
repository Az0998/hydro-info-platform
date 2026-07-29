"""数据装载：优先本地 CSV，缺失时从 USGS 拉取控制站日流量。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from config import DATA_DIR, RATING_CURVE, STATIONS

LOCAL_CSV = DATA_DIR / "basin_daily.csv"
META_JSON = DATA_DIR / "meta.json"


def q_to_stage(q: float | np.ndarray) -> float | np.ndarray:
    """演示绳套：流量 → 水位。"""
    a, b, c = RATING_CURVE["a"], RATING_CURVE["b"], RATING_CURVE["c"]
    q = np.asarray(q, dtype=float)
    stage = a * np.power(np.maximum(q, 1.0), b) + c
    return stage if stage.ndim else float(stage)


def _fetch_usgs_daily(site: str, start: str = "2018-01-01") -> pd.DataFrame:
    """拉取 USGS NWIS 日平均流量（参数 00060，cfs）。"""
    url = "https://waterservices.usgs.gov/nwis/dv/"
    params = {
        "format": "json",
        "sites": site,
        "startDT": start,
        "parameterCd": "00060",
        "siteStatus": "all",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    series = r.json()["value"]["timeSeries"][0]["values"][0]["value"]
    rows = [{"date": v["dateTime"][:10], "Q_target": float(v["value"])} for v in series if v["value"] not in ("", None)]
    return pd.DataFrame(rows)


def ensure_local_data() -> Path:
    """保证 data/basin_daily.csv 可用。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if LOCAL_CSV.exists() and LOCAL_CSV.stat().st_size > 1000:
        return LOCAL_CSV

    # 尝试复用同级 hydro-ml-paper 数据
    sibling = ROOT_SIBLING_POTOMAC()
    if sibling and sibling.exists():
        df = pd.read_csv(sibling)
        keep = ["date", "Q_target", "precip_target", "temp_target",
                "Q_01636500", "precip_01636500", "Q_01638480", "precip_01638480"]
        cols = [c for c in keep if c in df.columns]
        out = df[cols].copy()
        out.to_csv(LOCAL_CSV, index=False)
        META_JSON.write_text(
            json.dumps({"source": str(sibling), "rows": len(out)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return LOCAL_CSV

    # 兜底：只拉控制站
    df = _fetch_usgs_daily("01646500")
    df["precip_target"] = 0.0
    df["temp_target"] = np.nan
    df["Q_01636500"] = df["Q_target"] * 0.35
    df["precip_01636500"] = 0.0
    df["Q_01638480"] = df["Q_target"] * 0.08
    df["precip_01638480"] = 0.0
    df.to_csv(LOCAL_CSV, index=False)
    META_JSON.write_text(
        json.dumps({"source": "USGS NWIS live", "rows": len(df)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return LOCAL_CSV


def ROOT_SIBLING_POTOMAC() -> Path | None:
    sibling = DATA_DIR.parent.parent / "hydro-ml-paper" / "data" / "potomac_daily.csv"
    return sibling if sibling.exists() else None


@lru_cache(maxsize=1)
def load_basin_frame() -> pd.DataFrame:
    path = ensure_local_data()
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for st in STATIONS:
        qcol = st["q_col"]
        if qcol in df.columns:
            df[f"Z_{st['id']}"] = q_to_stage(df[qcol].ffill().fillna(0))
    return df


def reload_data() -> None:
    load_basin_frame.cache_clear()
    ensure_local_data()
    load_basin_frame()


def slice_window(days: int | None = None) -> pd.DataFrame:
    df = load_basin_frame()
    if days and days > 0:
        end = df["date"].max()
        start = end - pd.Timedelta(days=days)
        return df[df["date"] >= start].copy()
    return df.copy()
