"""Independent behavioral contract for the approved bounded-demand world.

These tests distinguish fixed machine capability from operation requirements and
exercise the actual demand sampler rather than relying on exported labels.
"""
import copy
import json
from collections import Counter
import math
from pathlib import Path
import unittest

from factory.data import InputError
from factory.world import World, demand_stream
from factory.world_engine import WorldConfig, WorldSimulation

ROOT = Path(__file__).resolve().parents[1]


def axis_fixture():
    # Start with the already validated legacy topology; replace only its catalogue
    # to avoid testing an accidental omission in a hand-written walking graph.
    raw = copy.deepcopy(World.load(ROOT / 'research/world/world.json').raw)
    machines = [m for m in raw['machines'] if m['machine_family'] == 'Milling']
    low, high = machines[:2]
    for m in raw['machines']:
        if m['machine_family'] == 'Milling':
            m['axis_capability'] = 3
    high['axis_capability'] = 4
    old = next(p for p in raw['part_families'] if p['operations'][0]['machine_family'] == 'Milling')
    setup = old['operations'][0]['setup_class']
    ops = [dict(id='THREE', name='Three-axis operation', position=1, machine_family='Milling', required_axes=3,
                setup_class=setup, eligible_machines=[low['id'], high['id']]),
           dict(id='FOUR', name='Four-axis operation', position=2, machine_family='Milling', required_axes=4,
                setup_class=setup, eligible_machines=[high['id']])]
    raw['part_families'] = [dict(id='TEST', complexity=1, demand_probability=1,
        quantity_distribution='triangular', quantity_parameters=[40., 80., 120.],
        quantity_values=[9999], operations=ops)]
    raw['processing_matrix'] = [dict(part_family='TEST', operation_id=o['id'], machine=m, time_per_unit=.01)
                               for o in ops for m in o['eligible_machines']]
    raw['demand']['baseline_jobs_per_day'] = 100
    return raw, low['id'], high['id']


class BoundedDemandReview(unittest.TestCase):
    def test_triangle_is_sampled_instead_of_compatibility_values(self):
        raw, _, _ = axis_fixture()
        rows = demand_stream(World(raw), WorldConfig(seed=37, horizon_days=10))
        self.assertGreater(len(rows), 500)
        quantities = [r['base_quantity'] for r in rows]
        self.assertTrue(all(40 <= q <= 120 for q in quantities))
        self.assertGreater(len(set(quantities)), 40)

    def test_algorithm_and_scales_preserve_common_random_numbers(self):
        raw, _, _ = axis_fixture()
        world = World(raw)
        a = demand_stream(world, WorldConfig(seed=37, horizon_days=2, algorithm='FIFO'))
        b = demand_stream(world, WorldConfig(seed=37, horizon_days=2, algorithm='SPT', scenario_id='other'))
        self.assertEqual(a, b)
        scaled = demand_stream(world, WorldConfig(seed=37, horizon_days=2, batch_size=1.5))
        self.assertEqual(len(a), len(scaled))
        for original, changed in zip(a, scaled):
            self.assertEqual({k:v for k,v in original.items() if k != 'quantity'},
                             {k:v for k,v in changed.items() if k != 'quantity'})
            self.assertEqual(changed['quantity'], math.floor(original['base_quantity'] * 1.5 + .5))
        intense = demand_stream(world, WorldConfig(seed=37, horizon_days=2, arrival_load=2))
        for original, changed in zip(a, intense):
            self.assertEqual(original['base_quantity'], changed['base_quantity'])
            self.assertEqual(original['item'], changed['item'])
            self.assertAlmostEqual(original['release'], 2 * changed['release'])

    def test_invalid_triangle_is_rejected_before_sampling(self):
        for parameters in ([40, 20, 120], [40, 80, float('nan')], [-40, 80, 120]):
            with self.subTest(parameters=parameters):
                raw, _, _ = axis_fixture()
                raw['part_families'][0]['quantity_parameters'] = parameters
                with self.assertRaises(InputError):
                    World(raw)

    def test_four_axis_operation_cannot_claim_three_axis_machine(self):
        raw, low, _ = axis_fixture()
        raw['part_families'][0]['operations'][1]['eligible_machines'].append(low)
        raw['processing_matrix'].append(dict(part_family='TEST', operation_id='FOUR', machine=low, time_per_unit=.01))
        with self.assertRaises(InputError):
            World(raw)

    def test_public_candidates_respect_asymmetric_capability(self):
        raw, low, high = axis_fixture()
        world = World(raw)
        sim = WorldSimulation(world, WorldConfig(horizon_days=1), manual_jobs=[])
        sim._handle('release', dict(id='AXIS', item='TEST', quantity=1, release=0, route=['THREE','FOUR']))
        ready = sim.public_state()['ready'][0]
        self.assertEqual({c['machine'] for c in ready['candidates']}, {low, high})
        self.assertEqual(set(world.eligibility['TEST','FOUR']), {high})


class GeneratedWorldReview(unittest.TestCase):
    def test_physical_inventory_matches_diagnostics_and_preserves_map(self):
        world = World.load(ROOT / 'research/world_v05/world.json')
        old = World.load(ROOT / 'research/world/world.json')
        diagnostics = json.loads((ROOT / 'research/world_v05/design_diagnostics.json').read_text())
        self.assertEqual({m:(v['x'],v['y']) for m,v in world.machines.items()},
                         {m:(v['x'],v['y']) for m,v in old.machines.items()})
        self.assertEqual(dict(Counter(m['machine_family'] for m in world.machines.values())),
                         diagnostics['machine_counts'])
        self.assertEqual(sum(m.get('axis_capability') == 4 for m in world.machines.values()),
                         diagnostics['milling_four_axis'])
        for m in world.machines.values():
            if m['machine_family'] == 'Milling':
                self.assertIn(m['axis_capability'], (3,4))
            self.assertGreater(m['speed'], 0)
            self.assertEqual(m['department'], 'milling' if m['x'] < 1150 else 'turning')

    def test_regular_and_setup_workers_are_floor_local_with_full_coverage(self):
        world = World.load(ROOT / 'research/world_v05/world.json')
        sim = WorldSimulation(world, WorldConfig(horizon_days=1), manual_jobs=[])
        resources = world.raw['resources']
        self.assertEqual(sum(not w.kind.startswith('setup') for w in sim.workers.values()),
                         resources['regular_day_workers'] + resources['regular_night_workers'])
        self.assertEqual(sum(w.kind.startswith('setup') for w in sim.workers.values()),
                         resources['setup_workers'])
        for worker in sim.workers.values():
            self.assertTrue(worker.skills)
            self.assertEqual({world.machines[m]['department'] for m in worker.skills}, {worker.department})
            home = world.graph['nodes'][worker.home_node]
            self.assertEqual('milling' if home[0] < 1150 else 'turning', worker.department)
        for mid,machine in world.machines.items():
            for shift in ('day','night','setup_day','setup_night'):
                self.assertTrue(any(w.kind == shift and mid in w.skills for w in sim.workers.values()),
                                (mid,shift,'has no qualified employee'))
        for department,counts in resources['regular_workers_by_floor'].items():
            self.assertEqual(counts['day'], 2 * counts['night'])
        # Cache a valid unrestricted path first: a cache hit must never allow a
        # worker to bypass the floor restriction on the same endpoint pair.
        left = next(world.graph['service_nodes'][m] for m,v in world.machines.items() if v['department'] == 'milling')
        right = next(world.graph['service_nodes'][m] for m,v in world.machines.items() if v['department'] == 'turning')
        world.path(left,right)
        with self.assertRaises(InputError):
            world.path(left,right,'milling')

    def test_catalogue_and_exact_processing_coverage(self):
        path = ROOT / 'research/world_v05/world.json'
        self.assertTrue(path.exists(), 'Build the approved world before running its acceptance suite')
        world = World.load(path)
        families = list(world.families.values())
        self.assertEqual(len(families), 18)
        self.assertEqual(sum(len(p['operations']) == 1 for p in families), 2)
        single_mass = sum(p['demand_probability'] for p in families if len(p['operations']) == 1)
        self.assertGreater(single_mass, 0)
        self.assertLessEqual(single_mass, .15)
        self.assertGreater(len({round(p['demand_probability'], 8) for p in families}), 3)
        self.assertTrue(all(1 <= len(p['operations']) <= 5 for p in families))
        mean = sum(p['demand_probability'] * sum(p['quantity_parameters']) / 3 for p in families)
        self.assertAlmostEqual(mean, 175., places=5)
        self.assertTrue(all(p['quantity_distribution'] == 'triangular' for p in families))
        self.assertNotIn('Inspection', {o['machine_family'] for o in world.operations.values()})
        expected = {(p,o,m) for (p,o), machines in world.eligibility.items() for m in machines}
        self.assertEqual(set(world.processing), expected)
        shared_pool_found = False
        required_four_found = False
        for key, op in world.operations.items():
            if op['machine_family'] != 'Milling':
                continue
            capabilities = {world.machines[m]['axis_capability'] for m in world.eligibility[key]}
            self.assertTrue(all(c >= op['required_axes'] for c in capabilities))
            shared_pool_found |= op['required_axes'] == 3 and capabilities == {3,4}
            required_four_found |= op['required_axes'] == 4 and capabilities == {4}
        self.assertTrue(shared_pool_found)
        self.assertTrue(required_four_found)


if __name__ == '__main__':
    unittest.main()
