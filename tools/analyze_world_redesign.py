"""Evidence and counterfactuals for joint world-design discussion; no engine mutation."""
import base64,csv,hashlib,html,json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/redesign';OUT.mkdir(parents=True,exist_ok=True)
DELIVER=ROOT.parent/'outputs';DELIVER.mkdir(parents=True,exist_ok=True)
w=json.loads((ROOT/'research/world/world.json').read_text())
ps=w['part_families'];ids=[p['id'] for p in ps]
q=np.array([x for p in ps for x in p['quantity_values']],float)
labels=np.array([p['id'] for p in ps for x in p['quantity_values']])
probs=np.array([p['demand_probability'] for p in ps])
COLORS=['#8a929e','#a44f39','#107c8d','#6654a1']
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold'})

def save(name,obj):
 (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
def table(rows):
 if not rows:return ''
 cols=list(rows[0]);fmt=lambda x:f'{x:,.3f}' if isinstance(x,float) else str(x)
 return '<div class="scroll"><table dir="ltr"><tr>'+''.join('<th>'+html.escape(str(k))+'</th>' for k in cols)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(fmt(r[k]))+'</td>' for k in cols)+'</tr>' for r in rows)+'</table></div>'
def image(name,caption):
 b64=base64.b64encode((OUT/(name+'.png')).read_bytes()).decode()
 return f'<figure><img src="data:image/png;base64,{b64}"><figcaption>{caption}</figcaption></figure>'
def compressed(target):
 lo,hi=0.,100.
 for _ in range(100):
  c=(lo+hi)/2
  if np.clip(c*np.sqrt(q),25,600).mean()<target:lo=c
  else:hi=c
 return np.floor(np.clip(c*np.sqrt(q),25,600)+.5),c
rootq,c=compressed(175)
linear=np.maximum(1,np.floor(q*175/q.mean()+.5))
variants={'Historical proxy':q,'Linear rescale to 175':linear,'Sqrt + bounds 25..600':rootq}
rows=[]
for name,v in variants.items():
 rows.append({'Variant':name,'Mean':float(v.mean()),'Median':float(np.median(v)),'Std':float(v.std(ddof=1)),'CV':float(v.std(ddof=1)/v.mean()),'P25':float(np.quantile(v,.25)),'P75':float(np.quantile(v,.75)),'P95':float(np.quantile(v,.95)),'Max':float(v.max()),'Share at minimum (%)':float(np.mean(v==v.min())*100),'Share at maximum (%)':float(np.mean(v==v.max())*100)})
qsort=np.sort(q)[::-1];tail={str(n):float(qsort[:n].sum()/q.sum()) for n in (17,35)}
save('quantity_comparison',{'statistics':rows,'power':.5,'coefficient':c,'engineering_lower':25,'engineering_upper':600,'target_mean':175,'observations':len(q),'largest_order_unit_share':tail,'classification':'Historical proxy is inferred; transformations and bounds are synthetic engineering alternatives, not fitted distributions.'})
fig,ax=plt.subplots(2,2,figsize=(13,9),layout='constrained')
ax[0,0].hist(q,bins=np.geomspace(1,q.max(),23),color=COLORS[0],edgecolor='white');ax[0,0].set(xscale='log',xlabel='Units per order (log scale)',ylabel='Historical jobs',title='A. Historical quantity proxy: full distribution')
ax[0,0].axvline(np.median(q),color=COLORS[2],ls='--',label='Median 475');ax[0,0].axvline(q.mean(),color=COLORS[1],ls='--',label='Mean 2,398');ax[0,0].legend(fontsize=9)
for (name,v),color in zip(variants.items(),COLORS):ax[0,1].plot(np.sort(v),np.arange(1,len(v)+1)/len(v),label=name,color=color,lw=2)
ax[0,1].set(xscale='log',xlabel='Units (log scale)',ylabel='Fraction of jobs at or below quantity',title='B. ECDF: same 343 underlying observations');ax[0,1].legend(fontsize=8)
ax[1,0].hist(rootq,bins=np.arange(0,651,25),color=COLORS[2],edgecolor='white');ax[1,0].set(xlabel='Synthetic units per job',ylabel='Transformed observations',title='C. Candidate: mean 175, median 118, maximum 600');ax[1,0].axvline(rootq.mean(),color='#203040',ls='--')
ax[1,1].plot(np.arange(1,len(q)+1)/len(q)*100,np.cumsum(qsort)/q.sum()*100,color=COLORS[1],lw=2)
for n in (17,35):ax[1,1].scatter(n/len(q)*100,tail[str(n)]*100,color=COLORS[1]);ax[1,1].annotate(f'{n} orders: {tail[str(n)]:.1%} of units',(n/len(q)*100,tail[str(n)]*100),xytext=(10,-12),textcoords='offset points')
ax[1,1].set(xlabel='Largest jobs included (% of all jobs)',ylabel='Share of total units (%)',title='D. A small tail carries most of the units',xlim=(0,100),ylim=(0,105))
fig.savefig(OUT/'quantity_alternatives.png',dpi=170);plt.close(fig)
# Synthetic size classes: parameters selected for controlled experimental diversity.
size_classes=[{'Class':'Small','Weight':.25,'Min':25,'Mode':50,'Max':135},
              {'Class':'Medium','Weight':.5,'Min':50,'Mode':150,'Max':325},
              {'Class':'Large','Weight':.25,'Min':100,'Mode':240,'Max':500}]
for z in size_classes:
 a,m,b=z['Min'],z['Mode'],z['Max'];z['Mean']=(a+m+b)/3;z['Variance']=(a*a+m*m+b*b-a*m-a*b-m*b)/18
xx=np.linspace(0,550,11001);mixcdf=np.zeros_like(xx);mixpdf=np.zeros_like(xx)
fig,axs=plt.subplots(1,2,figsize=(13,4.5),layout='constrained')
for z,color in zip(size_classes,COLORS[1:]):
 a,m,b=z['Min'],z['Mode'],z['Max'];cdf=np.where(xx<a,0,np.where(xx<m,(xx-a)**2/((b-a)*(m-a)),np.where(xx<b,1-(b-xx)**2/((b-a)*(b-m)),1)))
 pdf=np.where((xx>=a)&(xx<m),2*(xx-a)/((b-a)*(m-a)),np.where((xx>=m)&(xx<=b),2*(b-xx)/((b-a)*(b-m)),0))
 mixcdf+=z['Weight']*cdf;mixpdf+=z['Weight']*pdf
 axs[0].plot(xx,pdf,label=f"{z['Class']}: mean {z['Mean']:g}",color=color,lw=2)
axs[0].set(title='A. Synthetic family-specific quantity classes',xlabel='Units per job',ylabel='Probability density');axs[0].legend()
axs[1].plot(xx,mixcdf,color='#173d55',lw=2,label='Synthetic mixture (25%, 50%, 25%)');axs[1].plot(np.sort(rootq),np.arange(1,len(rootq)+1)/len(rootq),label='Data-derived square-root candidate',color=COLORS[2]);axs[1].set(title='B. Two engineering alternatives',xlabel='Units per job',ylabel='CDF / ECDF',xlim=(0,625));axs[1].legend(fontsize=8)
fig.savefig(OUT/'synthetic_size_classes.png',dpi=170);plt.close(fig)
smean=sum(z['Weight']*z['Mean'] for z in size_classes);svar=sum(z['Weight']*(z['Variance']+z['Mean']**2) for z in size_classes)-smean*smean
synthetic_stats={'Variant':'Synthetic triangular size-class mixture','Mean':smean,'Median':float(np.interp(.5,mixcdf,xx)),'Std':math.sqrt(svar),'CV':math.sqrt(svar)/smean,'P25':float(np.interp(.25,mixcdf,xx)),'P75':float(np.interp(.75,mixcdf,xx)),'P95':float(np.interp(.95,mixcdf,xx)),'Max':500,'Share at minimum (%)':0.,'Share at maximum (%)':0.}
save('synthetic_size_classes',{'classes':size_classes,'statistics_before_integer_rounding':synthetic_stats,'provenance':'Engineering alternative; triangular parameters selected, not fitted to historical quantities; mixture weights require matching demand mass by size class.'})
# Family composition: distinguish empirical order frequency from item diversity.
family=[];machine_counts={f:sum(m['machine_family']==f for m in w['machines']) for f in sorted({m['machine_family'] for m in w['machines']})}
for p in ps:
 route=p['operations'];ref=sum(o['reference_time_per_unit'] for o in route)
 family.append({'Family':p['id'],'Jobs':p['historical_job_count'],'Items':p['historical_item_count'],'Demand %':100*p['demand_probability'],'Operations':len(route),'Quantity mean':float(np.mean(p['quantity_values'])),'Processing contribution min/job':p['demand_probability']*float(np.mean(p['quantity_values']))*ref,'Route':' / '.join(o['machine_family'] for o in route)})
worksum=sum(r['Processing contribution min/job'] for r in family)
for r in family:r['Processing share %']=100*r['Processing contribution min/job']/worksum
family_stats={'below_half_percent':sum(p['demand_probability']<.005 for p in ps),'at_most_two_jobs':sum(p['historical_job_count']<=2 for p in ps),'at_most_two_job_share':sum(p['demand_probability'] for p in ps if p['historical_job_count']<=2),'all_single_process_family_job_share':sum(p['demand_probability'] for p in ps if len({o['machine_family'] for o in p['operations']})==1),'rows':family}
save('family_audit',family_stats)
fig,ax=plt.subplots(2,2,figsize=(14,10),layout='constrained');ix=np.arange(len(ps))
ax[0,0].bar(ix-.2,[r['Demand %'] for r in family],width=.4,label='Job frequency (%)',color=COLORS[2]);ax[0,0].bar(ix+.2,[r['Items']/sum(x['Items'] for x in family)*100 for r in family],width=.4,label='Unique item share (%)',color=COLORS[3]);ax[0,0].set_xticks(ix,ids,rotation=65);ax[0,0].set(title='A. Frequency is not product diversity',ylabel='Share (%)');ax[0,0].legend(fontsize=8)
ax[0,1].bar(ids,[r['Processing share %'] for r in family],color=COLORS[1]);ax[0,1].tick_params(axis='x',rotation=65);ax[0,1].set(title='B. Product-family contribution to offered processing',ylabel='Share of reference machine-minutes (%)')
lengths=range(1,12);ax[1,0].bar(list(lengths),[sum(p['historical_job_count'] for p in ps if len(p['operations'])==k) for k in lengths],color=COLORS[2]);ax[1,0].set(xticks=list(lengths),xlabel='Operations per route',ylabel='Historical jobs',title='C. Historical route lengths are not a design constraint')
ms=list(machine_counts);visit=[sum(p['demand_probability']*sum(o['machine_family']==f for o in p['operations']) for p in ps) for f in ms];reaches=[sum(p['demand_probability'] for p in ps if any(o['machine_family']==f for o in p['operations']))*100 for f in ms]
ax[1,1].bar(ms,reaches,color=COLORS[3]);ax[1,1].set(ylabel='Probability a job visits family (%)',title='D. Existing process mix; repeated visits counted once here')
fig.savefig(OUT/'family_evidence.png',dpi=170);plt.close(fig)
# Controlled quantity/staff counterfactual: keep OLD routes, mix, machine speeds/counts fixed.
capacity=[];resource_rows=[]
for target in (150,175,200):
 v,coef=compressed(target);unitops=0;loads={f:0. for f in ms}
 for p in ps:
  qm=float(v[labels==p['id']].mean());unitops+=p['demand_probability']*qm*len(p['operations'])
  for o in p['operations']:
   vals=[r['time_per_unit'] for r in w['processing_matrix'] if r['part_family']==p['id'] and r['operation_id']==o['id']]
   loads[o['machine_family']]+=p['demand_probability']*qm*float(np.mean(vals))
 manual=unitops*11/6
 for day,night in [(14,7),(20,10),(28,14)]:
  human=(day+night)*650*6/7
  mr=min(.75*machine_counts[f]*1440/loads[f] for f in ms)
  hr=.75*human/manual
  capacity.append({'Target quantity mean':target,'Day workers':day,'Night workers':night,'Manual min/job (approx.)':manual,'Machine-only lambda at 75%':mr,'Human-only lambda at 75%':hr,'Joint analytical candidate jobs/day':min(mr,hr),'Binding analytical resource':'human' if hr<mr else 'machine','Walking/setup/transport':'excluded; not stable-rate confirmation'})
  for f in ms:resource_rows.append({'Target mean':target,'Day workers':day,'Night workers':night,'Family':f,'Processing min/job':loads[f],'Machine count':machine_counts[f]})
save('capacity_counterfactual',{'rows':capacity,'family_loads':resource_rows,'status':'Analytical only, OLD 19 routes and mix held fixed; floor restrictions not applied; NOT new-world calibration.'})
fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
for (day,night),color in zip([(14,7),(20,10),(28,14)],COLORS[1:]):
 rr=[r for r in capacity if r['Day workers']==day];ax.plot([r['Target quantity mean'] for r in rr],[r['Joint analytical candidate jobs/day'] for r in rr],marker='o',label=f'{day} day + {night} night',color=color)
ax.set(xlabel='Synthetic mean job quantity',ylabel='Analytical jobs/day at 75% offered capacity',title='Quantity and staffing counterfactuals — old routes/mix fixed',xticks=[150,175,200]);ax.legend();ax.text(.02,.03,'Excludes walking, transport, setup and floor-local constraints. Not simulation results.',transform=ax.transAxes,fontsize=9)
fig.savefig(OUT/'capacity_alternatives.png',dpi=170);plt.close(fig)
# A new route catalogue is a DESIGN proposal; no historical frequency claim.
R=[
('Milling rough','Milling finish','Inspection'),('Turning rough','Turning finish','Inspection'),('Turning','Grinding','Inspection'),('WireEDM cut','Milling finish','Inspection'),('Milling','Finishing'),
('Turning','Milling','Inspection'),('Milling rough','Grinding','Milling finish','Inspection'),('WireEDM cut','Grinding','Inspection'),('Turning','Finishing'),('Milling rough','Milling drill','Finishing'),
('Turning','WireEDM cut','Finishing','Inspection'),('Milling','WireEDM cut','Milling finish','Inspection'),('Grinding','Finishing'),('Turning rough','Grinding','Turning finish','Inspection'),('Milling','Grinding','Finishing','Inspection'),
('WireEDM cut','Finishing'),('Turning','Milling','Grinding','Inspection'),('Milling rough','Turning','Milling finish','Finishing'),('Turning rough','Turning drill','Finishing','Inspection'),('WireEDM cut','Milling rough','Grinding','Finishing','Inspection')]
newroutes=[{'Family':f'CF{i:02}','Operations':len(rt),'Route':' / '.join(rt),'Baseline probability %':5.,'Provenance':'Synthetic proposal; not an inferred historical route'} for i,rt in enumerate(R,1)]
for i,row in enumerate(newroutes):
 z=size_classes[[0,1,2,1][i%4]];row['Quantity class']=z['Class'];row['Quantity mean']=z['Mean']
newfamilies=[]
for f in ['Milling','Turning','Grinding','WireEDM','Finishing','Inspection']:
 visits=sum(sum(o.split()[0]==f for o in rt) for rt in R)
 newfamilies.append({'Machine family':f,'Old mapped machines':machine_counts.get(f,0),'Proposed route coverage':sum(any(o.split()[0]==f for o in rt) for rt in R),'Mean visits/job under uniform proposal':visits/len(R),'Source interpretation':'Observed category / derived timing proxy' if f in ('Milling','Turning','WireEDM') else 'Synthetic broader process; Honing is evidence for a related operation, not equivalent equipment' if f=='Grinding' else 'Synthetic added stage; timing needs explicit engineering baseline'})
save('candidate_route_catalogue',{'status':'DISCUSSION_CANDIDATE_NOT_ACTIVE','families':newroutes,'machine_families':newfamilies,'selection':'20 explicit archetypes covering repeat, reentrant, finishing and inspection cases; count is engineering design, not statistical optimum','quantity':'Synthetic triangular size classes; repeating Small/Medium/Large/Medium assigns 5/10/5 families. With fixed 5% family probabilities, overall theoretical mean=175; no historical mapping claimed','demand':'Fixed 5% each is an experimental reference; sensitivity can introduce predefined skew independently of scheduling'})
# Export compact tables for reproducibility (not a spreadsheet workbook).
for name,rs in [('quantity_statistics',rows),('family_evidence',family),('capacity_alternatives',capacity),('candidate_routes',newroutes),('candidate_machine_families',newfamilies),('synthetic_quantity_classes',size_classes)]:
 with (OUT/(name+'.csv')).open('w',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=list(rs[0]));wr.writeheader();wr.writerows(rs)
parts=['''<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scheduling Simulation — בחירת עולם למחקר</title><style>body{font:17px/1.75 Arial,sans-serif;background:#f3f6fa;color:#203449;margin:0}main{max-width:1180px;margin:auto;padding:28px}h1{line-height:1.35}section{background:white;border:1px solid #d8e1eb;border-radius:10px;padding:24px;margin:24px 0}img{width:100%;height:auto}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.5}td,th{padding:9px;border-bottom:1px solid #dce4ed;text-align:left}th{background:#173d55;color:white}tr:nth-child(even){background:#f2f6fa}figcaption{font-size:14px}.note{background:#fff3d9;padding:14px;border-right:5px solid #bd8133}details{margin:14px 0}summary{cursor:pointer;font-weight:bold}code{direction:ltr;unicode-bidi:embed}.eq{direction:ltr;text-align:center;padding:10px;background:#edf5f8;font-family:monospace}</style><main><h1>בחירת עולם ייצור למחקר<br>נתונים, חלופות והחלטות שצריך להפריד</h1><p>המשך ל־v0.4, בעקבות שש ההערות שלך. זהו ניתוח חלופות, ולא הודעה שהעולם החדש כבר מופעל.</p><p class="note">מטרת הנתונים: לספק סדרי גודל ודפוסים. אין חובה לשמר את הכמויות, תמהיל המוצרים או כל מסלול היסטורי. גרסת v0.4 נשארה קרובה מדי למקור בנקודות אלה.</p>''']
parts+=['<section><h2>1. גודל עבודה: 150–200 הוא יעד הנדסי סביר לבחינה</h2><p>343 עבודות עם כמות מוסקת מהדיווחים. 17 ההזמנות הגדולות ביותר, כ־5% מהעבודות, מכילות '+f'{tail["17"]:.1%}'+' מכל היחידות. לכן ממוצע 2,398 וחציון 475 מתארים אוכלוסייה לא סימטרית מאוד; החלפת הממוצע בחציון לבדה אינה מגדירה התפלגות חדשה.</p>'+image('quantity_alternatives','נתונים מוסקים מול חלופות סינתטיות. כל ההתפלגויות מוצגות במלואן; בגרפים הלוגריתמיים מרחקים שווים מייצגים יחסים שווים.')+'<p><b>ECDF</b> מציג, לכל כמות בציר האופקי, איזה חלק מהעבודות קטן ממנה או שווה לה. כאן אפשר לראות האם החלופה יוצרת בעיקר עבודות זעירות או שומרת על טווח שימושי. אין כאן התאמת Lognormal או טענה למובהקות.</p>'+table(rows)+'<p>כפל כל הכמויות באותו יחס נותן ממוצע 175, אך משאיר יחס קיצוני בין עבודות קטנות לענקיות. חלופת השורש מצמצמת את הפערים, משמרת את סדר הגדלים, ומגדירה טווח הנדסי 25–600. הגבולות והחזקה הם בחירות לתכנון, לא תוצאות של התאמה סטטיסטית.</p><div class="eq">Q_new = round(clip(c × sqrt(Q_proxy), 25, 600))<br>c = '+f'{c:.6f}'+'; weighted target mean ≈ 175</div><p>המלצה לשלב הדיון: לבחון את חלופת השורש כנקודת ייחוס, מול 150 ו־200 כממוצעי רגישות. למשפחות החדשות מוצגת בהמשך חלופה עצמאית של קבוצות גודל קטנה/בינונית/גדולה; אין לחלק את אותן כמויות לכל המשפחות בלי הבחנה. אין לשנות יחד גם את גודל העבודה וגם את קצב הביקוש כדי להסתיר תוצאה.</p></section>']
parts+=['<section><h2>חלופה נוספת: עולם עם קבוצות גודל סינתטיות</h2><p>אפשר להשתחרר עוד יותר מהכמויות ההיסטוריות. לכל משפחה מגדירים קבוצת גודל קטנה, בינונית או גדולה. כל קבוצה משתמשת בהתפלגות משולשת: מינימום, הערך השכיח ביותר ומקסימום. זהו מודל פשוט ושקוף שאינו דורש לטעון שנמצאה התאמה סטטיסטית בדאטה.</p>'+image('synthetic_size_classes','משמאל: התפלגות מותנית בקבוצת גודל. מימין: ההתפלגות הכוללת לפי משקלי הביקוש הקבועים, מול התאמת השורש.')+table(size_classes)+table([synthetic_stats])+'<p>הממוצע בהתפלגות משולשת הוא סכום שלושת הפרמטרים חלקי שלוש. לכן ממוצעי הקבוצות הם 70, 175 ו־280; משקלים 25%, 50%, 25% נותנים ממוצע כולל 175. הממוצע והסטטיסטיקה כאן הם לפני עיגול ליחידות שלמות. אלה בחירות הנדסיות — הנתונים תומכים בצורך בשונות בין עבודות, אך אינם קובעים את הטווחים האלה.</p><p><b>זו המלצתי לקטלוג החדש:</b> להשתמש בקבוצות הגודל כנקודת ייחוס עצמאית, ולשמור את חלופת השורש כתרחיש רגישות שמבוסס יותר על המקור. בקטלוג מוצעות 5 משפחות קטנות, 10 בינוניות ו־5 גדולות. ההקצאה המחזורית היא תכנון ניסויי גלוי; יש לבדוק בהמשך את הקשר בין גודל העבודה לאורך המסלול. שינוי תמהיל המשפחות משנה גם את תמהיל הגדלים, ולכן יש לדווח את הממוצע מחדש בכל תרחיש.</p><p>טבלת הקיבולת בהמשך חושבה עבור חלופת השורש והמסלולים הישנים בלבד. היא אינה אומדן קיבולת של קבוצות הגודל והקטלוג החדשים.</p></section>']
parts+=['<section><h2>2. עובדים: לבצע השוואה לאחר הגדרת גודל עבודה</h2><p>ניצולת ממוצעת של כ־52% במועמד הקודם אינה כשלעצמה הוכחה למחסור כולל בעובדים. ייתכן חוסר מקומי בקומה, במשמרת או מול בעלות על פעולות, לצד עובדים פנויים במקום אחר. הגדלת הצוות אינה מבטלת זאת אוטומטית.</p>'+image('capacity_alternatives','חישוב קיבולת בלבד: המסלולים והתמהיל הישנים נשמרו כדי לבודד את השפעת הכמות וכוח האדם.')+table(capacity)+'<p>החישוב משתמש ב־650 דקות שירות למשמרת, שישה ימי עבודה בשבוע, ובזמן הטיפול ההנדסי הקיים. הוא אינו כולל הליכה, שינוע או Setup, ואינו אוכף עדיין קיבולת מקומית לקומה. אין לפרש את המספרים כקצב יציב שאומת בסימולציה. יחס יום:לילה נשמר 2:1 בכל חלופה.</p><p>סדר ההחלטות: גודל עבודה ותמהיל → פעולות וזמנים → משאבים בכל קומה → טווח קצב הגעה → הרצות כיול. לאחר מכן משווים את הצוותים באותו זרם ביקוש; אין לכייל לכל צוות קצב אחר ואז לייחס את ההבדל לכוח האדם.</p></section>']
parts+=['<section><h2>3. כיצד התקבלו 19 משפחות ומה הבעיה בכך</h2><p>המימוש איחד דיווחים של כל פריט לפי מספר פעולה, החליף כל שלב במשפחת המכונה שלו, וקיבץ רצפים זהים. התקבלו 19 רצפים מדויקים; לא בוצעו clustering או מיזוג לפי דמיון. הסתברות המשפחה נקבעה לפי מספר עבודות, ולא לפי מספר פריטים שונים. זו הייתה בחירת ייצוג, לא הוכחה ש־19 הוא מספר מיטבי.</p>'+image('family_evidence','הבדל בין שכיחות הזמנות למגוון פריטים; תרומת משפחות לעומס מחושבת לפי הכמות וזמן הייחוס, לפני מהירות מכונה ו־Setup.')+'<p>PF03: חמישים עבודות מפריט אחד, ולכן 14.6% מהביקוש. רק PF19 מתחת לחצי אחוז; חמש משפחות נשענות על עבודה אחת או שתיים, וביחד מהוות '+f'{family_stats["at_most_two_job_share"]:.1%}'+' מהביקוש. יתרה מכך, '+f'{family_stats["all_single_process_family_job_share"]:.1%}'+' מהעבודות עוברות במסלול שכל פעולותיו שייכות למשפחת מכונות אחת בלבד. זה מגביל את מגוון המעברים בעולם.</p><details><summary>כל המשפחות ההיסטוריות והתרומה לעומס</summary>'+table(family)+'</details><p>המלצה: להעביר את קטלוג 19 הרצפים לשכבת הראיות, ולתכנן קטלוג ניסויי חדש עם 2–5 פעולות, רצפים חוזרים, חזרה למשפחה קודמת ונתיבי עיבוד שונים. משפחה נדירה מוצדקת אם היא בודקת התנהגות חשובה; הסתברות היסטורית זעירה אינה חובה. תמהיל אחיד יכול לשמש נקודת ייחוס, ותמהילים מוטים וקבועים יהיו תרחישי רגישות.</p></section>']
parts+=['<section><h2>4. שש משפחות מכונות וקטלוג מוצע</h2><p>מוצעת הרחבה לשש יכולות: Milling, Turning, Grinding, WireEDM, Finishing, Inspection. Honing אינו שם נרדף לכל Grinding: השימוש בו כעוגן למשפחה רחבה יותר הוא הנחה סינתטית מפורשת. Finishing ו־Inspection הם שלבים חדשים שלא נצפו בדאטה הזה. Rough ו־Finish נשארים Operations, ואינם מוכרזים כסוגי מכונות רק כדי להגדיל את הספירה.</p>'+table(newfamilies)+'<p>להלן 20 מסלולי מועמד, שנבנו כדי לכלול מגוון התנהגויות שיבוץ. המספר 20 אינו נבחר באמצעות מבחן סטטיסטי ואינו סופי. אפשר להסיר דפוסים כפולים או להוסיף דפוס שחסר לאחר בדיקת העומס. 5% לכל משפחה הוא תמהיל ניסויי ראשוני, לא תמהיל לקוחות שנמדד. Inspection מופיע ב־14 מתוך 20 מסלולים במועמד הזה. גם זהו תכנון סינתטי; הוא אינו חובה לכל עבודה, וקיבולתו עדיין דורשת בדיקה מפורשת.</p><details open><summary>קטלוג מסלולים מוצע — טרם הופעל</summary>'+table(newroutes)+'</details><p>אין לקבוע מספר שווה של מכונות בכל משפחה: עומס נמדד בדקות, ולא בספירת פעולות בלבד. מספרי המכונות וזמני השלבים החדשים ייקבעו יחד עם מטריצת עיבוד מפורשת, תוך שמירת כמה מכונות מקבילות לכל פעולה. חלוקת 68 המיקומים הקיימים היא מגבלת פריסה אפשרית, לא חובה לשמר את 44/20/2/2.</p></section>']
parts+=['''<section><h2>5. קומות: ממצא מאומת של סוכן הבדיקה</h2><p>v0.4 נתנה לכל עובד כשירות לכל המכונות והתעלמה מגבול הקומה בחיפוש מסלול. זו בעיה במודל ולא טעות בתמונה. הגבול השמור הוא x=1150; x=1200 נותן אותה חלוקה של 40 מכונות בשמאל ו־28 בימין. גם Setup ושינוע הושפעו.</p><p>התיקון הנדרש: floor_id נפרד ממשפחת מכונות, צוות מקומי לכל קומה ומשמרת, מסלולי הליכה מוגבלים לקומה, handoff מקומי, אומדן ECT לפי משאבי הקומה, ובדיקות מפורשות שאף עובד אינו חוצה. ארבעת עובדי ה־Setup יכולים להתחיל כאחד לכל קומה ומשמרת.</p><p><b>מעבר חלקים הוא החלטה נפרדת ממעבר עובדים.</b> אם חלקים עוברים בין קומות, יש לייצג נקודת מסירה/מעלית ושני מקטעי טיפול של עובדים מקומיים. זמן וקיבולת ההעברה חייבים להיות גלויים. אם חלקים אינם עוברים, כל מסלול חייב להיות בר־ביצוע בתוך קומה אחת. אין לחסום את ההליכה ולהשאיר מסלולים בלתי אפשריים.</p><p>החריגה נבדקה אך עדיין לא תוקנה בקוד במסגרת מסמך הדיון הזה. 59 בדיקות v0.4 לא כיסו הפרדת קומות.</p></section><section><h2>6. Grid של 25 נקודות ומעלה</h2><p>המנוע כבר תומך במכפלה קרטזית. חמש רמות בכל ציר הן 25 נקודות; ה־UI מאפשר עד עשר רמות, כלומר 100 נקודות. תשע הנקודות בדוח הקודם היו פיילוט שבוצע, לא מגבלה.</p><p>לאחר הגדרת העולם: רמות 0.50, 0.75, 1.00, 1.25, 1.50 בכל ציר; 10 רפליקציות נותנות 250 הרצות לכל אלגוריתם. קודם פיילוט קצר לכל נקודה, כדי לזהות תרחישים מתבדרים ולהגדיר גבולות drain. אין להציג חישובי הקיבולת במסמך זה כמשטח תגובה של ריצות שלא בוצעו.</p></section><section><h2>מה מוגדר ומה נשאר לבחירה משותפת</h2><p>הכיוון המוצע: כמות ממוצעת כ־175 עם שונות נשלטת, שש משפחות מכונות, קטלוג מסלולים סינתטי, תמהיל קבוע שאינו תלוי בתורים, הפרדת עובדים לפי קומות, והשוואת צוותי יום/לילה באותו ביקוש. הנתונים משמשים עוגן ותיעוד, ואינם מחייבים שימור זנב הכמויות או שכיחות הפריטים ההיסטורית.</p><p>לפני הפעלת העולם החדש נדרשת הכרעה אחת על הפריסה: האם חלקים רשאים לעבור בין קומות? המסמך והקטלוג אינם משנים כרגע את ברירת המחדל של הסימולציה.</p></section></main></html>''']
(DELIVER/'Simulation_World_Design_Discussion.html').write_text(''.join(parts))
print(json.dumps({'quantity_statistics':rows,'family_summary':{k:v for k,v in family_stats.items() if k!='rows'},'capacity_at_175':[r for r in capacity if r['Target quantity mean']==175],'report':str(DELIVER/'Simulation_World_Design_Discussion.html')},indent=2))
