"""Schedulers receive detached public state; never the world or future samples.

A policy implements decide(snapshot) -> list of actions. Supported actions:
allocate(batch, machine), split(batch, quantities), transfer(batch, lo, hi,
machine). Ordinal intervals are half-open. The engine validates each action
atomically and records a reason code on rejection.
"""


class BaselinePolicy:
    def __init__(self, name='FIFO'):
        self.name = name

    def decide(self, state):
        actions = []
        machines = {m['id']: m for m in state['machines']}
        for buffer in state['outputs']:
            if self.name != 'CYCLE_TRANSFER' and buffer['state'] != 'COMPLETE':
                continue
            target = min((machines[m] for m in buffer['eligible_machines']),
                         key=lambda m: (m['batch'] is not None, m['available_since'], m['id']))
            for lo, hi in buffer['ranges']:
                actions.append(dict(kind='transfer', batch=buffer['id'], lo=lo, hi=hi, machine=target['id']))
        ready = sorted(state['ready'], key=lambda b:
                       ((b['expected_processing_min'],) if self.name == 'SPT' else ()) +
                       (b['ready_time'], b['release_time'], b['id']))
        reserved = set()
        for batch in ready:
            choices = [machines[m] for m in batch['eligible_machines']
                       if machines[m]['batch'] is None and m not in reserved
                       and (batch['target'] is None or batch['target'] == m)]
            if choices:
                machine = min(choices, key=lambda m: (m['available_since'], m['id']))
                actions.append(dict(kind='allocate', batch=batch['id'], machine=machine['id']))
                reserved.add(machine['id'])
        return actions
