# 菲律宾椰子产区天气看板（可发布网页新版）

这个包用于生成并发布一个可分享的菲律宾椰子产区天气网页看板。别人打开固定 GitHub Pages 链接，即可看到你最新更新后的数据。

## 本版看板结构

- 左侧：结论（简单版）
- 右侧：核心监控指标，可切换近 14 / 30 / 90 天
  - 产区加权降雨 / Normal
  - 产区加权缺雨量
  - Dry Spell 及以上覆盖产量比例
  - Drought 覆盖产量比例
- 交互地图：点大小 = PSA 2025 `Coconut (w/ husk)` 产量占比；点颜色 = 所选窗口 Dry 级别
- 点击地图点：查看该产区的产量占比、窗口降雨/Normal、缺雨量、高温天数、未来 7/16 天预测降雨、弥补判断、最近 150 天降雨距平和温度距平
- 主产区窗口指标：可筛选、可搜索、可下载 CSV，点击行可联动地图
- PAGASA 官方观点：按时间顺序展示，保留英文摘录、中文核心观点和源文件链接

## 1. 本地快速运行

```powershell
cd "D:\张雅\油脂分析\月桂酸油\菲律宾天气\philippines_coconut_weather_dashboard_publish_v2"
python -m pip install -r requirements.txt
.\run_update.bat
```

运行后会生成：

```text
output/YYYYMMDD/菲律宾椰子产区天气监测_YYYYMMDD.xlsx
output/YYYYMMDD/菲律宾椰子产区天气监测_YYYYMMDD.html
output/YYYYMMDD/菲律宾椰子产区天气监测_YYYYMMDD.docx
site/index.html
site/data/latest.json
```

如果只想生成网页发布文件，不生成 Excel/Word：

```powershell
.\build_site.bat
```

本地预览网页：

```powershell
.\preview_site.bat
```

然后浏览器打开：

```text
http://localhost:8000
```

## 2. 数据如何累计

完整历史日度库保存在：

```text
data/history/nasa_daily_all_coconut_regions.csv.gz
```

第一次运行会从 1981 年开始建立历史库；之后每天只补最新缺失日期。

- `-999`、`-9999` 会自动转成空值，不参与计算。
- 如果请求截止日比实际有效数据日更晚，程序会自动回退到最新有效观测日。
- 生产权重和点位标签使用 PSA 2025 `Coconut (w/ husk)` 产量占比。

## 3. 发布到 GitHub Pages

详细步骤见：

```text
docs/GITHUB_PAGES_DEPLOY.md
```

核心逻辑：

```text
GitHub Actions 每天 08:20（北京时间/马尼拉时间）自动运行
→ 抓数据
→ 生成 site/data/latest.json 和 site/index.html
→ 发布到 GitHub Pages
→ 你发给别人一个固定链接即可
```

## 4. 重要提醒

GitHub Pages 如果用公开仓库，网页和数据也是公开的。不要放客户、报价、交易建议、内部观点、账号密码或 API key。

这个包默认只使用公开天气数据、PAGASA 官方链接和你给的产区权重。
