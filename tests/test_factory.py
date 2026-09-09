"""Behavioral tests on a small independently defined generic production fixture."""
import copy
from dataclasses import replace
import unittest
from factory.data import Calibration, InputError
from factory.engine import Config, Simulation, cycle_budget, HANDLING_MEAN, WORK
from factory.randomness import Streams
from factory.experiments import confidence, stability


def fixture():
    machines=[dict(id='M1',department='milling',x=10,y=30,w=10,h=10),
              dict(id='M2',department='milling',x=30,y=30,w=10,h=10),
              dict(id='T1',department='turning',x=70,y=30,w=10,h=10)]
    models=[dict(item='A',operation=op,model={'family':'constant','value':2,'mean':2},scale_to_standard=1)
            for op in (1,2,3)]
    return Calibration(dict(machines=machines,processing_models=models,
        machine_eligibility=[dict(item='A',operation=1,machines=['M1','M2']),dict(item='A',operation=2,machines=['T1']),dict(item='A',operation=3,machines=['M2'])],
        historical_jobs=[dict(source_job_id=1,item='A',quantity_proxy=125,route=[1,2,3])],
        worker_profiles=[dict(id='Wm',department='milling',machines=['M1','M2']),dict(id='Wt',department='turning',machines=['T1'])],
        rosters={'milling':{'day_profiles':['Wm'],'night_profiles':['Wm']},'turning':{'day_profiles':['Wt'],'night_profiles':['Wt']}},
        walking_graph={'nodes':[[5,35],[25,35],[50,35],[65,35]],'edges_undirected':[[0,1,20],[1,2,25],[2,3,15]],
          'service_nodes':{'M1':0,'M2':1,'T1':3},'handoff_node':2,'boundary_x':50,'seconds_per_relative_unit':1},
        arrival_calibration={'daily_count_samples_by_weekday_monday0':{str(i):[1] for i in range(7)}}))


def manual(quantity=125,route=None,release=0,id='J1'):
    return dict(id=id,item='A',quantity=quantity,route=route or [1,2,3],release=release)


class FactoryTests(unittest.TestCase):
    def run_fixture(self,jobs=None,**kwargs):
        return Simulation(fixture(),Config(horizon_days=2,trace_days=14,**kwargs),jobs or [manual()]).run()

    def test_full_route_conserves_each_part_and_precedence(self):
        r=self.run_fixture()
        self.assertEqual(r['status'],'COMPLETE')
        ledgers={}
        for e in r['trace']['events']:
            if e['kind']=='parts_unloaded':
                for part in range(e['lo'],e['hi']):
                    key=(e['job'],e['operation'],part)
                    self.assertNotIn(key,ledgers)
                    if e['operation']>1:
                        self.assertLessEqual(ledgers[(e['job'],e['operation']-1,part)],e['time'])
                    ledgers[key]=e['time']
        self.assertEqual(len(ledgers),375)
        job=r['jobs'][0]
        self.assertEqual(job['completed'],125)
        self.assertAlmostEqual(r['mean_flow_min'],job['complete']-job['release'])

    def test_worker_exclusive_and_carries_at_most_sixty(self):
        r=self.run_fixture([manual(id='J1'),manual(id='J2',release=1)],algorithm='CYCLE_TRANSFER')
        self.assertEqual(r['status'],'COMPLETE')
        for wid in {w['id'] for w in r['workers']}:
            busy=sorted((i for i in r['trace']['intervals'] if i['entity']==wid and i['state'] in WORK),key=lambda i:i['start'])
            for a,b in zip(busy,busy[1:]):self.assertLessEqual(a['end'],b['start']+1e-9)
        carried=[e for e in r['trace']['events'] if e['kind']=='carry_start']
        self.assertTrue(carried)
        self.assertTrue(all(1<=e['quantity']<=60 for e in carried))
        for i in r['trace']['intervals']:
            if i.get('path'):
                xs=[r['trace']['nodes'][n][0] for n in i['path']]
                self.assertTrue(max(xs)<=50 if 'milling' in i['entity'] else min(xs)>=50)

    def test_cycle_transfer_can_overlap_successive_operations(self):
        r=self.run_fixture(algorithm='CYCLE_TRANSFER')
        events=[e for e in r['trace']['events'] if e['kind']=='parts_unloaded']
        op1=max(e['time'] for e in events if e['operation']==1)
        op2=min(e['time'] for e in events if e['operation']==2)
        self.assertLess(op2,op1)

    def test_fifo_waits_for_source_operation_but_allows_trip_arrivals(self):
        r=self.run_fixture()
        events=r['trace']['events']
        first_carry=min(e['time'] for e in events if e['kind']=='carry_start')
        final_source=max(e['time'] for e in events if e['kind']=='parts_unloaded' and e['operation']==1)
        self.assertGreaterEqual(first_carry,final_source)

    def test_reproducible_keyed_streams_and_split_processing(self):
        a=Streams(8,'s',0); b=Streams(8,'s',0)
        expected=a.rng('processing',['J',1]).random()
        for i in range(50):b.rng('handling',i).random()
        self.assertEqual(expected,b.rng('processing',['J',1]).random())
        self.assertNotEqual(expected,b.rng('processing',['J',2]).random())
        self.assertEqual(self.run_fixture(),self.run_fixture())
        sims=[Simulation(fixture(),Config(horizon_days=2,algorithm=a,trace=False),[manual()]) for a in ('FIFO','CYCLE_TRANSFER')]
        for sim in sims:sim.run()
        self.assertEqual(sims[0].samples,sims[1].samples)

    def test_cycle_budget_and_short_remainder(self):
        for t in (.01,.1,1,2,3,8,100):
            q,p,adjust=cycle_budget(t,10000)
            self.assertGreaterEqual(p,3-1e-10)
            self.assertAlmostEqual(p+HANDLING_MEAN,q*t+adjust)
        q,p,adjust=cycle_budget(.01,1)
        self.assertEqual(q,1);self.assertGreater(p,0);self.assertGreater(adjust,0)

    def test_no_manual_start_on_break_or_after_shift_end(self):
        r=self.run_fixture([manual(quantity=500,route=[1])])
        busy=[i for i in r['trace']['intervals'] if i['type']=='worker' and i['state'] in {'LOADING','UNLOADING','CYCLE_CHANGE'}]
        breaks=[i for i in r['trace']['intervals'] if i['type']=='worker' and i['state']=='ON_BREAK']
        for i in busy:
            self.assertFalse(any(b['entity']==i['entity'] and b['start']<=i['start']<b['end'] for b in breaks))
        self.assertTrue(any(abs((b['end']-b['start'])-20)<1e-8 for b in breaks))
        self.assertTrue(any(i['state']=='PROCESSING' and i['start']<180<i['end'] for i in r['trace']['intervals']))

    def test_zero_arrivals_no_fake_kpi(self):
        r=Simulation(fixture(),Config(horizon_days=1,arrival_load=0)).run()
        self.assertEqual(r['status'],'NO_MEASUREMENT_JOBS');self.assertIsNone(r['mean_flow_min'])

    def test_zero_workers_fails_input_gate(self):
        raw=copy.deepcopy(fixture().raw)
        for roster in raw['rosters'].values():roster['day_profiles']=[];roster['night_profiles']=[]
        with self.assertRaisesRegex(InputError,'NO_FUTURE'):Calibration(raw)

    def test_unreachable_graph_is_rejected(self):
        raw=copy.deepcopy(fixture().raw);raw['walking_graph']['edges_undirected']=[]
        with self.assertRaisesRegex(InputError,'UNREACHABLE'):Calibration(raw)

    def test_atomic_allocation_rejects_illegal_machine(self):
        sim=Simulation(fixture(),Config(horizon_days=1),[manual()]);sim.run(until=0)
        bid=next(iter(sim.batches))
        self.assertEqual(sim.validate_allocation(bid,'T1'),'MACHINE_INELIGIBLE')

    def test_measurement_cohort_excludes_burnin_and_drains(self):
        cfg=Config(horizon_days=.1,warmup_days=.1,trace_days=4)
        jobs=[manual(20,[1],0,'burn'),manual(300,[1],144,'measure')]
        r=Simulation(fixture(),cfg,jobs).run()
        self.assertEqual(r['measurement_jobs'],1)
        self.assertEqual(r['completed_measurement_jobs'],1)
        j=next(j for j in r['jobs'] if j['id']=='measure')
        self.assertGreater(j['complete'],r['measurement']['stop_min'])
        self.assertAlmostEqual(r['mean_flow_min'],j['complete']-144)

    def test_weekend_has_no_manual_work_friday_daytime(self):
        cfg=Config(horizon_days=3,start_date='2026-09-11T07:00:00',trace_days=4)
        r=Simulation(fixture(),cfg,[manual(1,[1])]).run()
        first=next(i for i in r['trace']['intervals'] if i['state']=='LOADING' and i['type']=='worker')
        self.assertGreaterEqual(first['start'],36*60)

    def test_ci_and_stability_failures_not_success(self):
        self.assertIsNone(confidence([None,4])['mean'])
        self.assertIsNone(confidence([0,0])['relative_half_width'])
        self.assertGreater(confidence([1,100,1,100])['relative_half_width'],.05)
        windows=[dict(time=(i+1)*10080,wip=2,queue=1,throughput=3,machine_utilization=.2,worker_utilization=.1) for i in range(4)]
        self.assertEqual(stability(windows)['warmup_days'],28)
        for w in windows:w['throughput']=0
        self.assertEqual(stability(windows)['status'],'NOT_STABILIZED')

if __name__=='__main__':unittest.main()
