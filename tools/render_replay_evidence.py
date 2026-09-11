"""Render a truthful diagnostic frame from recorded DES intervals (not UI QA)."""
import argparse,bisect,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
parser=argparse.ArgumentParser();parser.add_argument('--result',default='results/world-joint-replay/replay.json');parser.add_argument('--output',default='results/world-joint-replay');args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
r=json.loads(Path(args.result).read_text());tracks={}
for i in r['trace']['intervals']:tracks.setdefault(i['entity'],[]).append(i)
for v in tracks.values():v.sort(key=lambda x:x['start'])
window_start=max(r['trace']['start_min'],r['measurement']['start_min']);window_stop=min(r['trace']['end_min'],r['measurement']['stop_min'])
walks=[i for i in r['trace']['intervals'] if i['state'] in ('WALKING','CARRYING') and max(i['start'],window_start)<min(i['end'],window_stop)]
walking=max(walks,key=lambda x:min(x['end'],window_stop)-max(x['start'],window_start));t=(max(walking['start'],window_start)+min(walking['end'],window_stop))/2

def state(e):
 a=tracks.get(e,[]);ix=bisect.bisect_right([v['start'] for v in a],t)-1
 return a[ix] if ix>=0 and a[ix]['end']>=t else None
nodes=r['trace']['nodes'];colors={'PROCESSING':'#14b8a6','SETUP':'#a78bfa','LOADING':'#38bdf8','UNLOADING':'#38bdf8','CYCLE_CHANGE':'#38bdf8','WALKING':'#2563eb','CARRYING':'#d97706'}
fig,ax=plt.subplots(figsize=(16,6),layout='constrained');ax.set_facecolor('#f3f6fa');processing=0
for m in r['machines']:
 i=state(m['id']);s=i['state'] if i else 'IDLE_AVAILABLE';processing+=s=='PROCESSING';color=colors.get(s,'#d5dee6')
 ax.add_patch(Rectangle((m['x'],m['y']),m['w'],m['h'],facecolor=color,edgecolor='#4d6275',linewidth=.5));ax.text(m['x']+m['w']/2,m['y']+m['h']/2,m['id'],ha='center',va='center',fontsize=6)
active=0
for w in r['workers']:
 i=state(w['id'])
 if not i or i['state']=='OFF_SHIFT':continue
 active+=1;pos=nodes[i.get('node',w['home_node'])]
 if i.get('path'):
  points=[nodes[n] for n in i['path']];dist=[abs(b[0]-a[0])+abs(b[1]-a[1]) for a,b in zip(points,points[1:])];remaining=sum(dist)*max(0,min(1,(t-i['start'])/max(1e-12,i.get('move_end',i['end'])-i['start'])))
  pos=points[-1]
  for a,b,d in zip(points,points[1:],dist):
   if remaining<=d:pos=[a[k]+(b[k]-a[k])*remaining/max(d,1e-12) for k in (0,1)];break
   remaining-=d
  ax.plot([p[0] for p in points],[p[1] for p in points],color=colors.get(i['state'],'#555'),alpha=.8,lw=1.8)
 ax.scatter(*pos,s=42 if w['id'].startswith('S') else 22,c=colors.get(i['state'],'#334155'),marker='s' if w['id'].startswith('S') else 'o',edgecolors='white',linewidths=.5,zorder=5)
 ax.annotate(w['id'].split('_')[-1],pos,xytext=(3,5),textcoords='offset points',fontsize=6)
ax.set(xlim=(-40,2370),ylim=(840,-40),aspect='equal',xlabel='Relative floor coordinates (existing corridor geometry)',ylabel='Relative coordinates');ax.set_title(f'Actual event-log replay — day {t/1440:.4f} | {processing} machines processing | {active} on-duty workers\nTeal: automatic processing; purple: setup; blue/orange paths: recorded walking/carrying; squares: setup employees',fontsize=12)
ax.axvline(1150,color='#64748b',linestyle='--',linewidth=1);fig.savefig(out/'replay_frame.png',dpi=160)
(out/'frame_metadata.json').write_text(json.dumps({'time_min':t,'processing_machines':processing,'on_duty_workers':active,'selected_motion_worker':walking['entity'],'meaning':'Independent rendering of recorded intervals; not a browser screenshot'},indent=2))
print('Frame',t,processing,active)
