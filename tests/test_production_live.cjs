// Execute production UI data paths with a minimal DOM/canvas adapter.
// This verifies data/render contracts, not browser layout or pointer behavior.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const createCanvas=(width,height)=>({width,height,getContext:()=>new Proxy({},{get:(o,k)=>o[k]||((...args)=>{for(const a of args)if(typeof a==='number')assert(Number.isFinite(a),'Nonfinite canvas coordinate')})})});
const elements=new Map();
function element(id){if(elements.has(id))return elements.get(id);const canvas=createCanvas(id==='floor'?1500:800,id==='floor'?920:450);const el={id,value:({surfaceAlgorithm:'FIFO',view:'surface',search:'',speed:'600'})[id]||'',textContent:'',innerHTML:'',style:{},disabled:false,hidden:false,width:canvas.width,height:canvas.height,classList:{toggle(){}},setAttribute(){},querySelectorAll(){return[]},scrollIntoView(){},getContext:()=>canvas.getContext('2d'),canvas};elements.set(id,el);return el;}
const context={console,Map,Set,Date,Math,Number,Array,Object,String,JSON,URL,Blob,document:{getElementById:element,querySelectorAll:()=>[],body:{classList:{toggle(){}}}},location:{search:''},URLSearchParams,fetch:async()=>{throw Error('offline test')},requestAnimationFrame(){},setTimeout(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/production/production.js','utf8'),context);
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
w=tiny_world(quantity=2,unit_times=(.1,.2));ss=[]
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
