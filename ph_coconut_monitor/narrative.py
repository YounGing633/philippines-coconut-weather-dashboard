from __future__ import annotations
import numpy as np
import pandas as pd


def _fmt_pct(v):
    return 'NA' if pd.isna(v) else f'{v:.0f}%'

def _fmt_num(v, unit=''):
    return 'NA' if pd.isna(v) else f'{v:.1f}{unit}'


def build_narrative(metrics: pd.DataFrame, group_summary: pd.DataFrame, forecast: pd.DataFrame, pagasa: pd.DataFrame, official: pd.DataFrame, effective_date: str, requested_date: str, main_window: int = 30) -> dict:
    m = metrics[metrics['window_days']==main_window].copy() if not metrics.empty else pd.DataFrame()
    top = m.sort_values(['risk_score','coconut_mature_2025_share_pct'], ascending=False).head(8) if not m.empty else pd.DataFrame()
    prod_weighted_rain = np.nan
    prod_weighted_temp = np.nan
    if not m.empty:
        w = pd.to_numeric(m['coconut_weight'], errors='coerce').fillna(0)
        if w.sum() > 0:
            mask = m['rain_pct_normal'].notna()
            prod_weighted_rain = np.average(m.loc[mask,'rain_pct_normal'], weights=w[mask]) if mask.any() else np.nan
            mask = m['temp_anom_c'].notna()
            prod_weighted_temp = np.average(m.loc[mask,'temp_anom_c'], weights=w[mask]) if mask.any() else np.nan
    high_risk_share = m.loc[m['risk_score']>=4, 'coconut_mature_2025_share_pct'].sum() if not m.empty else 0
    dry_share = m.loc[m['risk_score']>=3, 'coconut_mature_2025_share_pct'].sum() if not m.empty else 0
    pag_drought_share = pagasa.loc[pagasa['pagasa_like_score']>=4, 'coconut_mature_2025_share_pct'].sum() if not pagasa.empty else 0
    # forecast relief for high share
    f16 = forecast[forecast['forecast_window_days']==16].copy() if not forecast.empty else pd.DataFrame()
    relief_text = '未来预测数据暂缺。'
    if not f16.empty:
        fw = pd.to_numeric(f16['coconut_weight'], errors='coerce').fillna(0)
        mask = f16['forecast_rain_to_30d_deficit_pct'].notna()
        relief = np.average(f16.loc[mask,'forecast_rain_to_30d_deficit_pct'], weights=fw[mask]) if mask.any() and fw[mask].sum()>0 else np.nan
        rain = np.average(f16['forecast_rain_mm'].fillna(0), weights=fw) if fw.sum()>0 else np.nan
        if pd.isna(relief):
            relief_text = f'未来16天产区加权预测降雨约{_fmt_num(rain,"mm")}；因前期30天亏缺不明显，弥补压力较小。'
        elif relief >= 80:
            relief_text = f'未来16天预测降雨对30天降雨亏缺的弥补率约{relief:.0f}%，有望明显缓解前期偏干。'
        elif relief >= 30:
            relief_text = f'未来16天预测降雨对30天降雨亏缺的弥补率约{relief:.0f}%，只能部分缓解，仍需观察。'
        else:
            relief_text = f'未来16天预测降雨对30天降雨亏缺的弥补率约{relief:.0f}%，难以弥补前期亏缺。'
    risk_sentence = '对CNO/Copra产量影响暂偏低。'
    if high_risk_share >= 25 and pag_drought_share >= 15:
        risk_sentence = '短期天气风险已经进入可跟踪阶段，若未来2-4周补雨不足，Copra/CNO供应端叙事可能升温。'
    elif high_risk_share >= 15 or pag_drought_share >= 15:
        risk_sentence = '部分主产区出现干旱风险，需要继续跟踪是否从短期降雨不足转化为持续性产量压力。'
    elif dry_share >= 30:
        risk_sentence = '主产区偏干面积不小，但是否影响产量仍取决于后续补雨。'
    one_liner = f'截至{effective_date}，菲律宾椰子产区近{main_window}天加权降雨约为常年{_fmt_pct(prod_weighted_rain)}，干旱/严重干旱风险覆盖约{high_risk_share:.1f}%成熟椰子产量；{relief_text}{risk_sentence}'
    if requested_date != effective_date:
        one_liner = f'【数据实际截止{effective_date}，不是请求日{requested_date}】' + one_liner
    detail_lines = []
    detail_lines.append(f'1、观测有效日期：本次请求截止{requested_date}，程序自动剔除-999/空值后，实际分析截止{effective_date}。')
    detail_lines.append(f'2、产区口径：所有监测点按你提供的菲律宾Coconut Mature 2025分省产量设置，地图标签括号内为全国成熟椰子产量占比。')
    detail_lines.append(f'3、近期天气：近{main_window}天产区加权降雨约为常年{_fmt_pct(prod_weighted_rain)}，温度距平约{_fmt_num(prod_weighted_temp,"℃")}；干旱/严重干旱风险覆盖{high_risk_share:.1f}%产量，偏干及以上覆盖{dry_share:.1f}%产量。')
    if not top.empty:
        detail_lines.append('4、风险较高的主产区：' + '；'.join([f"{r['province']}({r['coconut_mature_2025_share_pct']:.1f}%，{r['risk_label']}，降雨{_fmt_pct(r['rain_pct_normal'])})" for _, r in top.iterrows()]))
    detail_lines.append('5、未来预测：' + relief_text)
    detail_lines.append('6、产量影响判断：' + risk_sentence)
    if not pagasa.empty:
        ptop=pagasa[pagasa['pagasa_like_score']>=3].sort_values(['pagasa_like_score','coconut_mature_2025_share_pct'], ascending=False).head(8)
        if not ptop.empty:
            detail_lines.append('7、PAGASA式月度判断：' + '；'.join([f"{r['province']}({r['coconut_mature_2025_share_pct']:.1f}%，{r['pagasa_like_zh']})" for _, r in ptop.iterrows()]))
    return {'one_liner': one_liner, 'detail': '\n'.join(detail_lines), 'effective_date':effective_date, 'requested_date':requested_date}


def chinese_annotation_sections(summary: dict, metrics: pd.DataFrame, forecast: pd.DataFrame, pagasa: pd.DataFrame, quality: pd.DataFrame, main_window: int = 30) -> list[dict]:
    sections=[]
    sections.append({'title':'先看结论', 'bullets':[summary.get('one_liner','')], 'comment':'这句话可以直接复制到日报或PPT备注里。'})
    sections.append({'title':'如何看降雨百分比', 'bullets':['rain_pct_normal=过去窗口实际累计降雨 / 1981-2020同日历日常年累计降雨。','低于80%通常说明偏干，低于60%需要关注dry spell风险，低于40%接近way below normal。','-999和空值已自动剔除，不会当成0降雨参与计算。']})
    sections.append({'title':'如何看PAGASA式干旱图', 'bullets':['DROUGHT：连续3个月way below normal，属于最强信号。','DRY SPELL：连续3个月below normal或连续2个月way below normal。','DRY CONDITION：连续2个月below normal。','该图是用NASA日度降雨按PAGASA规则自动估算，不等同于PAGASA官方原图；官方结论仍看“官方观点”表。']})
    sections.append({'title':'对CNO/Copra的含义', 'bullets':['短期偏干不一定马上影响产量，关键看是否持续到90天以上并覆盖高产区。','Quezon、Zamboanga、Davao、Northern Mindanao等高占比地区若同时偏干，更容易形成CNO供应端天气叙事。','若未来16天预测降雨无法弥补30天亏缺，风险会从“短期少雨”向“持续干旱”演化。','若CNO供应风险升温，需同步观察PKO/CNO价差与替代需求。']})
    if quality is not None and not quality.empty:
        bad=quality[quality['coverage_pct']<0.75].head(5)
        bullets=[]
        if not bad.empty:
            bullets.append('部分点位有效数据覆盖不足：'+'、'.join(bad['province'].astype(str).tolist())+'。这些点位会在风险判断中标注数据不足。')
        else:
            bullets.append('主要点位有效数据覆盖较好。')
        sections.append({'title':'数据质量提示', 'bullets':bullets})
    return sections
