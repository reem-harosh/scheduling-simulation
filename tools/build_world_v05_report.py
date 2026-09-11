"""Self-contained Hebrew implementation report with actual finite-horizon results."""
import argparse,base64,html,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def table(rows):
    if not rows:return '<p>אין תוצאות בקבוצה זו.</p>'
    keys=list(rows[0]);esc=lambda x:html.escape(json.dumps(x,ensure_ascii=False) if isinstance(x,(dict,list)) else str(round(x,4) if isinstance(x,float) else x))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(k)+'</th>' for k in keys)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(r.get(k,''))+'</td>' for k in keys)+'</tr>' for r in rows)+'</tbody></table></div>'
def picture(p,caption):
    if not p.exists():return ''
    return '<figure><img src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"><figcaption>'+caption+'</figcaption></figure>'

def build(world,pilots,grid,replay,out):
    w=json.loads(world.read_text());p=json.loads((pilots/'summary.json').read_text());rows=p['results'];summary=[]
    for rate in sorted({r['rate'] for r in rows}):
        rr=[r for r in rows if r['rate']==rate];avg=lambda k:statistics.mean(r[k] for r in rr if r.get(k) is not None)
        summary.append({'קצב הגעה מתוכנן':rate,'רפליקציות':len(rr),'הושלמו':sum(r['status']=='COMPLETE' for r in rr),'תפוקה ליום':avg('throughput_jobs_per_day'),'זמן שהייה שעות':avg('mean_flow_min')/60,'WIP ממוצע':avg('mean_wip'),'מכונות תפוסות %':100*avg('machine_utilization'),'ניצולת עובדים %':100*avg('worker_available_utilization'),'ניצולת Setup %':100*avg('setup_worker_utilization'),'מגמת WIP עבודות/יום':avg('wip_slope_jobs_per_day') if any(r.get('wip_slope_jobs_per_day') is not None for r in rr) else 'אין מספיק חלונות שבועיים'})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for rep in sorted({r['replication'] for r in rows}):
        rr=sorted([r for r in rows if r['replication']==rep],key=lambda r:r['rate'])
        axes[0].plot([r['rate'] for r in rr],[r['mean_flow_min']/60 if r['mean_flow_min'] is not None else float('nan') for r in rr],marker='o',label=f'Replication {rep}')
        axes[1].plot([r['rate'] for r in rr],[r['mean_wip'] for r in rr],marker='o',label=f'Replication {rep}')
    axes[0].set(xlabel='Jobs/day',ylabel='Mean flow time (hours)',title='Arrival-cohort flow time, including drain');axes[1].set(xlabel='Jobs/day',ylabel='Mean WIP',title='Measurement-window inventory')
    for ax in axes:ax.grid(alpha=.2);ax.legend()
    plot=ROOT/'research/world_v05/calibration.png';fig.savefig(plot,dpi=160);plt.close(fig)
    parts=['<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8"><title>Scheduling Simulation v0.5</title><style>body{font:17px/1.7 Arial,sans-serif;color:#172a3a;background:#f4f7fa;max-width:1200px;margin:35px auto;padding:20px}section{background:white;padding:24px;margin:20px 0;border-radius:10px}h1,h2{color:#12617b}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:8px;border:1px solid #dce4eb;text-align:right}th{background:#edf3f8}img{max-width:100%;height:auto}.scroll{overflow:auto;max-height:520px}code{direction:ltr;display:inline-block}summary{cursor:pointer;font-weight:bold;padding:12px}figcaption{color:#456}a{color:#12617b}</style><h1>Scheduling Simulation — v0.5</h1><p>מימוש עולם סינתטי, בדיקות והרצות כיול. כל פרמטר שאינו נמדד במקור מוצג כהנחה הנדסית.</p>']
    parts+=['<section><h2>מה נכנס למנוע</h2><p>18 משפחות, 50 פעולות, כמויות של 42–374 יחידות בסקאלה 1 וממוצע משוקלל 175. שתי משפחות חד־שלביות מקבלות יחד 5% מהביקוש. יתר הביקוש אינו אחיד. כרסום 4 צירים יכול לבצע פעולות 3 צירים; הכיוון ההפוך אסור.</p><p>68 מיקומי המכונות נשמרו. הקצאה לפי זמן תפוסה, הכולל עיבוד וטיפול ידני, החליפה הקצאה לפי עיבוד בלבד: 51 כרסומות, 13 מחרטות, שתי מכונות הונינג ושתי מכונות חיתוך בחוט. בכרסום: 29 מכונות של 3 צירים ו־22 של 4 צירים.</p><p>24 עובדים רגילים ביום ו־12 בלילה, מחולקים שווה בין הקומות, וארבעה עובדי Setup קבועים. העובדים נשארים בקומה; חלקים עוברים באמצעות מעלית אחת, בקיבולת 60 יחידות ומחזור שירות הנדסי של 3 דקות למטען. כל הכמות מתאחדת לפני הפעולה הבאה.</p></section>']
    parts+=['<section><h2>מה למדנו מהכיול</h2><p>קצב הבסיס בקובץ העולם: <b>'+str(w['demand']['baseline_jobs_per_day'])+' עבודות ביום</b>. מצב: '+html.escape(w['demand']['baseline_status'])+'.</p><p>לכל רפליקציה '+str(p['warmup_days'])+' ימי חימום ו־'+str(p['measurement_days'])+' ימי מדידה. זמן השהייה מחושב לקבוצת העבודות שהגיעה בחלון המדידה, כולל ניקוז. ניצולת ותפוקה נמדדות בתוך החלון בלבד. מכונה תפוסה אינה בהכרח מעבדת: היא יכולה להיות בטעינה, Setup או המתנה לעובד.</p>'+table(summary)+picture(plot,'כל קו הוא רפליקציה בפועל. עלייה בזמן השהייה וב־WIP עם קצב ההגעה היא ממצא ניסויי; הגרף אינו הוכחה ליציבות ארוכת טווח.')+'</section>']
    if p.get('interrupted_runs'):
        parts+=['<section><p>ארבע הרצות הכיול בטבלה הושלמו. שתי הרצות נוספות בקצב 22 נעצרו לפני השלמה ואינן משמשות למסקנות. לא נטען שנמצא קצב ההגעה המרבי שהמערכת מסוגלת לשאת.</p></section>']
    selected=min(rows,key=lambda r:abs(r['rate']-w['demand']['baseline_jobs_per_day']))['rate'];chosen=[r for r in rows if r['rate']==selected]
    fam=[]
    for g in sorted(chosen[0]['per_family']):
        fam.append({'קבוצה':g,'מכונות':chosen[0]['per_family'][g]['machine_count'],'עיבוד אוטומטי %':100*statistics.mean(r['per_family'][g]['processing_utilization'] for r in chosen),'זמן תפוסה %':100*statistics.mean(r['per_family'][g]['busy_utilization'] for r in chosen),'תור מוכן ממוצע':statistics.mean(r['per_family'][g]['mean_ready_queue'] for r in chosen)})
    parts+=['<section><h2>אבחון קבוצות המכונות</h2><p>ממוצעים על פני הרפליקציות בקצב '+str(selected)+'. קבוצה בעלת ניצולת נמוכה נשארת גלויה; אין איזון ביקוש בזמן הריצה כדי להסתיר זאת.</p>'+table(fam)+'</section>']
    if (grid/'surface.json').exists():
        surface=json.loads((grid/'surface.json').read_text())
        import numpy as np
        fig=plt.figure(figsize=(12,5),layout='constrained');xs=surface['grid'];ys=surface['batch_grid']
        values=[v['mean']/60 for pt in surface['points'] for v in pt['algorithms'].values() if v['mean'] is not None]
        for index,algorithm in enumerate(surface['algorithms'],1):
            ax=fig.add_subplot(1,len(surface['algorithms']),index,projection='3d');z=np.full((len(ys),len(xs)),np.nan)
            for pt in surface['points']:
                mean=pt['algorithms'][algorithm]['mean']
                if mean is not None:z[ys.index(pt['batch_size']),xs.index(pt['arrival_load'])]=mean/60
            x,y=np.meshgrid(xs,ys);ax.plot_surface(x,y,z,cmap='viridis',vmin=min(values),vmax=max(values),alpha=.85);ax.scatter(x,y,z,c='black',s=12)
            ax.set(xlabel='Arrival scale',ylabel='Job size scale',zlabel='Mean flow time (hours)',title=algorithm,xticks=xs,yticks=ys,zlim=(0,max(values)*1.05))
        fig.suptitle('25 scenario points, 2 replications per algorithm; common vertical scale\n3 warm-up + 3 measurement days; full cohort drain; not steady-state estimates')
        fig.savefig(grid/'surface.png',dpi=160);plt.close(fig)
        parts+=['<section><h2>רשת ניסויים בפועל</h2><p>'+str(len(surface['points']))+' נקודות, '+str(surface['replications'])+' רפליקציות לנקודה ולכל אלגוריתם. ברשת זו: 3 ימי חימום ו־3 ימי מדידה. ציר X: עוצמת הגעה; Y: גודל עבודה; Z: זמן שהייה ממוצע. זהו ניסוי לאופק מוגדר, ולא אומדן מצב מתמיד. ההשוואה לכיול בן 21 ימי מדידה אינה השוואה של אותו חלון.</p>'+picture(grid/'surface.png','המשטחים משתמשים באותה סקאלה אנכית. תוצאות גולמיות מלאות נשמרות לכל נקודה; שתי רפליקציות אינן מספיקות להכרזה על אלגוריתם מנצח.')+'</section>']
    parts += ['<section><h2>רצפת הייצור מתוך לוג אירועים</h2>'+picture(replay/'replay_frame.png','הדמיה של מצבים ותנועות שנרשמו במנוע. זו אינה תמונת מסך של הדפדפן, ולא אנימציה מלאכותית.')+'</section>']
    tables={'משפחות וכמויות':[{k:v for k,v in f.items() if k not in ('operations','quantity_values')} for f in w['part_families']],'פעולות, דרישות צירים ו־Setup':[{ 'part_family':f['id'],**o} for f in w['part_families'] for o in f['operations']],'מכונות ומיקומים':w['machines'],'מטריצת זמני עיבוד':w['processing_matrix'],'מטריצות Setup':w['setup_matrices'],'משאבים והנחות':[{'parameter':k,'value':v} for k,v in {**w['resources'],**w['provenance']}.items()]}
    parts+=['<section><h2>כל טבלאות העולם</h2>']
    for title,rr in tables.items():parts+=['<details><summary>'+title+'</summary>'+table(rr)+'</details>']
    parts+=['</section><section><h2>הפעלה וגבולות המסקנות</h2><p>בתיקיית הפרויקט: <code>pip install -r requirements.txt</code>, ולאחר מכן <code>python run_factory.py</code>. הכתובת המקומית היא <code>http://127.0.0.1:8000/production/</code>.</p><p>כמות הזמנה, תפקידי פעולות, מורכבות, מקדמי טכנולוגיה, תמהיל ושיוך משאבים הם בחירות לעולם מחקרי סינתטי. זמני המקור הם פרוקסי של זמני תקן ולא מדידה מבודדת של זמן מכונה. הרצות סופיות ובדיקות תקינות אינן מוכיחות מצב מתמיד; נדרשות רפליקציות ארוכות יותר למחקר מסכם. המעלית מיוצגת כשירות מצרפי, ועמדות המעבר הן קירוב גאומטרי מתועד.</p></section></html>']
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(parts));print(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=ROOT/'research/world_v05/world.json');p.add_argument('--pilots',type=Path,default=ROOT/'results/v05-final-pilots');p.add_argument('--grid',type=Path,default=ROOT/'results/v05-grid');p.add_argument('--replay',type=Path,default=ROOT/'research/world_v05/replay');p.add_argument('--out',type=Path,default=ROOT.parent/'outputs/Simulation_v05_Update.html');a=p.parse_args();build(a.world,a.pilots,a.grid,a.replay,a.out)
