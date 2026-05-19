from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd

@dataclass
class Config:
    root: Path
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    history_dir: Path
    output_dir: Path
    settings: dict
    production_locations: pd.DataFrame


def load_config(root: str | Path | None = None) -> Config:
    if root is None:
        root = Path(__file__).resolve().parents[1]
    root = Path(root).resolve()
    cfg_dir = root / 'config'
    data_dir = root / 'data'
    cache_dir = data_dir / 'cache'
    history_dir = data_dir / 'history'
    output_dir = root / 'output'
    for p in [data_dir, cache_dir, history_dir, output_dir]:
        p.mkdir(parents=True, exist_ok=True)
    settings_path = cfg_dir / 'settings.json'
    settings = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
    loc_path = cfg_dir / 'production_regions_2025.csv'
    if not loc_path.exists():
        raise FileNotFoundError(f'Missing config file: {loc_path}')
    loc = pd.read_csv(loc_path)
    loc = loc[loc.get('selected_for_monitor', 1) == 1].copy()
    loc['coconut_weight'] = pd.to_numeric(loc['coconut_weight'], errors='coerce').fillna(0)
    total = loc['coconut_weight'].sum()
    loc['weight_norm'] = loc['coconut_weight'] / total if total else 1 / len(loc)
    return Config(root, cfg_dir, data_dir, cache_dir, history_dir, output_dir, settings, loc)
