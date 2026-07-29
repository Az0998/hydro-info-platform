"""水情数据质控：缺失、突变、阈值预警。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import STATIONS


def _spike_mask(series: pd.Series, z: float = 4.0) -> pd.Series:
    s = series.astype(float)
    med = s.rolling(7, center=True, min_periods=3).median()
    mad = (s - med).abs().rolling(7, center=True, min_periods=3).median()
    mad = mad.replace(0, np.nan)
    score = (s - med).abs() / (1.4826 * mad)
    return score > z


def station_qc(df: pd.DataFrame, station: dict) -> dict:
    qcol = station["q_col"]
    if qcol not in df.columns:
        return {"station_id": station["id"], "flags": [], "status": "no_data"}

    q = df[qcol]
    missing = int(q.isna().sum())
    spikes = int(_spike_mask(q.ffill()).sum())
    latest = float(q.dropna().iloc[-1]) if q.notna().any() else None

    status = "normal"
    if latest is not None:
        if latest >= station["alert_q"]:
            status = "alert"
        elif latest >= station["warn_q"]:
            status = "warn"

    flags = []
    if missing:
        flags.append({"type": "missing", "count": missing, "msg": f"缺失 {missing} 日"})
    if spikes:
        flags.append({"type": "spike", "count": spikes, "msg": f"疑似突变 {spikes} 处"})
    if status == "warn":
        flags.append({"type": "threshold", "msg": f"流量超过注意水位阈值 {station['warn_q']} cfs"})
    if status == "alert":
        flags.append({"type": "threshold", "msg": f"流量超过警戒阈值 {station['alert_q']} cfs"})

    return {
        "station_id": station["id"],
        "name": station["name"],
        "status": status,
        "latest_q": latest,
        "missing": missing,
        "spikes": spikes,
        "flags": flags,
    }


def run_qc(df: pd.DataFrame) -> list[dict]:
    return [station_qc(df, st) for st in STATIONS]


def basin_summary(df: pd.DataFrame) -> dict:
    reports = run_qc(df)
    alert_n = sum(1 for r in reports if r["status"] == "alert")
    warn_n = sum(1 for r in reports if r["status"] == "warn")
    return {
        "stations": len(reports),
        "alert": alert_n,
        "warn": warn_n,
        "normal": len(reports) - alert_n - warn_n,
        "date_start": df["date"].min().strftime("%Y-%m-%d") if len(df) else None,
        "date_end": df["date"].max().strftime("%Y-%m-%d") if len(df) else None,
        "rows": len(df),
        "reports": reports,
    }
