from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
import numpy as np
import pandas as pd
from .utils import iso

@dataclass
class RiskThresholds:
    normal: float = 90
    watch: float = 80
    dry: float = 60
    drought: float = 40


def _prep_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out['date'] = pd.to_datetime(out['date'])
    for c in ['PRECTOTCORR','T2M','T2M_MAX','T2M_MIN','RH2M','WS10M','ALLSKY_SFC_SW_DWN']:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors='coerce')
    out['doy'] = out['date'].dt.dayofyear
    return out


def make_daily_climatology(history: pd.DataFrame, baseline_start: str, baseline_end: str) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()
    h = _prep_daily(history)
    mask = (h['date'] >= pd.Timestamp(baseline_start)) & (h['date'] <= pd.Timestamp(baseline_end))
    h = h.loc[mask].copy()
    agg = {}
    for c in ['PRECTOTCORR','T2M','T2M_MAX','T2M_MIN','RH2M']:
        if c in h.columns:
            agg[c] = 'mean'
    clim = h.groupby(['location_id','doy'], as_index=False).agg(agg)
    clim = clim.rename(columns={c: c + '_clim' for c in agg.keys()})
    return clim


def effective_observation_date(current: pd.DataFrame, locations: pd.DataFrame, requested_end: date, min_weight_coverage: float = 0.70) -> date | None:
    if current.empty:
        return None
    d = _prep_daily(current)
    loc = locations[['location_id','weight_norm']].copy()
    d = d.merge(loc, on='location_id', how='left')
    d['valid_rain'] = d['PRECTOTCORR'].notna() if 'PRECTOTCORR' in d.columns else False
    cover = d[d['date'] <= pd.Timestamp(requested_end)].groupby('date').apply(lambda x: x.loc[x['valid_rain'], 'weight_norm'].sum(), include_groups=False)
    cover = cover[cover >= min_weight_coverage]
    if cover.empty:
        return None
    return cover.index.max().date()


def _risk_label(pct: float | None, heat_days: int, coverage_pct: float, threshold: RiskThresholds) -> tuple[int, str, str]:
    if pd.isna(pct) or coverage_pct < 0.75:
        return 0, '数据不足', '有效数据覆盖不足，暂不判定'
    if pct < threshold.drought:
        return 5, '严重干旱风险', '累计降雨低于常年40%，接近/达到PAGASA way below normal口径'
    if pct < threshold.dry:
        return 4, '干旱风险', '累计降雨低于常年60%，需警惕dry spell/drought演化'
    if pct < threshold.watch:
        return 3, '明显偏干', '累计降雨低于常年80%，天气风险上升'
    if pct < threshold.normal:
        return 2, '略偏干', '累计降雨略低于常年，需观察未来补雨'
    if heat_days >= 5:
        return 2, '高温关注', '降雨尚可但高温天数偏多'
    return 1, '正常/无明显干旱', '累计降雨接近或高于常年'


def window_metrics(current: pd.DataFrame, clim: pd.DataFrame, locations: pd.DataFrame, effective_end: date, lookbacks: list[int], thresholds: RiskThresholds, min_coverage_pct: float = 0.75) -> pd.DataFrame:
    d = _prep_daily(current)
    if d.empty:
        return pd.DataFrame()
    rows = []
    d = d[d['date'] <= pd.Timestamp(effective_end)].copy()
    for _, loc in locations.iterrows():
        lid = loc['location_id']
        ld = d[d['location_id'] == lid].copy()
        for win in lookbacks:
            start = pd.Timestamp(effective_end - timedelta(days=win-1))
            sub = ld[(ld['date'] >= start) & (ld['date'] <= pd.Timestamp(effective_end))].copy()
            valid_rain = sub[sub['PRECTOTCORR'].notna()] if 'PRECTOTCORR' in sub.columns else sub.iloc[0:0]
            rain_valid_days = int(valid_rain.shape[0])
            coverage_pct = rain_valid_days / win if win else np.nan
            rain_sum = valid_rain['PRECTOTCORR'].sum(min_count=1) if rain_valid_days else np.nan
            normal_sum = np.nan
            temp_anom = np.nan
            if clim is not None and not clim.empty and not valid_rain.empty:
                cc = valid_rain[['location_id','date','doy','PRECTOTCORR']].merge(clim, on=['location_id','doy'], how='left')
                normal_sum = cc['PRECTOTCORR_clim'].sum(min_count=1) if 'PRECTOTCORR_clim' in cc.columns else np.nan
            rain_pct = (rain_sum / normal_sum * 100) if normal_sum and not pd.isna(normal_sum) and normal_sum != 0 else np.nan
            rain_deficit = max(normal_sum - rain_sum, 0) if not pd.isna(rain_sum) and not pd.isna(normal_sum) else np.nan
            temp_valid = sub[sub.get('T2M', pd.Series(index=sub.index, dtype=float)).notna()] if 'T2M' in sub.columns else sub.iloc[0:0]
            tmean = temp_valid['T2M'].mean() if not temp_valid.empty else np.nan
            tmax_mean = sub['T2M_MAX'].mean() if 'T2M_MAX' in sub.columns else np.nan
            heat_days = int((sub.get('T2M_MAX', pd.Series(index=sub.index, dtype=float)) >= 35).sum()) if 'T2M_MAX' in sub.columns else 0
            extreme_heat_days = int((sub.get('T2M_MAX', pd.Series(index=sub.index, dtype=float)) >= 38).sum()) if 'T2M_MAX' in sub.columns else 0
            if clim is not None and not clim.empty and not temp_valid.empty:
                tc = temp_valid[['location_id','date','doy','T2M']].merge(clim, on=['location_id','doy'], how='left')
                if 'T2M_clim' in tc.columns:
                    temp_anom = (tc['T2M'] - tc['T2M_clim']).mean()
            risk_score, risk_label, risk_note = _risk_label(rain_pct, heat_days, coverage_pct, thresholds)
            # improvement: compare last half vs previous half rainfall pct of normal within the window
            trend_label = '暂无判断'
            if win >= 14:
                half = win // 2
                recent = sub[sub['date'] > pd.Timestamp(effective_end - timedelta(days=half))]
                prev = sub[(sub['date'] <= pd.Timestamp(effective_end - timedelta(days=half))) & (sub['date'] > pd.Timestamp(effective_end - timedelta(days=win)))]
                r1 = recent['PRECTOTCORR'].sum(min_count=1)
                r0 = prev['PRECTOTCORR'].sum(min_count=1)
                if not pd.isna(r1) and not pd.isna(r0):
                    if r1 >= r0 * 1.3 and r1 >= 5:
                        trend_label = '近期降雨好转'
                    elif r1 <= r0 * 0.7:
                        trend_label = '近期继续转干'
                    else:
                        trend_label = '近期变化不大'
            rows.append({
                **loc.to_dict(),
                'window_days': win,
                'start_date': iso(start.date()),
                'end_date': iso(effective_end),
                'rain_sum_mm': rain_sum,
                'rain_normal_mm': normal_sum,
                'rain_pct_normal': rain_pct,
                'rain_deficit_mm': rain_deficit,
                'rain_valid_days': rain_valid_days,
                'expected_days': win,
                'coverage_pct': coverage_pct,
                'temp_mean_c': tmean,
                'tmax_mean_c': tmax_mean,
                'temp_anom_c': temp_anom,
                'heat_days_ge_35c': heat_days,
                'extreme_heat_days_ge_38c': extreme_heat_days,
                'risk_score': risk_score,
                'risk_label': risk_label,
                'risk_note': risk_note,
                'trend_label': trend_label,
            })
    return pd.DataFrame(rows)


def weighted_group_summary(metrics: pd.DataFrame, group_cols: list[str], main_window: int | None = None) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame()
    df = metrics.copy()
    if main_window is not None:
        df = df[df['window_days'] == main_window].copy()
    rows=[]
    for keys, g in df.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys=(keys,)
        w = pd.to_numeric(g['coconut_weight'], errors='coerce').fillna(0)
        if w.sum() == 0:
            w = pd.Series(1, index=g.index)
        def wavg(col):
            vals=pd.to_numeric(g[col], errors='coerce')
            mask=vals.notna()
            return np.average(vals[mask], weights=w[mask]) if mask.any() and w[mask].sum()!=0 else np.nan
        out={col: val for col,val in zip(group_cols, keys)}
        out.update({
            'window_days': int(g['window_days'].iloc[0]) if 'window_days' in g.columns else main_window,
            'production_share_pct': g['coconut_husk_2025_share_pct'].sum() if 'coconut_husk_2025_share_pct' in g.columns else g['coconut_mature_2025_share_pct'].sum(),
            'rain_pct_normal_wavg': wavg('rain_pct_normal'),
            'rain_deficit_mm_wavg': wavg('rain_deficit_mm'),
            'temp_anom_c_wavg': wavg('temp_anom_c'),
            'heat_days_ge_35c_wavg': wavg('heat_days_ge_35c'),
            'max_risk_score': int(pd.to_numeric(g['risk_score'], errors='coerce').max()),
            'top_risk_provinces': '、'.join(g.sort_values(['risk_score','coconut_husk_2025_share_pct' if 'coconut_husk_2025_share_pct' in g.columns else 'coconut_mature_2025_share_pct'], ascending=False).head(5)['map_label'].astype(str).tolist())
        })
        rows.append(out)
    return pd.DataFrame(rows).sort_values(['max_risk_score','production_share_pct'], ascending=False)


def pagasa_like_assessment(current: pd.DataFrame, clim: pd.DataFrame, locations: pd.DataFrame, effective_end: date, months_back: int = 4, min_month_coverage: float = 0.75) -> pd.DataFrame:
    if current.empty or clim.empty:
        return pd.DataFrame()
    d = _prep_daily(current)
    # Use complete months. If current month incomplete, end at previous month end.
    eff = pd.Timestamp(effective_end)
    last_month_end = (eff.replace(day=1) - pd.Timedelta(days=1)) if eff.day < eff.days_in_month else eff
    month_starts = []
    cur = last_month_end.replace(day=1)
    for _ in range(months_back):
        month_starts.append(cur)
        cur = (cur - pd.Timedelta(days=1)).replace(day=1)
    starts = sorted(month_starts)
    rows=[]
    for _, loc in locations.iterrows():
        lid=loc['location_id']
        monthly=[]
        for ms in starts:
            me = (ms + pd.offsets.MonthEnd(0))
            sub=d[(d['location_id']==lid)&(d['date']>=ms)&(d['date']<=me)].copy()
            expected=int((me-ms).days)+1
            valid=sub[sub['PRECTOTCORR'].notna()]
            coverage=len(valid)/expected if expected else 0
            actual=valid['PRECTOTCORR'].sum(min_count=1) if not valid.empty else np.nan
            normal=np.nan
            if not valid.empty:
                cc=valid[['location_id','date','doy','PRECTOTCORR']].merge(clim,on=['location_id','doy'],how='left')
                normal=cc['PRECTOTCORR_clim'].sum(min_count=1)
            pct=actual/normal*100 if normal and not pd.isna(normal) else np.nan
            if coverage < min_month_coverage or pd.isna(pct):
                cat='insufficient'
            elif pct < 40:
                cat='way_below_normal'
            elif pct < 80:
                cat='below_normal'
            else:
                cat='normal_or_above'
            monthly.append({'month':ms.strftime('%Y-%m'), 'actual_mm':actual, 'normal_mm':normal, 'pct_normal':pct, 'category':cat, 'coverage_pct':coverage})
        cats=[m['category'] for m in monthly]
        # precedence: drought > dry spell > dry condition.
        assessment='Not affected'
        zh='未受影响'
        score=1
        if len(cats)>=3 and all(c=='way_below_normal' for c in cats[-3:]):
            assessment='DROUGHT'; zh='干旱'; score=5
        elif (len(cats)>=3 and all(c in ['below_normal','way_below_normal'] for c in cats[-3:])) or (len(cats)>=2 and all(c=='way_below_normal' for c in cats[-2:])):
            assessment='DRY SPELL'; zh='旱期'; score=4
        elif len(cats)>=2 and all(c in ['below_normal','way_below_normal'] for c in cats[-2:]):
            assessment='DRY CONDITION'; zh='偏干状态'; score=3
        if any(c=='insufficient' for c in cats[-3:]):
            assessment = assessment if score>1 else 'DATA INSUFFICIENT'
            zh = zh if score>1 else '数据不足'
        latest3='; '.join([f"{m['month']} {m['pct_normal']:.0f}%" if not pd.isna(m['pct_normal']) else f"{m['month']} NA" for m in monthly[-3:]])
        rows.append({**loc.to_dict(), 'pagasa_like_assessment':assessment, 'pagasa_like_zh':zh, 'pagasa_like_score':score, 'monthly_pct_latest3':latest3, 'months_used': ','.join([m['month'] for m in monthly]), 'monthly_detail': str(monthly)})
    return pd.DataFrame(rows).sort_values(['pagasa_like_score','coconut_husk_2025_share_pct' if 'coconut_husk_2025_share_pct' in pd.DataFrame(rows).columns else 'coconut_mature_2025_share_pct'], ascending=False)


def forecast_metrics(forecast: pd.DataFrame, metrics: pd.DataFrame, locations: pd.DataFrame, windows=(7,16), main_window=30) -> pd.DataFrame:
    if forecast.empty:
        return pd.DataFrame()
    fc=forecast.copy()
    fc['date']=pd.to_datetime(fc['date'])
    base=metrics[metrics['window_days']==main_window][['location_id','rain_deficit_mm','rain_pct_normal','risk_label']].copy() if not metrics.empty else pd.DataFrame(columns=['location_id'])
    rows=[]
    for _, loc in locations.iterrows():
        lid=loc['location_id']
        sub=fc[fc['location_id']==lid].sort_values('date')
        base_row=base[base['location_id']==lid].iloc[0].to_dict() if not base[base['location_id']==lid].empty else {}
        for win in windows:
            s=sub.head(win)
            frain=s['forecast_rain_mm'].sum(min_count=1) if 'forecast_rain_mm' in s.columns else np.nan
            ftmax=s['forecast_tmax_c'].mean() if 'forecast_tmax_c' in s.columns else np.nan
            deficit=base_row.get('rain_deficit_mm', np.nan)
            relief_pct=frain/deficit*100 if deficit and not pd.isna(deficit) and deficit>0 else np.nan
            if pd.isna(relief_pct):
                relief='无明显亏缺/无需弥补'
            elif relief_pct>=80:
                relief='未来降雨有望大幅弥补'
            elif relief_pct>=30:
                relief='未来降雨可部分缓解'
            else:
                relief='未来降雨难以弥补前期亏缺'
            rows.append({**loc.to_dict(), 'forecast_window_days':win, 'forecast_rain_mm':frain, 'forecast_tmax_mean_c':ftmax, 'forecast_rain_to_30d_deficit_pct':relief_pct, 'relief_label':relief, 'base_30d_rain_pct_normal':base_row.get('rain_pct_normal', np.nan), 'base_30d_risk_label':base_row.get('risk_label','')})
    return pd.DataFrame(rows)


def data_quality(current: pd.DataFrame, locations: pd.DataFrame, requested_end: date, effective_end: date, lookbacks: list[int]) -> pd.DataFrame:
    if current.empty:
        return pd.DataFrame()
    d=_prep_daily(current)
    rows=[]
    for _, loc in locations.iterrows():
        sub=d[d['location_id']==loc['location_id']]
        latest=sub.loc[sub['PRECTOTCORR'].notna(), 'date'].max()
        for win in lookbacks:
            start=pd.Timestamp(effective_end - timedelta(days=win-1))
            w=sub[(sub['date']>=start)&(sub['date']<=pd.Timestamp(effective_end))]
            valid=int(w['PRECTOTCORR'].notna().sum()) if 'PRECTOTCORR' in w.columns else 0
            rows.append({**loc.to_dict(), 'requested_end_date':iso(requested_end), 'effective_observation_end_date':iso(effective_end), 'latest_valid_date_this_location':iso(latest) if pd.notna(latest) else '', 'window_days':win, 'valid_rain_days':valid, 'expected_days':win, 'coverage_pct':valid/win if win else np.nan})
    return pd.DataFrame(rows)
