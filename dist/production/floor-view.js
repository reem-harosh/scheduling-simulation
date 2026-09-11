'use strict';
// Rendering only. Coordinates and replay quantities remain supplied by the DES.
const floorTheme={background:'#101c29',machine:'#1a2b3d',border:'#344b60',ink:'#e4edf5',muted:'#93a8bb',parts:'#e5c69b',worker:'#75baff',setup:'#bcabf1'};
let focusedStation=null,stationSignature='',workerDrawPositions=new Map(),workerVisuals=new Map(),visualClock=0;
const machineFamilies={Milling:{color:'#60a5fa',name:'כרסום · Milling'},Turning:{color:'#fb923c',name:'חריטה · Turning'},Honing:{color:'#c084fc',name:'השחזה · Honing'},WireEDM:{color:'#f472b6',name:'חיתוך חוט · WireEDM'}};
function machineFamilyColor(m){return machineFamilies[m.machine_family||m.department]?.color||'#94a3b8'}
const spriteBounds=[[160, 26, 154, 415], [566, 29, 239, 405], [1032, 29, 158, 413], [1439, 29, 235, 406], [114, 532, 217, 263], [530, 506, 260, 306], [967, 517, 260, 284], [1351, 500, 397, 333]];
const spriteCache=[];
const decorativeMotion=typeof matchMedia==='undefined'||!matchMedia('(prefers-reduced-motion: reduce)').matches;
if(typeof Image!=='undefined'){const atlas=new Image();atlas.onload=()=>{for(const b of spriteBounds){const c=document.createElement('canvas');c.width=96;c.height=128;const ctx=c.getContext('2d');const scale=Math.min(96/b[2],128/b[3]);ctx.drawImage(atlas,...b,(96-b[2]*scale)/2,(128-b[3]*scale)/2,b[2]*scale,b[3]*scale);spriteCache.push(c)}if(typeof result!=='undefined')drawFloor()};atlas.src='assets/factory-sprites.png'}
function sprite(ctx,index,x,y,w,h,flip=false){const cached=spriteCache[index];if(!cached)return false;ctx.save();ctx.translate(x,y);if(flip)ctx.scale(-1,1);ctx.drawImage(cached,-w/2,-h/2,w,h);ctx.restore();return true}
function familyShape(job){const family=result?.jobs.find(j=>j.id===job)?.item||'';const n=Number(family.match(/\d+/)?.[0])||1;return 4+(n-1)%3}
function spriteHTML(index,extra=''){return '<span class="atlas-sprite sprite-'+index+' '+extra+'" aria-hidden="true"></span>'}
function roundBox(ctx,x,y,w,h,r,fill,stroke){ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill()}if(stroke){ctx.strokeStyle=stroke;ctx.stroke()}}
function personGlyph(ctx,x,y,size,color){
 ctx.fillStyle=color;ctx.beginPath();ctx.arc(x,y-size*.28,size*.21,0,Math.PI*2);ctx.fill();
 ctx.beginPath();ctx.moveTo(x-size*.43,y+size*.43);ctx.quadraticCurveTo(x-size*.43,y,x,y);ctx.quadraticCurveTo(x+size*.43,y,x+size*.43,y+size*.43);ctx.closePath();ctx.fill();
}
function partGlyph(ctx,x,y,size,color){
 ctx.strokeStyle=color;ctx.lineWidth=1.8;
 for(const [dx,dy] of [[-.32,.19],[.32,.19],[0,-.34]]){ctx.beginPath();ctx.arc(x+dx*size,y+dy*size,size*.21,0,Math.PI*2);ctx.stroke()}
}
function partLegendIcon(){return '<svg viewBox="0 0 28 28" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="9" cy="17" r="4"/><circle cx="19" cy="17" r="4"/><circle cx="14" cy="8" r="4"/></g></svg>'}
function workerLegendIcon(){return '<svg viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="8" r="4" fill="currentColor"/><path d="M5 25v-4a9 9 0 0 1 18 0v4" fill="currentColor"/></svg>'}
function relevantStation(){
 if(selected?.type==='machines')return selected.id;
 if(selected?.type==='workers'){const i=intervalAt(selected.id);if(i?.machine)return i.machine;const owned=materialReplay?.rows(time).find(b=>b.owner===selected.id&&b.machine);if(owned)return owned.machine}
 if(selected?.type==='jobs'||selected?.type==='batches'){
  const row=materialReplay?.rows(time).find(b=>selected.type==='jobs'?b.job===selected.id:b.id===selected.id);
  if(row)return row.machine||(!row.location?.startsWith('@')?row.location:null);
 }
 if(focusedStation&&machineLayout.some(m=>m.id===focusedStation))return focusedStation;
 return machineLayout.find(m=>isWorking(intervalAt(m.id)?.state))?.id||null;
}
function renderFloorScene(){
 const canvas=$('floor'),tr=transform(),ctx=canvas.getContext('2d'),xy=p=>[tr.x+p[0]*tr.scale,tr.y+p[1]*tr.scale];
 const mid=relevantStation();focusedStation=mid;
 ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle=floorTheme.background;ctx.fillRect(0,0,canvas.width,canvas.height);hitboxes=[];
 // Sparse grid supports the spatial map without competing with material/people.
 ctx.strokeStyle='#1b2d3d';ctx.lineWidth=.5;
 for(let x=30;x<canvas.width;x+=80){ctx.beginPath();ctx.moveTo(x,58);ctx.lineTo(x,canvas.height-25);ctx.stroke()}
 for(let y=68;y<canvas.height;y+=80){ctx.beginPath();ctx.moveTo(25,y);ctx.lineTo(canvas.width-25,y);ctx.stroke()}
 ctx.fillStyle=floorTheme.muted;ctx.font='18px Segoe UI';ctx.textAlign='right';ctx.fillText('מפת התמצאות · לחצו על תחנה להגדלה ולפירוט',canvas.width-34,32);
 // Machine rectangles are the only rectangular entities on the map.
 for(const m of machineLayout){
  const [x,y]=xy([m.x,m.y]),w=m.w*tr.scale,h=m.h*tr.scale,i=intervalAt(m.id),active=isWorking(i?.state),chosen=m.id===mid;
  const family=machineFamilyColor(m),status=active?(colors[i.state]||'#fbbf24'):floorTheme.border;
  ctx.lineWidth=chosen?3:1.8;roundBox(ctx,x,y,w,h,5,family+(chosen?'55':'28'),chosen?'#ffffff':family);
  ctx.fillStyle=family;ctx.fillRect(x+4,y+5,4,Math.max(4,h-10));
  if(active){ctx.fillStyle=status;ctx.fillRect(x+11,y+5,Math.max(2,w-17),4)}
  ctx.fillStyle=active||chosen?floorTheme.ink:'#9bb0c3';ctx.font='bold 19px Consolas';ctx.textAlign='center';ctx.fillText(m.id,x+w/2,y+h/2+7);
  hitboxes.push({x,y,w,h,type:'machines',id:m.id});
 }
 const workers=liveData?.workers||result?.workers||[];
 buildWorkerVisuals(workers,xy);
 drawWorkerLinks(ctx,xy,mid,workers);
 drawPartMarkers(ctx,xy,mid);
 const foreground=w=>(isWorking(intervalAt(w.id)?.state)?1:0)+(workerVisuals.get(w.id)?.cargo.length?2:0)+(selected?.id===w.id?4:0);
 for(const w of [...workers].sort((a,b)=>foreground(a)-foreground(b))){
  const pose=workerVisuals.get(w.id);if(!pose)continue;
  const {x,y,bob,flip,moving}=pose,i=intervalAt(w.id),active=isWorking(i.state),setup=w.kind?.startsWith('setup'),chosen=selected?.id===w.id;
  ctx.globalAlpha=active||chosen?1:.55;
  const step=moving&&decorativeMotion?Math.floor(visualClock*4)%2:0;
  if(chosen){ctx.lineWidth=2;ctx.strokeStyle='#b7d8ef';ctx.beginPath();ctx.ellipse(x,y+12,18,6,0,0,Math.PI*2);ctx.stroke()}
  if(!sprite(ctx,(setup?2:0)+step,x,y-9+bob,38,51,flip))personGlyph(ctx,x,y,23,setup?floorTheme.setup:floorTheme.worker);
  ctx.globalAlpha=1;
  drawWorkerCargo(ctx,w,pose);
  if(chosen||pose.cargo.length){
   ctx.fillStyle=floorTheme.ink;ctx.font='15px Segoe UI';ctx.textAlign='center';
   ctx.fillText(workerName(w.id),x,y-41);
  }
  hitboxes.push({x:x-18,y:y-36,w:36,h:54,type:'workers',id:w.id});
 }
 renderStationDetail(mid);renderTransportActivity();
}
// A single pose drives both the person and the load. No independent cargo tween.
function mixPoint(a,b,t){t=Math.max(0,Math.min(1,t));return[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t]}
function manualServicePose(row,interval,base,xy){
 const m=machineLayout.find(m=>m.id===row.machine);if(!m)return null;
 const f=Math.max(0,Math.min(1,(time-interval.start)/(interval.end-interval.start||1)));
 const loading=interval.state==='LOADING'||(interval.state==='CYCLE_CHANGE'&&f>=.5);
 const phase=interval.state==='CYCLE_CHANGE'?(f<.5?f*2:(f-.5)*2):f;
 const segment=visualSegments(row).find(s=>s.state===(loading?(interval.state==='CYCLE_CHANGE'?'CYCLE_LOADING':'LOADING'):interval.state));
 if(!segment)return null;
 const tr=transform(),[mx,my]=xy([m.x,m.y]);
 const inside=[mx+m.w*tr.scale/2,my+m.h*tr.scale-8];
 const outside=[mx+(loading?-18:m.w*tr.scale+18),my+m.h*tr.scale+13];
 const source=loading?outside:inside,target=loading?inside:outside;
 // The hand sits eight pixels in front of the torso. Move the person to reach
 // each endpoint; never stretch a line from a stationary person to a flying part.
 const sourceBody=[source[0]-8,source[1]+6],targetBody=[target[0]-8,target[1]+6];
 let body,attached=false,part;
 if(phase<.2){body=mixPoint(base,sourceBody,phase/.2);part=source}
 else if(phase<.75){body=mixPoint(sourceBody,targetBody,(phase-.2)/.55);attached=true}
 else if(phase<.85){body=targetBody;part=target}
 else{body=mixPoint(targetBody,base,(phase-.85)/.15);part=target}
 return{body,part,attached,segment,job:row.job,batch:row.id,phase,loading,moving:phase<.75||phase>=.85};
}
function buildWorkerVisuals(workers,xy){
 workerDrawPositions=new Map();workerVisuals=new Map();
 const rows=liveData?[]:materialReplay?.rows(time)||[];
 for(const w of workers){
  const i=intervalAt(w.id),p=position(i);if(!p||i.state==='OFF_SHIFT')continue;
  const [px,py]=xy(p),base=[px-10,py-16];let body=base,handling=null;
  const cargo=rows.flatMap(b=>b.segments.filter(s=>s.worker===w.id&&i.state==='CARRYING').map(s=>({...s,job:b.job,batch:b.id})));
  if(['LOADING','UNLOADING','CYCLE_CHANGE'].includes(i.state)){
   const row=rows.find(b=>b.machine===i.machine&&b.id===i.batch);
   const service=row&&intervalAt(row.machine);
   if(service?.worker===w.id&&service.state===i.state){handling=manualServicePose(row,service,base,xy);if(handling)body=handling.body}
  }
  let moving=['WALKING','CARRYING'].includes(i.state)||!!handling?.moving;
  // For walking, face the current path leg, including corners and return trips.
  const ahead=position(i,Math.min(i.end-1e-9,time+1e-5));
  const flip=!handling&&!!ahead&&ahead[0]<p[0];
  const bob=moving&&decorativeMotion?Math.sin(visualClock*8)*1.2:0;
  const pose={x:body[0],y:body[1],flip,bob,moving,cargo,handling,hand:[body[0]+(flip?-8:8),body[1]-6+bob]};
  if(handling?.attached)pose.cargo.push({...handling.segment,job:handling.job,batch:handling.batch,manual:true});
  workerVisuals.set(w.id,pose);workerDrawPositions.set(w.id,body);
 }
}
function operationAssignments(worker){
 const rows=liveData?liveData.jobs.flatMap(j=>j.batches):materialReplay?.rows(time)||[];
 const assigned=new Map();
 for(const b of rows)if(b.owner===worker&&b.machine)assigned.set(b.machine,{owner:true,working:false});
 const i=intervalAt(worker);
 if(i?.machine&&isWorking(i.state))assigned.set(i.machine,{owner:assigned.get(i.machine)?.owner||false,working:true});
 return assigned;
}
function drawWorkerLinks(ctx,xy,mid,workers){
 for(const w of workers){
  const p=workerDrawPositions.get(w.id);if(!p)continue;
  for(const [id,link] of operationAssignments(w.id)){
   const m=machineLayout.find(m=>m.id===id);if(!m)continue;
   const highlighted=id===mid||selected?.id===w.id;
   const target=xy([m.x+m.w/2,m.y+m.h/2]);
   ctx.setLineDash(link.owner&&!link.working?[8,5]:[]);
   // A dark underlay keeps ownership legible over machines and queue labels.
   ctx.lineWidth=highlighted?5:4;ctx.strokeStyle='#081321';ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...target);ctx.stroke();
   ctx.lineWidth=highlighted?3:2;ctx.strokeStyle=link.owner?'#f6d365':'#8fd3ff';ctx.stroke();ctx.setLineDash([]);
  }
 }
}
function drawWorkerCargo(ctx,worker,pose){
 const cargo=pose.cargo,total=cargo.reduce((n,s)=>n+s.quantity,0);
 if(total){
  const [x,y]=pose.hand,index=total>1?7:familyShape(cargo[0].job);
  // Overlay the bin at the hands/waist, in the same transform and bob as its carrier.
  if(!sprite(ctx,index,x,y,total>1?24:18,total>1?27:22))partGlyph(ctx,x,y,16,floorTheme.parts);
  ctx.fillStyle='#102235';ctx.strokeStyle='#e5c69b';ctx.lineWidth=1;
  roundBox(ctx,pose.x-21,pose.y+16,42,21,6,'#102235','#e5c69b');
  ctx.fillStyle='#fff1d6';ctx.font='bold 15px Consolas';ctx.textAlign='center';ctx.fillText(String(total),pose.x,pose.y+31);
  hitboxes.push({x:x-14,y:y-14,w:28,h:28,type:'workers',id:worker.id,hint:'עובד '+worker.id+' נושא '+total+' חלקים'});
 }
 const h=pose.handling;
 if(h&&!h.attached&&h.part){
  const[x,y]=h.part;
  if(!sprite(ctx,familyShape(h.job),x,y,18,22))partGlyph(ctx,x,y,14,floorTheme.parts);
  hitboxes.push({x:x-12,y:y-12,w:24,h:24,type:'jobs',id:h.job,hint:(h.phase<.2?'איסוף':'הנחה')+' · '+h.segment.quantity+' חלקים'});
 }
}
function drawPartMarkers(ctx,xy,mid){
 if(!materialReplay||!result?.trace.material_version||liveData)return;
 const groups=new Map(),moving=[];
 // Aggregate authoritative ledger quantities separately from decorative handling poses.
 for(const row of materialReplay.rows(time))for(const s of row.segments){
  if(s.state==='COMPLETE'||s.worker||s.lift_start!=null)continue;
  const key=s.location||'pool';if(!groups.has(key))groups.set(key,{location:s.location,quantity:0,jobs:new Set()});
  const g=groups.get(key);g.quantity+=s.quantity;g.jobs.add(row.job);
 }
 for(const row of materialReplay.rows(time))for(const s of visualSegments(row)){
  if(s.state==='COMPLETE')continue;
  if(s.worker||s.lift_start!=null||['LOADING','CYCLE_LOADING','UNLOADING','CYCLE_CHANGE'].includes(s.state)){moving.push({row,s});continue}
  // Station counters already include this segment, including manually handled pieces.
 }
 const placed=machineLayout.map(m=>{const[x,y]=xy([m.x,m.y]);return{x,y,w:m.w*transform().scale,h:m.h*transform().scale}});let pool=0;
 // Locate summaries outside machine faces. Leaders retain the physical association.
 for(const g of groups.values()){
  const m=machineLayout.find(m=>m.id===g.location);let anchor;
  if(m)anchor=xy([m.x+m.w/2,m.y+m.h]);
  else if(g.location?.startsWith('@floor:'))anchor=xy(nodeCoords[result.trace.floor_handoff_nodes?.[g.location.split(':')[1]]]||[0,0]);
  else anchor=[100+pool++*125,transform().poolY];
  const width=m?122:70,height=m?58:29;let x=anchor[0]-width/2,y=anchor[1]+5;
  // Shift only the label; source coordinates and animation paths are untouched.
  const options=[];for(let dy=-120;dy<=120;dy+=30)for(let dx=-150;dx<=150;dx+=35)options.push({x:anchor[0]-width/2+dx,y:anchor[1]+5+dy,cost:dx*dx+dy*dy});
  options.sort((a,b)=>a.cost-b.cost);const free=options.find(p=>p.x>=18&&p.x+width<=1482&&p.y>=55&&p.y+height<=$('floor').height-10&&!placed.some(b=>p.x<b.x+b.w+3&&p.x+width>b.x-3&&p.y<b.y+b.h+3&&p.y+height>b.y-3));if(free){x=free.x;y=free.y}
  placed.push({x,y,w:width,h:height});ctx.lineWidth=1;ctx.strokeStyle='#c5a47480';ctx.beginPath();ctx.moveTo(...anchor);ctx.lineTo(x+width/2,y);ctx.stroke();
  ctx.lineWidth=m?.id===mid?2:1;roundBox(ctx,x,y,width,height,12,'#2b2c2b',m?.id===mid?'#f0d6ac':'#84745e');
  if(m){
   const c=stationCounts(m.id);
   ctx.font='12px Segoe UI';ctx.textAlign='center';
   for(const [offset,title,n,color] of [[21,'קלט',c.before,'#bfdbfe'],[61,'במכונה',c.inside,'#a7f3d0'],[101,'פלט',c.after,'#fbbf24']]){
    ctx.fillStyle=color;ctx.fillText(title,x+offset,y+13);if(n)sprite(ctx,n>1?7:familyShape([...g.jobs][0]),x+offset,y+29,22,24);ctx.fillStyle=color;ctx.font='bold 17px Consolas';ctx.fillText(String(n),x+offset,y+51);ctx.font='12px Segoe UI';
   }
  }else{if(!sprite(ctx,g.quantity>1?7:familyShape([...g.jobs][0]),x+16,y+14,31,33))partGlyph(ctx,x+13,y+13,17,floorTheme.parts);ctx.fillStyle='#f0dfc6';ctx.font='bold 17px Consolas';ctx.textAlign='center';ctx.fillText(String(g.quantity),x+43,y+18)}
  hitboxes.push({x,y,w:width,h:height,type:m?'machines':'jobs',id:m?m.id:[...g.jobs][0],hint:g.quantity+' חלקים · '+(g.location||'תור משותף')});
 }
 for(const {row,s} of moving){
  if(s.worker)continue; // Drawn once, attached to the carrier's person symbol.
  if(s.lift_start!=null){drawLift(ctx,s,row,xy);continue}
  // Manual pieces are drawn by the actual service worker's pose above.
  // A trace without an actor remains at the station; never invent a carrier.
  const actor=intervalAt(s.location)?.worker;
  if(workerVisuals.get(actor)?.handling)continue;
  const m=machineLayout.find(m=>m.id===s.location);if(!m)continue;
  const[x,y]=xy([m.x+m.w/2,m.y+m.h/2]);
  if(!sprite(ctx,familyShape(row.job),x,y,18,22))partGlyph(ctx,x,y,14,floorTheme.parts);
 }
}
function stationCounts(mid){
 const counts={before:0,inside:0,after:0,transit:0},jobs=new Set(),rows=materialReplay?.rows(time)||[];
 for(const b of rows)for(const s of b.segments){
  if(s.state==='COMPLETE')continue;
  if(s.location===mid){jobs.add(b.job);
   if(b.machine!==mid||s.state==='OUTPUT')counts.after+=s.quantity;
   else if(['WAITING_INPUT','WAITING_TRANSPORT','LOADING'].includes(s.state))counts.before+=s.quantity;
   else counts.inside+=s.quantity;
  }else if(b.machine===mid){jobs.add(b.job);counts.transit+=s.quantity}
 }
 return{...counts,jobs:[...jobs]};
}
function renderStationDetail(mid){
 const host=$('stationDetail');if(!host)return;
 const m=machineLayout.find(m=>m.id===mid);if(!m||!result){host.innerHTML='<p class="station-empty">בחרו מכונה במפה כדי לראות את החלקים והעובד בתחנה.</p>';return}
 const c=stationCounts(mid),i=intervalAt(mid),row=materialReplay?.rows(time).find(b=>b.machine===mid),person=i?.worker||row?.owner;
 const personActive=person&&intervalAt(person)?.state!=='OFF_SHIFT';
 const finished=materialReplay?.completedAt(mid,time);
 const operation=row?.operation||'';
 const signature=JSON.stringify([mid,c,i?.state,person,personActive,selected?.id,operation,finished]);
 if(signature!==stationSignature){stationSignature=signature;
  const shape=familyShape(c.jobs[0]);
  const zone=(type,title,n,note)=>`<div class="station-zone ${type}"><span class="zone-label">${title}</span><div class="zone-pile ${type}" aria-hidden="true">${Array.from({length:Math.min(n,type==='machine'?1:4)},(_,k)=>spriteHTML(shape,'pile-item pile-'+k)).join('')}</div><div class="zone-quantity"><strong>${n}</strong><span>חלקים</span></div><small>${note}</small></div>`;
  host.innerHTML=`<div class="station-heading"><div><span class="station-kicker">מבט מוגדל בתחנה</span><h3><bdi>${escape(mid)}</bdi> <span>${escape(m.machine_family||m.department)}</span></h3><p class="station-operation">${row?'עבודה <bdi>'+escape(row.job)+'</bdi> · פעולה <bdi>'+escape(operation)+'</bdi>':''}</p></div><span class="station-status">${escape(labels[i?.state]||'פנויה')}</span></div><div class="station-flow" dir="ltr">${zone('input','לפני טעינה',c.before,'ממתינים לצד המכונה')}<div class="station-transfer loading" aria-hidden="true"><span>→</span><i></i></div>${zone('machine','בתוך המכונה',c.inside,'בעיבוד או ממתינים לפריקה')}<div class="station-transfer unloading" aria-hidden="true"><span>→</span><i></i></div>${zone('output','אחרי פריקה',c.after,'סיימו כאן; ממתינים לשינוע או לפעולה הבאה')}</div><p class="station-completion">${finished?'הושלמו בפעולה האחרונה ויצאו מהמערכת: <b>'+finished.total+'</b> חלקים בחלון השחזור.':''}</p><p class="station-operation">הכמויות מתעדכנות בסיום הטיפול. בפעולה חדשה הקלט מתייחס לעבודה ולפעולה המצוינות למעלה.</p><div class="station-footer"><div class="station-person">${personActive?spriteHTML(result.workers.find(w=>w.id===person)?.kind?.startsWith('setup')?2:0,'station-worker'):workerLegendIcon()}<span>${personActive?(i?.worker?'מטפל כעת':'אחראי על המנה'):'אין עובד מטפל כעת'}${personActive?'<b dir="ltr">'+escape(workerName(person))+'</b>':''}</span></div><span class="station-inbound">${c.transit?'בדרך לתחנה / במקור: '+c.transit+' חלקים':''}</span><div class="station-job-links">${c.jobs.map(j=>`<button data-station-job="${escape(j)}">${spriteHTML(familyShape(j),'family-thumb')}<bdi>${escape(result.jobs.find(x=>x.id===j)?.item||'')}</bdi> · עבודה <bdi>${escape(j)}</bdi> ↗</button>`).join('')}</div></div>`;
  for(const b of host.querySelectorAll('[data-station-job]'))b.onclick=()=>select('jobs',b.dataset.stationJob);
 }
 const phase=i&&['LOADING','UNLOADING','CYCLE_CHANGE'].includes(i.state)?Math.max(0,Math.min(1,(time-i.start)/(i.end-i.start||1))):0;
 host.dataset.activity=i?.state||'IDLE_AVAILABLE';host.style.setProperty('--service-phase',String(phase));
}

function drawLift(ctx,s,row,xy){
 const p=materialPosition(s,row,xy);if(!p)return;const[x,y]=p;
 ctx.lineWidth=1.4;roundBox(ctx,x-24,y-14,132,30,6,'#273447','#c4b9df');
 ctx.fillStyle='#e1d9ee';ctx.font='16px Segoe UI';ctx.textAlign='center';ctx.fillText((time<s.lift_start?'המתנה למעלית · ':'↕ מעלית · ')+s.quantity,x+41,y+6);
 hitboxes.push({x:x-24,y:y-14,w:132,h:30,type:'jobs',id:row.job,hint:'מעלית משא · '+s.quantity+' חלקים'});
}

let transportSignature='';
function workerName(id){if(/^S\d+/.test(id))return 'הכנה '+id;const tail=id.match(/(day|night)(\d+)$/);if(!tail)return id;return (id.includes('milling')?'כרסום':id.includes('turning')?'חריטה':'מפעיל')+' · '+(tail[1]==='day'?'יום ':'לילה ')+tail[2]}
function renderTransportActivity(){
 const host=$('transportActivity');if(!host)return;
 const tasks=[];
 for(const w of result?.workers||[]){const i=intervalAt(w.id);if(!i||!['CARRYING','LOADING','UNLOADING','CYCLE_CHANGE'].includes(i.state))continue;
  const rows=materialReplay?.rows(time)||[];
  const carried=rows.flatMap(b=>b.segments.filter(s=>s.worker===w.id).map(s=>({...s,job:b.job})));
  const n=carried.reduce((n,s)=>n+s.quantity,0);const job=carried[0]?.job||i.job;
  if(i.state==='CARRYING'&&!n)continue;
  tasks.push({worker:w.id,state:i.state,job,quantity:n,machine:i.machine,setup:w.kind.startsWith('setup')});
 }
 const key=JSON.stringify(tasks);if(key===transportSignature)return;transportSignature=key;
 host.innerHTML=tasks.length?'<strong>מי מטפל בחלקים כעת</strong>'+tasks.map(t=>`<button data-carrier="${escape(t.worker)}">${spriteHTML(t.setup?2:0)}<span><bdi>${escape(workerName(t.worker))}</bdi> · ${escape(labels[t.state])}${t.quantity?' · '+t.quantity+' חלקים':''}<small>${escape(t.job||'')}${t.machine?' → '+escape(t.machine):''}</small></span></button>`).join(''):'';
 for(const b of host.querySelectorAll('[data-carrier]'))b.onclick=()=>select('workers',b.dataset.carrier);
}
