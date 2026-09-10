"""Audit a saved engine result without modifying it or assigning a visual score."""
import argparse
import json
from pathlib import Path


def validate(result):
    issues=[]
    workers={w['id']:w for w in result['workers']}
    tracks={}
    for interval in result['trace']['intervals']:
        tracks.setdefault(interval['entity'],[]).append(interval)
        if interval['end']<interval['start']:issues.append('negative interval duration')
        if interval['type']=='worker':
            if interval['state']!='OFF_SHIFT' and interval.get('node') is None and not interval.get('path'):
                issues.append('on-duty worker has no location: '+interval['entity'])
            if interval.get('machine') and interval['state'] in ('LOADING','UNLOADING','CYCLE_CHANGE'):
                if interval['machine'] not in workers[interval['entity']]['skills']:
                    issues.append('worker skill violation: '+interval['entity'])
    for entity,intervals in tracks.items():
        ordered=sorted(intervals,key=lambda i:i['start'])
        for first,second in zip(ordered,ordered[1:]):
            if first['end']>second['start']+1e-8:issues.append('overlapping resource states: '+entity)
    for event in result['trace']['events']:
        if event['kind']=='carry_start' and not 1<=event['quantity']<=60:
            issues.append('transport capacity violation')
    if result['status']=='COMPLETE':
        for job in result['jobs']:
            if job['completed']!=job['quantity']:issues.append('final quantity mismatch: '+job['id'])
            if any(job['operation_counts'].get(str(op),job['operation_counts'].get(op))!=job['quantity'] for op in job['route']):
                issues.append('operation quantity mismatch: '+job['id'])
    return dict(passed=not issues,issues=issues,resource_tracks=len(tracks),jobs=len(result['jobs']),
        replay_start_min=result['trace'].get('start_min',0),activity=result.get('activity'),
        scope='Resource exclusivity and location/skills within saved trace; per-operation conservation for drained jobs. Stability and visual quality require separate review.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('result');a=p.parse_args()
    report=validate(json.loads(Path(a.result).read_text()))
    print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
