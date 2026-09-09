"""Behavior checks for simulation correctness, independent of the UI."""
import importlib.util
import pathlib
import unittest
import copy

spec = importlib.util.spec_from_file_location("engine", pathlib.Path(__file__).parents[1]/"dist"/"engine.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


class SimulationTests(unittest.TestCase):
    def test_hand_calculated_reference(self):
        r = engine.simulate({"walking": False})
        self.assertEqual(r["completions"], {"A": 22, "B": 6, "C": 16, "D": 26})
        self.assertEqual(r["metrics"]["mean_flow"], 17.5)
        self.assertEqual(r["metrics"]["total_tardiness"], 14)

    def test_resource_exclusion_skills_and_precedence(self):
        for policy in ("fifo", "spt", "edd"):
            for seed in (1, 42, 117):
                r = engine.simulate(dict(policy=policy, seed=seed, variation=.5, walking=True, horizon=100))
                self.assertTrue(r["metrics"]["complete"])
                tasks = r["tasks"]
                self.assertEqual(len(tasks), 6)
                self.assertEqual(len({(t["job"],t["index"]) for t in tasks}), 6)
                for t in tasks:
                    self.assertAlmostEqual(t["end"]-t["start"], t["duration"], places=5)
                    self.assertGreaterEqual(t["start"], t["assigned"])
                    if t["operation"] == "bind":
                        self.assertEqual(t["worker"], "W2")
                        previous = next(p for p in tasks if p["job"] == t["job"] and p["index"] == 0)
                        self.assertGreaterEqual(t["assigned"], previous["end"])
                for key, resources in (("machine",r["machines"]),("worker",r["workers"])):
                    for resource in resources:
                        intervals = sorted((t["assigned"],t["end"]) for t in tasks if t[key]==resource["id"])
                        for first, second in zip(intervals,intervals[1:]):
                            self.assertLessEqual(first[1], second[0])

    def test_seed_reproducibility_and_common_samples(self):
        opts=dict(seed=42,variation=.2)
        a=engine.simulate(opts)
        self.assertEqual(a,engine.simulate(opts))
        b=engine.simulate({**opts,"policy":"spt"})
        samples=lambda r:{(t["job"],t["index"]):t["duration"] for t in r["tasks"]}
        self.assertEqual(samples(a),samples(b))
        self.assertNotEqual(samples(a),samples(engine.simulate({**opts,"seed":43})))

    def test_horizon_does_not_report_partial_mean_as_final(self):
        r=engine.simulate(dict(walking=False,horizon=10))
        self.assertEqual(r["end_time"],10)
        self.assertEqual(r["metrics"]["completed"],1)
        self.assertFalse(r["metrics"]["complete"])
        self.assertIsNone(r["metrics"]["mean_flow"])
        self.assertEqual(r["metrics"]["completed_mean_flow"],6)

    def test_walking_at_same_station_is_zero(self):
        self.assertEqual(engine.travel_path([300,290],[300,290]),[[300,290]])
        r=engine.simulate()
        c=next(t for t in r["tasks"] if t["job"]=="C")
        self.assertEqual(c["walking"],0)
        self.assertGreater(r["metrics"]["mean_flow"],17.5)

    def test_disabled_variation_is_deterministic(self):
        a=engine.simulate(dict(seed=1,variation=0))
        b=engine.simulate(dict(seed=100,variation=0))
        self.assertEqual(a["tasks"],b["tasks"])

    def test_invalid_input_rejected(self):
        for options in ({"horizon":0},{"horizon":float('nan')},{"variation":.6},{"policy":"unknown"}):
            with self.assertRaises(ValueError):engine.simulate(options)

    def test_external_scenario_changes_counts_and_capabilities(self):
        model = engine.load_scenario()
        extra = copy.deepcopy(model['jobs'][1])
        extra['id'] = 'E'
        model['jobs'].append(extra)
        model['machines'] = [model['machines'][0], model['machines'][2]]
        model['workers'] = [model['workers'][0]]
        model['workers'][0]['skills'] = ['print', 'bind']
        result = engine.simulate({'walking': False, 'horizon': 100}, scenario=model)
        self.assertEqual(result['metrics']['total'], 5)
        self.assertTrue(result['metrics']['complete'])
        self.assertEqual(len(result['machines']), 2)
        self.assertEqual(len(result['workers']), 1)
        self.assertTrue(all(t['worker'] == 'W1' for t in result['tasks']))
        self.assertEqual(len(engine.DEFAULT_SCENARIO['jobs']), 4)
        self.assertEqual(engine.simulate({'walking': False})['metrics']['mean_flow'], 17.5)

    def test_unserviceable_scenario_is_rejected_before_scheduling(self):
        model = engine.load_scenario()
        for worker in model['workers']:
            worker['skills'] = ['print']
        with self.assertRaisesRegex(ValueError, 'No feasible'):
            engine.simulate(scenario=model)
        model = engine.load_scenario()
        model['jobs'][0]['operations'][0][1] = 0
        with self.assertRaises(ValueError):
            engine.simulate(scenario=model)

    def test_missing_optional_due_date_means_no_deadline(self):
        model = engine.load_scenario()
        del model['jobs'][2]['due']
        result = engine.simulate({'walking': False}, scenario=model)
        self.assertIsNone(result['jobs'][2]['due'])
        self.assertEqual(result['metrics']['mean_flow'], 17.5)
        self.assertEqual(result['metrics']['total_tardiness'], 14)

if __name__ == "__main__":
    unittest.main()
