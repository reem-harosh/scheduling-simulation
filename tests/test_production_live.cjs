// Execute production UI data paths with a minimal DOM/canvas adapter.
// This verifies data/render contracts, not browser layout or pointer behavior.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const createCanvas=(width,height)=>({width,height,getContext:()=>new Proxy({},{get:(o,k)=>o[k]||((...args)=>{for(const a of args)if(typeof a==='number')assert(Number.isFinite(a),'Nonfinite canvas coordinate')})})});
const elements=new Map();
function element(id){if(elements.has(id))return elements.get(id);const canvas=createCanvas(id==='floor'?1500:800,id==='floor'?920:450);const el={id,dataset:{},value:({surfaceAlgorithm:'FIFO',view:'surface',search:'',speed:'600',ganttWindow:'480'})[id]||'',textContent:'',innerHTML:'',style:{setProperty(){}},disabled:false,hidden:false,width:canvas.width,height:canvas.height,classList:{toggle(){}},setAttribute(){},removeAttribute(){},querySelectorAll(){return[]},scrollIntoView(){},getContext:()=>canvas.getContext('2d'),canvas};elements.set(id,el);return el;}
const context={console,Map,Set,Date,Math,Number,Array,Object,String,JSON,URL,Blob,document:{getElementById:element,querySelectorAll:()=>[],body:{classList:{toggle(){}}}},location:{search:''},URLSearchParams,fetch:async()=>{throw Error('offline test')},requestAnimationFrame(){},setTimeout(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/production/replay.js','utf8')+'\n'+fs.readFileSync('dist/production/floor-view.js','utf8')+'\n'+fs.readFileSync('dist/production/production.js','utf8'),context);
context.surface=JSON.parse(fs.readFileSync('research/world_v05/response_surface.json'));
vm.runInContext('loadSurface(surface)',context);
assert.equal((element('resultsTable').innerHTML.match(/<tr>/g)||[]).length,50);
assert(vm.runInContext('surfaceHits.length',context)===25);

context.fixture=JSON.parse(require('node:child_process').execFileSync('python',['-c',`
import sys,json
sys.path.insert(0,'tests')
from test_calibrated_world_review import tiny_world,job
from factory.world_engine import WorldConfig,WorldSimulation
from unittest.mock import patch
w=tiny_world(quantity=2,unit_times=(.1,.2),eligibility=[['M1'],['M2']]);ss=[]
w.raw['resources']['cycle_capacity_units']=1
sim=WorldSimulation(w,WorldConfig(horizon_days=.1,drain_days=2),[job(w,2)],observer=ss.append)
with patch('factory.world_engine.wallclock.monotonic',side_effect=range(100000)):r=sim.run()
print(json.dumps({'world':w.raw,'live':next(s for s in ss if s['jobs']),'result':r}))
`],{encoding:'utf8'}));
for(const list of [context.fixture.world.machines,context.fixture.result.machines])list.forEach((m,i)=>Object.assign(m,{x:i*100,y:0,w:70,h:50}));
vm.runInContext('worldData=fixture.world;machineLayout=fixture.world.machines;nodeCoords=fixture.world.walking_graph.nodes;renderLive(fixture.live,"RUNNING")',context);
assert(element('liveResources').innerHTML.includes('מכונות מעבדות'));
assert(element('liveJobs').innerHTML.includes('data-live-job'));
vm.runInContext('liveJobId=fixture.live.jobs[0].id;renderLiveJob();loadRun(fixture.result)',context);
assert.equal((element('resultsTable').innerHTML.match(/<tr>/g)||[]).length,50,'Replay must retain grid');
vm.runInContext('select("jobs",result.jobs[0].id)',context);
assert(element('inspector').innerHTML.includes('פריקות שהושלמו'));
console.log('Production UI: 25 points/50 rows rendered, live job and resources rendered, replay retains grid and shows operation history.');

// Save/load must preserve the actual event replay, even with a grid loaded.
let exportedText=null,exportedFilename=null;
context.Blob=class{constructor(parts){exportedText=parts.join('')}};
context.URL={createObjectURL:()=> 'blob:test',revokeObjectURL(){}};
context.document.createElement=()=>({click(){exportedFilename=this.download},remove(){}});
context.document.body.appendChild=()=>{};
vm.runInContext("$('download').onclick()",context);
const exportedRun=JSON.parse(exportedText);
assert.equal(exportedFilename,'production-run.json');
assert(exportedRun.trace.intervals.length>0);
context.roundTrip=exportedRun;
vm.runInContext('loadRun(roundTrip)',context);
assert.equal(element('seek').disabled,false);
assert.equal(+element('horizon').value,context.fixture.result.config.horizon_days);
assert.equal(+element('arrivalLoad').value,context.fixture.result.config.arrival_load);
assert.equal(+element('batchSize').value,context.fixture.result.config.batch_size);
vm.runInContext("$('downloadSurface').onclick()",context);
assert.equal(exportedFilename,'production-experiment.json');
assert.equal(JSON.parse(exportedText).points.length,25);
// Live sidebar and inspector must use this snapshot, not the previous replay.
vm.runInContext('currentTab="workers";renderLive(fixture.live,"RUNNING")',context);
assert(element('entities').innerHTML.includes(context.fixture.live.workers[0].id));
vm.runInContext('select("jobs",fixture.live.jobs[0].id)',context);
assert(element('inspector').innerHTML.includes(context.fixture.live.jobs[0].id));
assert(element('inspector').innerHTML.includes('נפרקו'));
assert(element('queueCounts').innerHTML.includes('Milling'));
// A disappeared task must release the controls instead of retrying forever.
context.fetch=async()=>({ok:false,status:404,json:async()=>({message:'Unknown task'})});
(async()=>{
 await vm.runInContext('taskId="missing";busy(true);poll()',context);
 assert.equal(vm.runInContext('taskId',context),null);
 assert.equal(vm.runInContext('computing',context),false);
 assert(element('notice').textContent.includes('אינה קיימת'));
 console.log('Review UI regressions: full replay round-trip, separate exports, synced controls, live job/worker inspectors, actual queues, terminal 404 recovery passed.');
})().catch(e=>{console.error(e);process.exitCode=1});

// Replay state, filtering and timeline use the displayed time, including backwards seeks.
vm.runInContext('loadRun(fixture.result);time=0;updateClock();currentTab="jobs";renderEntities()',context);
assert(element('entities').innerHTML.includes('data-id="J"'));
vm.runInContext('select("jobs","J")',context);
assert(element('inspector').innerHTML.includes('2 / 2 חלקים ממופים'));
vm.runInContext('time=result.jobs[0].complete;updateClock();renderEntities()',context);
assert(!element('entities').innerHTML.includes('data-id="J"'),'Completed jobs must disappear at completion');
vm.runInContext('time=0;updateClock();renderEntities()',context);
assert(element('entities').innerHTML.includes('data-id="J"'),'Backwards seek restores the job');
assert(element('ganttRows').innerHTML.includes('gantt-bar'));
vm.runInContext('renderTaskProgress({status:"RUNNING",progress:{phase:"measurement",fraction:.25,completed_runs:1,total_runs:8,eta_seconds:120,work_done:50,work_total:200}})',context);
assert.equal(element('taskBar').value,25);
assert.equal(element('taskBarResearch').value,25);
assert(element('taskEta').textContent.includes('2 דק׳'));
console.log('Replay material counts, backward seek, completed-job filtering, timeline and both progress bars passed.');

// A visible moving load must resolve to the actual recorded worker.
vm.runInContext('loadRun(fixture.result);const trip=result.trace.intervals.find(i=>i.state==="CARRYING");time=(trip.start+trip.end)/2;drawFloor();updateClock()',context);
assert(element('transportActivity').innerHTML.includes('נושא חלקים'));
assert(element('transportActivity').innerHTML.includes('2 חלקים'));
assert(vm.runInContext('hitboxes.some(h=>h.type==="workers"&&h.hint?.includes("נושא 2 חלקים"))',context));
vm.runInContext('const station=stationCounts("M1")',context);
assert(element('stationDetail').innerHTML.includes('מבט מוגדל בתחנה'));
assert.equal(vm.runInContext('workerName("day_milling_milling_day04")',context),'כרסום · יום 04');
assert.notEqual(vm.runInContext('workerName("day_milling_milling_day04")',context),vm.runInContext('workerName("day_turning_turning_day04")',context));
console.log('Illustrated replay: actual carrier/quantity, selectable carried load, station detail and unambiguous worker names passed.');

// Motion invariants: sample real DES intervals, not just one carrying screenshot.
// Manual pieces follow the same pose as their worker; unloading precedes loading.
function verifyMotion(data){
 context.motionData=data;
 return vm.runInContext(`(()=>{
  loadRun(motionData);
  let tested=0;
  for(const state of ['CARRYING','LOADING','UNLOADING','CYCLE_CHANGE']){
   const intervals=result.trace.intervals.filter(i=>i.type==='worker'&&i.state===state&&i.start>=result.trace.start_min&&i.end<=result.trace.end_min);
   if(!intervals.length)throw Error('Missing motion fixture: '+state);
   // Beginning/middle/end occurrences exercise changing ownership and source stations.
   for(const trip of [...new Set([intervals[0],intervals[Math.floor(intervals.length/2)],intervals.at(-1)])]){
    const fractions=state==='CYCLE_CHANGE'?[.16,.32,.66,.82]:[.30,.65];
    let previous=null;
    for(const fraction of fractions){
     time=trip.start+(trip.end-trip.start)*fraction;drawFloor();
     const pose=workerVisuals.get(trip.entity);
     if(!pose?.cargo.length)throw Error('Recorded handler has no visible load: '+state);
     const total=pose.cargo.reduce((n,s)=>n+s.quantity,0);
     if(state==='CARRYING'){
      const actual=materialReplay.rows(time).flatMap(b=>b.segments).filter(s=>s.worker===trip.entity).reduce((n,s)=>n+s.quantity,0);
      if(total!==actual)throw Error('Carried quantity differs from ledger');
     }else{
      if(!pose.handling?.attached)throw Error('Part detached during manual carry');
      if(pose.cargo.length!==1)throw Error('Worker simultaneously handles outgoing and incoming pieces');
      const row=materialReplay.rows(time).find(b=>b.id===trip.batch);
      const segments=visualSegments(row),ranges=segments.flatMap(s=>Array.from({length:s.hi-s.lo},(_,n)=>s.lo+n));
      if(new Set(ranges).size!==ranges.length||ranges.length!==row.hi-row.lo)throw Error('Cycle visualization duplicates or drops parts');
      if(state==='CYCLE_CHANGE'&&pose.handling.loading!==(fraction>=.5))throw Error('Wrong cycle subphase');
     }
     if(Math.abs(Math.hypot(pose.hand[0]-pose.x,pose.hand[1]-pose.y)-10)>1e-6)throw Error('Load drifts away from carrier');
     // Two samples in the same manual carry stage must move both body and part.
     if(previous&&state!=='CARRYING'&&(state!=='CYCLE_CHANGE'||fraction===.32||fraction===.82)){
      const bodyDistance=Math.hypot(pose.x-previous.x,pose.y-previous.y);
      const loadDistance=Math.hypot(pose.hand[0]-previous.hand[0],pose.hand[1]-previous.hand[1]);
      if(bodyDistance<.01||Math.abs(bodyDistance-loadDistance)>1e-6)throw Error('Part moves without its worker');
     }
     previous=JSON.parse(JSON.stringify(pose));tested++;
    }
    // Rewinding must reconstruct exactly the same pose at the same replay instant.
    const target=trip.start+(trip.end-trip.start)*.32;
    time=target;drawFloor();const before=JSON.stringify(workerVisuals.get(trip.entity));
    time=trip.end;drawFloor();time=target;drawFloor();
    if(JSON.stringify(workerVisuals.get(trip.entity))!==before)throw Error('Seek history changes worker/cargo pose');
   }
  }
  return tested;
 })()`,context);
}
console.log('Worker/cargo motion samples passed:',verifyMotion(context.fixture.result));
if(process.env.REPLAY_REVIEW_FILE){
 console.log('Full-world motion samples passed:',verifyMotion(JSON.parse(fs.readFileSync(process.env.REPLAY_REVIEW_FILE))));
}
// Each recorded operation owner keeps every assignment, including an idle owner.
vm.runInContext(`loadRun(fixture.result);time=0;
 const ownerHistory=[...materialReplay.byBatch.values()].flat().find(e=>e.row?.owner&&e.row.machine);
 time=ownerHistory.time;const ownerRow=ownerHistory.row;
 const ownerAssignments=operationAssignments(ownerRow.owner);
 if(!ownerAssignments.get(ownerRow.machine)?.owner)throw Error('Missing operation-owner line');
 const ownerActiveBefore=ownerRow.owner_active;ownerRow.owner_active=false;
 if(!operationAssignments(ownerRow.owner).get(ownerRow.machine)?.owner)throw Error('Ownership incorrectly filtered by availability');
 ownerRow.owner_active=ownerActiveBefore;
`,context);
assert(vm.runInContext('new Set(["Milling","Turning","Honing","WireEDM"].map(machine_family=>machineFamilyColor({machine_family}))).size',context)===4);
vm.runInContext('setReplaySpeed(.25)',context);
assert.equal(element('speed').value,'0.25');
vm.runInContext('setReplaySpeed(7.5)',context);
assert.equal(element('speed').value,'custom');
assert.equal(element('speedCustom').value,7.5);
vm.runInContext("$('faster').onclick()",context);
assert.equal(element('speedCustom').value,15);
assert.equal(vm.runInContext('setReplaySpeed(NaN)',context),false);
assert.equal(vm.runInContext('setReplaySpeed(0)',context),false);
assert.equal(vm.runInContext('replaySpeed',context),15);
// Advance the actual animation loop at 60Hz: chosen speed changes simulated time.
context.performance={now:()=>0};
vm.runInContext('time=result.trace.start_min;playing=true;lastFrame=1000;lastPaint=1000;setReplaySpeed(10);for(let k=1;k<=60;k++)frame(1000+k*1000/60);playing=false;',context);
assert(Math.abs(vm.runInContext('time-result.trace.start_min',context)-10/60)<1e-8);
const paused=vm.runInContext('[time,visualClock]',context);
vm.runInContext('frame(2100)',context);
assert.equal(vm.runInContext('time',context),paused[0]);
assert.equal(vm.runInContext('visualClock',context),paused[1]);
console.log('Machine family colors, persistent ownership, custom speed, elapsed replay time and pause passed.');

// Counters must follow the ledger, not the two decorative halves of cycle change.
vm.runInContext(`loadRun(fixture.result);const change=result.trace.intervals.find(i=>i.type==='machine'&&i.state==='CYCLE_CHANGE');
 time=change.start+(change.end-change.start)*.2;const beforeCounts=JSON.stringify(stationCounts(change.entity));
 time=change.start+(change.end-change.start)*.7;
 if(JSON.stringify(stationCounts(change.entity))!==beforeCounts)throw Error('Decorative cycle phase changes station quantities');
 time=change.end;const afterCounts=stationCounts(change.entity);
 if(afterCounts.before!==JSON.parse(beforeCounts).before-1)throw Error('Loading completion must decrement input');
 if(afterCounts.after!==JSON.parse(beforeCounts).after+1)throw Error('Unloading completion must increment output');
 time=result.trace.end_min;const finalMachine=result.trace.events.filter(e=>e.kind==='parts_unloaded').at(-1).machine;
 if(materialReplay.completedAt(finalMachine,time).total!==2)throw Error('Final finished parts disappeared from completion accounting');
 playing=true;time=change.start;resourceStamp=Date.now();replayResources();
 const waited=result.machines.filter(m=>intervalAt(m.id)?.state.startsWith('WAITING')).length;
 if(!$('waitingDiagnostics').innerHTML.includes('מכונות ממתינות: '+waited))throw Error('Diagnostics and replay waiting count disagree');playing=false;
`,context);
console.log('Stable cycle quantities, visible final completions and synchronized waiting counts passed.');
