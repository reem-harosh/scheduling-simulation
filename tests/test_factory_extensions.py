import unittest
from test_factory import fixture,manual
from factory.engine import Simulation,Config
from factory.policies import BaselinePolicy
from factory.experiments import ExperimentRunner
from unittest.mock import patch
from tempfile import TemporaryDirectory


class OnePartPolicy(BaselinePolicy):
    def __init__(self):super().__init__('CYCLE_TRANSFER')
    def decide(self,state):
        actions=super().decide(state)
        for action in actions:
            if action['kind']=='transfer':
                action['hi']=action['lo']+1
        return actions


class ExtensionsTests(unittest.TestCase):
    def test_arbitrary_one_part_transfers_preserve_flow(self):
        sim=Simulation(fixture(),Config(horizon_days=2),[manual(7)],policy=OnePartPolicy())
        r=sim.run()
        self.assertEqual(r['status'],'COMPLETE')
        carries=[e for e in r['trace']['events'] if e['kind']=='carry_start']
        self.assertTrue(carries)
        self.assertTrue(all(e['quantity']==1 for e in carries))
        self.assertEqual(r['jobs'][0]['completed'],7)

    def test_public_state_detached_no_future_information(self):
        sim=Simulation(fixture(),Config(horizon_days=1),[manual(3,release=40)])
        state=sim.public_state()
        self.assertEqual(state['jobs'],[])
        self.assertNotIn('samples',state)
        state['machines'][0]['state']='BROKEN'
        self.assertNotEqual(next(iter(sim.machines.values())).state,'BROKEN')

    def test_invalid_transfer_has_no_side_effect(self):
        sim=Simulation(fixture(),Config(horizon_days=1),[manual(3)])
        sim.run(until=0)
        bid=next(iter(sim.batches))
        before=sim.batches[bid].available_output[:]
        self.assertEqual(sim.apply_action(dict(kind='transfer',batch=bid,lo=1,hi=2,machine='T1')),'PRECEDENCE_NOT_MET')
        self.assertEqual(sim.batches[bid].available_output,before)

    def test_cancellation_is_not_completion(self):
        sim=Simulation(fixture(),Config(horizon_days=1),[manual()],cancel=lambda:True)
        self.assertEqual(sim.run()['status'],'CANCELLED')

    def test_protocol_synchronizes_n_and_records_failed_precision(self):
        windows=[dict(time=(i+1)*10080,wip=2,queue=1,throughput=7,machine_utilization=.2,worker_utilization=.1) for i in range(4)]
        calls=[]
        def fake_run(cfg,until=None):
            calls.append((cfg.namespace,cfg.algorithm,cfg.replication))
            if until:return {'weekly':windows,'status':'FINITE_HORIZON_DIAGNOSTIC'}
            # One policy deliberately has high variance. Both must use n=100.
            value=1 if cfg.algorithm=='FIFO' else (1 if cfg.replication%2 else 1000)
            return {'status':'COMPLETE','mean_flow_min':value}
        with TemporaryDirectory() as folder:
            runner=ExperimentRunner(fixture(),folder)
            with patch.object(runner,'_run',side_effect=fake_run):result=runner.scenario()
        self.assertEqual(sum(ns=='pilot' for ns,_,_ in calls),10)
        self.assertEqual(result['status'],'PRECISION_NOT_MET')
        self.assertTrue(all(s['n']==100 for s in result['algorithms'].values()))
        self.assertEqual(result['paired_comparisons']['CYCLE_TRANSFER']['n'],100)

if __name__=='__main__':unittest.main()
