"""HydroInfo — 流域水情信息平台（智慧水利 / 水信息演示）。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import BASIN_NAME, BASIN_NAME_EN, DEFAULT_LOOKBACK_DAYS, STATIONS
from services.data_loader import load_basin_frame, q_to_stage, reload_data, slice_window
from services.forecast import forecast_control
from services.qc import basin_summary, run_qc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("hydroinfo")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.route("/")
def index():
    return render_template("index.html", basin=BASIN_NAME, basin_en=BASIN_NAME_EN)


@app.route("/api/overview")
def api_overview():
    days = int(request.args.get("days", DEFAULT_LOOKBACK_DAYS))
    df = slice_window(days)
    summary = basin_summary(df)
    cards = []
    for st in STATIONS:
        qcol = st["q_col"]
        if qcol not in df.columns:
            continue
        q = df[qcol].dropna()
        latest_q = float(q.iloc[-1]) if len(q) else None
        prev = float(q.iloc[-2]) if len(q) > 1 else latest_q
        cards.append(
            {
                "id": st["id"],
                "name": st["name"],
                "role": st["role"],
                "lat": st["lat"],
                "lon": st["lon"],
                "q_cfs": round(latest_q, 1) if latest_q is not None else None,
                "stage_ft": round(float(q_to_stage(latest_q)), 2) if latest_q is not None else None,
                "delta_q": round(latest_q - prev, 1) if latest_q is not None and prev is not None else None,
                "warn_q": st["warn_q"],
                "alert_q": st["alert_q"],
                "status": next(
                    (r["status"] for r in summary["reports"] if r["station_id"] == st["id"]),
                    "normal",
                ),
            }
        )
    return jsonify({"basin": BASIN_NAME, "summary": summary, "stations": cards})


@app.route("/api/series")
def api_series():
    days = int(request.args.get("days", DEFAULT_LOOKBACK_DAYS))
    station_id = request.args.get("station", "01646500")
    st = next((s for s in STATIONS if s["id"] == station_id), STATIONS[0])
    df = slice_window(days)
    qcol = st["q_col"]
    pcol = st.get("precip_col")
    dates = df["date"].dt.strftime("%Y-%m-%d").tolist()
    q = df[qcol].where(df[qcol].notna(), None).tolist() if qcol in df.columns else []
    precip = (
        df[pcol].where(df[pcol].notna(), None).tolist()
        if pcol and pcol in df.columns
        else [None] * len(dates)
    )
    stage = [round(float(q_to_stage(v)), 2) if v is not None else None for v in q]
    return jsonify(
        {
            "station": {"id": st["id"], "name": st["name"]},
            "dates": dates,
            "q_cfs": q,
            "stage_ft": stage,
            "precip_mm": precip,
            "warn_q": st["warn_q"],
            "alert_q": st["alert_q"],
        }
    )


@app.route("/api/qc")
def api_qc():
    days = int(request.args.get("days", DEFAULT_LOOKBACK_DAYS))
    df = slice_window(days)
    return jsonify({"reports": run_qc(df), "summary": basin_summary(df)})


@app.route("/api/forecast")
def api_forecast():
    days = int(request.args.get("days", 2000))
    horizon = int(request.args.get("horizon", 7))
    df = slice_window(days)
    return jsonify(forecast_control(df, horizon))


@app.route("/api/rating")
def api_rating():
    """演示水位—流量关系点。"""
    df = load_basin_frame()
    q = df["Q_target"].dropna().values
    # 抽样最多 400 点
    step = max(1, len(q) // 400)
    qs = q[::step]
    zs = [float(q_to_stage(v)) for v in qs]
    return jsonify(
        {
            "q_cfs": [round(float(v), 1) for v in qs],
            "stage_ft": [round(v, 2) for v in zs],
            "note": "演示绳套 Z = a·Q^b + c，非实测水位计成果",
        }
    )


@app.route("/api/health")
def api_health():
    df = load_basin_frame()
    return jsonify({"ok": True, "rows": len(df), "end": df["date"].max().strftime("%Y-%m-%d")})


def main():
    reload_data()
    log.info("HydroInfo ready — open http://127.0.0.1:5050")
    app.run(host="0.0.0.0", port=5050, debug=True)


if __name__ == "__main__":
    main()
