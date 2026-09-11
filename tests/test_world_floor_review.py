"""Floor-local humans, capacity-limited freight lift and uncommitted destination pool."""
import unittest
from factory.engine import Job
from factory.world import World
from factory.world_engine import WorldSimulation, WorldConfig
from tests.test_calibrated_world_review import tiny_world, job


def floor_world():
    raw=tiny_world(machine_count=3,eligibility=[['M1'],['M2','M3'],['M1']],unit_times=(.1,.2,.1)).raw
    raw['version']='floor-review'
    coords=[[100,0],[1300,0],[1400,0]]
    for m,xy in zip(raw['machines'],coords):
        m['x'],m['y']=xy;m['department']='milling' if xy[0]<1150 else 'turning'
    raw['walking_graph'].update(nodes=coords,edges_undirected=[[0,1,1200],[1,2,100]],node_floor_boundary=1150)
    raw['resources'].update(floor_local_workers=True,regular_workers_by_floor={'milling':{'day':2,'night':1},'turning':{'day':2,'night':1}},freight_lift_capacity_units=60,freight_lift_trip_minutes=3)
    return World(raw)


class FloorReview(unittest.TestCase):
    def test_parts_cross_but_workers_do_not_and_lift_serializes(self):
        w=floor_world();sim=WorldSimulation(w,WorldConfig(horizon_days=2,trace_days=4,drain_days=5),[job(w,125,identity='A'),job(w,125,identity='B')]);result=sim.run()
        self.assertEqual(result['status'],'COMPLETE')
        self.assertEqual(result['world_version'],'floor-review')
        self.assertEqual(len(result['lift_transfers']),4)
        transfers=sorted(result['lift_transfers'],key=lambda x:x['start'])
        for t in transfers:
            self.assertEqual(t['quantity'],125);self.assertEqual(t['trips'],3);self.assertAlmostEqual(t['end']-t['start'],9)
        for a,b in zip(transfers,transfers[1:]):self.assertLessEqual(a['end'],b['start'])
        for row in result['trace']['intervals']:
            if row['type']!='worker':continue
            worker=sim.workers[row['entity']]
            for node in row.get('path',[]):
                actual='milling' if w.graph['nodes'][node][0]<1150 else 'turning'
                self.assertEqual(actual,worker.department)
        setup=[w for w in sim.workers.values() if w.kind.startswith('setup')]
        self.assertEqual({(w.department,w.kind) for w in setup},{('milling','setup_day'),('milling','setup_night'),('turning','setup_day'),('turning','setup_night')})
        deliveries=[e for e in result['trace']['events'] if e['kind']=='lift_delivery']
        self.assertEqual(len(deliveries),4)
        self.assertTrue(all(e['target_machine'] is None for e in deliveries))
        self.assertEqual(result['counters']['splits'],0)
        self.assertTrue(all(j['operation_counts']=={'OP01':125,'OP02':125,'OP03':125} for j in result['jobs']))

    def test_transfer_request_does_not_reserve_destination_machine(self):
        world=floor_world();sim=WorldSimulation(world,WorldConfig(horizon_days=1),[job(world,125)])
        # A bounded run stops after the first operation and during lift travel.
        sim.run(until=30)
        transfers=[b for b in sim.batches.values() if b.state in ('WAITING_LIFT','INTERFLOOR_TRANSPORT')]
        self.assertTrue(transfers)
        for b in transfers:
            self.assertIsNone(b.target)
            self.assertTrue(all(m.batch!=b.id for m in sim.machines.values()))

    def test_busy_destination_floor_can_receive_uncommitted_transfer(self):
        world=floor_world();sim=WorldSimulation(world,WorldConfig(horizon_days=1),[])
        route=[o['id'] for o in world.families['PF']['operations']]
        # A valid processing batch occupies each physical machine.
        for mid,oi in [('M1',0),('M2',1),('M3',1)]:
            jid='busy-'+mid;sim.jobs[jid]=Job(jid,'PF',125,route,0)
            busy=sim._new_batch(jid,oi,0,125,location=mid);sim.ready.remove(busy.id)
            busy.state='PROCESSING';busy.cycle=(0,25);busy.cursor=25
            sim.machines[mid].batch=busy.id;sim.machines[mid].state='PROCESSING'
        sim.jobs['transfer']=Job('transfer','PF',125,route,0)
        batch=sim._new_batch('transfer',1,0,125,location='M1')
        for worker in sim.workers.values():
            worker.active=True;worker.node=worker.home_node
        before={mid:m.batch for mid,m in sim.machines.items()}
        self.assertTrue(sim._can_start(batch,'M2'))
        self.assertIsNone(sim.validate_allocation(batch.id,'M2'))
        sim._allocate()
        self.assertEqual(batch.state,'INTERFLOOR_TRANSPORT')
        self.assertIsNone(batch.target)
        self.assertNotIn(batch.id,sim.ready)
        self.assertEqual({mid:m.batch for mid,m in sim.machines.items()},before)

    def test_public_calendar_matches_configured_calendar(self):
        raw=floor_world().raw
        raw['resources'].update(day_start_hour=8,day_end_hour=20,working_weekdays=[0,2])
        world=World(raw);sim=WorldSimulation(world,WorldConfig(horizon_days=1,start_date='2026-09-09T08:00:00'),[])
        state=sim.public_state();cal=state['calendar']
        self.assertEqual(cal['day_hours'],[8,20]);self.assertEqual(cal['night_hours'],[20,8])
        self.assertEqual(cal['day_weekdays'],[0,2]);self.assertEqual(cal['night_start_weekdays'],[0,2])
        self.assertEqual(cal['day_breaks'],[[11,0,20],[14,0,30],[17,0,20]])
        self.assertEqual(cal['night_breaks'],[[23,0,20],[2,0,30],[5,0,20]])
        self.assertEqual(cal['extended_breaks'],[])
        self.assertTrue(all(not row['extended'] and row['kind'] in ('day','night','setup_day','setup_night') for row in state['workers']))
        self.assertEqual({row['service_role'] for row in state['workers']},{'setup','operator'})
        sim._calendar_day(sim.start.replace(hour=0))
        day_worker=next(w for w in sim.workers.values() if w.kind=='day')
        actual=[(event[0],event[4]) for event in sim.events if isinstance(event[5],tuple) and event[5][0]==day_worker.id]
        self.assertIn((0,'shift_start'),actual);self.assertIn((720,'shift_end'),actual)
        self.assertTrue(all((offset,'break') in actual for offset in (180,360,540)))

if __name__=='__main__':unittest.main()
