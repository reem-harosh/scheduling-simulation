"""Logical-key PCG64 random streams independent of scheduler consumption order."""
import hashlib
import json
import math
import numpy as np


class Streams:
    def __init__(self, seed, scenario, replication, namespace='measurement'):
        self.prefix = [int(seed), str(scenario), int(replication), namespace]

    def rng(self, stream, key):
        payload = json.dumps(self.prefix + [stream, key], ensure_ascii=False,
                             separators=(',', ':'), sort_keys=True).encode()
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:16], 'big')
        return np.random.Generator(np.random.PCG64(seed))

    def rounded(self, value, stream, key):
        return math.floor(value) + int(self.rng(stream, key).random() < value % 1)

    def processing(self, row, job, op):
        rng, model = self.rng('processing', [job, op]), row['model']
        family = model['family']
        if family == 'constant':
            value = model['value']
        elif family == 'empirical':
            value = float(rng.choice(model['values']))
        else:
            shape, loc, scale = model['parameters']
            if family == 'lognorm':
                value = loc + scale * rng.lognormal(0, shape)
            elif family == 'gamma':
                value = loc + rng.gamma(shape, scale)
            elif family == 'weibull_min':
                value = loc + scale * rng.weibull(shape)
            else:
                raise ValueError('Unknown processing family: ' + family)
        value *= row.get('scale_to_standard', 1)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('NONPOSITIVE_PROCESSING_SAMPLE')
        return value
