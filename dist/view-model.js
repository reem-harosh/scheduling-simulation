/** Pure view helpers. Never schedule operations: Python is authoritative. */
export const fmt=(value,digits=1)=>Number(value).toLocaleString('he-IL',{maximumFractionDigits:digits,minimumFractionDigits:digits});
export function fmtTime(minutes){const s=Math.max(0,Math.floor(minutes*60+1e-6));return String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');}
export function activeTask(trace,key,id,t){return trace.tasks.find(x=>x[key]===id&&x.assigned<=t+1e-8&&x.end>t+1e-8)||null;}
export function progressAt(task,t){return Math.max(0,Math.min(1,(t-task.start)/task.duration));}
export function workerPosition(trace,worker,t){
  const task=activeTask(trace,'worker',worker.id,t);
  if(task){
    if(t>=task.start||task.walking===0)return task.path.at(-1);
    const lengths=task.path.slice(1).map((p,i)=>Math.hypot(p[0]-task.path[i][0],p[1]-task.path[i][1]));
    let distance=lengths.reduce((a,b)=>a+b,0)*Math.max(0,(t-task.assigned)/task.walking);
    for(let i=0;i<lengths.length;i++){
      if(distance<=lengths[i]&&lengths[i]>0){const f=distance/lengths[i],a=task.path[i],b=task.path[i+1];return [a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f];}
      distance-=lengths[i];
    }
    return task.path.at(-1);
  }
  const previous=trace.tasks.filter(x=>x.worker===worker.id&&x.end<=t+1e-8).sort((a,b)=>b.end-a.end)[0];
  return previous?previous.path.at(-1):worker.home;
}
export function jobState(trace,job,t){
  const tasks=trace.tasks.filter(x=>x.job===job.id),completed=tasks.filter(x=>x.end<=t+1e-8).length;
  const task=activeTask(trace,'job',job.id,t);
  const phase=completed===job.operations.length?'done':task?(t<task.start-1e-8?'walk':'work'):'waiting';
  const total=tasks.reduce((s,x)=>s+x.duration,0);
  const progress=total?tasks.reduce((s,x)=>s+progressAt(x,t)*x.duration,0)/total:0;
  return {phase,completed,task,progress};
}
