# HydroInfo · 流域水情信息平台

面向 **智慧水利 / 水信息** 方向的最小可演示闭环：多站态势 → 质控预警 → 过程线与绳套 → 业务基线预报。

> 演示流域默认使用波托马克河公开 USGS 日数据（与 `hydro-ml-paper` 同源，便于复现）。业务基线预报是 Persistence→MA7；论文级 LSTM 见姊妹项目。

## 在线演示（个人站）

https://zhangsjqaq.vexr.dev/hydro

能力：国内示范站网 · Leaflet 地图 · 可变要素出图 · 洪水 CSI 回放 · LSTM 指标对接。

导出数据包到个人站：

```powershell
python scripts/export_portfolio_bundle.py
```

## 快速开始

```powershell
cd d:\deep-learning\code\hydro-info-platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

浏览器打开：http://127.0.0.1:5050

首次启动会自动：

1. 若同级存在 `hydro-ml-paper/data/potomac_daily.csv` → 复制为 `data/basin_daily.csv`
2. 否则从 USGS NWIS 拉取控制站日流量并生成演示上游序列

## 能力一览

| 模块 | 说明 |
|------|------|
| 多站 KPI | 控制站 + 上游站流量/水位/日变幅/状态 |
| 过程线 | 流量 + 降水，叠加注意/警戒阈值 |
| 质控 | 缺失统计、MAD 突变、阈值预警 |
| 绳套 | 演示水位—流量幂律关系 |
| 预报 | 7 日业务基线 + 1/3/7 日 Persistence NSE 回测 |

## API

- `GET /api/overview?days=365`
- `GET /api/series?station=01646500&days=365`
- `GET /api/qc?days=365`
- `GET /api/forecast?horizon=7`
- `GET /api/rating`
- `GET /api/health`

## 与个人站 / GitHub 同步

1. 本仓库推送到 GitHub（独立仓库 `hydro-info-platform`）
2. 在 `personal-portfolio/src/data/works-content.ts` 增加精选作品卡片
3. 推送 `personal-portfolio` → Render 部署时 `db:seed` 自动更新 https://zhangsjqaq.vexr.dev

## 路线图（岗位对齐）

- [ ] 接入国内公开站或自建 CSV 站网格式
- [ ] 洪水事件切片与 CSI 告警回放
- [ ] 对接 `hydro-ml-paper` LSTM 推理服务
- [ ] 地图站网（Leaflet）与角色权限演示

## License

MIT · 学习与作品集演示用途
