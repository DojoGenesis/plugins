"""Tests for scripts/dag_ops.py. Graphs are written by hand; subprocess tests use the interpreter running the tests."""
import importlib.util
import itertools
import json
import os
import random
import subprocess
import sys
import unittest

from wf_helpers import CASES, DAG_OPS

spec = importlib.util.spec_from_file_location("dag_ops", DAG_OPS)
dag_ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dag_ops)


def graph(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def run_cli(args, stdin=None):
    proc = subprocess.run([sys.executable, DAG_OPS] + args, input=stdin, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def ops(op, g, node=None):
    nodes, edges = dag_ops.build_graph(g)
    if op == "cone":
        return dag_ops.op_cone(nodes, edges, node)
    table = {"validate": dag_ops.op_validate, "width": dag_ops.op_width,
             "critical-path": dag_ops.op_critical_path, "reduce": dag_ops.op_reduce}
    return table[op](nodes, edges)


class WidthTests(unittest.TestCase):
    def test_chain_has_width_one(self):
        self.assertEqual(ops("width", graph(["a", "b", "c"], [["a", "b"], ["b", "c"]]))["width"], 1)

    def test_diamond_has_width_two(self):
        r = ops("width", graph(list("abcd"), [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"]]))
        self.assertEqual(r["width"], 2)
        self.assertEqual(r["antichain"], ["b", "c"])

    def test_two_independent_chains_have_width_two(self):
        r = ops("width", graph(list("abcd"), [["a", "b"], ["c", "d"]]))
        self.assertEqual(r["width"], 2)

    def test_no_edges_width_is_node_count(self):
        self.assertEqual(ops("width", graph(["a", "b", "c"], []))["width"], 3)

    def test_empty_graph(self):
        self.assertEqual(ops("width", graph([], []))["width"], 0)

    def test_property_against_brute_force(self):
        rng = random.Random(20261002)
        for case in range(120):
            n = rng.randint(1, 7)
            names = ["n%d" % i for i in range(n)]
            order = names[:]
            rng.shuffle(order)  # input order is not a topological order
            p = rng.choice([0.1, 0.3, 0.6])
            edges = [[order[i], order[j]] for i in range(n) for j in range(i + 1, n) if rng.random() < p]
            rng.shuffle(edges)
            if rng.random() < 0.3 and edges:
                edges.append(list(edges[0]))  # a duplicate edge
            r = ops("width", graph(names, edges))
            reach = {x: set() for x in names}
            for a, b in edges:
                reach[a].add(b)
            for k in names:  # transitive closure
                for i in names:
                    if k in reach[i]:
                        reach[i] |= reach[k]
            best = 1
            for size in range(1, n + 1):
                for combo in itertools.combinations(names, size):
                    if all(b not in reach[a] and a not in reach[b] for a, b in itertools.combinations(combo, 2)):
                        best = max(best, size)
            anti = r["antichain"]
            self.assertEqual(r["width"], best, "case %d: %r" % (case, edges))
            self.assertEqual(len(anti), r["width"], "case %d" % case)
            for a, b in itertools.combinations(anti, 2):
                self.assertTrue(b not in reach[a] and a not in reach[b], "case %d: %s and %s are ordered" % (case, a, b))

    def test_long_chain_does_not_recurse(self):
        names = ["n%d" % i for i in range(800)]
        edges = [[names[i], names[i + 1]] for i in range(799)]
        self.assertEqual(ops("width", graph(names, edges))["width"], 1)
        self.assertEqual(ops("critical-path", graph(names, edges))["length"], 800)

    def test_reversed_long_chain(self):
        names = ["n%d" % i for i in range(500)]
        edges = [[names[i + 1], names[i]] for i in range(499)]
        self.assertEqual(ops("width", graph(names, edges))["width"], 1)


class CriticalPathTests(unittest.TestCase):
    def test_diamond_with_a_tail(self):
        r = ops("critical-path", graph(list("abcde"), [["a", "b"], ["a", "c"], ["b", "d"], ["c", "d"], ["d", "e"]]))
        self.assertEqual(r["length"], 4)
        self.assertEqual(r["path"][0], "a")
        self.assertEqual(r["path"][-2:], ["d", "e"])
        self.assertIn(r["path"][1], ("b", "c"))

    def test_single_node(self):
        self.assertEqual(ops("critical-path", graph(["a"], []))["length"], 1)

    def test_both_spellings_work_on_the_command_line(self):
        g = json.dumps(graph(["a", "b"], [["a", "b"]]))
        for spelling in ("critical-path", "critical_path"):
            code, out, err = run_cli([spelling], stdin=g)
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["length"], 2)


class ConeReduceTests(unittest.TestCase):
    G = graph(list("abcde"), [["a", "b"], ["b", "c"], ["a", "d"], ["d", "c"], ["c", "e"]])

    def test_cone_ancestors_and_descendants(self):
        r = ops("cone", self.G, "c")
        self.assertEqual(r["ancestors"], ["a", "b", "d"])
        self.assertEqual(r["descendants"], ["e"])

    def test_cone_of_a_root_has_no_ancestors(self):
        r = ops("cone", self.G, "a")
        self.assertEqual(r["ancestors"], [])
        self.assertEqual(r["descendants"], ["b", "c", "d", "e"])

    def test_cone_unknown_node_is_bad_input(self):
        code, out, err = run_cli(["cone", "zzz", "--json", json.dumps(self.G)])
        self.assertEqual(code, 2)
        self.assertIn("unknown node", err)
        self.assertNotIn("Traceback", err)

    def test_reduce_removes_a_transitive_edge(self):
        r = ops("reduce", graph(list("abc"), [["a", "b"], ["b", "c"], ["a", "c"]]))
        self.assertEqual(r["removed_edges"], [["a", "c"]])
        self.assertEqual(r["kept_edges"], [["a", "b"], ["b", "c"]])

    def test_reduce_keeps_exactly_one_copy_of_a_duplicate_edge(self):
        r = ops("reduce", graph(list("ab"), [["a", "b"], ["a", "b"]]))
        self.assertEqual(r["kept_edges"], [["a", "b"]])
        self.assertEqual(r["removed_edges"], [])
        self.assertEqual(r["stats"]["edges_before"], 1)


class CycleTests(unittest.TestCase):
    CYCLE = graph(list("abc"), [["a", "b"], ["b", "c"], ["c", "a"]])
    SELF_LOOP = graph(["a"], [["a", "a"]])

    def test_validate_reports_the_cycle(self):
        r = ops("validate", self.CYCLE)
        self.assertFalse(r["is_dag"])
        cyc = r["example_cycle"]
        self.assertEqual(cyc[0], cyc[-1])
        self.assertEqual(set(cyc), {"a", "b", "c"})

    def test_validate_reports_a_self_loop(self):
        r = ops("validate", self.SELF_LOOP)
        self.assertFalse(r["is_dag"])
        self.assertEqual(r["example_cycle"], ["a", "a"])

    def test_validate_of_a_dag(self):
        r = ops("validate", graph(["a", "b"], [["a", "b"]]))
        self.assertTrue(r["is_dag"])
        self.assertIsNone(r["example_cycle"])

    def test_other_ops_exit_one_on_a_cycle(self):
        for g in (self.CYCLE, self.SELF_LOOP):
            for op in (["width"], ["critical-path"], ["reduce"], ["cone", "a"]):
                code, out, err = run_cli(op + ["--json", json.dumps(g)])
                self.assertEqual(code, 1, (op, out, err))
                body = json.loads(out)
                self.assertIn("cyclic", body["error"])
                self.assertTrue(body["remedy"])
                self.assertNotIn("scc", out.lower())


class InputTests(unittest.TestCase):
    def assert_bad(self, args, stdin=None):
        code, out, err = run_cli(args, stdin=stdin)
        self.assertEqual(code, 2, (args, out, err))
        self.assertNotIn("Traceback", err)
        self.assertEqual(len([l for l in err.strip().splitlines() if l]), 1, err)
        return err

    def test_garbage_json(self):
        self.assertIn("not valid JSON", self.assert_bad(["width"], stdin="{not json"))

    def test_edge_with_three_items(self):
        self.assert_bad(["width", "--json", json.dumps(graph(["a", "b", "c"], [["a", "b", "c"]]))])

    def test_edge_that_is_not_a_list(self):
        self.assert_bad(["width", "--json", json.dumps(graph(["a", "b"], ["ab"]))])

    def test_non_string_node(self):
        self.assert_bad(["width", "--json", json.dumps({"nodes": [[1]], "edges": []})])
        self.assert_bad(["width", "--json", json.dumps({"nodes": [1, 2], "edges": []})])

    def test_missing_nodes_key(self):
        self.assert_bad(["width", "--json", json.dumps({"edges": []})])

    def test_edge_naming_an_unlisted_node_is_an_error_not_a_phantom(self):
        err = self.assert_bad(["width", "--json", json.dumps(graph(["a", "b"], [["a", "typo"]]))])
        self.assertIn("typo", err)

    def test_top_level_list_is_not_a_graph(self):
        self.assert_bad(["width", "--json", "[]"])

    def test_oversized_graph_is_refused_cleanly(self):
        n = dag_ops.MAX_NODES + 1
        names = ["n%d" % i for i in range(n)]
        edges = [[names[i], names[i + 1]] for i in range(n - 1)]
        self.assertIn("limit", self.assert_bad(["width"], stdin=json.dumps(graph(names, edges))))

    def test_a_3000_node_chain_gives_no_recursion_error(self):
        names = ["n%d" % i for i in range(3000)]
        edges = [[names[i], names[i + 1]] for i in range(2999)]
        code, out, err = run_cli(["width"], stdin=json.dumps(graph(names, edges)))
        self.assertIn(code, (0, 2))
        self.assertNotIn("Traceback", err)
        self.assertNotIn("RecursionError", err)

    def test_reads_a_file_and_stdin(self):
        import tempfile
        g = graph(["a", "b"], [["a", "b"]])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "g.json")
            with open(path, "w") as fh:
                json.dump(g, fh)
            code_f, out_f, _ = run_cli(["width", "-f", path])
            code_s, out_s, _ = run_cli(["width"], stdin=json.dumps(g))
        self.assertEqual((code_f, code_s), (0, 0))
        self.assertEqual(json.loads(out_f), json.loads(out_s))

    def test_missing_file(self):
        self.assertIn("cannot read", self.assert_bad(["width", "-f", "/definitely/not/here.json"]))

    def test_no_operation_is_a_usage_error(self):
        code, out, err = run_cli([], stdin="{}")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_the_module_imports_without_running_main(self):
        self.assertTrue(callable(dag_ops.main))
        self.assertTrue(callable(dag_ops.op_width))


class TracksModeTests(unittest.TestCase):
    def tracks(self, tracks, extra=None, flags=None):
        body = {"tracks": tracks}
        body.update(extra or {})
        return run_cli(["tracks"] + (flags or []) + ["--json", json.dumps(body)])

    def test_independent_tracks(self):
        code, out, err = self.tracks([{"name": "api", "files": ["src/api/"]}, {"name": "ui", "files": ["src/ui/"]},
                                      {"name": "docs", "files": ["README.md"]}])
        self.assertEqual(code, 0, err)
        r = json.loads(out)
        self.assertEqual(r["width"], 3)
        self.assertTrue(r["fan_out_is_real"])
        self.assertEqual(r["track_count"], 3)

    def test_deps_lower_the_width(self):
        code, out, err = self.tracks([{"name": "api", "files": ["a.js"]}, {"name": "ui", "files": ["b.js"], "deps": ["api"]},
                                      {"name": "docs", "files": ["c.md"]}])
        self.assertEqual(code, 0, err)
        r = json.loads(out)
        self.assertEqual(r["width"], 2)
        self.assertFalse(r["fan_out_is_real"])
        self.assertEqual(r["critical_path"], ["api", "ui"])

    def test_unknown_dep_is_bad_input_not_a_phantom_node(self):
        code, out, err = self.tracks([{"name": "api", "files": ["a.js"]}, {"name": "ui", "files": ["b.js"], "deps": ["apii"]}])
        self.assertEqual(code, 2)
        self.assertIn("apii", err)
        self.assertNotIn("Traceback", err)

    def test_dep_cycle_exits_one(self):
        code, out, err = self.tracks([{"name": "a", "files": ["a.js"], "deps": ["b"]}, {"name": "b", "files": ["b.js"], "deps": ["a"]}])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["ok"])

    def test_bare_list_and_the_flag_form(self):
        body = json.dumps([{"name": "a", "files": ["a.js"]}, {"name": "b", "files": ["b.js"]}])
        code, out, err = run_cli(["--tracks", "--json", body])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["width"], 2)

    def test_track_that_is_not_an_object_is_bad_input(self):
        code, out, err = run_cli(["tracks", "--json", json.dumps(["a", "b"])])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_empty_tracks_are_bad_input(self):
        code, out, err = run_cli(["tracks", "--json", "[]"])
        self.assertEqual(code, 2)

    def test_the_shared_overlap_table(self):
        with open(CASES, encoding="utf-8") as fh:
            cases = json.load(fh)
        self.assertGreaterEqual(len(cases), 20)
        for c in cases:
            flags = []
            if c.get("reserved"):
                flags = ["--contract", c["reserved"]]
            extra = {"repo": c["repo"]} if c.get("repo") else {}
            code, out, err = self.tracks(c["tracks"], extra, flags)
            want = 1 if c["expect"] == "refuse" else 0
            self.assertEqual(code, want, "%s: exit %s, out %s, err %s" % (c["name"], code, out[:300], err))
            self.assertNotIn("Traceback", err, c["name"])


if __name__ == "__main__":
    unittest.main()
