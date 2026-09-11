"""Task progress from completed replications and actual part-operation work."""
import time


class TaskProgress:
    def __init__(self, task, total):
        self.task=task;self.total=total;self.done=0;self.cached=0
        self.started=time.monotonic();self.run_started=self.started;self.durations=[]
        self.publish(phase='preparing',fraction=0,eta=None)

    def publish(self, phase, fraction, eta, **fields):
        self.task['progress'] = dict(phase=phase,completed_runs=self.done,total_runs=self.total,
            cached_runs=self.cached,fraction=min(.999,max(0,(self.done+fraction)/self.total)),
            elapsed_seconds=time.monotonic()-self.started,eta_seconds=eta,**fields)

    def run_event(self, event):
        if event['kind']=='start':
            self.run_started=time.monotonic()
            self.task.pop('live',None)
            c=event['config']
            self.publish('preparing',0,self.estimate(0),algorithm=c['algorithm'],replication=c['replication'],
                         arrival_scale=c['arrival_load'],batch_scale=c['batch_size'])
        else:
            self.done+=1
            if event.get('cached'):self.cached+=1
            else:self.durations.append(time.monotonic()-self.run_started)
            self.publish('saving' if self.done==self.total else 'between_runs',0,self.estimate(0))

    def estimate(self, current):
        if not self.durations:return None
        average=sum(self.durations[-8:])/len(self.durations[-8:])
        return max(0,(self.total-self.done)*average-current)

    def observe(self, live):
        elapsed=live['elapsed_seconds'];done=live.get('work_done',0);total=live.get('work_total',0)
        window_fraction=min(1,live['time']/max(1,live['window_end']))
        fraction=min(.99,done/total) if total else .99*window_fraction
        eta=None
        if elapsed>=2 and done>0:
            work_remaining=elapsed*max(0,total-done)/done
            clock_remaining=elapsed*max(0,live['window_end']-live['time'])/max(.001,live['time'])
            current=max(work_remaining,clock_remaining)
            future=self.total-self.done-1
            average=sum(self.durations[-8:])/len(self.durations[-8:]) if self.durations else elapsed+current
            eta=current+future*average
        elif self.durations:eta=self.estimate(elapsed)
        self.publish(live['phase'],fraction,eta,events=live['events'],work_done=done,work_total=total,
                     sim_time=live['time'],remaining_jobs=live['released']-live['completed'],
                     algorithm=live['algorithm'],replication=live['replication'],
                     arrival_scale=live['arrival_scale'],batch_scale=live['batch_scale'])

    def finish(self,status):
        self.task['progress']={**self.task['progress'],'phase':status.lower(),
            'elapsed_seconds':time.monotonic()-self.started,'eta_seconds':0 if status=='COMPLETE' else None}
        if status=='COMPLETE':self.task['progress'].update(fraction=1,completed_runs=self.total)
