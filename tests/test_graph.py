import unittest

from gs import graph

# goldstack-v0의 실제 그래프
V0 = {
    "01": [], "02": ["01"], "03": ["02"], "04": ["03"], "05": ["02", "11"],
    "06": ["04", "05"], "07": ["04"], "08": ["06", "07"], "09": ["02"], "10": ["09"], "11": [],
}


class GraphTest(unittest.TestCase):
    def test_topo_order_respects_deps_and_is_deterministic(self):
        order = graph.topo_order(V0)
        self.assertEqual(sorted(order), sorted(V0))
        pos = {n: i for i, n in enumerate(order)}
        for n, deps in V0.items():
            for d in deps:
                self.assertLess(pos[d], pos[n], (d, n))
        self.assertEqual(order, graph.topo_order(dict(reversed(list(V0.items())))))

    def test_frontier(self):
        self.assertEqual(graph.frontier(V0), ["01", "11"])
        self.assertEqual(graph.frontier(V0, done={"01", "11"}), ["02"])
        self.assertEqual(graph.frontier(V0, done={"01", "02", "11"}), ["03", "05", "09"])

    def test_topo_order_with_done(self):
        self.assertEqual(graph.topo_order({"a": [], "b": ["a"]}, done={"a"}), ["b"])

    def test_unknown_refs(self):
        self.assertEqual(graph.unknown_refs({"a": ["x"], "b": ["a"]}), {"a": ["x"]})

    def test_cycles(self):
        self.assertEqual(graph.cycles(V0), [])
        self.assertEqual(graph.cycles({"a": ["a"]}), [["a", "a"]])
        self.assertEqual(graph.cycles({"a": ["b"], "b": ["c"], "c": ["a"], "d": ["a"]}), [["a", "b", "c", "a"]])
        two = graph.cycles({"a": ["b"], "b": ["a"], "c": ["d"], "d": ["c"]})
        self.assertEqual(len(two), 2)

    def test_cycle_members_drop_out_of_order(self):
        g = {"a": [], "b": ["c"], "c": ["b"], "d": ["a"]}
        self.assertEqual(graph.topo_order(g), ["a", "d"])

    def test_subgraph_wave_2(self):
        g, external, missing = graph.subgraph(V0, ["06", "07", "08", "10"])
        self.assertEqual(missing, [])
        self.assertEqual(sorted(g), ["06", "07", "08", "10"])
        self.assertEqual(external, {"06": ["04", "05"], "07": ["04"], "10": ["09"]})
        self.assertEqual(graph.frontier(g), ["06", "07", "10"])
        self.assertEqual(graph.topo_order(g), ["06", "07", "08", "10"])

    def test_subgraph_missing(self):
        _, _, missing = graph.subgraph(V0, ["01", "99"])
        self.assertEqual(missing, ["99"])


if __name__ == "__main__":
    unittest.main()
