from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from datetime import date, timedelta
import time
import json
import numpy as np
import pandas as pd
import requests
from .utils import ensure_dir, iso, daterange_chunks

MISSING_VALUES = {-999, -999.0, -9999, -9999.0}


def clean_missing(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if c in ['date', 'location_id', 'source', 'parameter']:
            continue
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].replace(list(MISSING_VALUES), np.nan)
    return out

@dataclass
class NASAClient:
    cache_dir: Path
    parameters: list[str]
    chunk_years: int = 5
    sleep_sec: float = 0.15
    retries: int = 4

    def __post_init__(self):
        self.cache_dir = ensure_dir(Path(self.cache_dir) / 'nasa_power')

    def _cache_path(self, location_id: str, start: date, end: date) -> Path:
        return self.cache_dir / f'{location_id}_{iso(start).replace("-","")}_{iso(end).replace("-","")}.csv'

    def fetch_point(self, location_id: str, lat: float, lon: float, start: date, end: date, force: bool = False) -> pd.DataFrame:
        cache_path = self._cache_path(location_id, start, end)
        if cache_path.exists() and not force:
            return clean_missing(pd.read_csv(cache_path, parse_dates=['date']))
        url = 'https://power.larc.nasa.gov/api/temporal/daily/point'
        params = {
            'latitude': float(lat),
            'longitude': float(lon),
            'start': iso(start).replace('-', ''),
            'end': iso(end).replace('-', ''),
            'community': 'AG',
            'parameters': ','.join(self.parameters),
            'format': 'JSON',
        }
        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                r = requests.get(url, params=params, timeout=90)
                r.raise_for_status()
                js = r.json()
                pdata = js.get('properties', {}).get('parameter', {})
                if not pdata:
                    raise ValueError('NASA POWER returned no parameter data')
                df = pd.DataFrame(pdata)
                df.index.name = 'date'
                df = df.reset_index()
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d', errors='coerce')
                df.insert(1, 'location_id', location_id)
                df['source'] = 'NASA_POWER_DAILY'
                df = clean_missing(df)
                df.to_csv(cache_path, index=False, encoding='utf-8-sig')
                time.sleep(self.sleep_sec)
                return df
            except Exception as e:
                last_err = e
                time.sleep(1.5 * attempt)
        print(f'[WARN] NASA failed for {location_id} {start}..{end}: {last_err}')
        return pd.DataFrame(columns=['date', 'location_id'] + self.parameters + ['source'])

    def fetch_locations(self, locations: pd.DataFrame, start: date, end: date, force: bool = False) -> pd.DataFrame:
        frames = []
        total = len(locations)
        for idx, row in locations.reset_index(drop=True).iterrows():
            lid = str(row['location_id'])
            print(f'[NASA] {idx + 1}/{total} {lid} {start}..{end}')
            loc_frames = []
            for s, e in daterange_chunks(start, end, self.chunk_years):
                loc_frames.append(self.fetch_point(lid, row['lat'], row['lon'], s, e, force=force))
            if loc_frames:
                frames.append(pd.concat(loc_frames, ignore_index=True))
        if not frames:
            return pd.DataFrame(columns=['date', 'location_id'] + self.parameters + ['source'])
        out = pd.concat(frames, ignore_index=True)
        out = out.drop_duplicates(['location_id', 'date']).sort_values(['location_id', 'date'])
        return clean_missing(out)

@dataclass
class HistoryStore:
    history_dir: Path
    filename: str = 'nasa_daily_all_coconut_regions.csv.gz'

    def __post_init__(self):
        self.history_dir = ensure_dir(self.history_dir)
        self.path = self.history_dir / self.filename
        self.manifest_path = self.history_dir / 'history_manifest.csv'

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.path, parse_dates=['date'])
        return clean_missing(df)

    def save(self, df: pd.DataFrame) -> Path:
        if df.empty:
            return self.path
        out = clean_missing(df).drop_duplicates(['location_id', 'date']).sort_values(['location_id', 'date'])
        out.to_csv(self.path, index=False, encoding='utf-8-sig', compression='gzip')
        manifest = out.groupby('location_id').agg(start_date=('date', 'min'), end_date=('date', 'max'), rows=('date', 'count')).reset_index()
        manifest.to_csv(self.manifest_path, index=False, encoding='utf-8-sig')
        return self.path

    def update(self, client: NASAClient, locations: pd.DataFrame, start: date, end: date, force: bool = False) -> pd.DataFrame:
        if force or not self.path.exists():
            print(f'[HISTORY] Build full history store: {start}..{end}')
            df_new = client.fetch_locations(locations, start, end, force=force)
            self.save(df_new)
            return df_new
        df_old = self.load()
        if df_old.empty:
            return self.update(client, locations, start, end, force=True)
        # Fetch missing tail if needed. If user later asks earlier date, rebuild from start.
        old_min = df_old['date'].min().date()
        old_max = df_old['date'].max().date()
        frames = [df_old]
        if start < old_min:
            print(f'[HISTORY] Extending backward: {start}..{old_min - timedelta(days=1)}')
            frames.append(client.fetch_locations(locations, start, old_min - timedelta(days=1), force=False))
        if end > old_max:
            print(f'[HISTORY] Extending forward: {old_max + timedelta(days=1)}..{end}')
            frames.append(client.fetch_locations(locations, old_max + timedelta(days=1), end, force=False))
        df = pd.concat(frames, ignore_index=True).drop_duplicates(['location_id', 'date']).sort_values(['location_id', 'date'])
        self.save(df)
        return clean_missing(df)

@dataclass
class OpenMeteoClient:
    cache_dir: Path
    retries: int = 3

    def __post_init__(self):
        self.cache_dir = ensure_dir(Path(self.cache_dir) / 'open_meteo')

    def fetch_locations(self, locations: pd.DataFrame, forecast_days: int = 16, force: bool = False) -> pd.DataFrame:
        run_key = pd.Timestamp.utcnow().strftime('%Y%m%d')
        cache = self.cache_dir / f'forecast_{run_key}_{forecast_days}d.csv'
        if cache.exists() and not force:
            return pd.read_csv(cache, parse_dates=['date'])
        frames = []
        for idx, row in locations.reset_index(drop=True).iterrows():
            lid = str(row['location_id'])
            print(f'[Forecast] {idx + 1}/{len(locations)} {lid}')
            url = 'https://api.open-meteo.com/v1/forecast'
            params = {
                'latitude': float(row['lat']),
                'longitude': float(row['lon']),
                'daily': 'precipitation_sum,temperature_2m_max,temperature_2m_min,temperature_2m_mean',
                'forecast_days': max(1, min(int(forecast_days), 16)),
                'timezone': 'Asia/Manila',
            }
            last_err = None
            for attempt in range(1, self.retries + 1):
                try:
                    r = requests.get(url, params=params, timeout=45)
                    r.raise_for_status()
                    js = r.json()
                    daily = js.get('daily', {})
                    if not daily or 'time' not in daily:
                        raise ValueError('Open-Meteo returned no daily data')
                    df = pd.DataFrame({
                        'date': pd.to_datetime(daily['time']),
                        'location_id': lid,
                        'forecast_rain_mm': daily.get('precipitation_sum'),
                        'forecast_tmax_c': daily.get('temperature_2m_max'),
                        'forecast_tmin_c': daily.get('temperature_2m_min'),
                        'forecast_tmean_c': daily.get('temperature_2m_mean'),
                    })
                    frames.append(df)
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(1.5 * attempt)
            if last_err and (not frames or frames[-1].get('location_id', pd.Series([None])).iloc[0] != lid):
                print(f'[WARN] Open-Meteo failed for {lid}: {last_err}')
        out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not out.empty:
            out.to_csv(cache, index=False, encoding='utf-8-sig')
        return out
