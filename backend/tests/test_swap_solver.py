from app.services.swap_solver import solve


def total(flows, pairs):
    return sum(q * pairs[(s, d)][0] for s, d, q in flows)


def test_global_matching_beats_greedy():
    # Greedy: A->X (90) then B is left with Y (10) = 100. Optimal: A->Y (80) + B->X (85) = 165.
    supplies = {"A": 10, "B": 10}
    demands = {"X": 10, "Y": 10}
    pairs = {("A", "X"): (90, 10), ("A", "Y"): (80, 10), ("B", "X"): (85, 10), ("B", "Y"): (10, 10)}
    flows = solve(supplies, demands, pairs)
    assert sorted(flows) == [("A", "Y", 10), ("B", "X", 10)]
    assert total(flows, pairs) == 1650


def test_respects_supply_demand_and_edge_caps():
    supplies = {"A": 30}
    demands = {"X": 12, "Y": 100}
    pairs = {("A", "X"): (90, 50), ("A", "Y"): (50, 7)}
    flows = {(s, d): q for s, d, q in solve(supplies, demands, pairs)}
    assert flows[("A", "X")] == 12      # demand cap
    assert flows[("A", "Y")] == 7       # edge cap
    assert sum(flows.values()) <= 30    # supply cap


def test_no_pairs_no_flow():
    assert solve({"A": 5}, {"X": 5}, {}) == []


def test_splits_one_supply_across_two_shops():
    flows = {(s, d): q for s, d, q in solve({"A": 10}, {"X": 6, "Y": 6}, {("A", "X"): (70, 6), ("A", "Y"): (60, 6)})}
    assert flows == {("A", "X"): 6, ("A", "Y"): 4}
