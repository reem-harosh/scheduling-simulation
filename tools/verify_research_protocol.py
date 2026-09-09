"""Exercise the complete experiment protocol using a deterministic controlled demand schedule.

This is a generic verification fixture, not a production result or calibration.
It uses the real event engine, pilot assessment, replications, CI and comparison.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_factory import fixture, manual
from factory.engine import Config,Simulation
from factory.experiments import ExperimentRunner,atomic_json


class ControlledRunner(ExperimentRunner):
    def _run(self, config, until=None):
        stop=(config.warmup_days+config.horizon_days)*1440
        jobs=[manual(1,[1],day*1440,'controlled-'+str(day)) for day in range(int(stop/1440))]
        result=Simulation(self.data,config,jobs).run(until=until)
        return result


def main():
    runner=ControlledRunner(fixture(),'results/protocol-verification',progress=lambda x:print(x,flush=True))
    result=runner.scenario(Config(horizon_days=28,scenario_id='controlled_protocol_fixture',trace=False))
    result['purpose']='Generic deterministic-demand verification fixture; NOT a production estimate'
    atomic_json('results/protocol-verification/result.json',result)
    print(result['status'],{a:s['n'] for a,s in result['algorithms'].items()})
    if result['status']!='PRECISION_MET':raise SystemExit('Protocol fixture did not reach precision')

if __name__=='__main__':main()
