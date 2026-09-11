"""Calibrated-world DES on the existing conservation/calendar/replay kernel.
Legacy factory.engine remains available solely for reproducing v0.3 experiments.
"""
import copy, hashlib, heapq, json, math, statistics
import time as wallclock
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
from .engine import Simulation, Config as LegacyConfig, Worker, MACHINE_BUSY, WORK
from .data import InputError
from .world import demand_stream
from .world_policies import make_policy, REGISTRY

@dataclass
class WorldConfig(LegacyConfig):
    algorithm: str='FIFO'
    drain_days: float=730
    def validate(self):
        for name in ('arrival_load','batch_size','horizon_days','warmup_days','trace_days','drain_days'):
            v=getattr(self,name)
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise InputError('INVALID_CONFIG_'+name)
        for name,minimum in [('seed',0),('replication',0),('max_events',1)]:
            v=getattr(self,name)
            if type(v) is not int or v<minimum:raise InputError('INVALID_CONFIG_'+name)
        if not isinstance(self.start_date,str):raise InputError('INVALID_START_DATE')
        if datetime.fromisoformat(self.start_date).tzinfo is not None:raise InputError('START_DATE_REQUIRES_LOCAL_NAIVE_TIME')
        if self.batch_size<=0 or self.horizon_days<=0:raise InputError('Positive quantity and horizon required')
        if self.algorithm not in REGISTRY:raise InputError('UNKNOWN_ALGORITHM')
        if self.baseline_calibration_multiplier!=1:raise InputError('v0.4 uses world baseline rate, not historical multiplier')

class WorldSimulation(Simulation):
    def __init__(self,world,config=None,manual_jobs=None,policy=None,cancel=None,observer=None):
        self.observer=observer; self._observed_at=0.; self._wall_start=wallclock.monotonic()
        world.refresh_identity(); self.manual_input=manual_jobs is not None
        config=config or WorldConfig(); config.validate()
        self._calendar_ready=False
        self.demand=demand_stream(world,config) if manual_jobs is None else copy.deepcopy(manual_jobs)
        self.code_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()
        self.setup_waits=[];self.queue_family_minutes={f:0. for f in {m['machine_family'] for m in world.machines.values()}}
        self.floor_local=world.raw['resources'].get('floor_local_workers',False);self.lift_available=0.;self.lift_transfers=[];self.floor_nodes={}
        self.terminal_at_stop=None;self.processing_totals={};self.handoffs=[];self.peak_processing=0
        # Supply a prepared stream: inherited historical generator never runs.
        super().__init__(world,config,self.demand,policy or make_policy(config.algorithm),cancel)
        self.streams.prefix[1]='operational-world'
        # The calibrated calendar has one configured day shift, no legacy extensions.
        for worker in self.workers.values():worker.extended=False
        n=world.raw['resources']['setup_workers'];nodes=list(world.graph['service_nodes'].values())
        for i in range(n):
            wid=f'S{i+1:02}';kind='setup_day' if i<(n+1)//2 else 'setup_night'
            floors=sorted({m.department for m in self.machines.values()})
            dept=floors[i%len(floors)] if self.floor_local else 'floor'
            skills={m.id for m in self.machines.values() if not self.floor_local or m.department==dept}
            w=Worker(wid,dept,skills,kind,False)
            w.home_node=self.machines[sorted(skills)[0]].node;self.workers[wid]=w
        self._calendar_ready=True
        self._calendar_day(self.start.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=1))
        self._event(self.arrivals_stop+config.drain_days*1440,1,'drain_limit')
    def _calendar_day(self,day):
        if not self._calendar_ready:return
        res=self.data.raw['resources']
        if day.weekday() not in res['working_weekdays']:return
        def at(h):return (day.replace(hour=h,minute=0,second=0,microsecond=0)-self.start).total_seconds()/60
        for w in sorted(self.workers.values(),key=lambda w:w.id):
            night=w.kind.endswith('night');begin=at(res['day_end_hour'] if night else res['day_start_hour']);end=at(res['day_start_hour'])+1440 if night else at(res['day_end_hour']);token=w.id+':'+day.date().isoformat()
            for t,kind,val in [(begin,'shift_start',token),(end,'shift_end',token)]:
                if t>=self.time:self._event(t,1,kind,(w.id,val))
                elif kind=='shift_start' and self.time==0 and begin<0<end:
                    self._event(0,1,kind,(w.id,val))
            for offset,dur in [(180,20),(360,30),(540,20)]:
                t=begin+offset
                if self.time<=t<end:self._event(t,1,'break',(w.id,dur,token))
                elif self.time==0 and t<0<min(t+dur,end):
                    self._event(0,1,'break',(w.id,min(t+dur,end),token))
    def _demand_day(self,day):pass
    def _integrate(self,until):
        dt=max(0,min(until,self.arrivals_stop)-max(self.time,self.measure_start))
        for bid in self.ready:
            b=self.batches[bid];j=self.jobs[b.job];f=self.data.operations[j.item,j.route[b.op_index]]['machine_family'];self.queue_family_minutes[f]+=dt
        self.peak_processing=max(self.peak_processing,sum(m.state=='PROCESSING' for m in self.machines.values()))
        super()._integrate(until)
    def _key(self,b):
        j=self.jobs[b.job];return j.item,j.route[b.op_index]
    def _eligible_workers(self,mid,kind):
        return [w for w in self.workers.values() if self._worker_available(w) and mid in w.skills and w.kind.startswith('setup')==(kind=='setup')]
    def _start_kind(self,b,mid):
        # Physical transport first; then preparation and manual loading.
        if b.location and b.location!=mid:return 'transport'
        tr=self.data.transition(mid,self.machines[mid].setup,self._key(b))
        return 'setup' if max(tr['triangular'])>0 else 'load'
    def _can_start(self,b,mid):
        if self._cross_floor(b,mid):
            return any(self._worker_available(w) and not w.kind.startswith('setup') and w.department==self._location_floor(b.location) for w in self.workers.values())
        return self.machines[mid].batch is None and bool(self._eligible_workers(mid,self._start_kind(b,mid)))
    def _location_floor(self,location):
        return location.split(':',1)[1] if location.startswith('@floor:') else self.machines[location].department
    def _floor_node(self,department):
        if department in self.floor_nodes:return self.floor_nodes[department]
        explicit=self.data.graph.get('floor_handoff_nodes',{})
        if department in explicit:
            self.floor_nodes[department]=explicit[department];return explicit[department]
        nodes={m.node for m in self.machines.values() if m.department==department}
        boundary=self.data.graph.get('node_floor_boundary',1150)
        node=min(nodes,key=lambda n:abs(self.data.graph['nodes'][n][0]-boundary))
        self.floor_nodes[department]=node;return node
    def _location_node(self,location):
        return self._floor_node(self._location_floor(location)) if location.startswith('@floor:') else self.machines[location].node
    def _cross_floor(self,b,mid):
        return self.floor_local and b.location is not None and self._location_floor(b.location)!=self.machines[mid].department
    def _worker_path(self,w,start,end):
        return self.data.path(start,end,w.department) if self.floor_local else self.data.path(start,end)
    def _transport_estimate(self,b,mid):
        if not b.location or b.location==mid:return 0.
        trips=math.ceil((b.hi-b.lo)/self.data.raw['resources']['transport_capacity_units'])
        src=self._location_node(b.location);dest=self.machines[mid].node
        if self._cross_floor(b,mid):
            a=self._location_floor(b.location);z=self.machines[mid].department
            distance=self.data.path(src,self._floor_node(a),a)[0]+self.data.path(self._floor_node(z),dest,z)[0]
            lift_trips=math.ceil((b.hi-b.lo)/self.data.raw['resources'].get('freight_lift_capacity_units',self.data.raw['resources']['transport_capacity_units']))
            return distance*self.data.graph['seconds_per_relative_unit']/60*(2*trips-1)+max(0,self.lift_available-self.time)+lift_trips*self.data.raw['resources'].get('freight_lift_trip_minutes',3.)
        distance=self.data.path(src,dest,self._location_floor(b.location) if self.floor_local else 'floor')[0]
        return distance*self.data.graph['seconds_per_relative_unit']/60*(2*trips-1)
    def public_state(self):
        s=super().public_state()
        res=self.data.raw['resources'];day_start=res['day_start_hour'];day_end=res['day_end_hour']
        def breaks(start,duration):
            return [[int((start*60+offset)//60)%24,int((start*60+offset)%60),length] for offset,length in [(180,20),(360,30),(540,20)] if offset<duration]
        s['calendar']=dict(start_date=self.config.start_date,day_weekdays=list(res['working_weekdays']),night_start_weekdays=list(res['working_weekdays']),day_hours=[day_start,day_end],extended_hours=[day_start,day_end],night_hours=[day_end,day_start],day_breaks=breaks(day_start,(day_end-day_start)*60),extended_breaks=[],night_breaks=breaks(day_end,(24-day_end+day_start)*60))
        for row in s['workers']:
            w=self.workers[row['id']];row['kind']=w.kind;row['service_role']='setup' if w.kind.startswith('setup') else 'operator';row['extended']=False
        # Snapshot-local resource summaries avoid rescanning all workers/requests per candidate.
        setup_counts={};setup_queues={};available_setup=set();available_regular=set();available_regular_floors=set()
        for w in self.workers.values():
            group=w.department if self.floor_local else 'floor'
            if w.kind.startswith('setup'):
                if w.active:setup_counts[group]=setup_counts.get(group,0)+1
                if self._worker_available(w):available_setup.update(w.skills)
            elif self._worker_available(w):
                available_regular.update(w.skills);available_regular_floors.add(w.department)
        for request in self.requests.values():
            if request['kind']!='setup':continue
            machine=self.machines[request['machine']];group=machine.department if self.floor_local else 'floor'
            setup_queues[group]=setup_queues.get(group,0.)+sum(self.data.transition(machine.id,machine.setup,self._key(self.batches[request['batch']]))['triangular'])/3
        # Existing jobs are public; future draws and future event times are absent.
        for row in s['ready']:
            b=self.batches[row['id']];key=self._key(b);row['location']=b.location;row['candidates']=[]
            for mid in row['eligible_machines']:
                m=self.machines[mid];tr=self.data.transition(mid,m.setup,key);setup=sum(tr['triangular'])/3
                proc=self.data.processing[*key,mid]*(b.hi-b.lo)
                # Remaining *deterministic* processing plus expected handling; no RNG sample lookup.
                residual=0.
                if m.batch:
                    current=self.batches[m.batch];unit=self.data.processing[*self._key(current),mid]
                    residual=(current.hi-current.cursor)*unit
                    if m.state=='PROCESSING':residual+=max(0,(current.cycle[1]-current.cycle[0])*unit-(self.time-m.since))
                    residual+=math.ceil(max(0,current.hi-current.cursor)/self.data.raw['resources']['cycle_capacity_units'])*11/6+11/12
                    if m.state=='SETUP':residual+=max(0,sum(self.data.transition(mid,m.setup,self._key(current))['triangular'])/3-(self.time-m.since))
                group=m.department if self.floor_local else 'floor'
                # Public expected service workload proxy; not a perfect calendar forecast.
                swait=setup_queues.get(group,0.)/max(1,setup_counts.get(group,0)) if setup else 0.
                if self._cross_floor(b,mid):can_start=self._location_floor(b.location) in available_regular_floors
                else:can_start=m.batch is None and mid in (available_setup if self._start_kind(b,mid)=='setup' else available_regular)
                transport=self._transport_estimate(b,mid)
                handling=(math.ceil((b.hi-b.lo)/self.data.raw['resources']['cycle_capacity_units']))*11/6
                row['candidates'].append({'machine':mid,'can_start':can_start,'ect':self.time+residual+swait+setup+transport+proc+handling,'residual':residual,'queued_machine_work':0.,'setup_mean':setup,'setup_worker_delay_estimate':swait,'transport_mean':transport,'processing':proc,'handling_mean':handling})
            row['expected_processing_min']=min(c['processing'] for c in row['candidates'])
        s['routing_semantics']='Pooled FIFO queue; ECT over all eligible machines with revisable busy-machine plans; commit at first resource reservation'
        return s
    def _allocate(self):
        if not self.ready:return
        idle={m.id for m in self.machines.values() if m.batch is None}
        # Cross-floor actions reserve a floor transfer, not the nominated machine.
        # Even an entirely busy destination floor can receive material in its pool.
        if not idle and not self.floor_local:return
        if not any(self._can_start(self.batches[bid],mid)
                   for bid in self.ready for mid in self.data.eligibility[self._key(self.batches[bid])]
                   if mid in idle or self._cross_floor(self.batches[bid],mid)):return
        for action in self.policy.decide(self.public_state()):self.apply_action(action)
    def apply_action(self,action):
        if action.get('kind')=='allocate':return self.accept_allocation(action.get('batch'),action.get('machine'))
        reason='SPLIT_DISABLED_BASELINE' if action.get('kind')=='split' else 'UNKNOWN_ACTION'
        self.counters['rejections'][reason]=self.counters['rejections'].get(reason,0)+1;return reason
    def validate_allocation(self,bid,mid):
        if bid not in self.batches or mid not in self.machines:return 'UNKNOWN_ENTITY'
        b=self.batches[bid]
        if mid not in self.data.eligibility[self._key(b)]:return 'MACHINE_INELIGIBLE'
        if b.state!='READY' or bid not in self.ready:return 'RESOURCE_BUSY'
        if self.machines[mid].batch is not None and not self._cross_floor(b,mid):return 'RESOURCE_BUSY'
        if not self._can_start(b,mid):return 'NO_START_RESOURCE'
        return None
    def accept_allocation(self,bid,mid):
        # Serve existing higher-priority human requests before reserving a new machine.
        self._dispatch()
        reason=self.validate_allocation(bid,mid)
        if reason:
            self.counters['rejections'][reason]=self.counters['rejections'].get(reason,0)+1;return reason
        b=self.batches[bid];m=self.machines[mid]
        if self._cross_floor(b,mid):
            self.ready.remove(bid);b.target=None;b.state='INTERFLOOR_TRANSPORT'
            src=self._location_node(b.location);dept=self._location_floor(b.location)
            self._request('transport',dept,src,machine=mid,batch=bid,destination=self._floor_node(dept),source_node=src,trips=math.ceil((b.hi-b.lo)/self.data.raw['resources']['transport_capacity_units']),trip=0,floor_handoff=True,destination_floor=m.department)
            self._log('floor_transfer_requested',batch=bid,job=b.job,source_floor=dept,destination_floor=m.department,target_machine=None)
            self._dispatch();return None
        self.ready.remove(bid);m.batch=bid;b.target=mid;b.state='COMMITTED'
        self._log('allocated',batch=bid,machine=mid,operation=self._key(b)[1],job=b.job)
        if b.location and b.location!=mid:
            source_node=self._location_node(b.location);trips=math.ceil((b.hi-b.lo)/self.data.raw['resources']['transport_capacity_units'])
            self._state(m,'WAITING_TRANSPORT','machine',batch=bid,job=b.job)
            self._request('transport',m.department,source_node,destination=m.node,machine=mid,batch=bid,trips=trips,trip=0,source_node=source_node)
        else:
            b.location=mid;self._begin_setup(m)
        # Reserve the real first worker now; later actions revalidate remaining capacity.
        self._dispatch()
        return None
    def _begin_setup(self,m):
        b=self.batches[m.batch];tr=self.data.transition(m.id,m.setup,self._key(b))
        if max(tr['triangular'])>0:
            b.state='WAITING_SETUP';self._state(m,'WAITING_SETUP','machine',batch=b.id,job=b.job,setup_type=tr['type'],from_class=tr['from_class'],to_class=tr['to_class']);self._request('setup','floor',m.node,machine=m.id,batch=b.id)
        else:m.setup=self._key(b);self._request_machine(m,'load')
    def _dispatch(self):
        order={'change':0,'unload':0,'setup':1,'transport':1,'load':2}
        for r in sorted(self.requests.values(),key=lambda r:(order[r['kind']],r['ready'],r['id'])):
            if r['reserved']:continue
            b=self.batches[r['batch']]
            if r.get('floor_handoff'):
                candidates=[w for w in self.workers.values() if self._worker_available(w) and not w.kind.startswith('setup') and w.department==r['department']]
            else:candidates=self._eligible_workers(r['machine'],r['kind'])
            if r['kind'] not in ('setup','transport') and b.owner:
                owner=self.workers[b.owner]
                if owner.busy or (owner.active and owner.shift==b.owner_shift):candidates=[w for w in candidates if w.id==owner.id]
            if not candidates:continue
            w=min(candidates,key=lambda w:(0 if w.node is None else self._worker_path(w,w.node,r['pickup'])[0],w.id));r['reserved']=w.id;w.busy=True
            if w.node is None:w.node=r['pickup']
            distance,path=self._worker_path(w,w.node,r['pickup'])
            if distance:self._move(w,path,distance,'WALKING','pickup',r['id'])
            else:self._event(self.time,0,'pickup',(w.id,r['id']))
    def _pickup(self,wid,rid):
        w=self.workers[wid];r=self.requests[rid];w.node=r['pickup'];w.busy=False
        if not self._worker_available(w):r['reserved']=False;self._rest(w);return
        b=self.batches[r['batch']];m=self.machines[r['machine']]
        if r['kind']=='setup':
            if not w.kind.startswith('setup'):raise RuntimeError('SETUP_ROLE')
            w.busy=True;tr=self.data.transition(m.id,m.setup,self._key(b));a,mode,c=tr['triangular']
            duration=a if a==c else float(self.streams.rng('setup',[b.job,*self._key(b),m.id,m.setup]).triangular(a,mode,c))
            if self.measure_start<=self.time<self.arrivals_stop:self.setup_waits.append(self.time-r['ready'])
            self._state(w,'SETUP','worker',node=w.node,batch=b.id,machine=m.id,job=b.job);self._state(m,'SETUP','machine',batch=b.id,job=b.job,worker=wid,setup_type=tr['type'],from_class=tr['from_class'],to_class=tr['to_class']);b.state='SETUP'
            self._log('setup_start',batch=b.id,operation=self._key(b)[1],machine=m.id,worker=wid,setup_type=tr['type'],from_class=tr['from_class'],to_class=tr['to_class'])
            self._event(self.time+duration,0,'world_setup_end',(wid,rid));return
        if r['kind']=='transport':
            w.busy=True;distance,path=self._worker_path(w,w.node,r['destination']);self._move(w,path,distance,'CARRYING','world_transport_end',rid)
            self.counters['transport_trips']=self.counters.get('transport_trips',0)+1
            self._log('carry_start',job=b.job,batch=b.id,worker=wid,quantity=min(self.data.raw['resources']['transport_capacity_units'],b.hi-b.lo-r['trip']*self.data.raw['resources']['transport_capacity_units']),from_node=w.node,to_node=r['destination']);return
        if w.kind.startswith('setup'):raise RuntimeError('OPERATOR_ROLE')
        if b.owner and b.owner!=wid:
            event={'time':self.time,'job':b.job,'batch':b.id,'operation':self._key(b)[1],'previous_worker':b.owner,'worker':wid,'reason':'previous_owner_shift_ended'}
            self.handoffs.append(event);self._log('ownership_handoff',**{k:v for k,v in event.items() if k!='time'})
        super()._pickup(wid,rid)
    def _processing(self,m):
        b=self.batches[m.batch];q=min(self.data.raw['resources']['cycle_capacity_units'],b.hi-b.cursor);unit=self.data.processing[*self._key(b),m.id];duration=q*unit
        b.cycle=(b.cursor,b.cursor+q);b.cursor+=q;b.state='PROCESSING';self.processing_totals[b.id]=self.processing_totals.get(b.id,0)+duration
        self._state(m,'PROCESSING','machine',batch=b.id,job=b.job,lo=b.cycle[0],hi=b.cycle[1]);self._event(self.time+duration,0,'processing_end',m.id)
    def _finished_parts(self,b,m):
        super()._finished_parts(b,m)
        self.output_ids.discard(b.id);b.available_output=[]
        if b.cursor==b.hi and b.unloaded==b.hi-b.lo:
            self._log('ownership_release',batch=b.id,operation=self._key(b)[1],worker=b.owner)
            b.owner=b.owner_shift=None
            if b.op_index+1<len(self.jobs[b.job].route):self._new_batch(b.job,b.op_index+1,b.lo,b.hi,location=m.id,parent=b.id)
    def _handle(self,kind,payload):
        if kind=='world_setup_end':
            wid,rid=payload;r=self.requests.pop(rid);m=self.machines[r['machine']];m.setup=self._key(self.batches[m.batch]);self._rest(self.workers[wid]);self._request_machine(m,'load')
        elif kind=='world_transport_end':
            wid,rid=payload;r=self.requests[rid];w=self.workers[wid];w.node=r['destination'];r['trip']+=1
            if r['trip']<r['trips']:
                self._rest(w);r['reserved']=False;r['pickup']=r['source_node']
            else:
                self.requests.pop(rid);b=self.batches[r['batch']];self._rest(w)
                if r.get('floor_handoff'):
                    res=self.data.raw['resources'];trips=math.ceil((b.hi-b.lo)/res.get('freight_lift_capacity_units',res['transport_capacity_units']))
                    start=max(self.time,self.lift_available);end=start+trips*res.get('freight_lift_trip_minutes',3.)
                    self.lift_available=end;b.state='WAITING_LIFT';b.location='@floor:'+r['department']
                    transfer=dict(batch=b.id,job=b.job,source_floor=r['department'],destination_floor=r['destination_floor'],quantity=b.hi-b.lo,trips=trips,ready=self.time,start=start,end=end)
                    self.lift_transfers.append(transfer);self._log('lift_queued',**transfer)
                    self._event(end,0,'world_lift_end',(b.id,r['destination_floor']))
                else:
                    b.location=r['machine'];self._begin_setup(self.machines[r['machine']])
        elif kind=='world_lift_end':
            bid,dept=payload;b=self.batches[bid];b.location='@floor:'+dept;b.target=None;b.state='READY';b.ready=self.time;self.ready.append(bid)
            self._log('lift_delivery',batch=bid,job=b.job,destination_floor=dept,quantity=b.hi-b.lo,target_machine=None)
        elif kind=='arrivals_stop':
            live=[j for j in self.jobs.values() if j.complete is None];self.terminal_at_stop={'wip':len(live),'unfinished_job_ages_min':[self.time-j.release for j in live],'released':len(self.jobs),'completed':sum(j.complete is not None for j in self.jobs.values())}
        elif kind=='drain_limit':pass
        else:super()._handle(kind,payload)
    def observe(self, force=False):
        """Read-only telemetry: no RNG calls or scheduler inputs; bounded wall-clock cadence."""
        now=wallclock.monotonic()
        if not self.observer or (not force and now-self._observed_at<.5):return
        self._observed_at=now
        machines=[dict(id=m.id,state=m.state,since=m.since,**getattr(m,'_metadata',{})) for m in self.machines.values()]
        workers=[dict(id=w.id,state=w.state,node=w.node,kind=w.kind,department=w.department,active=w.active,busy=w.busy,available=self._worker_available(w),since=w.since,**{k:v for k,v in getattr(w,'_metadata',{}).items() if k!='node'}) for w in self.workers.values()]
        jobs=[]
        for j in self.jobs.values():
            if j.complete is not None:continue
            batches=[b for b in self.batches.values() if b.job==j.id and b.state not in ('COMPLETE','SPLIT')]
            jobs.append(dict(id=j.id,item=j.item,quantity=j.quantity,release=j.release,route=j.route,operation_counts=dict(j.operation_counts),batches=[dict(id=b.id,operation=j.route[b.op_index],state=b.state,quantity=b.hi-b.lo,unloaded=b.unloaded,cycle_quantity=b.cycle[1]-b.cycle[0],owner=b.owner,machine=b.target,location=b.location) for b in batches]))
        phase='warmup' if self.time<self.measure_start else 'measurement' if self.time<self.arrivals_stop else 'drain'
        self.observer(dict(algorithm=self.config.algorithm,replication=self.config.replication,arrival_scale=self.config.arrival_load,batch_scale=self.config.batch_size,time=self.time,phase=phase,window_end=self.arrivals_stop,elapsed_seconds=now-self._wall_start,events=self.counters['events'],machines=machines,workers=workers,jobs=jobs,released=len(self.jobs),completed=sum(j.complete is not None for j in self.jobs.values()),queue=self._counts()[1],ready_queue_by_family=self.ready_queue_counts()))

    def ready_queue_counts(self):
        counts={f:0 for f in self.queue_family_minutes}
        for bid in self.ready:
            counts[self.data.operations[self._key(self.batches[bid])]['machine_family']]+=1
        return counts

    def run(self,until=None):
        self.observe(force=True)
        status='COMPLETE';limit=until if until is not None else self.arrivals_stop+self.config.drain_days*1440
        while self.events:
            if self.cancel():status='CANCELLED';break
            t=self.events[0][0]
            if t>limit:
                self._integrate(limit);status='FINITE_HORIZON_DIAGNOSTIC';break
            self._integrate(t)
            while self.events and self.events[0][0]==t:
                _,_,_,_,kind,payload=heapq.heappop(self.events);self._handle(kind,payload);self.counters['events']+=1
            self._allocate();self._dispatch()
            self.observe()
            if self.config.trace and self.trace_start<=self.time<=self.trace_stop:
                wip,queue,_,_=self._counts();self.snapshots.append(dict(time=self.time,wip=wip,queue=queue,released=len(self.jobs),completed=sum(j.complete is not None for j in self.jobs.values()),ready_queue_by_family=self.ready_queue_counts()))
            if self.counters['events']>=self.config.max_events:status='EVENT_LIMIT';break
            if until is None and self.time>=self.arrivals_stop and all(j.complete is not None for j in self.jobs.values()):break
        for m in self.machines.values():self._close_interval(m,'machine')
        for w in self.workers.values():self._close_interval(w,'worker')
        self.observe(force=True)
        return self.result(status)
    def result(self,status):
        if self.time>=self.arrivals_stop and all(j.complete is not None for j in self.jobs.values()) and status not in ('CANCELLED','EVENT_LIMIT','DEADLOCK_INFEASIBLE'):status='COMPLETE'
        r=super().result(status);duration=r['measurement']['denominator_min'];families={m['machine_family'] for m in self.data.machines.values()}
        resource={}
        for wid,states in self.state_minutes['worker'].items():
            on=sum(v for k,v in states.items() if k not in ('OFF_SHIFT','ON_BREAK'));busy=sum(v for k,v in states.items() if k in WORK or k=='SETUP');resource[wid]={'type':'setup' if self.workers[wid].kind.startswith('setup') else 'operator','busy_min':busy,'on_duty_min':on,'utilization':busy/on if on else 0.}
        groups={}
        for typ in ('setup','operator'):
            vv=[v for v in resource.values() if v['type']==typ];on=sum(v['on_duty_min'] for v in vv);groups[typ]=sum(v['busy_min'] for v in vv)/on if on else 0.
        per_family={}
        for f in families:
            ids=[m for m in self.machines if self.data.machines[m]['machine_family']==f]
            per_family[f]={'machine_count':len(ids),'processing_utilization':sum(self.state_minutes['machine'].get(m,{}).get('PROCESSING',0) for m in ids)/(duration*len(ids)),'busy_utilization':sum(r['per_machine_utilization'].get(m,0) for m in ids)/len(ids),'mean_ready_queue':self.queue_family_minutes[f]/duration}
            per_family[f]['occupied_utilization']=sum(v for m in ids for k,v in self.state_minutes['machine'].get(m,{}).items() if k!='IDLE_AVAILABLE')/(duration*len(ids))
            per_family[f]['waiting_utilization']=sum(v for m in ids for k,v in self.state_minutes['machine'].get(m,{}).items() if k.startswith('WAITING'))/(duration*len(ids))
        r['machine_occupied_utilization']=sum(v for states in self.state_minutes['machine'].values() for k,v in states.items() if k!='IDLE_AVAILABLE')/(duration*len(self.machines))
        r['machine_waiting_utilization']=sum(v for states in self.state_minutes['machine'].values() for k,v in states.items() if k.startswith('WAITING'))/(duration*len(self.machines))
        r['utilization_definitions']={'service':'setup + manual handling + automatic processing; excludes waiting',
            'occupied':'all non-idle machine states, including waiting for service',
            'waiting':'machine WAITING states only','denominator':'calendar minutes in measurement window per machine; excludes drain'}
        r['setup_wait_definition']='Requests whose setup service starts in the measurement window; includes waits begun in warmup, excludes still-pending requests. Not an uncensored all-request mean.'
        r['setup_wait_sample_count']=len(self.setup_waits)
        r['setup_transition_rule']='Distinct operation identity with zero class transition uses lightest positive configured setup tier; same-operation continuation unchanged. Engineering assumption.'
        windows=[w for w in self.weekly if self.measure_start<w['time']<=self.arrivals_stop]
        slope=float(np.polyfit([w['time']/1440 for w in windows],[w['end_wip'] for w in windows],1)[0]) if len(windows)>=3 else None
        code=self.code_hash
        r.update(world_version=self.data.raw.get('version','unknown'),lift_transfers=self.lift_transfers,engine_source_sha256=code,demand_stream=self.demand,demand_sha256=hashlib.sha256(json.dumps(self.demand,sort_keys=True).encode()).hexdigest(),per_family=per_family,resource_statistics=resource,setup_worker_utilization=groups['setup'],worker_available_utilization=groups['operator'],mean_setup_wait_min=statistics.mean(self.setup_waits) if self.setup_waits else 0.,setup_wait_samples_min=self.setup_waits,observation_end=self.terminal_at_stop,wip_slope_jobs_per_day=slope,processing_totals_min=self.processing_totals,handoffs=self.handoffs,peak_processing_machines=self.peak_processing,stability_status='NOT_ESTABLISHED_SINGLE_RUN',model_provenance=self.data.raw['provenance'])
        r['demand_provenance']={'mode':'manual' if self.manual_input else 'exogenous_homogeneous_poisson','effective_arrival_rate':self.data.raw['demand']['baseline_jobs_per_day']*self.config.arrival_load,'baseline_jobs_per_day':self.data.raw['demand']['baseline_jobs_per_day'],'baseline_status':self.data.raw['demand']['baseline_status'],'arrival_load':self.config.arrival_load,'realized_arrival_rate':r['measurement_jobs']/(duration/1440),'rate_unit':'jobs/day'}
        # Relaxation of the implemented unsplit sequential route: each operation
        # gets its fastest eligible machine, with all nonprocessing delays removed.
        measured=[j for j in self.jobs.values() if self.measure_start<=j.release<self.arrivals_stop]
        bounds=[dict(job=j.id,processing_lower_bound_min=j.quantity*sum(min(self.data.processing[j.item,op,m] for m in self.data.eligibility[j.item,op]) for op in j.route)) for j in measured]
        lower=statistics.mean(x['processing_lower_bound_min'] for x in bounds) if bounds else None
        actual=r['mean_flow_min']
        r['flow_reference']={'kind':'PROCESSING_ONLY_LOWER_BOUND','definition':'Quantity times sum of fastest eligible per-unit processing time for every sequential operation. Excludes queues, setup, handling, transport, shifts and contention. Not an attained or proven optimum. Valid for the current no-split sequential-route model.','cohort':'same measurement-release cohort as mean_flow_min','mean_lower_bound_min':lower,'actual_to_lower_bound_ratio':actual/lower if actual is not None and lower else None,'excess_over_lower_bound_percent':100*(actual/lower-1) if actual is not None and lower else None,'per_job':bounds}
        r['queue_definition']='pooled ready execution lots plus unreserved human requests; per-family queues count ready lots only'
        r['routing_semantics']='FIFO pooled queue; ECT over all eligible machines with virtual queued workload; first-service reservation commits machine'
        return r
