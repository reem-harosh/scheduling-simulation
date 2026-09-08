import {activeTask, workerPosition, jobState, progressAt, fmtTime, fmt} from './view-model.js';

const $=id=>document.getElementById(id);
const canvas=$('floor'),ctx=canvas.getContext('2d');
const state={trace:null,time:0,playing:false,ready:false,dirty:false,tab:'jobs',selected:null,request:0,batchId:0,batchRunning:false,batch:null,hover:null};
let worker,lastFrame=0,lastUI=0,timelineSignature='';
const fallback={machines:[{id:'P1',name:'מדפסת 01',kind:'print',position:[300,185],dock:[300,290]},{id:'P2',name:'מדפסת 02',kind:'print',position:[640,185],dock:[640,290]},{id:'F1',name:'עמדת כריכה',kind:'bind',position:[560,440],dock:[560,370]}],workers:[{id:'W1',name:'עובד 01',skills:['print'],home:[125,330],color:'#38bdf8'},{id:'W2',name:'עובד 02',skills:['print','bind'],home:[175,330],color:'#fb923c'}],jobs:[{id:'A',color:'#818cf8'},{id:'B',color:'#2dd4bf'},{id:'C',color:'#fbbf24'},{id:'D',color:'#fb7185'}],tasks:[]};
const current=()=>state.trace||fallback;
const color=id=>current().jobs.find(j=>j.id===id)?.color||'#94a3b8';
const opName=op=>op==='print'?'הדפסה':'כריכה';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function status(message,loading=false){$('engineStatus').innerHTML=`<span class="status-dot ${loading?'loading':''}"></span>${escape(message)}`;}
function showError(message){$('errorText').textContent=message;$('errorBox').classList.remove('hidden');}
function initWorker(){
  worker?.terminate();state.ready=false;state.playing=false;state.batchRunning=false;
  $('canvasLoading').classList.remove('hidden');$('errorBox').classList.add('hidden');status('טוען את מנוע הסימולציה…',true);
  worker=new Worker('./worker.js');
  worker.onmessage=({data})=>{
    if(data.type==='loading') status(data.message,true);
    if(data.type==='ready') {state.ready=true;status('המנוע מוכן');$('applyButton').disabled=false;applySettings();}
    if(data.type==='trace'&&data.id===state.request){
      state.trace=data.result;state.time=0;state.playing=false;state.dirty=false;state.selected=null;
      $('canvasLoading').classList.add('hidden');$('configNotice').classList.add('hidden');
      for(const id of ['playButton','resetButton','stepButton','seek','applyButton','batchButton'])$(id).disabled=false;
      $('seek').max=state.trace.end_time;$('seek').value=0;$('seekEnd').textContent=fmtTime(state.trace.end_time);
      $('walkingNote').textContent=state.trace.options.walking?'זמן התנועה נכלל בתוצאות ההרצה':'זמן הליכה כבוי · תרחיש הבסיס';
      $('repNote').textContent=state.trace.options.variation>0?`זמן כל פעולה נדגם בטווח ±${Math.round(state.trace.options.variation*100)}%. הזרע משתנה בכל רפליקציה; ההרצות ניתנות לשחזור.`:'בזמנים קבועים, כל הרפליקציות מחזירות אותה תוצאה. אפשר להפעיל זמני עבודה משתנים בהגדרות.';
      timelineSignature='';status('מוכן להרצה');renderUI();draw();
    }
    if(data.type==='batchProgress'&&data.id===state.batchId){$('batchProgress').textContent=`הושלמו ${data.done} מתוך ${data.total} הרצות`;}
    if(data.type==='batch'&&data.id===state.batchId){
      state.batch={results:data.results,options:data.options};finishBatch();renderBatch();
    }
    if(data.type==='batchCancelled'&&data.id===state.batchId){finishBatch();$('batchProgress').classList.remove('hidden');$('batchProgress').textContent='הניסוי בוטל.';}
    if(data.type==='error'){
      if(data.id===state.batchId)finishBatch();
      $('canvasLoading').classList.add('hidden');status('אירעה שגיאה');showError('לא ניתן להשלים את החישוב. נסה לטעון מחדש. '+data.message);
      $('applyButton').disabled=!state.ready;
    }
  };
  worker.onerror=()=>{status('הטעינה לא הושלמה');$('canvasLoading').classList.add('hidden');showError('מנוע הסימולציה לא נטען. בדוק את החיבור ונסה לטעון מחדש.');};
}
function readOptions(){
  const horizon=Number($('horizon').value),seed=Number($('seed').value);
  if(!$('horizon').value||!Number.isFinite(horizon)||horizon<1||horizon>1000)throw Error('אופק ההרצה חייב להיות בין 1 ל־1,000 דקות.');
  if(!$('seed').value||!Number.isInteger(seed)||seed<0||seed>2147483647)throw Error('הזרע חייב להיות מספר שלם בין 0 ל־2,147,483,647.');
  return {policy:$('policy').value,horizon,seed,walking:$('walking').checked,variation:$('randomness').checked?Number($('variation').value)/100:0};
}
function applySettings(){
  let options;try{options=readOptions();}catch(e){showError(e.message);return;}
  if(!state.ready)return;
  state.playing=false;if(state.batchRunning){worker.postMessage({type:'cancel'});state.batchId++;finishBatch();}
  state.batch=null;$('batchResults').classList.add('hidden');$('errorBox').classList.add('hidden');
  $('applyButton').disabled=true;$('batchButton').disabled=true;status('מחשב את התרחיש…',true);
  worker.postMessage({type:'simulate',options,id:++state.request});
}
function markDirty(){state.dirty=true;$('configNotice').classList.remove('hidden');$('batchButton').disabled=true;}
function setTab(tab){
  state.tab=tab;
  for(const item of ['jobs','resources','experiments']){
    $(item+'Panel').classList.toggle('hidden',item!==tab);
    $(item+'Tab').setAttribute('aria-selected',String(item===tab));$(item+'Tab').tabIndex=item===tab?0:-1;
  }
  renderUI();
}
function setTime(time){if(!state.trace)return;state.time=Math.max(0,Math.min(time,state.trace.end_time));$('seek').value=state.time;renderUI();draw();}
function togglePlay(){
  if(!state.trace)return;
  if(state.time>=state.trace.end_time-1e-7)setTime(0);
  state.playing=!state.playing;renderUI();
}
function nextEvent(){
  if(!state.trace)return;state.playing=false;
  const next=state.trace.events.find(e=>e.time>state.time+1e-7);
  setTime(next?Math.min(next.time,state.trace.end_time):state.trace.end_time);
}

function workerDescription(w){
  const tr=state.trace,t=state.time,task=tr&&activeTask(tr,'worker',w.id,t);
  if(!task)return {label:tr&&tr.metrics.complete&&tr.end_time<=t+1e-7?'סיים פעילות':'פנוי',detail:w.skills.includes('bind')?'כשיר להדפסה ולכריכה':'כשיר להדפסה',task:null,phase:'idle'};
  if(t<task.start-1e-7)return {label:'בתנועה',detail:`אל ${task.machine} · מנה ${task.job}`,task,phase:'walk'};
  return {label:'בעבודה',detail:`${opName(task.operation)} · ${task.machine} · מנה ${task.job}`,task,phase:'work'};
}
function machineDescription(m){
  const task=state.trace&&activeTask(state.trace,'machine',m.id,state.time);
  if(!task)return {label:'פנויה',detail:'אין פעולה פעילה',task:null,phase:'idle'};
  if(state.time<task.start-1e-7)return {label:'ממתינה לעובד',detail:`${task.worker} בדרך · מנה ${task.job}`,task,phase:'walk'};
  return {label:'עובדת',detail:`מנה ${task.job} · ${task.worker} · נותרו ${fmt(Math.max(0,task.end-state.time))} דק׳`,task,phase:'work'};
}
function jobDetail(job,s){
  if(s.phase==='done')return `הושלמה ב־${fmtTime(state.trace.completions[job.id])} · שהייה ${fmt(state.trace.completions[job.id]-job.release)} דק׳`;
  if(s.phase==='walk')return `${s.task.worker} בדרך אל ${s.task.machine} · ${opName(s.task.operation)}`;
  if(s.phase==='work')return `${opName(s.task.operation)} ב־${s.task.machine} עם ${s.task.worker}`;
  const next=job.operations[s.completed]?.[0];
  const freeMachine=state.trace.machines.some(m=>m.kind===next&&!activeTask(state.trace,'machine',m.id,state.time));
  const freeWorker=state.trace.workers.some(w=>w.skills.includes(next)&&!activeTask(state.trace,'worker',w.id,state.time));
  return !freeMachine?`בתור ל${next==='print'?'הדפסה':'כריכה'}`:!freeWorker?'ממתינה לעובד כשיר':'ממתינה לשיבוץ';
}

function renderUI(){
  const tr=state.trace,t=state.time;
  $('clock').textContent=fmtTime(t);
  $('playIcon').textContent=state.playing?'Ⅱ':'▶';$('playLabel').textContent=state.playing?'השהה':t>0&&tr&&t>=tr.end_time-1e-7?'הרץ שוב':'הפעל';
  const ended=tr&&t>=tr.end_time-1e-7;
  $('playState').textContent=state.playing?'בהרצה':ended?(tr.metrics.complete?'הושלם':'אופק ההרצה הושג'):t>0?'מושהה':'מוכן לצפייה';
  $('playState').classList.toggle('running',state.playing);
  if(!tr)return;
  const done=tr.jobs.filter(j=>tr.completions[j.id]<=t+1e-7);
  $('completed').textContent=done.length;$('flow').textContent=done.length?fmt(done.reduce((s,j)=>s+tr.completions[j.id]-j.release,0)/done.length):'—';
  $('activeWorkers').textContent=tr.workers.filter(w=>activeTask(tr,'worker',w.id,t)).length;
  if(ended&&!tr.metrics.complete)status(`${done.length} מתוך ${tr.jobs.length} מנות הושלמו · ההרצה נעצרה באופק`);
  else if(ended)status('כל המנות הושלמו');else status(state.playing?'הסימולציה פעילה':'מוכן לצפייה');
  $('workerStrip').innerHTML=tr.workers.map(w=>{const d=workerDescription(w);return `<div class="worker-mini"><span class="worker-avatar" style="color:${w.color}">${w.id}</span><div><strong>${w.name}</strong><p>${d.detail}</p></div><span class="worker-state">${d.label}</span></div>`;}).join('');
  if(state.tab==='jobs')$('jobCards').innerHTML=tr.jobs.map(j=>{
    const s=jobState(tr,j,t),late=j.due!==null&&(s.phase==='done'?tr.completions[j.id]:t)>j.due+1e-7;
    const label={done:'הושלמה',walk:'בתנועה',work:'בעבודה',waiting:'ממתינה'}[s.phase];
    const cls={done:'done',walk:'walk',work:'active',waiting:''}[s.phase];
    return `<article class="job-card ${s.phase==='done'?'is-complete':''}" style="--job:${j.color}"><div class="job-top"><span class="job-id">${j.id}</span><span class="job-name">${j.name}</span><span class="badge ${cls}">${label}</span></div><div class="job-sub"><span>${j.source} · ${j.quantity} יח׳</span><span class="${late?'badge late':''}">${j.due===null?'למלאי':late?'באיחור':'יעד '+fmtTime(j.due)}</span></div><div class="operation-line">${j.operations.map(([op],i)=>`<span class="operation-chip ${i<s.completed?'done':s.task?.index===i?'current':''}">${i<s.completed?'✓ ':''}${opName(op)}</span>`).join('')}</div><div class="progress-track"><div class="progress-fill" style="width:${s.progress*100}%"></div></div><p class="job-detail">${jobDetail(j,s)}</p></article>`;
  }).join('');
  if(state.tab==='resources'){
    const machineCards=tr.machines.map(m=>{const d=machineDescription(m);return `<article class="resource-card ${state.selected===m.id?'selected':''}"><div class="title"><span><b dir="ltr">${m.id}</b> · ${m.name}</span><span class="badge ${d.phase==='work'?'active':d.phase==='walk'?'walk':''}">${d.label}</span></div><p>${d.detail}</p><small>${m.kind==='bind'?'עובד כשיר: W2':'עובדים כשירים: W1, W2'}</small></article>`;}).join('');
    const workerCards=tr.workers.map(w=>{const d=workerDescription(w);return `<article class="resource-card ${state.selected===w.id?'selected':''}"><div class="title"><span style="color:${w.color}"><b dir="ltr">${w.id}</b> · ${w.name}</span><span class="badge ${d.phase==='work'?'active':d.phase==='walk'?'walk':''}">${d.label}</span></div><p>${d.detail}</p><small>${w.skills.map(opName).join(' / ')}${d.task?' · עד '+fmtTime(d.task.end):''}</small></article>`;}).join('');
    $('resourceCards').innerHTML='<div class="resource-group-label">מכונות</div>'+machineCards+'<div class="resource-group-label">עובדים</div>'+workerCards;
  }
  renderTimeline();
  const events=tr.events.filter(e=>e.time<=t+1e-7&&e.time<=tr.end_time+1e-7);
  $('eventCount').textContent=events.length+' אירועים';
  $('eventLog').innerHTML=events.length?events.slice(-30).reverse().map(e=>`<div class="event-row" style="--job:${color(e.job)}"><time>${fmtTime(e.time)}</time><span>${eventText(e)}</span></div>`).join(''):'<div class="event-empty">האירועים יופיעו כאן עם תחילת ההרצה.</div>';
}
function eventText(e){
  if(e.type==='walk')return `${e.worker} הולך אל ${e.machine} עבור <b>${e.job}</b>`;
  if(e.type==='start')return `התחלת ${e.machine==='F1'?'כריכה':'הדפסה'} של <b>${e.job}</b> ב־${e.machine}`;
  if(e.type==='finish')return `סיום פעולה של <b>${e.job}</b> ב־${e.machine}`;
  return `מנה <b>${e.job}</b> הושלמה`;
}
function renderTimeline(){
  const tr=state.trace;if(!tr)return;
  const signature=JSON.stringify(tr.options);
  if(signature!==timelineSignature){
    timelineSignature=signature;
    const scale=tr.end_time;
    $('timeline').innerHTML=[...tr.machines.map(x=>[x.id,'machine']),...tr.workers.map(x=>[x.id,'worker'])].map(([id,kind])=>{
      const blocks=tr.tasks.filter(x=>x[kind]===id&&x.assigned<scale).map(x=>{
        const left=x.start/scale*100,width=(Math.min(x.end,scale)-x.start)/scale*100;
        const walk=x.walking>0?`<div class="time-block walk-block" style="--job:${color(x.job)};left:${x.assigned/scale*100}%;width:${Math.max(0,Math.min(x.start,scale)-x.assigned)/scale*100}%" title="${kind==='machine'?'שמירה לעובד שבדרך':'הליכה'} · ${x.job}"></div>`:'';
        return walk+(width>0?`<div class="time-block" style="--job:${color(x.job)};left:${left}%;width:${width}%" title="${x.job} · ${fmtTime(x.start)}–${fmtTime(x.end)}">${x.job}</div>`:'');
      }).join('');
      return `<div class="timeline-row"><span class="timeline-label">${id}</span><div class="timeline-track">${blocks}<span class="time-marker"></span></div></div>`;
    }).join('')+`<div class="timeline-ticks">${[0,.25,.5,.75,1].map(f=>`<span>${fmt(scale*f)}</span>`).join('')}</div>`;
  }
  document.querySelectorAll('.time-marker').forEach(el=>el.style.left=`${Math.min(99.7,state.time/tr.end_time*100)}%`);
}

function startBatch(){
  if(!state.trace||state.batchRunning||state.dirty)return;
  const count=Number($('replications').value);
  if(!Number.isInteger(count)||count<1||count>500){showError('בחר מספר שלם של רפליקציות בין 1 ל־500.');return;}
  state.batchRunning=true;state.batch=null;$('batchResults').classList.add('hidden');$('batchButton').disabled=true;
  $('cancelBatch').classList.remove('hidden');$('batchProgress').classList.remove('hidden');$('batchProgress').textContent='מתחיל ניסוי…';
  worker.postMessage({type:'batch',id:++state.batchId,count,options:state.trace.options});
}
function finishBatch(){state.batchRunning=false;$('batchButton').disabled=state.dirty||!state.trace;$('cancelBatch').classList.add('hidden');$('batchProgress').classList.add('hidden');}
function renderBatch(){
  const batch=state.batch;if(!batch)return;
  const values=batch.results.filter(r=>r.complete).map(r=>r.mean_flow),n=values.length;
  const mean=n?values.reduce((a,b)=>a+b,0)/n:null,sd=n>1?Math.sqrt(values.reduce((a,b)=>a+(b-mean)**2,0)/(n-1)):null;
  const min=n?Math.min(...values):0,max=n?Math.max(...values):1;
  const policy={fifo:'סדר קבוע',spt:'פעולה קצרה',edd:'מועד יעד קרוב'}[batch.options.policy];
  let html=`<p class="batch-title">${batch.results.length} הרצות · ${policy}<br>זרע ראשון ${batch.options.seed} · שונות ±${Math.round(batch.options.variation*100)}% · הליכה ${batch.options.walking?'פעילה':'כבויה'}</p>`;
  if(n<batch.results.length)html+=`<p class="batch-warning">ב־${batch.results.length-n} הרצות אופק הזמן הסתיים לפני השלמת כל המנות. אין מדד סופי להרצות האלה; הנתונים הבאים מתייחסים רק ל־${n} ההרצות המלאות, ואינם אומדן לכל ההרצות.</p>`;
  html+=`<div class="batch-stats"><div class="batch-stat"><span>זמן שהייה ממוצע</span><strong>${mean===null?'—':fmt(mean)}</strong></div><div class="batch-stat"><span>סטיית תקן בין הרצות</span><strong>${sd===null?'—':fmt(sd,2)}</strong></div><div class="batch-stat"><span>מינימום · דקות</span><strong>${n?fmt(min):'—'}</strong></div><div class="batch-stat"><span>מקסימום · דקות</span><strong>${n?fmt(max):'—'}</strong></div></div>`;
  if(n)html+=`<div class="mini-chart" aria-label="זמן שהייה ממוצע לכל רפליקציה מלאה">${values.slice(0,80).map((v,i)=>`<div class="mini-bar" title="רפליקציה ${batch.results.filter(r=>r.complete)[i].replication}: ${fmt(v)} דקות" style="height:${Math.max(5,v/max*100)}%"></div>`).join('')}</div><p class="small-note">${n>80?'מוצגות 80 ההרצות המלאות הראשונות.':'כל עמודה מייצגת הרצה מלאה.'} היחידות: דקות.</p>`;
  html+=`<label class="field" style="margin-top:16px" for="replayReplication">צפייה ברפליקציה<select id="replayReplication">${batch.results.map(r=>`<option value="${r.replication-1}">הרצה ${r.replication} · זרע ${r.seed}${r.complete?'':' · חלקית'}</option>`).join('')}</select></label><button class="secondary wide" id="replayButton">טען לצפייה ברצפת הייצור</button><button class="secondary wide" id="exportBatch">הורדת תוצאות CSV</button>`;
  $('batchResults').innerHTML=html;$('batchResults').classList.remove('hidden');$('exportBatch').addEventListener('click',exportBatch);
  $('replayButton').addEventListener('click',()=>{
    const row=batch.results[Number($('replayReplication').value)];
    if(!row)return;
    const options={...batch.options,seed:row.seed};
    $('policy').value=options.policy;$('horizon').value=options.horizon;$('seed').value=options.seed;
    $('walking').checked=options.walking;$('randomness').checked=options.variation>0;
    $('variation').value=options.variation*100;$('variationLabel').textContent=`±${Math.round(options.variation*100)}%`;$('variation').disabled=options.variation===0;
    state.playing=false;state.dirty=false;$('configNotice').classList.add('hidden');
    worker.postMessage({type:'simulate',options,id:++state.request});
    $('floor').scrollIntoView({behavior:'smooth',block:'center'});
  });
}
function exportBatch(){
  if(!state.batch)return;
  const rows=['replication,seed,policy,walking,variation,horizon,completed,complete,mean_flow_minutes,makespan_minutes,total_tardiness_minutes'];
  for(const r of state.batch.results)rows.push([r.replication,r.seed,state.batch.options.policy,state.batch.options.walking,state.batch.options.variation,state.batch.options.horizon,r.completed,r.complete,r.mean_flow??'',r.makespan??'',r.total_tardiness].join(','));
  const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.join('\n')],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='printflow-replications.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

// The following canvas is an operational floor diagram. All motion follows
// Python task timestamps and route coordinates, including while scrubbing.
function rect(x,y,w,h,r=0,fill,stroke){
  ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.stroke();}
}
function text(s,x,y,size=16,fill='#a2b3c9',align='center',weight='400'){
  ctx.font=`${weight} ${size}px "Segoe UI", Arial, sans-serif`;ctx.fillStyle=fill;ctx.textAlign=align;ctx.textBaseline='middle';ctx.direction='rtl';ctx.fillText(s,x,y);
}
function line(points,stroke,width=1,dash=[]){ctx.beginPath();ctx.lineWidth=width;ctx.strokeStyle=stroke;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();ctx.setLineDash([]);ctx.lineWidth=1;}
function circle(x,y,r,fill,stroke){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.stroke();}}
function drawMachine(m){
  const [x,y]=m.position,d=machineDescription(m),isPrint=m.kind==='print',w=isPrint?210:230,h=isPrint?116:88;
  const tint=d.phase==='work'?'#2dd4bf':d.phase==='walk'?'#fbbf24':'#637d99';
  if(state.selected===m.id||state.hover===m.id){rect(x-w/2-9,y-h/2-9,w+18,h+18,14,null,'#2dd4bf');}
  ctx.shadowColor='#0006';ctx.shadowBlur=16;ctx.shadowOffsetY=8;
  rect(x-w/2,y-h/2,w,h,12,'#22384e','#4c667e');ctx.shadowBlur=0;ctx.shadowOffsetY=0;
  rect(x-w/2+4,y-h/2+4,w-8,16,8,'#344f67');
  if(isPrint){
    rect(x-78,y-23,92,45,5,'#0b1726','#456077');
    for(let i=0;i<5;i++){
      const pulse=d.phase==='work'?((state.time*10+i*.2)%1):.1;
      rect(x-70+i*15,y-16,10,30,3,`rgba(45,212,191,${.12+pulse*.24})`);
    }
    rect(x+25,y-21,52,36,5,'#0c1d2d','#476078');
    text(d.task?d.task.job:'—',x+51,y-5,22,d.task?color(d.task.job):'#68819c','center','600');
    rect(x-65,y+35,127,15,3,'#0a1420','#40576f');
    if(d.phase==='work'){
      const p=(state.time*5)%1;
      rect(x-39,y+36+p*16,78,15,2,'#ccdce7');
      line([[x-26,y+42+p*16],[x+22,y+42+p*16]],color(d.task.job),2);
    }
    circle(x+89,y+39,4,tint);
  }else{
    rect(x-82,y-19,97,43,4,'#0d1c2b','#456078');
    const moving=d.phase==='work'?Math.sin(state.time*12)*8:0;
    rect(x-65,y-13+moving,67,17,3,'#8da8bb');
    if(d.phase==='work')rect(x-55,y+15,49,8,2,color(d.task.job));
    rect(x+37,y-18,48,37,4,'#0d1c2b','#456078');text(d.task?d.task.job:'—',x+60,y,20,d.task?color(d.task.job):'#68819c');
    circle(x+98,y+27,4,tint);
  }
  text(m.name,x,y-h/2-26,19,'#e1ebf6','center','500');
  text(m.id,x-w/2+25,y-h/2+13,12,'#b7cbe0','center','600');
  if(d.task){
    const p=d.phase==='work'?progressAt(d.task,state.time):0;
    rect(x-w/2,y+h/2+12,w,5,3,'#263c51');if(p>0)rect(x-w/2,y+h/2+12,w*p,5,3,color(d.task.job));
    text(d.phase==='work'?`${d.label} · ${Math.floor(p*100)}%`:`${d.task.worker} בדרך`,x,y+h/2+35,15,tint);
  }else text('פנויה',x,y+h/2+27,15,'#7e96af');
  ctx.save();ctx.setLineDash([4,4]);circle(...m.dock,17,null,'#38536a');ctx.restore();
}
function drawWorker(w){
  const tr=state.trace,d=workerDescription(w),p=tr?workerPosition(tr,w,state.time):w.home;
  if(d.phase==='walk'){
    line(d.task.path,w.color+'66',2,[5,7]);
  }
  const x=p[0],y=p[1];
  if(state.hover===w.id||state.selected===w.id)circle(x,y,27,null,w.color);
  ctx.save();ctx.translate(x,y);ctx.shadowColor='#0008';ctx.shadowBlur=8;ctx.shadowOffsetY=4;
  const stride=d.phase==='walk'?Math.sin(state.time*24)*7:0;
  line([[-5,7],[-6,18+stride]],'#7d95af',5);line([[5,7],[6,18-stride]],'#7d95af',5);
  circle(0,0,14,w.color);ctx.shadowBlur=0;ctx.shadowOffsetY=0;
  line([[-11,0],[-18,7-stride/2]],w.color,5);line([[11,0],[18,7+stride/2]],w.color,5);
  circle(0,-12,8,'#e4c4a6','#213548');
  ctx.restore();
  rect(x-21,y+27,42,22,5,'#091521',w.color+'77');text(w.id,x,y+38,13,w.color,'center','600');
  if(d.task){circle(x+22,y-18,11,color(d.task.job));text(d.task.job,x+22,y-18,12,'#0a1726','center','700');}
}
function draw(){
  const width=canvas.clientWidth;if(!width)return;
  const dpr=Math.min(window.devicePixelRatio||1,2),height=width*560/900;
  const targetW=Math.round(width*dpr),targetH=Math.round(height*dpr);
  if(canvas.width!==targetW||canvas.height!==targetH){canvas.width=targetW;canvas.height=targetH;}
  ctx.setTransform(targetW/900,0,0,targetH/560,0,0);ctx.clearRect(0,0,900,560);
  rect(0,0,900,560,0,'#0d1725');
  for(let x=20;x<900;x+=25)for(let y=20;y<560;y+=25)circle(x,y,.7,'#213146');
  rect(28,27,844,500,17,'#102031','#2a4157');
  rect(42,41,816,254,10,'#142536');rect(42,376,816,137,10,'#142536');
  rect(43,304,814,53,0,'#192e3d');
  line([[50,303],[850,303]],'#4b684a',1,[14,12]);line([[50,358],[850,358]],'#4b684a',1,[14,12]);
  for(let x=100;x<830;x+=130){line([[x,328],[x+20,328]],'#3a5363',2);line([[x+13,322],[x+20,328],[x+13,334]],'#3a5363',2);}
  text('אזור הדפסה',810,65,16,'#718aa4','right');text('כריכה וגימור',808,402,16,'#718aa4','right');
  text('כניסת עבודות',107,74,15,'#9aafc3');
  const tr=state.trace;
  current().jobs.forEach((j,i)=>{
    const done=tr&&tr.completions[j.id]<=state.time+1e-7;
    const processing=tr&&activeTask(tr,'job',j.id,state.time);
    const opacity=done?.15:processing?.35:1;
    ctx.globalAlpha=opacity;rect(72,98+i*37,72,27,5,'#1c3044',j.color+'77');
    rect(79,105+i*37,13,14,2,j.color);text(j.id,114,112+i*37,15,j.color,'center','600');ctx.globalAlpha=1;
  });
  text('עבודות שהושלמו',165,412,15,'#9aafc3');
  if(tr){
    const done=tr.jobs.filter(j=>tr.completions[j.id]<=state.time+1e-7);
    done.forEach((j,i)=>{rect(80+i*46,442,35,35,6,'#1c3044',j.color);text(j.id,97+i*46,460,17,j.color,'center','600');});
    if(!done.length)text('—',165,457,24,'#385069');
  }
  current().machines.forEach(drawMachine);current().workers.forEach(drawWorker);
  text('מעבר עובדים',827,332,12,'#7192a4','right');
  text('תצוגה סכמטית · מסלולי תנועה קבועים',860,544,12,'#688198','right');
}
function objectAt(event){
  const r=canvas.getBoundingClientRect(),x=(event.clientX-r.left)*900/r.width,y=(event.clientY-r.top)*560/r.height;
  for(const w of current().workers){const p=state.trace?workerPosition(state.trace,w,state.time):w.home;if(Math.hypot(x-p[0],y-p[1])<30)return {id:w.id,name:w.name,detail:workerDescription(w).detail};}
  for(const m of current().machines){const [mx,my]=m.position;if(Math.abs(x-mx)<120&&Math.abs(y-my)<70)return {id:m.id,name:m.name,detail:machineDescription(m).detail};}
  return null;
}
canvas.addEventListener('pointermove',e=>{
  const hit=objectAt(e);state.hover=hit?.id||null;canvas.style.cursor=hit?'pointer':'default';
  if(hit){const r=canvas.getBoundingClientRect();$('floorTip').textContent=`${hit.id} · ${hit.detail}`;$('floorTip').classList.remove('hidden');$('floorTip').style.left=Math.max(8,Math.min(r.width-220,e.clientX-r.left-100))+'px';$('floorTip').style.top=Math.max(8,e.clientY-r.top-55)+'px';}
  else $('floorTip').classList.add('hidden');
});
canvas.addEventListener('pointerleave',()=>{state.hover=null;$('floorTip').classList.add('hidden');});
canvas.addEventListener('click',e=>{const hit=objectAt(e);if(hit){state.selected=hit.id;setTab('resources');}});
$('playButton').addEventListener('click',togglePlay);$('stepButton').addEventListener('click',nextEvent);
$('resetButton').addEventListener('click',()=>{state.playing=false;setTime(0);});
$('seek').addEventListener('input',e=>{state.playing=false;setTime(Number(e.target.value));});
$('applyButton').addEventListener('click',applySettings);$('batchButton').addEventListener('click',startBatch);
$('cancelBatch').addEventListener('click',()=>worker.postMessage({type:'cancel'}));
$('retryButton').addEventListener('click',initWorker);
for(const id of ['policy','horizon','seed','walking','randomness','variation'])$(id).addEventListener('input',markDirty);
$('randomness').addEventListener('change',()=>{$('variation').disabled=!$('randomness').checked;});
$('variation').addEventListener('input',()=>{$('variationLabel').textContent=`±${$('variation').value}%`;});
document.querySelectorAll('[data-tab]').forEach(b=>{
  b.addEventListener('click',()=>setTab(b.dataset.tab));
  b.addEventListener('keydown',e=>{const tabs=['jobs','resources','experiments'],i=tabs.indexOf(state.tab);if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();const next=tabs[(i+(e.key==='ArrowLeft'?1:2))%3];setTab(next);$(next+'Tab').focus();}});
});
$('helpButton').addEventListener('click',()=>$('helpDialog').showModal());$('closeHelp').addEventListener('click',()=>$('helpDialog').close());
document.addEventListener('keydown',e=>{if(e.code==='Space'&&!['INPUT','SELECT','BUTTON','TEXTAREA','A'].includes(e.target.tagName)&&!$('helpDialog').open){e.preventDefault();togglePlay();}});
document.addEventListener('visibilitychange',()=>{lastFrame=0;});
function frame(now){
  const delta=lastFrame?Math.min((now-lastFrame)/1000,.25):0;lastFrame=now;
  if(state.playing&&state.trace){state.time=Math.min(state.trace.end_time,state.time+delta*Number($('speed').value)/60);$('seek').value=state.time;if(state.time>=state.trace.end_time-1e-7)state.playing=false;}
  draw();if(now-lastUI>120){renderUI();lastUI=now;}requestAnimationFrame(frame);
}
initWorker();requestAnimationFrame(frame);
