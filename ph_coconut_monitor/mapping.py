from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

COLORS = {
    'DROUGHT':'#b30000',
    'DRY SPELL':'#f59e0b',
    'DRY CONDITION':'#fff176',
    'DATA INSUFFICIENT':'#bdbdbd',
    'Not affected':'#ffffff',
    '严重干旱风险':'#b30000',
    '干旱风险':'#e34a33',
    '明显偏干':'#f59e0b',
    '略偏干':'#fff176',
    '高温关注':'#fed976',
    '正常/无明显干旱':'#d9f0a3',
    '数据不足':'#bdbdbd',
}

def _setup_map(ax):
    ax.set_xlim(116, 128)
    ax.set_ylim(4, 21.5)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.grid(True, alpha=.2, linestyle='--')
    ax.set_facecolor('#f8fbff')
    # rough labels to orient the map
    ax.text(121.0, 16.5, 'LUZON', fontsize=14, weight='bold', color='#94a3b8', ha='center')
    ax.text(123.6, 11.1, 'VISAYAS', fontsize=14, weight='bold', color='#94a3b8', ha='center')
    ax.text(124.5, 7.4, 'MINDANAO', fontsize=14, weight='bold', color='#94a3b8', ha='center')


def make_drought_map(pagasa: pd.DataFrame, out_path: str | Path, title: str = '') -> Path:
    out=Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10.5, 11), dpi=180)
    _setup_map(ax)
    if not pagasa.empty:
        df=pagasa.copy()
        sizes=40 + np.sqrt(pd.to_numeric(df['coconut_mature_2025_share_pct'], errors='coerce').fillna(0))*180
        colors=[COLORS.get(x, '#bdbdbd') for x in df['pagasa_like_assessment']]
        ax.scatter(df['lon'], df['lat'], s=sizes, c=colors, edgecolor='#333333', linewidth=.6, alpha=.95)
        # label largest/highest-risk provinces
        lab=df.sort_values(['pagasa_like_score','coconut_mature_2025_share_pct'], ascending=False).head(18)
        for _, r in lab.iterrows():
            ax.text(r['lon']+.08, r['lat']+.08, f"{r['province']}\n{r['coconut_mature_2025_share_pct']:.1f}%", fontsize=7.5, ha='left', va='bottom')
    ax.set_title(title or 'Philippines Coconut Areas: PAGASA-like Dry Condition / Dry Spell / Drought Assessment\n菲律宾椰子产区：PAGASA口径近似干旱评估', fontsize=13, weight='bold')
    handles=[]
    for k in ['DROUGHT','DRY SPELL','DRY CONDITION','Not affected','DATA INSUFFICIENT']:
        handles.append(plt.Line2D([0],[0], marker='o', color='w', markerfacecolor=COLORS[k], markeredgecolor='#333', markersize=9, label=k))
    ax.legend(handles=handles, loc='lower left', frameon=True, fontsize=9)
    fig.tight_layout()
    fig.savefig(out, bbox_inches='tight')
    plt.close(fig)
    return out


def make_market_risk_map(metrics: pd.DataFrame, out_path: str | Path, window_days: int = 30) -> Path:
    out=Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax=plt.subplots(figsize=(10.5, 11), dpi=180)
    _setup_map(ax)
    df=metrics[metrics['window_days']==window_days].copy() if not metrics.empty else pd.DataFrame()
    if not df.empty:
        sizes=40 + np.sqrt(pd.to_numeric(df['coconut_mature_2025_share_pct'], errors='coerce').fillna(0))*180
        colors=[COLORS.get(x, '#bdbdbd') for x in df['risk_label']]
        ax.scatter(df['lon'], df['lat'], s=sizes, c=colors, edgecolor='#333333', linewidth=.6, alpha=.95)
        lab=df.sort_values(['risk_score','coconut_mature_2025_share_pct'], ascending=False).head(18)
        for _, r in lab.iterrows():
            pct = r['rain_pct_normal'] if not pd.isna(r['rain_pct_normal']) else np.nan
            txt=f"{r['province']}\n{r['coconut_mature_2025_share_pct']:.1f}% | {pct:.0f}%" if not pd.isna(pct) else f"{r['province']}\n{r['coconut_mature_2025_share_pct']:.1f}%"
            ax.text(r['lon']+.08, r['lat']+.08, txt, fontsize=7.5, ha='left', va='bottom')
    ax.set_title(f'Latest {window_days}d Rainfall Risk Map for CNO/Copra Areas\n近{window_days}天菲律宾椰子产区降雨风险地图（点大小=成熟椰子产量占比）', fontsize=13, weight='bold')
    handles=[]
    for k in ['严重干旱风险','干旱风险','明显偏干','略偏干','正常/无明显干旱','数据不足']:
        handles.append(plt.Line2D([0],[0], marker='o', color='w', markerfacecolor=COLORS[k], markeredgecolor='#333', markersize=9, label=k))
    ax.legend(handles=handles, loc='lower left', frameon=True, fontsize=9)
    fig.tight_layout(); fig.savefig(out,bbox_inches='tight'); plt.close(fig); return out


def make_trend_chart(metrics: pd.DataFrame, out_path: str | Path, window_days: int = 30, top_n: int = 15) -> Path:
    out=Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    df=metrics[metrics['window_days']==window_days].copy() if not metrics.empty else pd.DataFrame()
    if df.empty:
        fig, ax=plt.subplots(figsize=(10,5), dpi=160); ax.text(.5,.5,'No data',ha='center'); fig.savefig(out); plt.close(fig); return out
    df=df.sort_values('coconut_mature_2025_share_pct', ascending=False).head(top_n)
    labels=[f"{p} ({s:.1f}%)" for p,s in zip(df['province'], df['coconut_mature_2025_share_pct'])]
    fig, ax=plt.subplots(figsize=(11,6), dpi=170)
    y=np.arange(len(df))
    ax.barh(y, df['rain_pct_normal'])
    ax.axvline(80, color='#f59e0b', linestyle='--', linewidth=1)
    ax.axvline(60, color='#e34a33', linestyle='--', linewidth=1)
    ax.axvline(40, color='#b30000', linestyle='--', linewidth=1)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Rainfall % of 1981-2020 normal / 降雨占常年比例')
    ax.set_title(f'Top Coconut Provinces: {window_days}d Rainfall vs Normal\n菲律宾椰子主产区近{window_days}天降雨 vs 常年', weight='bold')
    for i, v in enumerate(df['rain_pct_normal']):
        if not pd.isna(v): ax.text(v+1, i, f'{v:.0f}%', va='center', fontsize=8)
    fig.tight_layout(); fig.savefig(out,bbox_inches='tight'); plt.close(fig); return out


def make_forecast_relief_chart(forecast_metrics: pd.DataFrame, out_path: str | Path, window_days: int = 16, top_n: int = 15) -> Path:
    out=Path(out_path); out.parent.mkdir(parents=True, exist_ok=True)
    df=forecast_metrics[forecast_metrics['forecast_window_days']==window_days].copy() if not forecast_metrics.empty else pd.DataFrame()
    if df.empty:
        fig, ax=plt.subplots(figsize=(10,5), dpi=160); ax.text(.5,.5,'No forecast data',ha='center'); fig.savefig(out); plt.close(fig); return out
    df=df.sort_values('coconut_mature_2025_share_pct', ascending=False).head(top_n)
    labels=[f"{p} ({s:.1f}%)" for p,s in zip(df['province'], df['coconut_mature_2025_share_pct'])]
    fig, ax=plt.subplots(figsize=(11,6), dpi=170)
    y=np.arange(len(df))
    ax.barh(y, df['forecast_rain_mm'])
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel(f'Forecast rainfall next {window_days}d / 未来{window_days}天预测降雨(mm)')
    ax.set_title(f'Forecast Rainfall: Can it Offset Recent Deficit?\n未来降雨是否可能弥补前期亏缺', weight='bold')
    for i, (v, lab) in enumerate(zip(df['forecast_rain_mm'], df['relief_label'])):
        if not pd.isna(v): ax.text(v+1, i, f'{v:.0f}mm | {lab}', va='center', fontsize=8)
    fig.tight_layout(); fig.savefig(out,bbox_inches='tight'); plt.close(fig); return out
