"""Read-only material ledger for the calibrated, unsplit-lot world.

Frames are deltas at settled DES timestamps. Ranges are half-open; a token in
the UI represents a range, not an extra simulated part. Manual service changes
quantities atomically at its completion, just like the scheduler.
"""
import copy


def material_rows(sim):
    requests = {r['batch']: r for r in sim.requests.values() if r['kind'] == 'transport'}
    lifts = {r['batch']: r for r in sim.lift_transfers if r['end'] > sim.time}
    rows = {}
    capacity = sim.data.raw['resources']['transport_capacity_units']
    for bid in tuple(sim._material_active):
        b = sim.batches[bid]
        if b.state in ('COMPLETE', 'SPLIT'):
            sim._material_active.discard(bid)
            continue
        j = sim.jobs[b.job]
        m = sim.machines.get(b.target)
        state = m.state if m and m.batch == bid else b.state
        row = dict(id=bid, job=b.job, operation=j.route[b.op_index], op_index=b.op_index,
                   lo=b.lo, hi=b.hi, unloaded=b.unloaded, cycle=list(b.cycle),
                   state=state, location=b.location, machine=b.target, owner=b.owner,
                   owner_active=bool(b.owner and (sim.workers[b.owner].active or sim.workers[b.owner].busy)),
                   segments=[])
        def add(lo, hi, status, location=None, **extra):
            if hi > lo:
                row['segments'].append(dict(lo=lo, hi=hi, quantity=hi-lo,
                                            state=status, location=location, **extra))
        r = requests.get(bid)
        if r:
            dest = '@floor:'+r['department'] if r.get('floor_handoff') else r['machine']
            arrived = min(b.hi, b.lo+r['trip']*capacity)
            w = sim.workers.get(r['reserved'])
            moving = w and w.state == 'CARRYING' and getattr(w, '_metadata', {}).get('request') == r['id']
            end = min(b.hi, arrived+capacity) if moving else arrived
            add(b.lo, arrived, 'WAITING_INPUT', dest)
            add(arrived, end, 'CARRYING', None, worker=w.id if moving else None)
            add(end, b.hi, 'WAITING_TRANSPORT', b.location)
        elif bid in lifts:
            lift = lifts[bid]
            # The engine models one aggregate lift shipment, not individual trips.
            add(b.lo, b.hi, 'LIFT' if sim.time >= lift['start'] else 'WAITING_LIFT', b.location,
                lift_start=lift['start'], lift_end=lift['end'],
                destination='@floor:'+lift['destination_floor'])
        else:
            done = b.lo+b.unloaded
            add(b.lo, done, 'COMPLETE' if b.op_index == len(j.route)-1 else 'OUTPUT', b.location)
            inside = state in ('PROCESSING', 'WAITING_FOR_WORKER_UNLOAD', 'WAITING_FOR_CYCLE_CHANGE', 'UNLOADING', 'CYCLE_CHANGE')
            end = b.cycle[1] if inside else done
            add(done, end, state, b.location)
            if state == 'LOADING':
                loaded = min(b.hi, end+sim.data.raw['resources']['cycle_capacity_units'])
                add(end, loaded, 'LOADING', b.location)
                end = loaded
            add(end, b.hi, 'WAITING_INPUT', b.location)
        rows[bid] = row
    return rows


def capture_material(sim):
    if not sim.config.trace or not sim.trace_start <= sim.time <= sim.trace_stop:
        return
    rows = material_rows(sim)
    # A state beginning exactly at the trace boundary has no positive-length
    # interval. Retain the settled state so the final replay frame is truthful.
    sim._replay_end_resources = [dict(id=e.id,start=e.since,state=e.state,
        **copy.deepcopy(getattr(e,'_metadata',{})))
        for e in [*sim.machines.values(),*sim.workers.values()]]
    changed = [r for bid, r in rows.items() if sim._material_previous.get(bid) != r]
    removed = sorted(set(sim._material_previous)-set(rows))
    if changed or removed or not sim.material_frames:
        sim.material_frames.append(dict(time=sim.time, upsert=copy.deepcopy(changed), remove=removed))
        sim._material_previous = copy.deepcopy(rows)
