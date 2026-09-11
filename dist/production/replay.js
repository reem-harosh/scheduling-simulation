'use strict';
// Independent indexes: seeking backwards must never reuse a future material state.
class MaterialReplay {
 constructor(data) {
  this.data=data; this.byBatch=new Map(); this.jobs=new Map(data.jobs.map(j=>[j.id,j]));
  for(const frame of data.trace.material||[]){
   for(const row of frame.upsert)this.push(row.id,{time:frame.time,row});
   for(const id of frame.remove)this.push(id,{time:frame.time,row:null});
  }
  this.finalUnloads=new Map();
  for(const e of data.trace.events||[]){
   if(e.kind!=='parts_unloaded'||e.operation!==this.jobs.get(e.job)?.route.at(-1))continue;
   if(!this.finalUnloads.has(e.machine))this.finalUnloads.set(e.machine,[]);
   const history=this.finalUnloads.get(e.machine);history.push({time:e.time,total:(history.at(-1)?.total||0)+e.hi-e.lo,job:e.job});
  }
  this.lastTime=null;this.cached=[];this.queueIntervals=[];
  for(const history of this.byBatch.values())for(let k=0;k<history.length;k++){
   const event=history[k],r=event.row;if(!r||!['READY','WAITING_LIFT','INTERFLOOR_TRANSPORT'].includes(r.state))continue;
   const end=history[k+1]?.time??data.trace.end_min;
   if(end>event.time)this.queueIntervals.push({job:r.job,entity:r.location||'תור משותף',state:r.state,type:'material',start:event.time,end});
  }
 }
 push(id,event){if(!this.byBatch.has(id))this.byBatch.set(id,[]);this.byBatch.get(id).push(event)}
 rows(t){
  if(t===this.lastTime)return this.cached;
  this.lastTime=t;this.cached=[];
  for(const history of this.byBatch.values()){
   let lo=0,hi=history.length-1,found=null;
   while(lo<=hi){const m=(lo+hi)>>1;if(history[m].time<=t){found=history[m].row;lo=m+1}else hi=m-1}
   if(found)this.cached.push(found);
  }
  return this.cached;
 }
 completedAt(mid,t){
  const history=this.finalUnloads.get(mid)||[];let lo=0,hi=history.length-1,found=null;
  while(lo<=hi){const m=(lo+hi)>>1;if(history[m].time<=t){found=history[m];lo=m+1}else hi=m-1}
  return found;
 }
 parts(job,t){
  const j=this.jobs.get(job);if(!j||j.release>t)return [];
  if(j.complete!=null&&j.complete<=t)return [{quantity:j.quantity,lo:1,hi:j.quantity+1,state:'COMPLETE',location:'תוצרת גמורה',operation:j.route.at(-1),op_index:j.route.length-1,job}];
  return this.rows(t).filter(b=>b.job===job).flatMap(b=>b.segments.map(s=>({...s,job,batch:b.id,operation:b.operation,op_index:b.op_index,machine:b.machine,state:s.lift_start!=null?(t>=s.lift_start?'LIFT':'WAITING_LIFT'):s.state})));
 }
}
let materialReplay=null,ganttStamp='',progressStarted=0,progressTask=null,resourceStamp=0;
const materialLabels={WAITING_INPUT:'לפני הפעולה',OUTPUT:'אחרי הפעולה',COMPLETE:'הושלם',LIFT:'במעלית',WAITING_LIFT:'ממתין למעלית',WAITING_TRANSPORT:'ממתין לשינוע',CARRYING:'בשינוע',LOADING:'בטעינה',PROCESSING:'בעיבוד',UNLOADING:'בפריקה',CYCLE_CHANGE:'החלפת מחזור',WAITING_FOR_WORKER_UNLOAD:'במכונה · ממתין לפריקה',WAITING_FOR_CYCLE_CHANGE:'במכונה · ממתין להחלפה'};
const isWorking=s=>!!s&&!['OFF_SHIFT','ON_BREAK','IDLE_AT_LOCATION','IDLE_AVAILABLE'].includes(s);
function activeEntity(e,type){
 if(type==='jobs')return e.release<=time&&(e.complete==null||e.complete>time);
 if(type==='batches')return materialReplay&&result.trace.material_version?materialReplay.rows(time).some(b=>b.id===e.id):e.ready<=time&&!['הושלמה','פוצלה','טרם הגיעה'].includes(batchState(e));
 return isWorking(intervalAt(e.id)?.state);
}
function replayResources(){
 if(!result)return;
 const machines=result.machines.map(m=>intervalAt(m.id)?.state||'IDLE_AVAILABLE');
 const workers=result.workers.map(w=>({kind:w.kind,state:intervalAt(w.id)?.state||'OFF_SHIFT'}));
 const activeJobs=result.jobs.filter(j=>activeEntity(j,'jobs'));
 const cards=[['עבודות פעילות',activeJobs.length],['מכונות מעבדות',machines.filter(s=>s==='PROCESSING').length],['ממתינות',machines.filter(s=>s.startsWith('WAITING')).length],['בהכנה',machines.filter(s=>s==='SETUP').length],['טיפול ידני',machines.filter(s=>['LOADING','UNLOADING','CYCLE_CHANGE'].includes(s)).length],['עובדים בפעולה',workers.filter(w=>isWorking(w.state)).length],['עובדים פנויים',workers.filter(w=>w.state==='IDLE_AT_LOCATION').length],['מכונות פנויות',machines.filter(s=>s==='IDLE_AVAILABLE').length]];
 const cardsHTML=cards.map(([label,n])=>`<div><span>${label}</span><strong>${n}</strong></div>`).join('');if($('liveResources').innerHTML!==cardsHTML)$('liveResources').innerHTML=cardsHTML;
 $('liveProgress').textContent='כל המונים, החלקים והקשרים מתייחסים לשעון השחזור.';
 $('materialNotice').textContent=result.trace.material_version?'המכלים מציגים מצבורי חלקים; המספר מציין כמות מדויקת. צורת החלק היא המחשה למשפחה. לחצו על תחנה לפירוט.':'בקובץ זה חסר תיעוד מיקומי חלקים. הרצה חדשה תאפשר תורים וחלוקת חלקים מדויקת.';
 $('liveJobs').innerHTML=activeJobs.map(j=>`<button data-live-job="${escape(j.id)}">${escape(j.id)} · ${j.quantity} חלקים</button>`).join('')||'אין עבודות פעילות בזמן זה.';
 for(const b of $('liveJobs').querySelectorAll('button'))b.onclick=()=>select('jobs',b.dataset.liveJob);
 renderWaitingDiagnostics();renderGantt();
}
function materialDetail(j){
 if(!result.trace.material_version)return '<p>מיקום החלקים לא נשמר בקובץ זה. יש להריץ מחדש לקבלת הפירוט.</p>';
 const parts=materialReplay.parts(j.id,time),total=parts.reduce((n,p)=>n+p.quantity,0);
 const statuses=parts.map(p=>`<tr><td><b>${p.quantity}</b><small>חלקים <bdi>${p.lo}–${p.hi-1}</bdi></small></td><td>${escape(materialLabels[p.state]||p.state)}<small>${escape(p.operation)}</small></td><td><bdi>${escape(p.worker||p.location||'תור משותף')}</bdi>${p.worker?' · עובד':''}</td></tr>`).join('');
 const counts=j.route.map((op,oi)=>{
  const before=parts.filter(p=>p.op_index<oi||(p.op_index===oi&&['WAITING_INPUT','WAITING_TRANSPORT','CARRYING','LIFT','WAITING_LIFT','LOADING'].includes(p.state))).reduce((n,p)=>n+p.quantity,0);
  const after=parts.filter(p=>p.op_index>oi||(p.op_index===oi&&['OUTPUT','COMPLETE'].includes(p.state))).reduce((n,p)=>n+p.quantity,0);
  return `<tr><td>${escape(op)}</td><td>${before}</td><td>${Math.max(0,total-before-after)}</td><td>${after}</td></tr>`;
 }).join('');
 return `<div class="parts-detail"><p><b>${total} / ${j.quantity} חלקים ממופים</b>${total!==j.quantity&&j.release<=time?' · חסר תיעוד ברגע זה':''}</p><div class="table-wrap"><table><thead><tr><th>פעולה</th><th>לפני</th><th>במכונה</th><th>אחרי פריקה</th></tr></thead><tbody>${counts}</tbody></table></div><p class="muted">״לפני״ כולל פעולות קודמות, תור, שינוע וטעינה. ״במכונה״ כולל עיבוד והמתנה לפריקה. הכמויות מתעדכנות בסיום הפעולה הידנית.</p><div class="table-wrap"><table><thead><tr><th>כמות</th><th>מצב</th><th>מיקום</th></tr></thead><tbody>${statuses}</tbody></table></div></div>`;
}
function jobTint(id){let h=0;for(const c of id)h=(h*31+c.charCodeAt(0))>>>0;return `hsl(${(h*137.508)%360} 75% 68%)`}
function materialPosition(segment,row,xy){
 if(segment.worker){const w=intervalAt(segment.worker);const p=position(w);if(p){const [x,y]=xy(p);return[x+14,y+12]}}
 if(segment.lift_start!=null&&time>=segment.lift_start){
  const a=nodeCoords[result.trace.floor_handoff_nodes?.[segment.location?.split(':')[1]]],b=nodeCoords[result.trace.floor_handoff_nodes?.[segment.destination?.split(':')[1]]];
  if(a&&b){const f=Math.max(0,Math.min(1,(time-segment.lift_start)/(segment.lift_end-segment.lift_start||1)));return xy([a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f])}
 }
 if(segment.location?.startsWith('@floor:')){const p=nodeCoords[result.trace.floor_handoff_nodes?.[segment.location.split(':')[1]]];if(p){const[x,y]=xy(p);return[x,y+24]}}
 const m=machineLayout.find(m=>m.id===segment.location);
 if(m){
  const [x,y]=xy([m.x,m.y]),tr=transform(),w=m.w*tr.scale,h=m.h*tr.scale;
  const inside=[x+w/2,y+h-8],input=[x-22,y+h/2],output=[x+w+22,y+h/2];
  if(segment.state==='OUTPUT')return output;
  if(segment.state==='WAITING_INPUT'||segment.state==='WAITING_TRANSPORT')return input;
  const i=intervalAt(m.id),f=Math.max(0,Math.min(1,(time-(i?.start||0))/((i?.end||0)-(i?.start||0)||1)));
  if(segment.state==='LOADING'||segment.state==='CYCLE_LOADING'){const u=segment.state==='CYCLE_LOADING'?Math.max(0,2*f-1):f;return[input[0]+(inside[0]-input[0])*u,input[1]+(inside[1]-input[1])*u]}
  if(segment.state==='UNLOADING'||segment.state==='CYCLE_CHANGE'){const u=segment.state==='CYCLE_CHANGE'?Math.min(1,2*f):f;return[inside[0]+(output[0]-inside[0])*u,inside[1]+(output[1]-inside[1])*u]}
  return inside;
 }
 return null;
}
function drawMaterial(ctx,xy){
 if(!materialReplay||!result?.trace.material_version||liveData)return;
 const rows=materialReplay.rows(time),slots=new Map();
 // Dashes mean continuing lot responsibility; solid lines mean current service.
 for(const w of result.workers){
  const i=intervalAt(w.id),pos=position(i);if(!pos||i.state==='OFF_SHIFT')continue;
  const assignments=new Map();
  for(const b of rows)if(b.owner===w.id&&b.owner_active&&b.machine)assignments.set(b.machine,false);
  if(i.machine&&isWorking(i.state))assignments.set(i.machine,true);
  for(const [mid,servicing] of assignments){const m=machineLayout.find(m=>m.id===mid);if(!m)continue;
   ctx.strokeStyle=selected?.id===w.id?'#ffffff':servicing?'#93c5fdbb':'#93c5fd55';ctx.lineWidth=servicing?2.4:1.5;ctx.setLineDash(servicing?[]:[5,5]);ctx.beginPath();ctx.moveTo(...xy(pos));ctx.lineTo(...xy([m.x+m.w/2,m.y+m.h/2]));ctx.stroke();ctx.setLineDash([]);
   if(servicing){const [x,y]=xy([m.x+m.w/2,m.y]);ctx.fillStyle='#bfdbfe';ctx.font='14px Consolas';ctx.textAlign='center';ctx.fillText(w.id.split('_').at(-1),x,y-5)}
  }
 }
 let pool=0;
 for(const row of rows)for(const segment of visualSegments(row)){
  if(segment.state==='COMPLETE')continue;
  let p=materialPosition(segment,row,xy);
  if(!p){p=[80+pool%10*138,transform().poolY+Math.floor(pool/10)*38];pool++}
  let[x,y]=p;const key=Math.round(x)+','+Math.round(y),slot=slots.get(key)||0;slots.set(key,slot+1);y+=slot*23;
  const isSelected=selected?.id===row.job||selected?.id===row.id;
  ctx.fillStyle=jobTint(row.job);ctx.strokeStyle=isSelected?'#fff':'#07121f';ctx.lineWidth=isSelected?2.5:1;
  const count=Math.min(3,segment.quantity);for(let k=count-1;k>=0;k--){ctx.beginPath();ctx.roundRect(x-19+k*3,y-10-k*3,38,20,3);ctx.fill();ctx.stroke()}
  ctx.fillStyle='#07121f';ctx.textAlign='center';ctx.font='bold 19px Consolas';ctx.fillText(String(segment.quantity),x,y+5);
  if(!segment.location&&!segment.worker){ctx.fillStyle='#dce9f7';ctx.font='12px Segoe UI';ctx.fillText('תור משותף',x+62,y+5)}
  hitboxes.push({x:x-22,y:y-17,w:48,h:32,type:'jobs',id:row.job});
 }
}
function timelineBounds(){const start=result.trace.start_min||0,end=result.trace.end_min,span=$('ganttWindow').value==='all'?end-start:+$('ganttWindow').value;const anchor=Math.floor(time/Math.max(1,span/12))*Math.max(1,span/12);const left=Math.max(start,Math.min(anchor-span/2,end-span));return[left,Math.min(end,left+span)]}
function renderGantt(force=false){
 if(!result)return;
 const [start,end]=timelineBounds(),span=Math.max(.001,end-start),pct=t=>100*(t-start)/span;
 const key=[start,end,$('ganttFocus').checked,selected?.id].join('/');if(!force&&key===ganttStamp){for(const c of $('ganttRows').querySelectorAll('.gantt-cursor'))c.style.left=pct(time)+'%';return}ganttStamp=key;
 const chosen=selected?.type==='jobs'?selected.id:selected?.type==='batches'?result.batches.find(b=>b.id===selected.id)?.job:null;
 const segments=[...result.trace.intervals,...(materialReplay?.queueIntervals||[])].filter(i=>i.job&&i.start<end&&i.end>start&&(i.type==='machine'||i.type==='material'||i.state==='CARRYING')&&(!$('ganttFocus').checked||!chosen||i.job===chosen));
 const groups=new Map();for(const i of segments){const k=i.job+'|'+i.entity;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(i)}
 $('ganttRange').textContent=(span>1440?'מבט מרוכז: הטווח כולל המתנות בין מקטעים; לחצו לתצוגה מפורטת. ':'')+`יום ${format(start/1440,2)} – ${format(end/1440,2)} · לחיצה על מקטע עוברת לזמן ולפירוט העבודה`;
 const ticks=Array.from({length:5},(_,i)=>`<span style="left:${i*25}%">${format((start+i*span/4)/60,1)} ש׳</span>`).join('');
 let html=`<div class="gantt-axis"><div>שעות מתחילת הסימולציה</div><div class="gantt-track">${ticks}</div></div>`;
 for(const [key,items] of groups){const [job,entity]=key.split('|');html+=`<div class="gantt-row ${job===chosen?'selected':''}"><button class="gantt-name" data-job="${escape(job)}" title="${escape(job)}">${escape(job)}<small>${escape(entity)}</small></button><div class="gantt-track"><i class="gantt-cursor" style="left:${pct(time)}%"></i>`;
  const overview=span>1440;const displayed=overview?[{...items[0],start:Math.min(...items.map(i=>i.start)),end:Math.max(...items.map(i=>i.end)),state:'OVERVIEW'}]:items;
  for(const i of displayed){const left=pct(Math.max(start,i.start)),width=100*(Math.min(end,i.end)-Math.max(start,i.start))/span;const label=labels[i.state]||({OVERVIEW:'טווח פעילות · לחצו לפירוט',INTERFLOOR_TRANSPORT:'מעבר קומה',WAITING_LIFT:'המתנה / מעלית'}[i.state])||i.state;html+=`<button class="gantt-bar" data-overview="${overview}" data-job="${escape(job)}" data-time="${Math.max(start,i.start)}" style="left:${left}%;width:${width}%;background:${i.state==='OVERVIEW'?jobTint(job):(colors[i.state]||'#fbbf24')}" title="${escape(job+' · '+entity+' · '+label+' · '+format(i.start)+'–'+format(i.end)+' דקות')}" aria-label="${escape(job+' · '+entity+' · '+label)}">${width>4?escape(label):''}</button>`}
  html+='</div></div>';
 }
 $('ganttRows').innerHTML=html+(groups.size?'':'<p>אין פעילות מתועדת בחלון הזמן. הרחיבו את החלון או עברו לאירוע הבא.</p>');
 for(const b of $('ganttRows').querySelectorAll('button'))b.onclick=e=>{if(b.dataset.time!==undefined){time=+b.dataset.time;if(b.dataset.overview==='true'){if(e.detail){const rect=b.parentElement.getBoundingClientRect();time=Math.max(start,Math.min(end,start+(e.clientX-rect.left)/rect.width*span))}$('ganttWindow').value='120'};playing=false;$('play').textContent='▶ הפעל שחזור'}select('jobs',b.dataset.job);updateClock();renderGantt(true)};
}
function renderTaskProgress(task){
 progressTask=task;const p=task.progress||{},running=task.status==='RUNNING';
 const phase={preparing:'מכין את ההרצה',warmup:'חימום',measurement:'מדידה',drain:'משלים עבודות שנותרו',between_runs:'מעבר לריצה הבאה',saving:'שומר תוצאות',complete:'הושלם',cancelled:'בוטל',error:'שגיאה'}[p.phase]||task.message;
 const percent=Number.isFinite(p.fraction)?p.fraction*100:null;
 for(const suffix of ['','Research']){
  $('taskProgress'+suffix).hidden=false;const bar=$('taskBar'+suffix);
  if(percent===null||p.phase==='preparing')bar.removeAttribute('value');else bar.value=percent;
  $('taskTitle'+suffix).textContent=`${phase}${percent===null?'':' · '+format(percent,1)+'%'}${p.total_runs>1?' · הסתיימו '+p.completed_runs+' / '+p.total_runs+' ריצות':''}`;
  $('taskDetail'+suffix).textContent=[p.algorithm,p.replication!=null?'חזרה '+(p.replication+1):'',p.arrival_scale!=null?'הגעה ×'+p.arrival_scale+' · גודל ×'+p.batch_scale:'',p.events!=null?format(p.events,0)+' אירועים':'',running?'חלפו '+durationText(Math.max(p.elapsed_seconds||0,(Date.now()-progressStarted)/1000)):'',p.work_total!=null?format(p.work_done,0)+' / '+format(p.work_total,0)+' חלקים־פעולות הושלמו':'',p.phase==='drain'?p.remaining_jobs+' עבודות לסיום':'',p.cached_runs?p.cached_runs+' ריצות נטענו מתוצאות שמורות':''].filter(Boolean).join(' · ');
  $('taskEta'+suffix).textContent=running?(p.eta_seconds!=null?'זמן משוער שנותר: '+durationText(p.eta_seconds)+' · האומדן מתעדכן':'זמן משוער: אוסף נתונים לאומדן…'):'משך ההרצה: '+durationText(p.elapsed_seconds||0);
 }
}
function durationText(seconds){return seconds<60?Math.ceil(seconds)+' שנ׳':seconds<3600?Math.ceil(seconds/60)+' דק׳':format(seconds/3600,1)+' שעות'}

function visualSegments(row){
 if(row.state!=='CYCLE_CHANGE')return row.segments;
 const i=intervalAt(row.machine);
 const loading=i&&(time-i.start)/(i.end-i.start||1)>=.5;
 return row.segments.flatMap(s=>{
  if(s.state==='CYCLE_CHANGE'&&loading)return[{...s,state:'OUTPUT'}];
  if(s.state!=='WAITING_INPUT'||!loading)return[s];
  const q=Math.min(s.quantity,result.trace.cycle_capacity_units||1);
  return[{...s,state:'CYCLE_LOADING',quantity:q,hi:s.lo+q},...(q<s.quantity?[{...s,lo:s.lo+q,quantity:s.quantity-q}]:[])];
 });
}

function renderWaitingDiagnostics(){
 const host=$('waitingDiagnostics');if(!host||!result)return;
 const idle=result.workers.filter(w=>intervalAt(w.id)?.state==='IDLE_AT_LOCATION');
 const waiting=result.machines.filter(m=>intervalAt(m.id)?.state?.startsWith('WAITING'));
 const rows=materialReplay?.rows(time)||[];
 const details=waiting.map(m=>{
  const i=intervalAt(m.id),setup=i.state==='WAITING_SETUP';
  const qualified=idle.filter(w=>w.kind.startsWith('setup')===setup&&w.skills?.includes(m.id));
  const assigned=result.workers.filter(w=>{const t=intervalAt(w.id);return t?.machine===m.id&&isWorking(t.state)});
  const owner=rows.find(b=>b.machine===m.id)?.owner;
  const why=assigned.length?'כבר מטופלת / עובד בדרך: '+assigned.map(w=>workerName(w.id)).join(', '):
   !result.trace.operator_assistance&&owner&&intervalAt(owner)?.state!=='OFF_SHIFT'?'ממתינה לאחראי '+workerName(owner)+'; עובד אחר אינו רשאי להחליפו במהלך המשמרת':
   !qualified.length?'אין כרגע '+(setup?'מומחה הכנה':'מפעיל')+' פנוי וכשיר למכונה':'ממתינה לשיבוץ';
  return `<tr><td><bdi>${escape(m.id)}</bdi></td><td>${escape(labels[i.state]||i.state)}</td><td>${qualified.length}</td><td>${escape(why)}</td></tr>`;
 }).join('');
 const html=`<summary>מכונות ממתינות: ${waiting.length} · למה הן ממתינות?</summary><p>מפעילים פנויים: ${idle.filter(w=>!w.kind.startsWith('setup')).length} · מומחי הכנה פנויים: ${idle.filter(w=>w.kind.startsWith('setup')).length} · בהפסקה: ${result.workers.filter(w=>intervalAt(w.id)?.state==='ON_BREAK').length} · מחוץ למשמרת: ${result.workers.filter(w=>intervalAt(w.id)?.state==='OFF_SHIFT').length} · מנות בתור לשיבוץ: ${rows.filter(b=>b.state==='READY').length}</p><p>עבודות במערכת: ${result.jobs.filter(j=>activeEntity(j,'jobs')).length}. כל מנה מעובדת במכונה אחת בכל פעולה; מכונות נוספות יכולות להישאר פנויות כשאין מנה מתאימה לשיבוץ.</p><div class="table-wrap"><table><thead><tr><th>מכונה</th><th>מצב</th><th>כשירים פנויים, כולל מי שאינו אחראי</th><th>הסבר</th></tr></thead><tbody>${details}</tbody></table></div>${result.trace.operator_assistance?'<p>קובץ זה נוצר עם כלל סיוע שבוטל. הריצו מחדש כדי לבדוק את כלל האחראי הבלעדי.</p>':'<p>טעינה, החלפת מחזור ופריקה מבוצעות בידי אחראי הפעולה בלבד. עובד כשיר אחר יכול להישאר פנוי; העברת אחריות מתקיימת לפי כללי חילופי המשמרת.</p>'}`;
 if(host.innerHTML!==html)host.innerHTML=html;
}
