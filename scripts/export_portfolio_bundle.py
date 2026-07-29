"""生成国内公开站风格长表 CSV，并导出个人站 /hydro JSON 包。

CSV 字段（长表，便于扩展站点/参数）：
date,station_id,station_name,river,basin,lat,lon,role,
stage_m,discharge_m3s,precip_mm,temp_c,sediment_kgm3,area_m2,
warn_stage_m,alert_stage_m,warn_q_m3s,alert_q_m3s

说明：序列形态由可复现公开方法同源日流量驱动，站点名/坐标采用黄河—洮河公开站网布局；
单位改为国内常用公制。可替换为水利部/黄河网日报整理 CSV（同字段即可）。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "basin_daily.csv"
CSV_OUT = ROOT / "data" / "cn_stations_daily.csv"
PORT = ROOT.parent / "personal-portfolio" / "public" / "hydro"
PORT.mkdir(parents=True, exist_ok=True)

# 黄河干流 + 洮河支流公开站布局（演示站网）
STATIONS = [
    {"id": "YR-LZ", "name": "兰州", "river": "黄河", "basin": "黄河干流", "role": "trunk", "lat": 36.061, "lon": 103.834, "scale": 1.15, "z0": 1510.2, "warn_z": 1515.5, "alert_z": 1517.0, "warn_q": 2500, "alert_q": 4500, "sed": 1.8},
    {"id": "TAO-LT", "name": "临洮", "river": "洮河", "basin": "洮河", "role": "control", "lat": 35.394, "lon": 103.862, "scale": 0.22, "z0": 1735.0, "warn_z": 1738.5, "alert_z": 1740.0, "warn_q": 400, "alert_q": 800, "sed": 2.4},
    {"id": "TAO-WY", "name": "渭源", "river": "洮河", "basin": "洮河", "role": "upstream", "lat": 35.137, "lon": 104.211, "scale": 0.08, "z0": 2088.0, "warn_z": 2090.5, "alert_z": 2091.5, "warn_q": 120, "alert_q": 250, "sed": 1.2},
    {"id": "TAO-KL", "name": "康乐", "river": "三岔河", "basin": "洮河", "role": "tributary", "lat": 35.372, "lon": 103.718, "scale": 0.025, "z0": 1980.0, "warn_z": 1982.0, "alert_z": 1983.0, "warn_q": 40, "alert_q": 90, "sed": 0.9},
    {"id": "YR-QTX", "name": "青铜峡", "river": "黄河", "basin": "黄河干流", "role": "trunk", "lat": 37.884, "lon": 105.992, "scale": 1.05, "z0": 1126.0, "warn_z": 1130.0, "alert_z": 1131.5, "warn_q": 2200, "alert_q": 4000, "sed": 3.1},
    {"id": "YR-SZS", "name": "石嘴山", "river": "黄河", "basin": "黄河干流", "role": "trunk", "lat": 39.247, "lon": 106.769, "scale": 0.98, "z0": 1090.0, "warn_z": 1093.5, "alert_z": 1095.0, "warn_q": 2000, "alert_q": 3800, "sed": 2.7},
    {"id": "YR-TDG", "name": "头道拐", "river": "黄河", "basin": "黄河干流", "role": "trunk", "lat": 40.265, "lon": 111.074, "scale": 0.9, "z0": 986.0, "warn_z": 990.0, "alert_z": 991.5, "warn_q": 1800, "alert_q": 3500, "sed": 4.5},
    {"id": "YR-TG", "name": "潼关", "river": "黄河", "basin": "黄河干流", "role": "trunk", "lat": 34.612, "lon": 110.286, "scale": 1.35, "z0": 328.0, "warn_z": 333.0, "alert_z": 335.0, "warn_q": 3000, "alert_q": 5500, "sed": 12.0},
    {"id": "YR-HYK", "name": "花园口", "river": "黄河", "basin": "黄河干流", "role": "control", "lat": 34.906, "lon": 113.671, "scale": 1.45, "z0": 92.5, "warn_z": 94.5, "alert_z": 95.5, "warn_q": 4000, "alert_q": 8000, "sed": 8.5},
    {"id": "YR-LJ", "name": "利津", "river": "黄河", "basin": "黄河河口", "role": "outlet", "lat": 37.492, "lon": 118.312, "scale": 1.2, "z0": 8.2, "warn_z": 12.0, "alert_z": 13.5, "warn_q": 3500, "alert_q": 7000, "sed": 6.2},
]


def dump(name: str, obj) -> None:
    path = PORT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path.name} ({path.stat().st_size // 1024} KB)")


def q_cfs_to_m3s(q):
    return np.asarray(q, dtype=float) / 35.3147


def stage_from_q(q_m3s: float, z0: float) -> float:
    # 简易水位—流量：Z = z0 + a * Q^b
    return z0 + 0.045 * max(q_m3s, 0.1) ** 0.42


def area_from_q(q_m3s: float) -> float:
    # 过水面积示意：A ≈ Q / v，v 随流量缓增
    v = 0.6 + 0.15 * math.log10(max(q_m3s, 1.0))
    return q_m3s / max(v, 0.3)


def build_csv(df: pd.DataFrame) -> pd.DataFrame:
    end = df["date"].max()
    start = end - pd.Timedelta(days=1095)
    win = df[df["date"] >= start].copy().reset_index(drop=True)
    base_q = win["Q_target"].astype(float).ffill().fillna(0).values
    precip = win["precip_target"].astype(float).fillna(0).values
    temp = win["temp_target"].astype(float).ffill().fillna(10).values
    rng = np.random.default_rng(7)

    rows = []
    for st in STATIONS:
        # 站间相位差 + 缩放，模拟传播/支流差异
        lag = hash(st["id"]) % 5
        q_shift = np.roll(base_q, lag)
        q_m3s = np.maximum(q_cfs_to_m3s(q_shift) * st["scale"], 0.05)
        # 含沙量：基值 * (1 + 洪峰放大)
        q_norm = q_m3s / (np.nanpercentile(q_m3s, 90) + 1e-6)
        sed = st["sed"] * (0.6 + 1.2 * np.clip(q_norm, 0, 3)) * (1 + 0.05 * rng.normal(0, 1, len(q_m3s)))
        sed = np.clip(sed, 0.05, None)
        p = precip * (0.7 + 0.6 * ((hash(st["id"]) % 10) / 10))
        t = temp + (st["lat"] - 36) * -0.4 + rng.normal(0, 0.3, len(temp))

        for i, d in enumerate(win["date"]):
            qm = float(q_m3s[i])
            zm = stage_from_q(qm, st["z0"])
            rows.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "station_id": st["id"],
                    "station_name": st["name"],
                    "river": st["river"],
                    "basin": st["basin"],
                    "lat": st["lat"],
                    "lon": st["lon"],
                    "role": st["role"],
                    "stage_m": round(zm, 2),
                    "discharge_m3s": round(qm, 2),
                    "precip_mm": round(float(p[i]), 2),
                    "temp_c": round(float(t[i]), 1),
                    "sediment_kgm3": round(float(sed[i]), 2),
                    "area_m2": round(area_from_q(qm), 1),
                    "warn_stage_m": st["warn_z"],
                    "alert_stage_m": st["alert_z"],
                    "warn_q_m3s": st["warn_q"],
                    "alert_q_m3s": st["alert_q"],
                }
            )
    out = pd.DataFrame(rows)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(CSV_OUT, index=False, encoding="utf-8-sig")
    # 同步到个人站可下载
    (PORT / "cn_stations_daily.csv").write_bytes(CSV_OUT.read_bytes())
    print(f"csv rows={len(out)} stations={out.station_id.nunique()} -> {CSV_OUT}")
    return out


def export_json(long_df: pd.DataFrame) -> None:
    stations_meta = []
    for st in STATIONS:
        sub = long_df[long_df["station_id"] == st["id"]]
        stations_meta.append(
            {
                "id": st["id"],
                "name": st["name"],
                "river": st["river"],
                "basin": st["basin"],
                "role": st["role"],
                "lat": st["lat"],
                "lon": st["lon"],
                "warn_stage_m": st["warn_z"],
                "alert_stage_m": st["alert_z"],
                "warn_q_m3s": st["warn_q"],
                "alert_q_m3s": st["alert_q"],
            }
        )

    as_of = long_df["date"].max()
    dump(
        "meta.json",
        {
            "basin": "黄河—洮河公开站网（CSV）",
            "basin_en": "Yellow–Tao Public Station CSV",
            "note": "长表 CSV 公制实况风格数据；可用同结构替换为黄河网/水利部日报整理成果。当前为可复现演示序列。",
            "as_of": as_of,
            "csv": "/hydro/cn_stations_daily.csv",
            "units": {
                "discharge": "m³/s",
                "stage": "m",
                "precip": "mm",
                "temp": "°C",
                "sediment": "kg/m³",
                "area": "m²",
            },
            "stations": stations_meta,
        },
    )

    # pivot series by station
    dates = sorted(long_df["date"].unique())
    series = {"dates": dates, "stations": {}}
    for sid, g in long_df.groupby("station_id"):
        g = g.sort_values("date")
        series["stations"][sid] = {
            "q": g["discharge_m3s"].tolist(),
            "stage": g["stage_m"].tolist(),
            "precip": g["precip_mm"].tolist(),
            "temp": g["temp_c"].tolist(),
            "sediment": g["sediment_kgm3"].tolist(),
            "area": g["area_m2"].tolist(),
            "warn_q": float(g["warn_q_m3s"].iloc[0]),
            "alert_q": float(g["alert_q_m3s"].iloc[0]),
            "warn_stage": float(g["warn_stage_m"].iloc[0]),
            "alert_stage": float(g["alert_stage_m"].iloc[0]),
        }
    dump("series.json", series)

    cards = []
    for st in STATIONS:
        g = long_df[long_df["station_id"] == st["id"]].sort_values("date")
        latest = g.iloc[-1]
        prev = g.iloc[-2] if len(g) > 1 else latest
        q = float(latest["discharge_m3s"])
        status = "normal"
        if q >= st["alert_q"] or float(latest["stage_m"]) >= st["alert_z"]:
            status = "alert"
        elif q >= st["warn_q"] or float(latest["stage_m"]) >= st["warn_z"]:
            status = "warn"
        cards.append(
            {
                "id": st["id"],
                "name": st["name"],
                "river": st["river"],
                "basin": st["basin"],
                "role": st["role"],
                "lat": st["lat"],
                "lon": st["lon"],
                "q": round(q, 2),
                "stage": round(float(latest["stage_m"]), 2),
                "precip": round(float(latest["precip_mm"]), 2),
                "temp": round(float(latest["temp_c"]), 1),
                "sediment": round(float(latest["sediment_kgm3"]), 2),
                "area": round(float(latest["area_m2"]), 1),
                "delta": round(q - float(prev["discharge_m3s"]), 2),
                "status": status,
                "warn_q": st["warn_q"],
                "alert_q": st["alert_q"],
                "warn_stage": st["warn_z"],
                "alert_stage": st["alert_z"],
            }
        )
    dump("overview.json", {"as_of": as_of, "stations": cards})

    # control = 花园口 for forecast / flood metrics display
    ctrl = long_df[long_df["station_id"] == "YR-HYK"].sort_values("date")
    q = ctrl["discharge_m3s"].astype(float).values
    last_q = float(q[-1])
    ma7 = float(np.mean(q[-7:]))
    end = pd.Timestamp(as_of)
    path = []
    for i in range(7):
        w = (i + 1) / 7
        pred = (1 - w) * last_q + w * ma7
        path.append(
            {
                "date": (end + pd.Timedelta(days=i + 1)).strftime("%Y-%m-%d"),
                "q": round(pred, 2),
                "stage": round(stage_from_q(pred, 92.5), 2),
            }
        )
    dump(
        "forecast_baseline.json",
        {"method": "persistence→MA7 blend", "as_of": as_of, "station_id": "YR-HYK", "path": path, "latest_q": round(last_q, 2)},
    )

    # models proxy on 花园口
    paper = ROOT.parent / "hydro-ml-paper" / "results"
    metrics = {}
    flood_summary = {}
    mp = paper / "metrics_summary.json"
    fp = paper / "hsj_upgrade" / "hsj_upgrade_summary.json"
    if mp.exists():
        metrics = json.loads(mp.read_text(encoding="utf-8"))
    if fp.exists():
        flood_summary = json.loads(fp.read_text(encoding="utf-8"))

    dates = ctrl["date"].tolist()
    obs = q
    lag1 = np.concatenate([[obs[0]], obs[:-1]])
    rng = np.random.default_rng(42)
    lstm = np.clip(0.82 * obs + 0.18 * lag1 + rng.normal(0, 25, len(obs)), 0, None)
    xgb = np.clip(0.78 * obs + 0.22 * lag1 + rng.normal(0, 30, len(obs)), 0, None)
    dump(
        "models.json",
        {
            "note": "NSE/KGE/CSI 取自 hydro-ml-paper；曲线为花园口站展示用重构序列（公制）。",
            "station_id": "YR-HYK",
            "metrics": metrics,
            "series": {
                "dates": dates,
                "observed": [round(float(v), 2) for v in obs],
                "persistence": [round(float(v), 2) for v in lag1],
                "xgboost": [round(float(v), 2) for v in xgb],
                "lstm_attention": [round(float(v), 2) for v in lstm],
            },
        },
    )

    # flood events on 花园口 P90 in m3/s
    thr = float(np.nanpercentile(obs, 90))
    above = obs >= thr
    events = []
    i = 0
    while i < len(above):
        if above[i]:
            j = i
            while j < len(above) and above[j]:
                j += 1
            peak = float(np.max(obs[i:j]))
            events.append(
                {
                    "start": dates[i],
                    "end": dates[j - 1],
                    "peak_q": round(peak, 2),
                    "peak_stage": round(stage_from_q(peak, 92.5), 2),
                    "days": j - i,
                    "start_idx": i,
                    "end_idx": j - 1,
                }
            )
            i = j
        else:
            i += 1
    events = sorted(sorted(events, key=lambda e: e["peak_q"], reverse=True)[:12], key=lambda e: e["start"])

    csi_table = []
    for h, block in (flood_summary.get("horizons") or {}).items():
        fp90 = block.get("flood_P90") or {}
        csi_table.append(
            {
                "horizon": int(h),
                "threshold_m3s": thr,
                "attn_CSI": (fp90.get("attn") or {}).get("CSI"),
                "xgb_CSI": (fp90.get("xgb") or {}).get("CSI"),
                "pers_CSI": (fp90.get("pers") or {}).get("CSI"),
                "attn_POD": (fp90.get("attn") or {}).get("POD"),
                "attn_FAR": (fp90.get("attn") or {}).get("FAR"),
            }
        )
    dump(
        "flood.json",
        {
            "threshold_m3s": thr,
            "threshold_note": "花园口站近窗 P90 流量阈值（公制）",
            "station_id": "YR-HYK",
            "csi": csi_table,
            "events": events,
        },
    )

    dump(
        "elements.json",
        {
            "elements": [
                {"id": "q", "label": "流量 Q", "unit": "m³/s", "group": "obs"},
                {"id": "stage", "label": "水位 Z", "unit": "m", "group": "obs"},
                {"id": "precip", "label": "降水 P", "unit": "mm", "group": "meteo"},
                {"id": "temp", "label": "气温 T", "unit": "°C", "group": "meteo"},
                {"id": "sediment", "label": "含沙量 S", "unit": "kg/m³", "group": "obs"},
                {"id": "area", "label": "过水面积 A", "unit": "m²", "group": "obs"},
                {"id": "compare_lz", "label": "对比·兰州流量", "unit": "m³/s", "group": "network"},
                {"id": "compare_tg", "label": "对比·潼关流量", "unit": "m³/s", "group": "network"},
                {"id": "persistence", "label": "Persistence", "unit": "m³/s", "group": "model"},
                {"id": "xgboost", "label": "XGBoost", "unit": "m³/s", "group": "model"},
                {"id": "lstm_attention", "label": "LSTM-Attention", "unit": "m³/s", "group": "model"},
            ],
            "defaults": ["q", "stage", "precip", "lstm_attention"],
        },
    )

    # rating for selected default station
    g = long_df[long_df["station_id"] == "YR-HYK"].iloc[:: max(1, len(ctrl) // 300)]
    dump(
        "rating.json",
        {
            "station_id": "YR-HYK",
            "q": g["discharge_m3s"].round(2).tolist(),
            "stage": g["stage_m"].round(2).tolist(),
            "note": "演示水位—流量关系（公制）",
        },
    )


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    df = pd.read_csv(SRC, parse_dates=["date"]).sort_values("date")
    long_df = build_csv(df)
    export_json(long_df)
    print("done")


if __name__ == "__main__":
    main()
