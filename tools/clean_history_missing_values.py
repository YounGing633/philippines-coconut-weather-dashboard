from pathlib import Path
import pandas as pd
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
paths = list((ROOT/'data'/'history').glob('*.csv*')) + list((ROOT/'data'/'cache').glob('**/*.csv'))
for p in paths:
    try:
        kwargs = {'compression':'gzip'} if p.suffix == '.gz' else {}
        df = pd.read_csv(p, **kwargs)
        before = int(df.isin([-999,-999.0,-9999,-9999.0]).sum().sum())
        if before:
            df = df.replace([-999,-999.0,-9999,-9999.0], np.nan)
            df.to_csv(p, index=False, encoding='utf-8-sig', **kwargs)
        print(f'{p}: cleaned {before} placeholder values')
    except Exception as e:
        print(f'[WARN] failed {p}: {e}')
