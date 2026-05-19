from __future__ import annotations
from pathlib import Path
from urllib.parse import urljoin
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

PAGASA_CLIMATE_URL='https://www.pagasa.dost.gov.ph/climate/climate-advisories'


def _extract_pdf_text(path: Path, max_chars=8000) -> str:
    try:
        import fitz
        text=[]
        doc=fitz.open(str(path))
        for i, page in enumerate(doc):
            if i>=5: break
            text.append(page.get_text('text'))
        return re.sub(r'\s+', ' ', '\n'.join(text)).strip()[:max_chars]
    except Exception:
        return ''


def _extract_date(title: str, url: str) -> str:
    s = f'{title} {url}'
    patterns = [
        r'(20\d{2})[-_/ ]?(\d{2})[-_/ ]?(\d{2})',
        r'(\d{2})(\d{2})(20\d{2})',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*(\d{1,2})?\s*(20\d{2})',
        r'(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s*(20\d{2})',
    ]
    month_map={'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}
    for pat in patterns[:2]:
        m=re.search(pat, s, re.I)
        if m:
            if pat.startswith('(20'):
                y,mo,d=m.groups(); return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
            else:
                mo,d,y=m.groups(); return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    m=re.search(patterns[2], s, re.I)
    if m:
        mo, d, y = m.groups(); d = d or '01'
        return f'{int(y):04d}-{month_map[mo[:3].lower()]:02d}-{int(d):02d}'
    m=re.search(patterns[3], s, re.I)
    if m:
        d, mo, y = m.groups()
        return f'{int(y):04d}-{month_map[mo[:3].lower()]:02d}-{int(d):02d}'
    return ''


def _key_sentences(text: str, limit: int = 5) -> list[str]:
    if not text:
        return []
    sents = re.split(r'(?<=[.!?])\s+', text)
    kws = ['drought','dry spell','dry condition','below normal','way below normal','rainfall','el niño','el nino','enso','outlook','forecast','luzon','visayas','mindanao']
    scored=[]
    for sent in sents:
        low=sent.lower()
        score=sum(1 for k in kws if k in low)
        if score>0 and 30 <= len(sent) <= 360:
            scored.append((score, sent.strip()))
    # Keep original-ish order among relevant sentences after selecting high score.
    chosen=[]
    for _,sent in sorted(scored, key=lambda x:-x[0])[:limit*2]:
        if sent not in chosen:
            chosen.append(sent)
        if len(chosen)>=limit:
            break
    return chosen


def _make_zh_core(text: str) -> str:
    if not text:
        return '未能提取到PDF正文；请打开源文件核对受影响省份、降雨展望和干旱评估。'
    low=text.lower()
    bullets=[]
    # try to preserve useful quantitative info
    m=re.search(r'(\d+)\s+(?:province|provinces|areas?)\s+[^.]{0,80}(drought|dry spell|dry condition)', text, re.I)
    if m:
        bullets.append(f'文件提到 {m.group(1)} 个省/区域涉及 {m.group(2)}，需核对是否落在椰子主产区。')
    m2=re.search(r'(drought|dry spell|dry condition)[^.]{0,80}(\d+)\s+(?:province|provinces|areas?)', text, re.I)
    if m2:
        bullets.append(f'文件提到 {m2.group(2)} 个省/区域涉及 {m2.group(1)}，属于官方干旱信号。')
    if 'way below normal' in low:
        bullets.append('出现 way below normal rainfall 表述，说明部分地区降雨显著低于常年，是Drought/Dry spell判断中的强信号。')
    elif 'below normal' in low:
        bullets.append('出现 below normal rainfall 表述，说明部分地区降雨低于常年，需要关注是否连续化。')
    if 'drought' in low or 'dry spell' in low or 'dry condition' in low:
        bullets.append('官方文件涉及 dry condition / dry spell / drought，请优先核对省份名单与椰子产区重合度。')
    if 'outlook' in low or 'forecast' in low:
        bullets.append('文件包含未来气候展望，可与本看板未来7/16天预测一起判断是否缓解。')
    if 'el niño' in low or 'el nino' in low or 'enso' in low:
        bullets.append('文件涉及 ENSO / El Niño 背景，可能提高未来阶段性偏干概率。')
    if not bullets:
        ks=_key_sentences(text,3)
        if ks:
            bullets.append('核心相关信息：' + ' / '.join(ks[:2]))
        else:
            bullets.append('已抓取官方文件，建议打开源文件核对省份列表和未来展望。')
    return '；'.join(dict.fromkeys(bullets))


def download_pagasa_official(out_dir: str | Path, limit: int = 20, force: bool = False) -> pd.DataFrame:
    out_dir=Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    rows=[]
    try:
        html=requests.get(PAGASA_CLIMATE_URL, timeout=60).text
        soup=BeautifulSoup(html, 'html.parser')
        links=[]
        for a in soup.find_all('a', href=True):
            href=urljoin(PAGASA_CLIMATE_URL, a['href'])
            txt=a.get_text(' ', strip=True)
            if '.pdf' in href.lower() or 'pubfiles.pagasa' in href.lower():
                comb=(txt+' '+href).lower()
                if any(k in comb for k in ['drought','dryspell','dry spell','seasonal','monthlyclimate','climateassessment','mca','enso','rainfall']):
                    links.append((txt or href.split('/')[-1], href))
        seen=set()
        for title, url in links[:limit*2]:
            if url in seen: continue
            seen.add(url)
            fname=re.sub(r'[^A-Za-z0-9_.-]+','_', url.split('/')[-1]) or 'pagasa.pdf'
            path=out_dir/fname
            downloaded=False
            if path.exists() and not force:
                downloaded=True
            else:
                try:
                    r=requests.get(url, timeout=120)
                    r.raise_for_status()
                    if len(r.content)>1000:
                        path.write_bytes(r.content)
                        downloaded=True
                except Exception as e:
                    print(f'[WARN] Failed downloading PAGASA file {url}: {e}')
            text=_extract_pdf_text(path) if downloaded and path.exists() else ''
            sents=_key_sentences(text, limit=4)
            rows.append({
                'published_date': _extract_date(title, url),
                'title':title,
                'url':url,
                'local_file':str(path) if path.exists() else '',
                'downloaded':downloaded,
                'english_core_text':' '.join(sents)[:1000] if sents else text[:800],
                '中文核心观点':_make_zh_core(text),
                'source_type':'PAGASA official'
            })
        df=pd.DataFrame(rows)
        if not df.empty:
            # Latest first; if date missing, keep after dated files.
            df['_sort']=pd.to_datetime(df['published_date'], errors='coerce')
            df=df.sort_values('_sort', ascending=False, na_position='last').drop(columns=['_sort']).head(limit)
        return df
    except Exception as e:
        print(f'[WARN] PAGASA climate page failed: {e}')
        return pd.DataFrame(rows)
