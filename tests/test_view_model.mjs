import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {activeTask, workerPosition, jobState} from '../dist/view-model.js';
import {comparisonRows, retainExperiment} from '../dist/experiments.js';

const root=fileURLToPath(new URL('../',import.meta.url));
const trace=JSON.parse(execFileSync('python',['-B','dist/engine.py'],{cwd:root,encoding:'utf8'}));
let snapshots=0;
for(const task of trace.tasks){
  const worker=trace.workers.find(w=>w.id===task.worker);
  const job=trace.jobs.find(j=>j.id===task.job);
  assert.equal(activeTask(trace,'worker',worker.id,task.start),task);
  assert.deepEqual(workerPosition(trace,worker,task.start),task.path.at(-1));
  if(task.walking>0){
    assert.deepEqual(workerPosition(trace,worker,task.assigned),task.path[0]);
    const midpoint=workerPosition(trace,worker,task.assigned+task.walking/2);
    assert(midpoint.every(Number.isFinite));
    assert.notDeepEqual(midpoint,task.path[0]);
    assert.notDeepEqual(midpoint,task.path.at(-1));
    assert.equal(jobState(trace,job,task.assigned+task.walking/2).phase,'walk');
  }
  assert.equal(jobState(trace,job,task.start+task.duration/2).phase,'work');
  snapshots++;
}
for(const job of trace.jobs)assert.equal(jobState(trace,job,trace.end_time).phase,'done');
// Backward seeking is a pure lookup; the end-of-run lookup must not affect t=0.
assert.deepEqual(workerPosition(trace,trace.workers[0],0),trace.workers[0].home);

const experiment=(policy,value,overrides={})=>({scenario:'same-world',options:{policy,walking:false,horizon:40,variation:0,seed:42,...overrides},results:[{seed:42,complete:true,mean_flow:value,makespan:26,total_tardiness:1}]});
const fifo=experiment('fifo',17.5),spt=experiment('spt',15.5);
let history=retainExperiment([],fifo);history=retainExperiment(history,spt);
let rows=comparisonRows(history,spt);
assert.equal(rows.length,2);assert.equal(rows[0].policy,'spt');
assert(Math.abs(rows[0].improvement-100*2/17.5)<1e-10);
assert.equal(retainExperiment(history,spt).length,2,'Identical experiment is replaced');
const otherHorizon=experiment('edd',10,{horizon:50});
assert.equal(comparisonRows([...history,otherHorizon],fifo).length,2);
const otherSeed=experiment('edd',10);otherSeed.results[0].seed=43;
assert.equal(comparisonRows([...history,otherSeed],fifo).length,2);
const otherWorld=experiment('edd',10);otherWorld.scenario='different-world';
assert.equal(comparisonRows([...history,otherWorld],fifo).length,2);
const partial=experiment('edd',null);partial.results[0].complete=false;
rows=comparisonRows([...history,partial],fifo);
assert.equal(rows.at(-1).meanFlow,null);assert.equal(rows.at(-1).improvement,null);
assert.equal(rows.at(-1).completed,0);
console.log(`View-model checks passed for ${snapshots} operations; comparison matching, deduplication and partial-run safeguards passed.`);
