"""Material conservation through multi-trip transfers, warmup, and task progress."""
import unittest
from tempfile import TemporaryDirectory
from test_calibrated_world_review import tiny_world, job
from factory.world_engine import WorldConfig, WorldSimulation
from factory.world_experiments import WorldExperimentRunner
from factory.progress import TaskProgress


class MaterialReplayTests(unittest.TestCase):
    def test_ranges_conserved_and_partial_trip_locations(self):
        world=tiny_world(eligibility=[['M1'],['M2'],['M1']])
        config=WorldConfig(horizon_days=.2,trace_days=1)
        result=WorldSimulation(world,config,[job(world)]).run()
        current={};partial=False
        for frame in result['trace']['material']:
            for bid in frame['remove']:current.pop(bid,None)
            current.update({r['id']:r for r in frame['upsert']})
            parts=[s for r in current.values() for s in r['segments']]
            if frame['time']<result['jobs'][0]['complete']:
                self.assertEqual(sorted(n for s in parts for n in range(s['lo'],s['hi'])),list(range(1,126)))
            carrying=[s for s in parts if s['state']=='CARRYING']
            for s in carrying:self.assertLessEqual(s['quantity'],60)
            if carrying and any(s['location']=='M2' and s['quantity']==60 for s in parts) and any(s['location']=='M1' and s['quantity']==5 for s in parts):partial=True
        self.assertTrue(partial,'Second trip must leave 60 at destination, carry 60 and leave 5 at source')
        self.assertFalse(current)
        self.assertTrue(all(row['state']=='IDLE_AVAILABLE' for row in result['trace']['end_resources'] if row['id'] in world.machines))
        config.trace=False
        no_trace=WorldSimulation(world,config,[job(world)]).run()
        self.assertEqual(result['jobs'],no_trace['jobs'],'Telemetry must not alter scheduling or RNG outcomes')
        self.assertEqual(result['counters'],no_trace['counters'])

    def test_warmup_starts_with_current_ranges_and_owner(self):
        world=tiny_world(unit_times=(1,2,3))
        result=WorldSimulation(world,WorldConfig(warmup_days=.05,horizon_days=.1,trace_days=1),[job(world)]).run()
        frame=result['trace']['material'][0]
        self.assertGreaterEqual(frame['time'],72)
        parts=[s for r in frame['upsert'] for s in r['segments']]
        self.assertEqual(sum(s['quantity'] for s in parts),125)
        self.assertTrue(any(s['state']=='OUTPUT' for s in parts))
        self.assertTrue(any(r['owner'] for r in frame['upsert']))

    def test_progress_grid_and_cache_finish(self):
        world=tiny_world(quantity=2,machine_count=1,unit_times=(.1,))
        with TemporaryDirectory() as directory:
            for cached in (False,True):
                task={};progress=TaskProgress(task,8);events=[]
                def run_event(e):
                    events.append(e);progress.run_event(e)
                runner=WorldExperimentRunner(world,directory,observer=progress.observe,run_observer=run_event)
                runner.grid(WorldConfig(horizon_days=.1,trace=False),grid=(.5,1),replications=1)
                self.assertEqual(progress.done,8)
                self.assertEqual(len([e for e in events if e['kind']=='complete']),8)
                self.assertEqual(progress.cached,8 if cached else 0)
                self.assertLess(task['progress']['fraction'],1)
                progress.finish('COMPLETE')
                self.assertEqual(task['progress']['fraction'],1)
                self.assertEqual(task['progress']['eta_seconds'],0)
