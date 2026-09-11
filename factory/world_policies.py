"""Pooled dispatching plus ECT over every eligible physical machine.
A preferred busy machine is a revisable plan, never a binding target. Earlier
ready work contributes virtual queued workload within one policy decision.
Actions commit only immediately serviceable machines; later events recompute.
"""
class ECTPolicy:
    def __init__(self,discipline='FIFO',work_conserving=False):
        self.discipline=discipline;self.work_conserving=work_conserving
    def decide(self,state):
        reserved=set();planned={};actions=[]
        rows=sorted(state['ready'],key=lambda b:((b['expected_processing_min'],) if self.discipline=='SPT' else ())+ (b['ready_time'],b['release_time'],b['id']))
        for b in rows:
            choices=[c for c in b['candidates'] if not self.work_conserving or c['can_start']]
            if not choices:continue
            c=min(choices,key=lambda c:(c['ect']+planned.get(c['machine'],0),c['machine']))
            mid=c['machine']
            if c['can_start'] and mid not in reserved and planned.get(mid,0)==0:
                reserved.add(mid);actions.append({'kind':'allocate','batch':b['id'],'machine':mid})
            planned[mid]=planned.get(mid,0)+c.get('processing',0)+c.get('setup_mean',0)+c.get('handling_mean',0)+c.get('transport_mean',0)
        return actions

REGISTRY={'FIFO':lambda:ECTPolicy('FIFO'),'ECT':lambda:ECTPolicy('FIFO'),'SPT':lambda:ECTPolicy('SPT'),'WORK_CONSERVING':lambda:ECTPolicy('FIFO',True)}
def register(name,factory):
    if not name or name in REGISTRY:raise ValueError('Policy name empty or already registered')
    REGISTRY[name]=factory

def make_policy(name):
    try:return REGISTRY[name]()
    except KeyError:raise ValueError('Unknown policy: '+str(name)) from None
