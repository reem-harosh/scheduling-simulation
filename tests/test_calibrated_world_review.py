"""Independent behavioral checks using a hand-computable synthetic world."""
import copy
import unittest
from factory.world import World, demand_stream
from factory.world_engine import WorldConfig, WorldSimulation
from factory.world_policies import ECTPolicy
from factory.data import InputError


def tiny_world(quantity=125, machine_count=2, unit_times=(.1, .2, .3), eligibility=None):
    mids=[f'M{i+1}' for i in range(machine_count)]
    ops=[dict(id=f'OP{i+1:02}',name=f'Milling stage {i+1}',machine_family='Milling',position=i+1,
              setup_class=chr(65+i),eligible_machines=(eligibility[i] if eligibility else mids))
         for i in range(len(unit_times))]
    classes=[o['setup_class'] for o in ops]
    raw=dict(version='review-fixture', source_sha256='synthetic-review-fixture',
        part_families=[dict(id='PF',complexity=1,demand_probability=1,quantity_values=[quantity],operations=ops)],
        machines=[dict(id=m,department='floor',machine_family='Milling',speed=1,x=i*10,y=0) for i,m in enumerate(mids)],
        processing_matrix=[dict(part_family='PF',operation_id=o['id'],machine=m,time_per_unit=t) for o,t in zip(ops,unit_times) for m in o['eligible_machines']],
        setup_matrices=[dict(machine_family='Milling',from_class=a,to_class=b,type='None' if a==b else 'Minor',triangular=[0,0,0] if a==b else [2,2,2]) for a in ['INITIAL']+classes for b in classes],
        walking_graph=dict(nodes=[[i*10,0] for i in range(machine_count)],edges_undirected=[[i,i+1,10] for i in range(machine_count-1)],service_nodes={m:i for i,m in enumerate(mids)},handoff_node=0,seconds_per_relative_unit=1),
        demand=dict(baseline_jobs_per_day=10,baseline_status='synthetic-review'),
        resources=dict(regular_day_workers=2,regular_night_workers=2,setup_workers=4,cycle_capacity_units=25,transport_capacity_units=60,working_weekdays=list(range(7)),day_start_hour=7,day_end_hour=19),
        provenance={'fixture':'Synthetic independent reviewer example'})
    return World(raw)


def job(world, quantity=125, release=0, identity='J'):
    return dict(id=identity,item='PF',quantity=quantity,release=release,route=[o['id'] for o in world.families['PF']['operations']])


def run(world, jobs=None, **config):
    cfg=WorldConfig(horizon_days=2,trace_days=4,drain_days=10,**config)
    sim=WorldSimulation(world,cfg,manual_jobs=jobs if jobs is not None else [job(world)])
    return sim,sim.run()


class CalibratedWorldIndependentReview(unittest.TestCase):
    def test_repeated_family_operations_and_same_machine_setup(self):
        world=tiny_world(machine_count=1)
        sim,r=run(world)
        self.assertEqual(r['status'],'COMPLETE')
        self.assertEqual(r['jobs'][0]['operation_counts'],{'OP01':125,'OP02':125,'OP03':125})
        self.assertEqual(len(r['batches']),3)
        setups=[e for e in r['trace']['events'] if e['kind']=='setup_start']
        self.assertEqual([(e['from_class'],e['to_class']) for e in setups],[('INITIAL','A'),('A','B'),('B','C')])
        self.assertEqual({e['machine'] for e in setups},{'M1'})
        for batch,t in zip(sorted(r['batches'],key=lambda b:b['op_index']),(.1,.2,.3)):
            self.assertAlmostEqual(r['processing_totals_min'][batch['id']],125*t)
        owners=[e for e in r['trace']['events'] if e['kind']=='ownership_acquire']
        self.assertEqual(len(owners),3)
        self.assertEqual(len([e for e in r['trace']['events'] if e['kind']=='ownership_release']),3)

    def test_transport_capacity_does_not_split_execution_batch(self):
        world=tiny_world(eligibility=[['M1'],['M2'],['M1']])
        _,r=run(world)
        self.assertEqual(r['status'],'COMPLETE')
        self.assertEqual(r['counters']['splits'],0)
        self.assertEqual(len(r['batches']),3)
        carries=[e for e in r['trace']['events'] if e['kind']=='carry_start']
        self.assertEqual(sorted(e['quantity'] for e in carries),[5,5,60,60,60,60])
        self.assertEqual(r['counters']['transport_trips'],6)
        self.assertTrue(all(b['hi']-b['lo']==125 for b in r['batches']))

    def test_mechanical_duration_is_job_and_seed_independent(self):
        world=tiny_world(machine_count=1,unit_times=(.123,))
        totals=[]
        for seed in (1,42):
            _,r=run(world,[job(world,30,identity='A'),job(world,30,identity='B')],seed=seed)
            totals.extend(r['processing_totals_min'].values())
        self.assertEqual(len(totals),4)
        for value in totals:self.assertAlmostEqual(value,30*.123)

    def test_owner_handoff_after_shift_and_no_manual_overlap(self):
        world=tiny_world(machine_count=1,unit_times=(3.,))
        world.raw['resources']['cycle_capacity_units']=1
        _,r=run(world,[job(world,1,release=717)])
        self.assertEqual(r['status'],'COMPLETE')
        self.assertTrue(r['handoffs'])
        handoff=r['handoffs'][0]
        self.assertEqual(handoff['operation'],'OP01')
        self.assertNotEqual(handoff['previous_worker'],handoff['worker'])
        self.assertGreaterEqual(handoff['time'],720)
        intervals=[i for i in r['trace']['intervals'] if i['type']=='worker' and i['state'] in ('LOADING','UNLOADING','CYCLE_CHANGE','SETUP','CARRYING','WALKING')]
        for wid in {i['entity'] for i in intervals}:
            ii=sorted((i for i in intervals if i['entity']==wid),key=lambda i:i['start'])
            for a,b in zip(ii,ii[1:]):self.assertLessEqual(a['end'],b['start']+1e-9)
        for i in intervals:
            if i['entity'].startswith('S'):self.assertIn(i['state'],('WALKING','SETUP'))

    def test_processing_releases_operator_for_other_machine(self):
        world=tiny_world(unit_times=(30.,))
        world.raw['resources']['cycle_capacity_units']=1
        # Roster was constructed already: constrain skills on one day worker.
        for pid,p in world.profiles.items():
            if pid=='day01':p['machines']=[]
        _,r=run(world,[job(world,1,identity='A'),job(world,1,identity='B')])
        machine=[i for i in r['trace']['intervals'] if i['type']=='machine' and i['state']=='PROCESSING']
        loads=[i for i in r['trace']['intervals'] if i['type']=='worker' and i['state']=='LOADING']
        self.assertEqual(len(loads),2)
        self.assertEqual(loads[0]['entity'],loads[1]['entity'])
        self.assertTrue(any(p['start']<loads[1]['start']<p['end'] for p in machine))

    def test_demand_crn_across_policy_and_quantity_scale(self):
        world=tiny_world(quantity=125)
        a=demand_stream(world,WorldConfig(seed=5,horizon_days=3,algorithm='FIFO',scenario_id='fifo'))
        b=demand_stream(world,WorldConfig(seed=5,horizon_days=3,algorithm='SPT',scenario_id='spt'))
        c=demand_stream(world,WorldConfig(seed=5,horizon_days=3,batch_size=1.5,scenario_id='scaled'))
        self.assertTrue(a)
        self.assertEqual(a,b)
        for x,y in zip(a,c):
            self.assertEqual({k:v for k,v in x.items() if k!='quantity'},{k:v for k,v in y.items() if k!='quantity'})
            self.assertEqual(y['quantity'],188)
        faster=demand_stream(world,WorldConfig(seed=5,horizon_days=3,arrival_load=2))
        for x,y in zip(a,faster):
            self.assertAlmostEqual(x['release'],2*y['release'])
            self.assertEqual(x['base_quantity'],y['base_quantity'])

    def test_policy_snapshot_is_detached(self):
        world=tiny_world();sim=WorldSimulation(world,WorldConfig(horizon_days=1),manual_jobs=[])
        snapshot=sim.public_state();snapshot['machines'][0]['state']='CORRUPT';snapshot['workers'][0]['skills'].clear()
        self.assertEqual(sim.machines['M1'].state,'IDLE_AVAILABLE')
        self.assertTrue(next(iter(sim.workers.values())).skills)

    def test_atomic_allocations_and_unknown_action(self):
        world=tiny_world();sim=WorldSimulation(world,WorldConfig(horizon_days=1),manual_jobs=[])
        sim._handle('release',job(world,1,identity='A'));sim._handle('release',job(world,1,identity='B'))
        bids=list(sim.ready)
        self.assertEqual(sim.accept_allocation(bids[0],'M1'),'NO_START_RESOURCE')
        self.assertIsNone(sim.machines['M1'].batch)
        specialist=sim.workers['S01'];specialist.active=True;specialist.state='IDLE_AT_LOCATION';specialist.node=0
        self.assertIsNone(sim.accept_allocation(bids[0],'M1'))
        self.assertTrue(specialist.busy)
        self.assertEqual(sim.accept_allocation(bids[1],'M2'),'NO_START_RESOURCE')
        self.assertIsNone(sim.machines['M2'].batch)
        self.assertEqual(sim.accept_allocation(bids[0],'M2'),'RESOURCE_BUSY')
        self.assertEqual(sim.accept_allocation('missing','M1'),'UNKNOWN_ENTITY')
        self.assertEqual(sim.apply_action(dict(kind='split',batch=bids[1],quantities=[1,1])),'SPLIT_DISABLED_BASELINE')
        self.assertEqual(sim.apply_action(dict(kind='unsupported')),'UNKNOWN_ACTION')

    def test_first_resource_is_reserved_for_new_commitment(self):
        world=tiny_world();sim=WorldSimulation(world,WorldConfig(horizon_days=1),manual_jobs=[])
        sim._handle('release',job(world,1,identity='old'));sim._handle('release',job(world,1,identity='new'))
        old,new=list(sim.ready)
        # Existing transported batch is waiting for a setup specialist.
        sim.ready.remove(old);sim.machines['M1'].batch=old
        sim.batches[old].location='M1';sim.batches[old].state='WAITING_SETUP'
        sim._request('setup','floor',0,machine='M1',batch=old)
        specialist=sim.workers['S01'];specialist.active=True;specialist.state='IDLE_AT_LOCATION';specialist.node=0
        response=sim.accept_allocation(new,'M2')
        if response is None:
            self.assertTrue(any(r['batch']==new and r['reserved'] for r in sim.requests.values()),
                            'New machine commitment was accepted but its first worker was reserved for older work')
        else:
            self.assertIsNone(sim.machines['M2'].batch)

    def test_operation_ids_need_not_sort_lexically(self):
        world=tiny_world(machine_count=1,unit_times=(.1,.2))
        raw=copy.deepcopy(world.raw)
        raw['part_families'][0]['operations'][0]['id']='ROUGH'
        raw['part_families'][0]['operations'][1]['id']='FINISH'
        for r in raw['processing_matrix']:r['operation_id']={'OP01':'ROUGH','OP02':'FINISH'}[r['operation_id']]
        world=World(raw)
        _,r=run(world,[job(world,1)])
        self.assertEqual(r['status'],'COMPLETE')
        self.assertEqual(r['jobs'][0]['route'],['ROUGH','FINISH'])

if __name__=='__main__':unittest.main()
