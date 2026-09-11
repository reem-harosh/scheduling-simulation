"""Independent integration/research checks; fixture assumptions are synthetic."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from factory.world import World, demand_stream
from factory.world_engine import WorldConfig, WorldSimulation
from factory.world_experiments import WorldExperimentRunner
from factory.world_policies import ECTPolicy
from factory.experiments import confidence
from test_calibrated_world_review import tiny_world, job
from run_factory import Service


class WorldIntegrationIndependentReview(unittest.TestCase):
    def test_busy_fast_ect_preference_is_recomputed_without_binding(self):
        # Public candidate contract only: unavailable fast machine beats idle slow.
        fast={'machine':'FAST','can_start':False,'ect':12.,'processing':8.}
        slow={'machine':'SLOW','can_start':True,'ect':30.,'processing':25.}
        state={'ready':[{'id':'B','expected_processing_min':8.,'ready_time':0.,
                         'release_time':0.,'candidates':[fast,slow]}]}
        policy=ECTPolicy()
        before=copy.deepcopy(state)
        self.assertEqual(policy.decide(state),[])
        self.assertEqual(state,before)
        # A later event revises availability/workload; no stale target is retained.
        fast['ect']=40.
        self.assertEqual(policy.decide(state),[{'kind':'allocate','batch':'B','machine':'SLOW'}])
        # The same policy can subsequently select FAST when that is now earliest.
        fast.update(can_start=True,ect=10.)
        self.assertEqual(policy.decide(state),[{'kind':'allocate','batch':'B','machine':'FAST'}])

    def test_service_selects_world_engine_and_exposes_real_operation_results(self):
        world=tiny_world(quantity=1,unit_times=(.1,.2))
        service=Service(world)
        service.tasks['review']={'status':'RUNNING','cancel':False}
        try:
            with patch('run_factory.atomic_json') as save:
                service.execute('review','run',WorldConfig(horizon_days=.1,drain_days=2),[job(world,1)])
            task=service.tasks['review']
            self.assertEqual(task['status'],'COMPLETE')
            result=task['result']
            self.assertEqual(result['world_version'],world.raw['version'])
            self.assertEqual(result['jobs'][0]['operation_counts'],{'OP01':1,'OP02':1})
            self.assertEqual(result['operating_point']['status'],'NOT_CALIBRATED')
            save.assert_called_once()
        finally:service.executor.shutdown()

    def test_cartesian_grid_persists_every_run_and_pairs_demand(self):
        world=tiny_world(quantity=1,unit_times=(.1,))
        cfg=WorldConfig(horizon_days=1,drain_days=2,seed=5,trace=False)
        with tempfile.TemporaryDirectory() as directory:
            runner=WorldExperimentRunner(world,directory)
            surface=runner.grid(cfg,grid=[.5,1.],batch_grid=[.75,1.25],algorithms=['FIFO','SPT'],replications=2)
            self.assertEqual(len(surface['points']),4)
            files=list((Path(directory)/'raw').glob('*.json'))
            self.assertEqual(len(files),16)
            self.assertEqual(sum(len(p['raw_runs']) for p in surface['points']),16)
            for point in surface['points']:
                for rep in range(2):
                    rows=[r for r in point['raw_runs'] if r['replication']==rep]
                    self.assertEqual(len(rows),2)
                    self.assertEqual(rows[0]['demand_sha256'],rows[1]['demand_sha256'])
                for summary in point['algorithms'].values():
                    self.assertNotEqual(summary['status'],'CALIBRATED')
            for path in files:
                result=json.loads(path.read_text())
                self.assertIn('jobs',result)
                self.assertIn('resource_statistics',result)
                self.assertIn('observation_end',result)
                self.assertEqual(result['dataset_sha256'],world.digest)
            with patch('factory.world_experiments.WorldSimulation',side_effect=AssertionError('Cached run reran')):
                runner.grid(cfg,grid=[.5,1.],batch_grid=[.75,1.25],algorithms=['FIFO','SPT'],replications=2)

    def test_censored_cohort_does_not_report_completed_only_mean(self):
        world=tiny_world(machine_count=1,quantity=1,unit_times=(1000.,))
        config=WorldConfig(horizon_days=.01,drain_days=0,trace=False)
        result=WorldSimulation(world,config,manual_jobs=[job(world,1)]).run()
        self.assertEqual(result['status'],'FINITE_HORIZON_DIAGNOSTIC')
        self.assertIsNone(result['mean_flow_min'])
        self.assertIsNone(result['median_flow_min'])
        self.assertIsNone(result['p95_flow_min'])
        self.assertEqual(result['observation_end']['wip'],1)
        self.assertEqual(result['completed_measurement_jobs'],0)
        self.assertEqual(result['stability_status'],'NOT_ESTABLISHED_SINGLE_RUN')

    def test_drain_flow_and_window_utilization_have_distinct_denominators(self):
        world=tiny_world(machine_count=1,quantity=1,unit_times=(50.,))
        config=WorldConfig(horizon_days=.01,drain_days=1,trace=False)
        result=WorldSimulation(world,config,manual_jobs=[job(world,1)]).run()
        self.assertEqual(result['status'],'COMPLETE')
        self.assertGreater(result['mean_flow_min'],14.4)
        self.assertAlmostEqual(result['measurement']['denominator_min'],14.4)
        self.assertEqual(result['throughput_jobs_per_day'],0)
        self.assertEqual(result['observation_end']['wip'],1)
        self.assertLessEqual(result['machine_utilization'],1)

    def test_uncertainty_requires_independent_valid_replications(self):
        self.assertIsNone(confidence([12])['ci95'])
        self.assertIsNone(confidence([12,None])['mean'])
        ci=confidence([10,12,14])
        self.assertEqual(ci['mean'],12)
        self.assertEqual(ci['n'],3)
        self.assertLess(ci['ci95'][0],12)
        self.assertGreater(ci['ci95'][1],12)

    def test_resource_scenario_changes_world_hash_but_not_exogenous_demand(self):
        base=tiny_world(quantity=2,unit_times=(.1,))
        raw=copy.deepcopy(base.raw)
        raw['resources']['setup_workers']=6
        raw['resources']['regular_day_workers']=3
        modified=World(raw)
        config=WorldConfig(horizon_days=1,seed=5,trace=False)
        self.assertNotEqual(base.digest,modified.digest)
        self.assertEqual(demand_stream(base,config),demand_stream(modified,config))
        sim=WorldSimulation(modified,config,manual_jobs=[])
        self.assertEqual(sum(w.kind.startswith('setup') for w in sim.workers.values()),6)
        self.assertEqual(sum(w.kind=='day' for w in sim.workers.values()),3)

    def test_manual_demand_provenance_is_not_claimed_poisson(self):
        world=tiny_world(quantity=1,unit_times=(.1,))
        result=WorldSimulation(world,WorldConfig(horizon_days=.1,drain_days=1,trace=False),manual_jobs=[job(world,1)]).run()
        self.assertEqual(result['demand_provenance']['mode'],'manual')

if __name__=='__main__':unittest.main()
