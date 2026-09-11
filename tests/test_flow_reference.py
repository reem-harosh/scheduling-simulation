import unittest
from factory.world_engine import WorldConfig,WorldSimulation
from test_calibrated_world_review import tiny_world,job

class FlowReferenceTests(unittest.TestCase):
    def test_reference_sums_every_operation_and_uses_same_cohort(self):
        w=tiny_world(quantity=2,unit_times=(.1,.2))
        r=WorldSimulation(w,WorldConfig(horizon_days=.1,drain_days=2),[job(w,2)]).run()
        ref=r['flow_reference']
        self.assertAlmostEqual(ref['mean_lower_bound_min'],.6)
        self.assertEqual(len(ref['per_job']),1)
        self.assertGreaterEqual(r['mean_flow_min'],ref['mean_lower_bound_min'])
        self.assertAlmostEqual(ref['actual_to_lower_bound_ratio'],r['mean_flow_min']/.6)
    def test_no_cohort_has_no_reference_or_ratio(self):
        w=tiny_world(quantity=1,unit_times=(.1,))
        r=WorldSimulation(w,WorldConfig(horizon_days=.01),[]).run()
        self.assertIsNone(r['flow_reference']['mean_lower_bound_min'])
        self.assertIsNone(r['flow_reference']['actual_to_lower_bound_ratio'])
