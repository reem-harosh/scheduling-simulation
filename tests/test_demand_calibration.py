import unittest
from dataclasses import replace
from test_factory import fixture, manual
from factory.engine import Config, Simulation
from factory.load_calibration import assess

class DemandCalibrationTests(unittest.TestCase):
    def test_idle_roster_has_real_location_without_jobs(self):
        sim=Simulation(fixture(),Config(horizon_days=1),manual_jobs=[])
        result=sim.run(until=60)
        day=[w for w in sim.workers.values() if w.kind=='day']
        self.assertTrue(all(w.active and w.node==w.home_node and w.node is not None for w in day))
        self.assertTrue(all(i.get('node') is not None for i in result['trace']['intervals'] if i['state']=='IDLE_AT_LOCATION'))

    def test_scaling_intensity_preserves_existing_job_mix(self):
        base=Config(horizon_days=7,trace=False)
        a=Simulation(fixture(),base).run(until=7*1440)
        b=Simulation(fixture(),replace(base,baseline_calibration_multiplier=4)).run(until=7*1440)
        old={j['id']:j for j in a['jobs']}; new={j['id']:j for j in b['jobs']}
        self.assertGreater(len(new),len(old))
        for key,j in old.items():
            for field in ('item','quantity','route','release'):self.assertEqual(j[field],new[key][field])
        self.assertEqual(b['demand_provenance']['effective_arrival_rate'],4)

    def test_replay_contains_state_at_measurement_start(self):
        r=Simulation(fixture(),Config(horizon_days=1,warmup_days=1,trace_days=1),[manual(quantity=10000)]).run(until=2880)
        self.assertEqual(r['trace']['start_min'],1440)
        self.assertEqual(r['trace']['end_min'],2880)
        self.assertTrue(any(i['start']<=1440<i['end'] for i in r['trace']['intervals']))
        self.assertTrue(all(i['end']>=1440 for i in r['trace']['intervals']))
        self.assertEqual(r['machine_calendar_utilization'],r['machine_available_utilization'])
        self.assertGreaterEqual(r['worker_available_utilization'],r['worker_utilization'])

    def test_partial_run_denominator_is_observed_window(self):
        r=Simulation(fixture(),Config(horizon_days=28),[manual()]).run(until=60)
        self.assertEqual(r['measurement']['denominator_min'],60)
        self.assertLessEqual(r['bottleneck_utilization'],1)

    def test_overload_is_rejected(self):
        weeks=[dict(time=(i+1)*10080,wip=10+20*i,released=100,throughput=50) for i in range(8)]
        r=dict(measurement={'start_min':0},weekly=weeks,status='FINITE_HORIZON_DIAGNOSTIC',active_machine_utilization=.8,mean_wip=80,mean_queue=30,bottleneck_utilization=.99)
        a=assess(r)
        self.assertEqual(a['status'],'REJECTED')
        self.assertIn('WIP_GROWTH',a['reasons'])
