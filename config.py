"""站点与预警阈值配置 — 智慧水情信息平台。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

# 演示流域：波托马克河（公开 USGS 日数据，便于复现）
BASIN_NAME = "波托马克河 Potomac"
BASIN_NAME_EN = "Potomac River Basin"

STATIONS = [
    {
        "id": "01646500",
        "name": "华盛顿控制站",
        "name_en": "Potomac River at Washington, DC",
        "role": "control",
        "lat": 38.9498,
        "lon": -77.1278,
        "q_col": "Q_target",
        "precip_col": "precip_target",
        "temp_col": "temp_target",
        # 演示用流量预警阈值（cfs）
        "warn_q": 25000,
        "alert_q": 50000,
    },
    {
        "id": "01636500",
        "name": "上游站 · Shenandoah",
        "name_en": "Shenandoah River near Millville",
        "role": "upstream",
        "lat": 39.2784,
        "lon": -77.7883,
        "q_col": "Q_01636500",
        "precip_col": "precip_01636500",
        "temp_col": None,
        "warn_q": 12000,
        "alert_q": 25000,
    },
    {
        "id": "01638480",
        "name": "上游站 · Monocacy",
        "name_en": "Monocacy River near Frederick",
        "role": "upstream",
        "lat": 39.3890,
        "lon": -77.3780,
        "q_col": "Q_01638480",
        "precip_col": "precip_01638480",
        "temp_col": None,
        "warn_q": 3000,
        "alert_q": 8000,
    },
]

# 简易水位—流量绳套（演示）：Z = a * Q^b + c（英尺）
RATING_CURVE = {"a": 0.085, "b": 0.42, "c": 2.8}

DEFAULT_LOOKBACK_DAYS = 365
FORECAST_HORIZON_DAYS = 7
