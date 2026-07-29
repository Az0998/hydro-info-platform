"""简易多预见期预报：持续性 + 7 日滑动均值（业务基线，非论文模型）。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import FORECAST_HORIZON_DAYS, STATIONS
from services.data_loader import q_to_stage


def _metrics(obs: np.ndarray, pred: np.ndarray) -> dict:
    mask = np.isfinite(obs) & np.isfinite(pred)
    o, p = obs[mask], pred[mask]
    if len(o) < 5:
        return {"nse": None, "rmse": None, "mae": None}
    rmse = float(np.sqrt(np.mean((p - o) ** 2)))
    mae = float(np.mean(np.abs(p - o)))
    denom = np.sum((o - o.mean()) ** 2)
    nse = float(1 - np.sum((p - o) ** 2) / denom) if denom > 0 else None
    return {"nse": nse, "rmse": rmse, "mae": mae}


def backtest_baselines(df: pd.DataFrame, qcol: str = "Q_target", horizon: int = 1) -> dict:
    """用末尾 20% 作测试，评估 persistence / MA7。"""
    q = df[qcol].astype(float).values
    n = len(q)
    split = int(n * 0.8)
    obs, pers, ma = [], [], []
    for t in range(split, n - horizon):
        obs.append(q[t + horizon])
        pers.append(q[t])
        window = q[max(0, t - 6) : t + 1]
        ma.append(float(np.nanmean(window)))
    return {
        "horizon_day": horizon,
        "persistence": _metrics(np.array(obs), np.array(pers)),
        "ma7": _metrics(np.array(obs), np.array(ma)),
    }


def forecast_station(df: pd.DataFrame, station: dict, horizon: int = FORECAST_HORIZON_DAYS) -> dict:
    qcol = station["q_col"]
    if qcol not in df.columns:
        return {"station_id": station["id"], "error": "no_column"}

    series = df[["date", qcol]].dropna().copy()
    last_date = series["date"].iloc[-1]
    last_q = float(series[qcol].iloc[-1])
    ma7 = float(series[qcol].tail(7).mean())

    dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
    # 混合：近预见期偏持续性，远预见期向滑动均值回归
    preds = []
    for i in range(horizon):
        w = min(1.0, (i + 1) / horizon)
        preds.append((1 - w) * last_q + w * ma7)

    path = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "q_cfs": round(q, 1),
            "stage_ft": round(float(q_to_stage(q)), 2),
        }
        for d, q in zip(dates, preds)
    ]

    backtests = [backtest_baselines(df, qcol, h) for h in (1, 3, 7)]

    return {
        "station_id": station["id"],
        "name": station["name"],
        "as_of": last_date.strftime("%Y-%m-%d"),
        "latest_q": last_q,
        "latest_stage": round(float(q_to_stage(last_q)), 2),
        "method": "persistence→MA7 blend（业务基线）",
        "horizon_days": horizon,
        "path": path,
        "backtest": backtests,
    }


def forecast_control(df: pd.DataFrame, horizon: int = FORECAST_HORIZON_DAYS) -> dict:
    control = next(s for s in STATIONS if s["role"] == "control")
    return forecast_station(df, control, horizon)
