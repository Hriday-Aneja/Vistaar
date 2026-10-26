"""Min-cost-flow solver for the Mohalla Swap Engine.

Problem (per product): several shops hold stock that will not sell before expiry (supplies);
several nearby shops are about to run short (demands). Choose who sends how much to whom so the
total swap score is as high as possible, without sending the same unit twice or overfilling a shop.

A greedy "each shop picks its best partner" approach can send everything to the same hot shop and
leave other swaps unmatched. This solves it globally: successive shortest paths on a flow network
  source -> supply(batch) -> demand(shop) -> sink
with cost = -score, stopping as soon as another unit would not add positive score.
Pure Python, no dependencies.
"""
from dataclasses import dataclass


@dataclass
class _Edge:
    to: int
    cap: int
    cost: int
    rev: int


def solve(
    supplies: dict[str, int],
    demands: dict[str, int],
    pairs: dict[tuple[str, str], tuple[float, int]],
) -> list[tuple[str, str, int]]:
    """supplies: {supply_key: units available}; demands: {demand_key: units wanted};
    pairs: {(supply_key, demand_key): (score, max_units)} - only allowed pairs, score > 0.

    Returns [(supply_key, demand_key, units)] with units > 0, maximising sum(units * score).
    """
    s_keys, d_keys = list(supplies), list(demands)
    n = len(s_keys) + len(d_keys) + 2
    src, sink = 0, n - 1
    s_idx = {k: 1 + i for i, k in enumerate(s_keys)}
    d_idx = {k: 1 + len(s_keys) + i for i, k in enumerate(d_keys)}
    graph: list[list[_Edge]] = [[] for _ in range(n)]

    def add(u: int, v: int, cap: int, cost: int) -> _Edge:
        fwd = _Edge(v, cap, cost, len(graph[v]))
        back = _Edge(u, 0, -cost, len(graph[u]))
        graph[u].append(fwd)
        graph[v].append(back)
        return fwd

    for k, qty in supplies.items():
        if qty > 0:
            add(src, s_idx[k], qty, 0)
    for k, qty in demands.items():
        if qty > 0:
            add(d_idx[k], sink, qty, 0)
    pair_edges: dict[tuple[str, str], _Edge] = {}
    for (sk, dk), (score, cap) in pairs.items():
        if sk in s_idx and dk in d_idx and cap > 0 and score > 0:
            pair_edges[(sk, dk)] = add(s_idx[sk], d_idx[dk], cap, -int(round(score * 100)))

    while True:
        dist = [None] * n
        prev: list[tuple[int, int] | None] = [None] * n
        dist[src] = 0
        queue, in_queue = [src], {src}
        while queue:  # SPFA (Bellman-Ford with a queue): handles negative costs
            u = queue.pop(0)
            in_queue.discard(u)
            for i, e in enumerate(graph[u]):
                if e.cap > 0 and dist[u] is not None and (dist[e.to] is None or dist[u] + e.cost < dist[e.to]):
                    dist[e.to] = dist[u] + e.cost
                    prev[e.to] = (u, i)
                    if e.to not in in_queue:
                        queue.append(e.to)
                        in_queue.add(e.to)
        if dist[sink] is None or dist[sink] >= 0:
            break  # no remaining path adds positive score
        push, v = float("inf"), sink
        while v != src:
            u, i = prev[v]
            push = min(push, graph[u][i].cap)
            v = u
        v = sink
        while v != src:
            u, i = prev[v]
            graph[u][i].cap -= push
            graph[v][graph[u][i].rev].cap += push
            v = u

    out = []
    for (sk, dk), edge in pair_edges.items():
        used = graph[edge.to][edge.rev].cap  # flow = capacity of the reverse edge
        if used > 0:
            out.append((sk, dk, used))
    return out
