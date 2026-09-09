/** Compare only experiments with the same world, settings, and actual seed list. */
export const policyNames={fifo:'סדר קבוע',spt:'פעולה קצרה',edd:'מועד יעד קרוב'};
export function comparisonKey(batch){
  const o=batch.options;
  return JSON.stringify([batch.scenario,o.horizon,o.walking,o.variation,batch.results.map(r=>r.seed)]);
}
export function retainExperiment(history,batch){
  const key=comparisonKey(batch);
  return [...history.filter(x=>comparisonKey(x)!==key||x.options.policy!==batch.options.policy),batch].slice(-20);
}
export function comparisonRows(history,reference){
  const rows=history.filter(x=>comparisonKey(x)===comparisonKey(reference)).map(batch=>{
    const complete=batch.results.filter(r=>r.complete),n=batch.results.length;
    const mean=key=>complete.length===n&&n>0?complete.reduce((s,r)=>s+r[key],0)/n:null;
    return {policy:batch.options.policy,total:n,completed:complete.length,
      meanFlow:mean('mean_flow'),makespan:mean('makespan'),tardiness:mean('total_tardiness')};
  });
  const baseline=rows.find(r=>r.policy==='fifo')?.meanFlow;
  return rows.map(r=>({...r,improvement:baseline>0&&r.meanFlow!==null?(baseline-r.meanFlow)/baseline*100:null}))
    .sort((a,b)=>(a.meanFlow??Infinity)-(b.meanFlow??Infinity)||a.policy.localeCompare(b.policy));
}
