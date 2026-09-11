"""Behavioral regressions found in the September 2026 multi-agent review."""
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from factory.world import World
from factory.world_engine import WorldConfig, WorldSimulation
from factory.world_experiments import WorldExperimentRunner
from factory.experiments import confidence
from factory.data import InputError
from run_factory import Service
from test_calibrated_world_review import tiny_world,job

class ReviewRegressions(unittest.TestCase):
    def test_distinct_operation_same_class_requires_preparation(self):
        raw=tiny_world(quantity=1,machine_count=1,unit_times=(.1,.2)).raw
        raw['part_families'][0]['operations'][1]['setup_class']='A'
        w=World(raw)
        self.assertEqual(w.transition('M1',('PF','OP01'),('PF','OP01'))['triangular'],[0,0,0])
        r=WorldSimulation(w,WorldConfig(horizon_days=.1,trace_days=1),[job(w,1)]).run()
        setups=[e for e in r['trace']['events'] if e['kind']=='setup_start']
        self.assertEqual(len(setups),2)
        self.assertEqual((setups[1]['from_class'],setups[1]['to_class']),('A','A'))
        self.assertEqual(r['jobs'][0]['operation_counts'],{'OP01':1,'OP02':1})

    def test_default_nf12_has_positive_same_class_transition(self):
        w=World.load('research/world_v05/world.json')
        mid=w.eligibility['NF12','OP050'][0]
        self.assertEqual(w.transition(mid,('NF12','OP040'),('NF12','OP050'))['triangular'],[8,15,25])

    def test_initial_capacity_during_day_night_break_and_offday(self):
        w=World.load('research/world_v05/world.json')
        for date,operators,setups,on_break in [('2026-09-09T08:00:00',24,2,False),('2026-09-09T00:00:00',12,2,False),('2026-09-09T10:10:00',24,2,True),('2026-09-11T12:00:00',0,0,False)]:
            with self.subTest(date=date):
                sim=WorldSimulation(w,WorldConfig(start_date=date,horizon_days=.1),[])
                sim.run(until=1)
                self.assertEqual(sum(x.active and not x.kind.startswith('setup') for x in sim.workers.values()),operators)
                self.assertEqual(sum(x.active and x.kind.startswith('setup') for x in sim.workers.values()),setups)
                self.assertEqual(any(x.state=='ON_BREAK' for x in sim.workers.values()),on_break)
                if on_break:
                    self.assertTrue(all(abs(x.break_until-10)<1e-8 for x in sim.workers.values() if x.active))

    def test_reject_invalid_config_before_sampling(self):
        for c in [WorldConfig(arrival_load=float('inf')),WorldConfig(seed=True),WorldConfig(replication=-1),WorldConfig(max_events=0)]:
            with self.subTest(config=c),patch('factory.world_engine.demand_stream',side_effect=AssertionError('sampler reached')):
                with self.assertRaises(InputError):WorldSimulation(tiny_world(),c)

    def test_malformed_request_and_large_warmup(self):
        service=Service(tiny_world())
        try:
            for payload in [[],None,{'config':[]},{'config':{'warmup_days':731}}]:
                with self.subTest(payload=payload),self.assertRaises(ValueError):service.submit(payload)
        finally:service.executor.shutdown(wait=True)

    def test_single_replication_retains_descriptive_summaries_without_ci(self):
        self.assertEqual(confidence([4]),{'n':1,'mean':4,'half_width':None,'relative_half_width':None,'ci95':None})
        with TemporaryDirectory() as d:
            p=WorldExperimentRunner(tiny_world(quantity=2,machine_count=1,unit_times=(.1,)),d).scenario(WorldConfig(horizon_days=.1,drain_days=2,seed=17),replications=1)
        for a in ('FIFO','SPT'):
            self.assertIsNotNone(p['algorithms'][a]['throughput']['mean'])
            self.assertIsNone(p['algorithms'][a]['throughput']['ci95'])
        self.assertEqual(p['paired_comparisons']['SPT']['mean'],0)
        self.assertEqual(p['algorithms']['FIFO']['stability_evidence'],'INSUFFICIENT_WEEKLY_OBSERVATIONS')

    def test_machine_waiting_occupies_capacity_but_is_not_service(self):
        w=tiny_world(quantity=1,machine_count=1,unit_times=(4,))
        r=WorldSimulation(w,WorldConfig(horizon_days=.2,drain_days=2,trace=False),[job(w,1,release=179)]).run()
        self.assertGreater(r['machine_occupied_utilization'],r['machine_utilization'])
        self.assertAlmostEqual(r['machine_waiting_utilization']*.2*1440,19)
        self.assertAlmostEqual(r['machine_occupied_utilization'],r['machine_utilization']+r['machine_waiting_utilization'])

    def test_queue_telemetry_and_replay_counts_use_actual_ready_lots(self):
        w=tiny_world(quantity=2,machine_count=1,unit_times=(4,));seen=[]
        sim=WorldSimulation(w,WorldConfig(horizon_days=.1,drain_days=2),[job(w,2,identity='A'),job(w,2,identity='B')],observer=seen.append)
        with patch('factory.world_engine.wallclock.monotonic',side_effect=range(100000)):
            r=sim.run()
        self.assertTrue(any(x['ready_queue_by_family']['Milling']>0 for x in seen))
        for x in seen:self.assertLessEqual(sum(x['ready_queue_by_family'].values()),x['queue'])
        self.assertTrue(any(x['ready_queue_by_family']['Milling']>0 for x in r['trace']['snapshots']))

if __name__=='__main__':unittest.main()
