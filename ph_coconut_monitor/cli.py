from __future__ import annotations
import argparse
from pathlib import Path
from datetime import timedelta
import pandas as pd
from .config import load_config
from .fetchers import NASAClient, HistoryStore, OpenMeteoClient
from .analysis import RiskThresholds, make_daily_climatology, effective_observation_date, window_metrics, weighted_group_summary, pagasa_like_assessment, forecast_metrics, data_quality
from .official_pagasa import download_pagasa_official
from .mapping import make_drought_map, make_market_risk_map, make_trend_chart, make_forecast_relief_chart
from .narrative import build_narrative, chinese_annotation_sections
from .outputs import write_excel, write_docx
from .dashboard import write_interactive_html
from .site_generator import write_site_dashboard
from .utils import parse_date, today_manila, iso, ensure_dir


def build_parser():
    p=argparse.ArgumentParser(description='Philippines coconut/CNO weather monitor')
    p.add_argument('--root', default=None)
    p.add_argument('--end', default=None, help='Requested end date YYYY-MM-DD. Default today Manila.')
    p.add_argument('--history-start', default=None, help='Full history start date. Default from settings: 1981-01-01')
    p.add_argument('--lookbacks', default='7,14,30,90')
    p.add_argument('--main-window', type=int, default=30)
    p.add_argument('--forecast-days', type=int, default=16)
    p.add_argument('--formats', default='xlsx,html,docx')
    p.add_argument('--official-limit', type=int, default=20)
    p.add_argument('--force', action='store_true', help='Force refetch/rebuild history cache')
    p.add_argument('--quick', action='store_true', help='Quick run: only fetch recent 150 days if history does not exist. Baseline/climatology may be incomplete.')
    p.add_argument('--build-site', action='store_true', help='Build GitHub Pages-ready site/index.html and site/data/latest.json.')
    p.add_argument('--site-dir', default='site', help='Static website output directory. Default: site')
    return p


def run(args):
    cfg=load_config(args.root)
    settings=cfg.settings
    locations=cfg.production_locations
    lookbacks=[int(x.strip()) for x in args.lookbacks.split(',') if x.strip()]
    requested_end=parse_date(args.end, default=today_manila())
    history_start=parse_date(args.history_start or settings.get('default_history_start','1981-01-01'))
    if args.quick:
        history_start=max(history_start, requested_end - timedelta(days=150))
    params=settings.get('nasa_parameters',['PRECTOTCORR','T2M','T2M_MAX','T2M_MIN','RH2M'])
    nasa=NASAClient(cfg.cache_dir, parameters=params)
    store=HistoryStore(cfg.history_dir)
    history=store.update(nasa, locations, history_start, requested_end, force=args.force)
    min_weight=settings.get('min_effective_weight_coverage',0.70)
    eff=effective_observation_date(history, locations, requested_end, min_weight)
    if eff is None:
        eff=requested_end
        print(f'[WARN] No effective observation date found; using requested end {eff}.')
    elif eff != requested_end:
        print(f'[INFO] Requested end date: {requested_end}; latest valid weighted observation date: {eff}. Report uses {eff}.')
    run_id=iso(eff).replace('-','')
    run_dir=ensure_dir(cfg.output_dir / run_id)
    fig_dir=ensure_dir(run_dir / 'figures')
    # Build baseline climatology from the stored history.
    clim=make_daily_climatology(history, settings.get('baseline_start','1981-01-01'), settings.get('baseline_end','2020-12-31'))
    thresholds=RiskThresholds(**settings.get('risk_thresholds',{}))
    metrics=window_metrics(history, clim, locations, eff, lookbacks, thresholds, min_coverage_pct=settings.get('min_location_coverage_pct',0.75))
    group_area=weighted_group_summary(metrics, ['area_group','window_days']) if not metrics.empty else pd.DataFrame()
    group_region=weighted_group_summary(metrics, ['psa_region','window_days']) if not metrics.empty else pd.DataFrame()
    group_summary=pd.concat([group_area.assign(summary_level='三大区域'), group_region.assign(summary_level='PSA地区')], ignore_index=True) if not group_area.empty or not group_region.empty else pd.DataFrame()
    pagasa=pagasa_like_assessment(history, clim, locations, eff)
    forecast_raw=OpenMeteoClient(cfg.cache_dir).fetch_locations(locations, forecast_days=max(1,min(args.forecast_days,16)), force=args.force)
    fmetrics=forecast_metrics(forecast_raw, metrics, locations, windows=(7, min(args.forecast_days,16)), main_window=args.main_window)
    quality=data_quality(history, locations, requested_end, eff, lookbacks)
    official=download_pagasa_official(cfg.data_dir / 'pagasa_pdfs', limit=args.official_limit, force=args.force)
    summary=build_narrative(metrics, group_summary, fmetrics, pagasa, official, iso(eff), iso(requested_end), main_window=args.main_window)
    sections=chinese_annotation_sections(summary, metrics, fmetrics, pagasa, quality, main_window=args.main_window)
    chart_paths={
        'PAGASA式干旱评估地图': make_drought_map(pagasa, fig_dir / 'pagasa_like_drought_map.png', title=f'PAGASA-like Drought Assessment as of {iso(eff)} / 菲律宾椰子产区干旱评估'),
        f'近{args.main_window}天降雨风险地图': make_market_risk_map(metrics, fig_dir / f'rain_risk_map_{args.main_window}d.png', window_days=args.main_window),
        f'主产区近{args.main_window}天降雨走势': make_trend_chart(metrics, fig_dir / f'top_area_rain_pct_{args.main_window}d.png', window_days=args.main_window),
        '未来16天降雨弥补图': make_forecast_relief_chart(fmetrics, fig_dir / 'forecast_relief_16d.png', window_days=min(args.forecast_days,16)),
    }
    source_log=pd.DataFrame([
        {'source':'NASA POWER Daily API','purpose':'Historical/current daily rainfall, temperature, humidity, wind and solar. -999/-9999 treated as missing.','url':'https://power.larc.nasa.gov/api/temporal/daily/point'},
        {'source':'Open-Meteo Forecast API','purpose':'Future 7-16 day rainfall and temperature forecast.','url':'https://api.open-meteo.com/v1/forecast'},
        {'source':'PAGASA Climate Advisories','purpose':'Official dry spell/drought/outlook PDFs and dry/drought assessment files.','url':'https://www.pagasa.dost.gov.ph/climate/climate-advisories'},
        {'source':'User uploaded PSA coconut production workbook','purpose':'2025 Coconut (w/ husk) production shares are used as dashboard weighting and marker sizing.','url':'local: config/production_regions_2025.csv'},
    ])
    hist_recent_start=pd.Timestamp(eff - timedelta(days=400))
    if not history.empty:
        htmp = history[history['date']>=hist_recent_start].copy()
        htmp['date'] = pd.to_datetime(htmp['date'])
        htmp['doy'] = htmp['date'].dt.dayofyear
        htmp = htmp.merge(clim, on=['location_id','doy'], how='left') if clim is not None and not clim.empty else htmp
        if 'PRECTOTCORR_clim' in htmp.columns:
            htmp['rain_anom_mm'] = htmp['PRECTOTCORR'] - htmp['PRECTOTCORR_clim']
        if 'T2M_MAX_clim' in htmp.columns:
            htmp['tmax_anom_c'] = htmp['T2M_MAX'] - htmp['T2M_MAX_clim']
        loc_cols=[c for c in ['location_id','map_label','area_group','province','psa_region','coconut_husk_2025_share_pct','coconut_mature_2025_share_pct'] if c in locations.columns]
        history_recent=htmp.merge(locations[loc_cols], on='location_id', how='left')
    else:
        history_recent=pd.DataFrame()
    outputs={}
    fmts={x.strip().lower() for x in args.formats.split(',') if x.strip()}
    if 'xlsx' in fmts:
        outputs['xlsx']=write_excel(run_dir / f'菲律宾椰子产区天气监测_{run_id}.xlsx', summary, sections, metrics, group_summary, fmetrics, pagasa, official, locations, quality, history_recent, source_log, chart_paths, store.path)
    if 'html' in fmts:
        outputs['html']=write_interactive_html(run_dir / f'菲律宾椰子产区天气监测_{run_id}.html', summary, sections, metrics, group_summary, fmetrics, pagasa, official, quality, history_recent, source_log, store.path, main_window=args.main_window)
    if 'docx' in fmts:
        outputs['docx']=write_docx(run_dir / f'菲律宾椰子产区天气监测_{run_id}.docx', summary, sections, chart_paths)
    if args.build_site:
        site_path = Path(args.site_dir)
        if not site_path.is_absolute():
            site_path = Path(cfg.root) / site_path
        outputs['site'] = write_site_dashboard(
            site_path, summary, sections, metrics, group_summary, fmetrics, pagasa, official,
            quality, history_recent, source_log, store.path, main_window=args.main_window,
            run_id=run_id, effective_date=iso(eff), requested_end_date=iso(requested_end)
        )
    print('[DONE] Outputs:')
    for k,v in outputs.items(): print(f'  {k}: {v}')
    print(f'  history_store: {store.path}')
    return outputs


def main(argv=None):
    args=build_parser().parse_args(argv)
    run(args)
    return 0
