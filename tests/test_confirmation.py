import copy
import unittest
from factory.engine import ENGINE_SOURCE_SHA256
from tools.confirm_operating_point import confirm

class ConfirmationTests(unittest.TestCase):
    def rows(self):
        return [dict(config=dict(replication=i,horizon_days=728,warmup_days=364,algorithm='FIFO'),
          status='FINITE_HORIZON_DIAGNOSTIC',engine_source_sha256=ENGINE_SOURCE_SHA256,dataset_sha256='fixture',
          assessment=dict(wip_slope_jobs_per_day=0,arrivals=500,completions=500),
          activity=dict(distinct_moving_workers=4,concurrent_machine_minutes=dict(milling=100,turning=100)),
          measurement_jobs=500,mean_wip=10,mean_queue=20,machine_utilization=.3,machine_available_utilization=.3,
          active_machine_utilization=.6,bottleneck_utilization=.8,worker_available_utilization=.6,throughput_jobs_per_day=500/728)
          for i in range(100,108)]

    def test_balanced_active_fixture_can_pass(self):
        self.assertTrue(confirm(self.rows())['accepted'])

    def test_positive_drift_is_not_called_stable(self):
        rows=self.rows()
        for r in rows:r['assessment']['wip_slope_jobs_per_day']=.001
        self.assertIn('RESIDUAL_POSITIVE_WIP_TREND',confirm(rows)['reasons'])

    def test_mixed_config_and_duplicate_seeds_cannot_confirm(self):
        rows=self.rows();rows[1]['config']['algorithm']='SPT'
        self.assertIn('MIXED_CONFIGURATIONS',confirm(rows)['reasons'])
        rows=self.rows();rows[1]['config']['replication']=100
        self.assertFalse(confirm(rows)['accepted'])
