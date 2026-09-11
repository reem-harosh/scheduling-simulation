"""Telemetry is observational: verify identical outcomes and independent snapshots."""
import json,tempfile,unittest
from unittest.mock import patch
from factory.world_engine import WorldSimulation,WorldConfig
from factory.world_experiments import WorldExperimentRunner
from test_calibrated_world_review import tiny_world,job

class LiveTelemetryTests(unittest.TestCase):
    def test_observer_does_not_change_outcomes_and_snapshots_are_detached(self):
        w=tiny_world(quantity=2,unit_times=(.1,.2));cfg=WorldConfig(horizon_days=.1,drain_days=2)
        base=WorldSimulation(w,cfg,[job(w,2)]).run();snapshots=[]
        sim=WorldSimulation(w,cfg,[job(w,2)],observer=snapshots.append)
        with patch('factory.world_engine.wallclock.monotonic',side_effect=range(100000)):
            observed=sim.run()
        for key in ('demand_sha256','jobs','mean_flow_min','machine_utilization','worker_available_utilization'):
            self.assertEqual(base[key],observed[key],key)
        self.assertGreater(len(snapshots),2)
        self.assertEqual(snapshots[0]['released'],0)
        self.assertEqual(snapshots[-1]['completed'],1)
        self.assertTrue(any(s['jobs'] for s in snapshots))
        json.dumps(snapshots,allow_nan=False)
        for s in snapshots:
            self.assertEqual(len(s['machines']),len(w.machines))
            for j in s['jobs']:
                self.assertTrue(all(n<=j['quantity'] for n in j['operation_counts'].values()))
    def test_partial_surface_snapshots_are_not_mutated_by_later_points(self):
        with tempfile.TemporaryDirectory() as d:
            snapshots=[]
            runner=WorldExperimentRunner(tiny_world(quantity=1,unit_times=(.1,)),d,surface_observer=snapshots.append)
            surface=runner.grid(WorldConfig(horizon_days=.01,drain_days=2),grid=[.5,1],batch_grid=[1],replications=1)
            self.assertEqual([len(s['points']) for s in snapshots],[1,2])
            self.assertEqual(len(surface['points']),2)
