"""Supplementary aggregate source evidence; does not mutate world parameters."""
from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
source=Path('data/raw/production_reports.xlsx');d=pd.read_excel(source)
def describe(v):
 v=pd.to_numeric(v,errors='coerce');v=v[np.isfinite(v)&(v>0)]
 return {'n':int(len(v)),'mean':float(v.mean()),'median':float(v.median()),'std':float(v.std()),'p25':float(v.quantile(.25)),'p75':float(v.quantile(.75)),'p95':float(v.quantile(.95)),'max':float(v.max())}
standard=pd.to_numeric(d['זמן תקן\nהוראת\nייצור'],errors='coerce');qty=pd.to_numeric(d['כמות\nטובים'],errors='coerce');net=pd.to_numeric(d['זמן עבודה נטו (דקות)'],errors='coerce');ratio=(net/qty).replace([np.inf,-np.inf],np.nan)
summary={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'report_types':{str(k):int(v) for k,v in d['סוג\nדיווח'].value_counts(dropna=False).items()},'standard_minutes_per_unit':describe(standard),'reported_net_minutes_per_good_unit':describe(ratio),'timestamp_interpretation':'Observed reporting timestamps, not order arrivals. No fitted hourly NHPP shape is justified.','setup_interpretation':'Report-type counts and descriptions are evidence of reporting categories, not a validated machine from-configuration/to-configuration changeover matrix. New setup classes remain synthetic.'}
Path('research/world/source_evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for ax,v,title in zip(axes,[standard,ratio],['Reported instruction standards','Reported net time / good quantity']):
 v=v[np.isfinite(v)&(v>0)];ax.hist(np.log10(v),bins=50);ax.set(xlabel='log10(minutes per unit)',ylabel='Report count',title=title)
fig.suptitle('Reporting proxies: neither series isolates autonomous machine time');fig.savefig('research/world/processing_source_evidence.png',dpi=150)
print(json.dumps(summary,ensure_ascii=False,indent=2))
