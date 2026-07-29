"""导出个人站 /hydro 演示数据包（国内站网元数据 + 时序 + CSI + LSTM 指标/示意序列）。"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "basin_daily.csv"
PAPER = ROOT.parent / "hydro-ml-paper"
OUT = ROOT.parent / "personal-portfolio" / "public" / "hydro"
OUT.mkdir(parents=True, exist_ok=True)

# 国内示范站网（洮河流域坐标，序列由公开 Potomac 方法同源数据映射，标注为演示）
STATIONS = [
    {
        "id": "TAO-CTRL",
        "name": "临洮控制站",
        "role": "control",
        "river": "洮河",
        "lat": 35.394,
        "lon": 103.862,
        "q_col": "Q_target",
        "precip_col": "precip_target",
        "temp_col": "temp_target",
        "warn_q": 25000,
        "alert_q": 50000,
        "mapped_from": "USGS 01646500 方法演示映射",
    },
    {
        "id": "TAO-UP1",
        "name": "渭源上游站",
        "role": "upstream",
        "river": "洮河上游",
        "lat": 35.137,
        "lon": 104.211,
        "q_col": "Q_01636500",
        "precip_col": "precip_01636500",
        "temp_col": None,
        "warn_q": 12000,
        "alert_q": 25000,
        "mapped_from": "USGS 01636500 方法演示映射",
    },
    {
        "id": "TAO-UP2",
        "name": "康乐支流站",
        "role": "upstream",
        "river": "三岔河",
        "lat": 35.372,
        "lon": 103.718,
        "q_col": "Q_01638480",
        "precip_col": "precip_01638480",
        "temp_col": None,
        "warn_q": 3000,
        "alert_q": 8000,
        "mapped_from": "USGS 01638480 方法演示映射",
    },
]

RATING = {"a": 0.085, "b": 0.42, "c": 2.8}


def q_to_stage(q: float) -> float:
    return float(RATING["a"] * max(q, 1.0) ** RATING["b"] + RATING["c"])


def dump(name: str, obj) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


def load_metrics() -> dict:
    p = PAPER / "results" / "metrics_summary.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_flood_csi() -> dict:
    summary = PAPER / "results" / "hsj_upgrade" / "hsj_upgrade_summary.json"
    if summary.exists():
        return json.loads(summary.read_text(encoding="utf-8"))
    return {}


def main() -> None:
    if not CSV.exists():
        raise SystemExit(f"missing {CSV}")

    df = pd.read_csv(CSV, parse_dates=["date"]).sort_values("date")
    # 近 3 年压缩包，兼顾体积与可演示性
    end = df["date"].max()
    start = end - pd.Timedelta(days=1095)
    win = df[df["date"] >= start].copy().reset_index(drop=True)

    # stations meta
    dump(
        "meta.json",
        {
            "basin": "洮河示范站网",
            "basin_en": "Tao River Demo Network",
            "note": "国内站网产品形态演示；流量序列由公开水文方法同源数据映射，便于复现，非实时报汛。",
            "as_of": end.strftime("%Y-%m-%d"),
            "units": {"q": "cfs（演示单位，可换算 m³/s）", "stage": "ft（演示）", "precip": "mm", "temp": "°C"},
            "stations": STATIONS,
            "rating": RATING,
        },
    )

    # compact series for all stations
    dates = win["date"].dt.strftime("%Y-%m-%d").tolist()
    series = {"dates": dates, "stations": {}}
    for st in STATIONS:
        q = win[st["q_col"]].astype(float)
        precip = win[st["precip_col"]].astype(float) if st["precip_col"] in win.columns else None
        temp = (
            win[st["temp_col"]].astype(float)
            if st.get("temp_col") and st["temp_col"] in win.columns
            else None
        )
        series["stations"][st["id"]] = {
            "q": [None if pd.isna(v) else round(float(v), 1) for v in q],
            "stage": [None if pd.isna(v) else round(q_to_stage(float(v)), 2) for v in q],
            "precip": [None if precip is None or pd.isna(v) else round(float(v), 2) for v in (precip if precip is not None else [])]
            if precip is not None
            else None,
            "temp": [None if temp is None or pd.isna(v) else round(float(v), 1) for v in (temp if temp is not None else [])]
            if temp is not None
            else None,
            "warn_q": st["warn_q"],
            "alert_q": st["alert_q"],
        }
    dump("series.json", series)

    # overview / KPI
    cards = []
    for st in STATIONS:
        q = win[st["q_col"]].dropna()
        latest = float(q.iloc[-1])
        prev = float(q.iloc[-2]) if len(q) > 1 else latest
        status = "normal"
        if latest >= st["alert_q"]:
            status = "alert"
        elif latest >= st["warn_q"]:
            status = "warn"
        cards.append(
            {
                "id": st["id"],
                "name": st["name"],
                "role": st["role"],
                "lat": st["lat"],
                "lon": st["lon"],
                "q": round(latest, 1),
                "stage": round(q_to_stage(latest), 2),
                "delta": round(latest - prev, 1),
                "status": status,
                "warn_q": st["warn_q"],
                "alert_q": st["alert_q"],
            }
        )
    dump("overview.json", {"as_of": end.strftime("%Y-%m-%d"), "stations": cards})

    # business baseline forecast
    q = win["Q_target"].astype(float)
    last_q = float(q.iloc[-1])
    ma7 = float(q.tail(7).mean())
    path = []
    for i in range(7):
        w = (i + 1) / 7
        pred = (1 - w) * last_q + w * ma7
        d = (end + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d")
        path.append({"date": d, "q": round(pred, 1), "stage": round(q_to_stage(pred), 2)})
    dump(
        "forecast_baseline.json",
        {
            "method": "persistence→MA7 blend",
            "as_of": end.strftime("%Y-%m-%d"),
            "path": path,
            "latest_q": round(last_q, 1),
        },
    )

    # rating sample
    qs = win["Q_target"].dropna().values[:: max(1, len(win) // 300)]
    dump(
        "rating.json",
        {
            "q": [round(float(v), 1) for v in qs],
            "stage": [round(q_to_stage(float(v)), 2) for v in qs],
            "note": "演示绳套 Z=a·Q^b+c",
        },
    )

    # LSTM metrics + reconstructed demo overlay for chart toggles
    metrics = load_metrics()
    flood = load_flood_csi()
    threshold = float(flood.get("threshold_P90_cfs", np.nanpercentile(q.dropna(), 90)))

    # Reconstruct a demo LSTM-Attention series on window: blend obs with lag error scaled by paper RMSE
    # Labelled as visualization proxy — real weights live in hydro-ml-paper training runs.
    obs = q.values.astype(float)
    lag1 = np.concatenate([[obs[0]], obs[:-1]])
    # Pull toward truth with residual like RMSE ~2422 for 1d (scaled down for visual)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 800, size=len(obs))
    lstm_proxy = 0.82 * obs + 0.18 * lag1 + noise
    lstm_proxy = np.clip(lstm_proxy, 0, None)
    xgb_proxy = 0.78 * obs + 0.22 * lag1 + rng.normal(0, 1000, size=len(obs))
    xgb_proxy = np.clip(xgb_proxy, 0, None)
    pers = lag1

    dump(
        "models.json",
        {
            "note": "LSTM-Attention / XGBoost 曲线为展示用重构序列；NSE/KGE/CSI 取自 hydro-ml-paper 正式实验结果。",
            "metrics": metrics,
            "series": {
                "dates": dates,
                "observed": [None if math.isnan(v) else round(float(v), 1) for v in obs],
                "persistence": [round(float(v), 1) for v in pers],
                "xgboost": [round(float(v), 1) for v in xgb_proxy],
                "lstm_attention": [round(float(v), 1) for v in lstm_proxy],
            },
        },
    )

    # Flood events for CSI playback
    above = q.values >= threshold
    events = []
    i = 0
    arr = above.astype(int)
    while i < len(arr):
        if arr[i] == 1:
            j = i
            while j < len(arr) and arr[j] == 1:
                j += 1
            peak = float(np.nanmax(obs[i:j]))
            events.append(
                {
                    "start": dates[i],
                    "end": dates[j - 1],
                    "peak_q": round(peak, 1),
                    "peak_stage": round(q_to_stage(peak), 2),
                    "days": j - i,
                    "start_idx": i,
                    "end_idx": j - 1,
                }
            )
            i = j
        else:
            i += 1

    # Keep largest 12 events for playback
    events = sorted(events, key=lambda e: e["peak_q"], reverse=True)[:12]
    events = sorted(events, key=lambda e: e["start"])

    csi_table = []
    for h, block in (flood.get("horizons") or {}).items():
        fp = block.get("flood_P90") or {}
        csi_table.append(
            {
                "horizon": int(h),
                "threshold_cfs": threshold,
                "routing_CSI": (fp.get("routing") or {}).get("CSI"),
                "xgb_CSI": (fp.get("xgb") or {}).get("CSI"),
                "attn_CSI": (fp.get("attn") or {}).get("CSI"),
                "pers_CSI": (fp.get("pers") or {}).get("CSI"),
                "attn_POD": (fp.get("attn") or {}).get("POD"),
                "attn_FAR": (fp.get("attn") or {}).get("FAR"),
            }
        )

    dump(
        "flood.json",
        {
            "threshold_cfs": threshold,
            "threshold_note": "P90 洪水阈值（与 HSJ 升级实验一致）",
            "csi": csi_table,
            "events": events,
        },
    )

    # element catalog for variable plotting
    dump(
        "elements.json",
        {
            "elements": [
                {"id": "q", "label": "流量 Q", "unit": "cfs", "group": "obs"},
                {"id": "stage", "label": "水位 Z", "unit": "ft", "group": "obs"},
                {"id": "precip", "label": "降水 P", "unit": "mm", "group": "meteo"},
                {"id": "temp", "label": "气温 T", "unit": "°C", "group": "meteo"},
                {"id": "upstream_up1", "label": "渭源上游流量", "unit": "cfs", "group": "network"},
                {"id": "upstream_up2", "label": "康乐支流流量", "unit": "cfs", "group": "network"},
                {"id": "persistence", "label": "Persistence", "unit": "cfs", "group": "model"},
                {"id": "xgboost", "label": "XGBoost", "unit": "cfs", "group": "model"},
                {"id": "lstm_attention", "label": "LSTM-Attention", "unit": "cfs", "group": "model"},
            ],
            "defaults": ["q", "precip", "lstm_attention"],
        },
    )

    print("done →", OUT)


if __name__ == "__main__":
    main()
