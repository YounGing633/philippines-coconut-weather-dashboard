from __future__ import annotations
from pathlib import Path
import json, html, math
from typing import Any
import numpy as np
import pandas as pd

THEME = '#007370'

CN_COLS = {
    'map_label':'产区（产量占比）', 'province':'产区', 'area_group':'区域', 'psa_region':'PSA地区',
    'window_days':'窗口天数', 'rain_sum_mm':'实际累计降雨_mm', 'rain_normal_mm':'常年累计降雨_mm',
    'rain_pct_normal':'降雨占常年_%', 'rain_deficit_mm':'较常年少雨_mm', 'temp_mean_c':'平均气温_℃',
    'tmax_mean_c':'平均最高温_℃', 'temp_anom_c':'气温距平_℃', 'heat_days_ge_35c':'≥35℃天数',
    'risk_label':'风险等级', 'trend_label':'近期是否好转', 'risk_note':'风险说明',
    'forecast_window_days':'预测窗口天数', 'forecast_rain_mm':'未来预测降雨_mm',
    'forecast_rain_to_30d_deficit_pct':'对30天缺雨弥补率_%', 'relief_label':'未来能否弥补',
    'pagasa_like_assessment':'PAGASA式判断', 'pagasa_like_zh':'中文判断', 'monthly_pct_latest3':'最近3个月降雨/常年',
    'coconut_mature_2025_share_pct':'成熟椰子产量占比_%', 'production_share_pct':'产量占比_%',
    'rain_pct_normal_wavg':'加权降雨占常年_%', 'rain_deficit_mm_wavg':'加权缺雨量_mm',
    'temp_anom_c_wavg':'加权气温距平_℃', 'max_risk_score':'最高风险分', 'top_risk_provinces':'主要风险产区',
    'title':'文件标题', 'url':'源文件链接', 'english_core_text':'英文核心观点', '中文核心观点':'中文核心观点'
}


def _clean_val(v: Any) -> Any:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if isinstance(v, pd.Timestamp):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        v = float(v)
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _records(df: pd.DataFrame | None, cols: list[str] | None = None, limit: int | None = None) -> list[dict]:
    if df is None or df.empty:
        return []
    d = df.copy()
    if cols:
        d = d[[c for c in cols if c in d.columns]]
    if limit:
        d = d.head(limit)
    out = []
    for rec in d.to_dict('records'):
        out.append({k: _clean_val(v) for k, v in rec.items()})
    return out


def _fmt_table_html(df: pd.DataFrame | None, cols: list[str], max_rows: int = 60) -> str:
    if df is None or df.empty:
        return '<p class="muted">暂无数据</p>'
    d = df[[c for c in cols if c in df.columns]].copy().head(max_rows)
    d = d.rename(columns={c: CN_COLS.get(c, c) for c in d.columns})
    return d.to_html(index=False, border=0, classes='data-table', escape=False)


def _sections_html(sections):
    blocks=[]
    for sec in sections:
        lis=''.join(f'<li>{html.escape(str(x))}</li>' for x in sec.get('bullets',[]))
        comment=f"<p class='note'>{html.escape(sec.get('comment',''))}</p>" if sec.get('comment') else ''
        blocks.append(f"<div class='explain-block'><h3>{html.escape(sec.get('title','说明'))}</h3><ul>{lis}</ul>{comment}</div>")
    return ''.join(blocks)


def write_interactive_html(
    out_path: str | Path,
    summary: dict,
    sections: list[dict],
    metrics: pd.DataFrame,
    group_summary: pd.DataFrame,
    forecast_metrics: pd.DataFrame,
    pagasa: pd.DataFrame,
    official: pd.DataFrame,
    quality: pd.DataFrame,
    history_recent: pd.DataFrame,
    source_log: pd.DataFrame,
    history_path: Path,
    main_window: int = 30,
) -> Path:
    """Write a clickable HTML dashboard. It refreshes whenever the Python package is rerun."""
    out = Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)

    main = metrics[metrics['window_days'] == main_window].copy() if metrics is not None and not metrics.empty and 'window_days' in metrics.columns else pd.DataFrame()
    if main.empty and metrics is not None and not metrics.empty:
        main = metrics.drop_duplicates('location_id').copy()

    loc_rows = []
    for _, r in main.sort_values(['risk_score','coconut_mature_2025_share_pct'], ascending=False).iterrows():
        lid = r.get('location_id')
        windows = {}
        if metrics is not None and not metrics.empty:
            for _, wr in metrics[metrics['location_id'] == lid].iterrows():
                windows[str(int(wr.get('window_days', 0)))] = {k: _clean_val(v) for k, v in wr.to_dict().items()}
        fc = {}
        if forecast_metrics is not None and not forecast_metrics.empty:
            for _, fr in forecast_metrics[forecast_metrics['location_id'] == lid].iterrows():
                fc[str(int(fr.get('forecast_window_days', 0)))] = {k: _clean_val(v) for k, v in fr.to_dict().items()}
        pr = {}
        if pagasa is not None and not pagasa.empty:
            pg = pagasa[pagasa['location_id'] == lid]
            if not pg.empty:
                pr = {k: _clean_val(v) for k, v in pg.iloc[0].to_dict().items()}
        qr = {}
        if quality is not None and not quality.empty:
            q = quality[quality['location_id'] == lid]
            if not q.empty:
                qr = {k: _clean_val(v) for k, v in q.iloc[0].to_dict().items()}
        loc_rows.append({
            'location_id': lid,
            'province': _clean_val(r.get('province')),
            'map_label': _clean_val(r.get('map_label')),
            'area_group': _clean_val(r.get('area_group')),
            'psa_region': _clean_val(r.get('psa_region')),
            'lat': _clean_val(r.get('lat')),
            'lon': _clean_val(r.get('lon')),
            'share': _clean_val(r.get('coconut_mature_2025_share_pct')),
            'risk_label': _clean_val(r.get('risk_label')),
            'risk_score': _clean_val(r.get('risk_score')),
            'risk_note': _clean_val(r.get('risk_note')),
            'trend_label': _clean_val(r.get('trend_label')),
            'rain_pct_normal': _clean_val(r.get('rain_pct_normal')),
            'rain_deficit_mm': _clean_val(r.get('rain_deficit_mm')),
            'temp_anom_c': _clean_val(r.get('temp_anom_c')),
            'windows': windows,
            'forecast': fc,
            'pagasa': pr,
            'quality': qr,
        })

    ts_rows=[]
    if history_recent is not None and not history_recent.empty:
        h = history_recent.copy()
        h['date'] = pd.to_datetime(h['date'], errors='coerce')
        max_date = h['date'].max()
        if pd.notna(max_date):
            h = h[h['date'] >= max_date - pd.Timedelta(days=150)]
        keep_cols = ['date','location_id','PRECTOTCORR','T2M','T2M_MAX','T2M_MIN','RH2M','map_label','province']
        h = h[[c for c in keep_cols if c in h.columns]].sort_values(['location_id','date'])
        h['date'] = h['date'].dt.strftime('%Y-%m-%d')
        ts_rows = _records(h)

    official_rows = _records(official, ['title','url','english_core_text','中文核心观点'], 20)
    source_rows = _records(source_log, None, 20)

    kpi = {}
    if not main.empty:
        w = pd.to_numeric(main.get('coconut_weight'), errors='coerce').fillna(0)
        if w.sum() > 0:
            def wavg(col):
                vals = pd.to_numeric(main.get(col), errors='coerce')
                mask = vals.notna()
                return float(np.average(vals[mask], weights=w[mask])) if mask.any() and w[mask].sum() > 0 else None
            kpi['weighted_rain_pct_normal_30d'] = wavg('rain_pct_normal')
            kpi['weighted_rain_deficit_mm_30d'] = wavg('rain_deficit_mm')
            kpi['weighted_temp_anom_c_30d'] = wavg('temp_anom_c')
        if 'risk_score' in main.columns:
            risk_scores = pd.to_numeric(main['risk_score'], errors='coerce')
            kpi['dry_or_worse_share'] = float(main.loc[risk_scores >= 3, 'coconut_mature_2025_share_pct'].sum())
            kpi['drought_or_worse_share'] = float(main.loc[risk_scores >= 4, 'coconut_mature_2025_share_pct'].sum())

    payload = {
        'summary': {k:_clean_val(v) for k,v in summary.items()},
        'kpi': {k:_clean_val(v) for k,v in kpi.items()},
        'locations': loc_rows,
        'series': ts_rows,
        'official': official_rows,
        'source_log': source_rows,
        'history_path': str(history_path),
        'main_window': main_window,
    }
    data_json = json.dumps(payload, ensure_ascii=False)

    group_html = _fmt_table_html(group_summary, ['summary_level','area_group','psa_region','window_days','production_share_pct','rain_pct_normal_wavg','rain_deficit_mm_wavg','temp_anom_c_wavg','max_risk_score','top_risk_provinces'], 80)
    metrics_view = metrics[metrics['window_days'].isin([30,90])] if metrics is not None and not metrics.empty and 'window_days' in metrics.columns else metrics
    metrics_html = _fmt_table_html(metrics_view, ['map_label','area_group','window_days','rain_pct_normal','rain_deficit_mm','temp_anom_c','heat_days_ge_35c','risk_label','trend_label','risk_note'], 120)
    forecast_view = forecast_metrics[forecast_metrics['forecast_window_days'].isin([7,16])] if forecast_metrics is not None and not forecast_metrics.empty and 'forecast_window_days' in forecast_metrics.columns else forecast_metrics
    forecast_html = _fmt_table_html(forecast_view, ['map_label','forecast_window_days','forecast_rain_mm','forecast_rain_to_30d_deficit_pct','relief_label','base_30d_risk_label'], 120)
    official_html = _fmt_table_html(official, ['title','url','english_core_text','中文核心观点'], 30)

    css = r'''
    :root{--theme:#007370;--light:#f4fbf9;--line:#d9e6e3;--text:#1f2937;--muted:#64748b;}
    *{box-sizing:border-box} body{margin:0;font-family:Arial,'Microsoft YaHei','PingFang SC',sans-serif;color:var(--text);background:#f8fafc;}
    .topbar{background:linear-gradient(135deg,#00655f,#009688);color:white;padding:20px 28px;position:sticky;top:0;z-index:1000;box-shadow:0 2px 14px rgba(0,0,0,.15)}
    .topbar h1{margin:0;font-size:24px}.topbar p{margin:6px 0 0 0;opacity:.92}.container{padding:18px 24px 40px;max-width:1780px;margin:0 auto;}
    .card{background:white;border:1px solid var(--line);border-radius:16px;padding:16px;margin:14px 0;box-shadow:0 2px 10px rgba(15,23,42,.05)}
    .summary{display:grid;grid-template-columns:1.2fr .8fr;gap:14px}.summary h2{margin:0 0 10px;color:var(--theme)} pre{white-space:pre-wrap;line-height:1.55;font-family:inherit;margin:0}
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.kpi{background:var(--light);border-left:5px solid var(--theme);border-radius:12px;padding:12px}.kpi .label{color:var(--muted);font-size:12px}.kpi .value{font-size:24px;font-weight:700;margin-top:5px}
    .dashboard{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;align-items:stretch}.map-wrap{height:720px;position:relative}.map{height:100%;border-radius:12px;border:1px solid var(--line)}
    .detail{height:720px;overflow:auto}.detail h2{margin:0;color:var(--theme)} .muted{color:var(--muted)} .pill{display:inline-block;padding:3px 9px;border-radius:999px;background:#e2e8f0;margin:2px;font-size:12px}
    .risk{color:white;background:#64748b}.stat-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0}.stat{background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:9px}.stat .k{font-size:12px;color:var(--muted)}.stat .v{font-size:16px;font-weight:700;margin-top:3px}
    .controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px}.controls select,.controls input{border:1px solid var(--line);border-radius:10px;padding:8px 10px;background:white;min-width:160px}.btn{border:none;border-radius:10px;padding:8px 12px;background:var(--theme);color:white;cursor:pointer}
    .legend{background:white;border:1px solid var(--line);border-radius:12px;padding:10px;margin-top:8px;display:flex;gap:8px;flex-wrap:wrap}.legend span{display:inline-flex;align-items:center;gap:5px;font-size:12px}.dot{width:12px;height:12px;border-radius:50%;display:inline-block;border:1px solid #333}
    .explain-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.explain-block{background:var(--light);border-left:5px solid var(--theme);border-radius:12px;padding:12px}.explain-block h3{margin:0 0 8px;color:var(--theme)}.explain-block li{line-height:1.55;margin:4px 0}.note{background:#fff7ed;border-left:4px solid #f59e0b;border-radius:8px;padding:8px;color:#555}
    table.data-table{border-collapse:collapse;width:100%;font-size:12px;background:white} table.data-table th{background:var(--theme);color:white;position:sticky;top:0} table.data-table td,table.data-table th{border:1px solid #e5e7eb;padding:7px;vertical-align:top} .table-wrap{max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px}
    .source a{color:var(--theme);font-weight:600}.small{font-size:12px}.chart{height:270px;margin-top:10px}.active-row{outline:2px solid var(--theme)}
    @media(max-width:1180px){.summary,.dashboard,.explain-grid{grid-template-columns:1fr}.detail,.map-wrap{height:640px}.kpis{grid-template-columns:repeat(2,1fr)}}
    '''

    js = r'''
    const DATA = __DATA__;
    const fmt = (v, d=1, suffix='') => (v===null || v===undefined || Number.isNaN(Number(v))) ? 'NA' : `${Number(v).toFixed(d)}${suffix}`;
    const fmtPct = (v) => (v===null || v===undefined || Number.isNaN(Number(v))) ? 'NA' : `${Number(v).toFixed(0)}%`;
    const riskColors = {'严重干旱风险':'#b30000','干旱风险':'#e34a33','明显偏干':'#f59e0b','略偏干':'#fff176','高温关注':'#fed976','正常/无明显干旱':'#4ade80','数据不足':'#9ca3af'};
    const riskTextColor = {'略偏干':'#111827','高温关注':'#111827','正常/无明显干旱':'#111827'};
    const locations = DATA.locations || [];
    const series = DATA.series || [];
    const byId = Object.fromEntries(locations.map(x=>[x.location_id, x]));
    let selectedId = locations.length ? locations[0].location_id : null;
    let map, markerById = {};

    function initSelects(){
      const s = document.getElementById('provinceSelect');
      locations.forEach(loc=>{ const o=document.createElement('option'); o.value=loc.location_id; o.textContent=`${loc.province}（${fmt(loc.share,1,'%')}）`; s.appendChild(o); });
      s.onchange = () => selectLocation(s.value, true);
      document.getElementById('riskFilter').onchange = refreshMarkers;
      document.getElementById('windowSelect').onchange = () => renderDetail(selectedId);
    }

    function initMap(){
      map = L.map('map', {zoomControl:true}).setView([11.7, 123.5], 5.7);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 10, attribution:'&copy; OpenStreetMap'}).addTo(map);
      refreshMarkers();
    }

    function refreshMarkers(){
      if(!map) return;
      Object.values(markerById).forEach(m=>map.removeLayer(m)); markerById={};
      const filter = document.getElementById('riskFilter').value;
      locations.forEach(loc=>{
        if(!loc.lat || !loc.lon) return;
        if(filter !== 'ALL' && loc.risk_label !== filter) return;
        const color = riskColors[loc.risk_label] || '#9ca3af';
        const radius = Math.max(6, Math.min(22, 5 + Math.sqrt(Number(loc.share||0))*5));
        const m = L.circleMarker([loc.lat, loc.lon], {radius, color:'#1f2937', weight:1, fillColor:color, fillOpacity:.85});
        m.bindTooltip(`${loc.province}｜${fmt(loc.share,1,'%')}｜${loc.risk_label||''}`, {sticky:true});
        m.on('click', ()=>selectLocation(loc.location_id, false));
        m.addTo(map); markerById[loc.location_id]=m;
      });
    }

    function selectLocation(id, moveMap=false){
      selectedId=id; document.getElementById('provinceSelect').value=id;
      const loc=byId[id]; if(!loc) return;
      if(moveMap && map && loc.lat && loc.lon) map.setView([loc.lat, loc.lon], 7);
      Object.entries(markerById).forEach(([mid,m])=>m.setStyle({weight: mid===id ? 4 : 1, opacity:1}));
      renderDetail(id);
    }

    function windowRow(loc, w){ return loc.windows && loc.windows[String(w)] ? loc.windows[String(w)] : {}; }
    function forecastRow(loc, w){ return loc.forecast && loc.forecast[String(w)] ? loc.forecast[String(w)] : {}; }

    function renderDetail(id){
      const loc = byId[id]; if(!loc) return;
      const win = Number(document.getElementById('windowSelect').value || DATA.main_window || 30);
      const cur = windowRow(loc, win);
      const m30 = windowRow(loc, 30);
      const m90 = windowRow(loc, 90);
      const f7 = forecastRow(loc, 7);
      const f16 = forecastRow(loc, 16);
      const color = riskColors[cur.risk_label || loc.risk_label] || '#64748b';
      document.getElementById('detail').innerHTML = `
        <h2>${loc.province} <span class="pill">${fmt(loc.share,2,'%')} 成熟椰子产量占比</span></h2>
        <p class="muted">${loc.area_group||''}｜${loc.psa_region||''}</p>
        <p><span class="pill risk" style="background:${color};color:${riskTextColor[cur.risk_label]||'white'}">${cur.risk_label||loc.risk_label||'NA'}</span><span class="pill">${cur.trend_label||loc.trend_label||'暂无趋势判断'}</span></p>
        <div class="stat-grid">
          <div class="stat"><div class="k">近${win}天降雨/常年</div><div class="v">${fmtPct(cur.rain_pct_normal)}</div></div>
          <div class="stat"><div class="k">较常年少雨</div><div class="v">${fmt(cur.rain_deficit_mm,1,' mm')}</div></div>
          <div class="stat"><div class="k">近30天降雨/常年</div><div class="v">${fmtPct(m30.rain_pct_normal)}</div></div>
          <div class="stat"><div class="k">近90天降雨/常年</div><div class="v">${fmtPct(m90.rain_pct_normal)}</div></div>
          <div class="stat"><div class="k">平均最高温</div><div class="v">${fmt(cur.tmax_mean_c,1,'℃')}</div></div>
          <div class="stat"><div class="k">≥35℃天数</div><div class="v">${fmt(cur.heat_days_ge_35c,0,'天')}</div></div>
        </div>
        <div class="card" style="margin:10px 0;padding:12px"><b>风险解释</b><p>${cur.risk_note||'暂无。'}</p></div>
        <div class="stat-grid">
          <div class="stat"><div class="k">未来7天预测降雨</div><div class="v">${fmt(f7.forecast_rain_mm,1,' mm')}</div><div class="small muted">${f7.relief_label||''}</div></div>
          <div class="stat"><div class="k">未来16天预测降雨</div><div class="v">${fmt(f16.forecast_rain_mm,1,' mm')}</div><div class="small muted">弥补率：${fmtPct(f16.forecast_rain_to_30d_deficit_pct)}</div></div>
        </div>
        <div class="card" style="margin:10px 0;padding:12px"><b>PAGASA式月度判断</b><p>${(loc.pagasa && (loc.pagasa.pagasa_like_zh+' / '+loc.pagasa.pagasa_like_assessment)) || 'NA'}</p><p class="small muted">最近3个月：${(loc.pagasa && loc.pagasa.monthly_pct_latest3) || 'NA'}</p></div>
        <div id="detailChart" class="chart"></div>
      `;
      renderChart(id);
    }

    function renderChart(id){
      const rows = series.filter(x=>x.location_id===id);
      const x = rows.map(r=>r.date);
      const rain = rows.map(r=>r.PRECTOTCORR);
      const tmax = rows.map(r=>r.T2M_MAX);
      const traces = [
        {x, y:rain, type:'bar', name:'日降雨 mm', yaxis:'y1', marker:{opacity:.65}},
        {x, y:tmax, type:'scatter', mode:'lines', name:'最高温 ℃', yaxis:'y2'}
      ];
      const layout = {margin:{l:45,r:45,t:20,b:45}, legend:{orientation:'h'}, yaxis:{title:'降雨 mm'}, yaxis2:{title:'最高温 ℃', overlaying:'y', side:'right'}, xaxis:{title:'最近约150天'}, paper_bgcolor:'white', plot_bgcolor:'white'};
      Plotly.newPlot('detailChart', traces, layout, {responsive:true, displayModeBar:false});
    }

    function initKpis(){
      document.getElementById('kpiRain').textContent = fmtPct(DATA.kpi.weighted_rain_pct_normal_30d);
      document.getElementById('kpiDeficit').textContent = fmt(DATA.kpi.weighted_rain_deficit_mm_30d,1,' mm');
      document.getElementById('kpiDryShare').textContent = fmt(DATA.kpi.dry_or_worse_share,1,'%');
      document.getElementById('kpiDroughtShare').textContent = fmt(DATA.kpi.drought_or_worse_share,1,'%');
    }

    function initOfficial(){
      const el=document.getElementById('officialCards');
      if(!DATA.official || DATA.official.length===0){ el.innerHTML='<p class="muted">暂无官方文件。</p>'; return; }
      el.innerHTML = DATA.official.slice(0,8).map(o=>`<div class="source card" style="margin:8px 0;padding:12px"><b>${o.title||'PAGASA file'}</b><p>${o['中文核心观点']||''}</p><p class="small muted">${o.english_core_text||''}</p><a href="${o.url||'#'}" target="_blank">打开源文件 / Source</a></div>`).join('');
    }

    document.addEventListener('DOMContentLoaded', ()=>{
      initSelects(); initKpis(); initMap(); initOfficial();
      if(selectedId) selectLocation(selectedId, true);
    });
    '''.replace('__DATA__', data_json)

    html_txt = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>菲律宾椰子产区天气交互看板</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
    <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
    <style>{css}</style></head><body>
    <div class="topbar"><h1>菲律宾椰子产区天气交互看板</h1><p>CNO/Copra Weather Dashboard｜点地图上的产区，可查看过去降雨/温度、干旱风险、未来降雨弥补和官方观点</p></div>
    <div class="container">
      <div class="summary">
        <div class="card"><h2>一句话结论</h2><p>{html.escape(str(summary.get('one_liner','')))}</p><h2>详细解释</h2><pre>{html.escape(str(summary.get('detail','')))}</pre></div>
        <div class="card"><h2>核心监控指标</h2><div class="kpis">
          <div class="kpi"><div class="label">产区加权近30天降雨/常年</div><div class="value" id="kpiRain">NA</div></div>
          <div class="kpi"><div class="label">产区加权近30天缺雨量</div><div class="value" id="kpiDeficit">NA</div></div>
          <div class="kpi"><div class="label">偏干及以上覆盖产量</div><div class="value" id="kpiDryShare">NA</div></div>
          <div class="kpi"><div class="label">干旱风险覆盖产量</div><div class="value" id="kpiDroughtShare">NA</div></div>
        </div><p class="small muted">注：缺雨量=历史同期正常累计降雨-实际累计降雨；空值与-999不计入。</p></div>
      </div>
      <div class="card">
        <div class="controls"><b>交互区：</b><select id="provinceSelect"></select><select id="windowSelect"><option value="7">近7天</option><option value="14">近14天</option><option value="30" selected>近30天</option><option value="90">近90天</option></select><select id="riskFilter"><option value="ALL">全部风险</option><option value="严重干旱风险">严重干旱风险</option><option value="干旱风险">干旱风险</option><option value="明显偏干">明显偏干</option><option value="略偏干">略偏干</option><option value="正常/无明显干旱">正常/无明显干旱</option><option value="数据不足">数据不足</option></select><button class="btn" onclick="selectLocation(selectedId,true)">定位当前产区</button></div>
        <div class="dashboard"><div class="map-wrap"><div id="map" class="map"></div><div class="legend"><span><i class="dot" style="background:#b30000"></i>严重干旱</span><span><i class="dot" style="background:#e34a33"></i>干旱风险</span><span><i class="dot" style="background:#f59e0b"></i>明显偏干</span><span><i class="dot" style="background:#fff176"></i>略偏干</span><span><i class="dot" style="background:#4ade80"></i>正常</span><span><i class="dot" style="background:#9ca3af"></i>数据不足</span><span>点大小=2025成熟椰子产量占比</span></div></div><div id="detail" class="detail card"></div></div>
      </div>
      <div class="card"><h2>中文释义 / 如何看这份报告</h2><div class="explain-grid">{_sections_html(sections)}</div></div>
      <div class="card"><h2>区域汇总</h2><div class="table-wrap">{group_html}</div></div>
      <div class="card"><h2>主产区窗口指标</h2><div class="table-wrap">{metrics_html}</div></div>
      <div class="card"><h2>未来预测与弥补判断</h2><div class="table-wrap">{forecast_html}</div></div>
      <div class="card"><h2>PAGASA官方观点 / English + 中文核心观点</h2><div id="officialCards"></div><div class="table-wrap">{official_html}</div></div>
      <div class="card"><h2>历史日度数据积累</h2><p>完整历史库：<code>{html.escape(str(history_path))}</code></p><p class="small muted">每天重跑后，此HTML会随最新缓存与历史库自动更新；无需手动改HTML。</p></div>
    </div><script>{js}</script></body></html>'''
    out.write_text(html_txt, encoding='utf-8')
    return out
