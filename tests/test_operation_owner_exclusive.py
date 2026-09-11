import unittest
from test_calibrated_world_review import tiny_world,job
from factory.world_engine import WorldSimulation,WorldConfig

class ExclusiveOperationOwnerTests(unittest.TestCase):
    def test_free_qualified_colleague_cannot_replace_active_owner(self):
        class AuditedSimulation(WorldSimulation):
            def __init__(self,*args,**kwargs):
                self.owner_waits=[]
                super().__init__(*args,**kwargs)
            def _dispatch(self):
                super()._dispatch()
                for r in self.requests.values():
                    if r['kind'] in ('setup','transport'):continue
                    b=self.batches[r['batch']]
                    owner=self.workers.get(b.owner)
                    if not owner or not (owner.busy or (owner.active and owner.shift==b.owner_shift)):continue
                    if r['reserved']:
                        if r['reserved']!=owner.id:raise AssertionError('Non-owner reserved for manual service')
                    elif any(w.id!=owner.id for w in self._eligible_workers(r['machine'],r['kind'])):
                        self.owner_waits.append((self.time,r['id']))
        w=tiny_world(machine_count=3,unit_times=(.1,))
        w.raw['resources']['cycle_capacity_units']=1
        sim=AuditedSimulation(w,WorldConfig(horizon_days=1,drain_days=2),[job(w,10,identity=str(i)) for i in range(3)])
        r=sim.run()
        self.assertEqual(r['status'],'COMPLETE')
        self.assertTrue(sim.owner_waits,'Fixture must include eligible idle workers blocked by ownership')
        self.assertFalse(r['trace']['operator_assistance'])
        self.assertFalse(any(e['kind']=='operator_assistance' for e in r['trace']['events']))
        for worker in sim.workers:
            intervals=sorted([i for i in r['trace']['intervals'] if i['entity']==worker],key=lambda i:i['start'])
            for a,b in zip(intervals,intervals[1:]):self.assertLessEqual(a['end'],b['start'])
        self.assertTrue(all(j['operation_counts']['OP01']==10 for j in r['jobs']))
