#!/usr/bin/env python3
"""Dependency-graph checks for planning parallel work. Standard library only, Python 3.9 or newer.

Input is JSON, from -f FILE, --json TEXT, or stdin:

  {"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["a", "c"]]}      an edge [x, y] means x comes before y

Operations (first argument):

  validate        is it a DAG? names one example cycle when it is not
  width           the widest set of nodes with no path between any two (the real parallelism), plus one such set
  critical-path   the longest chain (the floor on how fast the work can finish); critical_path also works
  cone NODE       everything NODE depends on, and everything that depends on it
  reduce          which edges are implied by other edges, and the graph without them
  tracks          workflow-style tracks [{name, files, deps?}] (or {"tracks": [...]}): checks file ownership,
                  builds the graph from deps, and reports the width, so you can see whether a fan-out is real
                  before any model is called. --tracks works as a flag too.

Exit codes: 0 ok (validate always exits 0 on a well-formed graph: read is_dag). 1 another operation met a cycle, or
the tracks were refused (overlap, duplicate name, bad path). 2 the input itself is unusable (bad JSON, wrong shape, unknown node, unknown dependency, too many nodes).

Every operation except validate refuses a cyclic graph. Remove or reverse one edge on the cycle and run it again.
Nodes must be strings. Edges may only name nodes listed in "nodes" (a typo is an error, not a new node).
Graphs above 2000 nodes are refused.

  python3 dag_ops.py validate -f graph.json
  python3 dag_ops.py cone build -f graph.json
  python3 dag_ops.py width --json '{"nodes": ["a", "b"], "edges": []}'
  python3 dag_ops.py tracks --json '[{"name": "api", "files": ["src/api/"]}, {"name": "ui", "files": ["src/ui/"]}]'
"""
import argparse
import json
import re
import sys
from collections import deque

MAX_NODES = 2000


class InputError(Exception):
    """The input cannot be used. Reported as one line on stderr, exit 2."""


# ---- loading and validating -------------------------------------------------------------------------------------

def read_text(path, inline):
    if inline is not None:
        return inline
    if path is None:
        return sys.stdin.read()
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("cannot read %s: %s" % (path, exc))


def parse_json(text):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise InputError("input is not valid JSON: %s" % exc)


def build_graph(obj):
    """Validate {"nodes": [...], "edges": [...]} and return (nodes, edges) with duplicates removed."""
    if not isinstance(obj, dict):
        raise InputError("the graph must be a JSON object with a \"nodes\" list")
    if "nodes" not in obj:
        raise InputError("the graph has no \"nodes\" key")
    raw_nodes = obj["nodes"]
    if not isinstance(raw_nodes, list):
        raise InputError("\"nodes\" must be a list")
    for n in raw_nodes:
        if not isinstance(n, str):
            raise InputError("every node must be a string (got %s)" % type(n).__name__)
    nodes = list(dict.fromkeys(raw_nodes))
    if len(nodes) > MAX_NODES:
        raise InputError("the graph has %d nodes; the limit is %d" % (len(nodes), MAX_NODES))
    raw_edges = obj.get("edges", [])
    if not isinstance(raw_edges, list):
        raise InputError("\"edges\" must be a list")
    known = set(nodes)
    edges = []
    seen = set()
    for e in raw_edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2:
            raise InputError("every edge must be a two-item list [from, to] (got %s)" % json.dumps(e)[:60])
        a, b = e
        if not isinstance(a, str) or not isinstance(b, str):
            raise InputError("edge endpoints must be strings (got %s)" % json.dumps(e)[:60])
        for n in (a, b):
            if n not in known:
                raise InputError("edge %s names a node that is not in \"nodes\": %s" % (json.dumps(e)[:60], n))
        if (a, b) not in seen:
            seen.add((a, b))
            edges.append((a, b))
    return nodes, edges


def load_graph(path=None, inline=None):
    return build_graph(parse_json(read_text(path, inline)))


# ---- graph primitives -------------------------------------------------------------------------------------------

def adjacency(nodes, edges, reverse=False):
    adj = {n: [] for n in nodes}
    for a, b in edges:
        if reverse:
            adj[b].append(a)
        else:
            adj[a].append(b)
    return adj


def topo_order(nodes, edges):
    """Kahn's algorithm. Returns (order, is_dag, example_cycle)."""
    adj = adjacency(nodes, edges)
    indeg = {n: 0 for n in nodes}
    for _, b in edges:
        indeg[b] += 1
    q = deque(n for n in nodes if indeg[n] == 0)
    order = []
    while q:
        n = q.popleft()
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(order) == len(nodes):
        return order, True, None
    placed = set(order)
    residual = {n for n in nodes if n not in placed}
    changed = True
    while changed:
        changed = False
        for n in list(residual):
            if not any(m in residual for m in adj[n]):
                residual.discard(n)
                changed = True
    start = next(n for n in nodes if n in residual)
    seen, path, cur = {}, [], start
    while cur not in seen:
        seen[cur] = len(path)
        path.append(cur)
        cur = next(m for m in adj[cur] if m in residual)
    return order, False, path[seen[cur]:] + [cur]


def reachable_from(node, adj):
    out, q = set(), deque([node])
    while q:
        for m in adj[q.popleft()]:
            if m not in out:
                out.add(m)
                q.append(m)
    return out


def bits(mask):
    """Indexes of the set bits of a non-negative int, ascending."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def closure_masks(nodes, edges):
    """reach[i] is a bitmask of the node indexes reachable from node i (excluding i). The graph must be a DAG."""
    idx = {n: i for i, n in enumerate(nodes)}
    order, _, _ = topo_order(nodes, edges)
    adj = adjacency(nodes, edges)
    reach = [0] * len(nodes)
    for n in reversed(order):
        m = 0
        for s in adj[n]:
            m |= reach[idx[s]] | (1 << idx[s])
        reach[idx[n]] = m
    return idx, reach


class Cyclic(Exception):
    def __init__(self, op, cycle):
        Exception.__init__(self, op)
        self.op = op
        self.cycle = cycle


def require_dag(nodes, edges, op):
    _, is_dag, cycle = topo_order(nodes, edges)
    if not is_dag:
        raise Cyclic(op, cycle)


# ---- operations -------------------------------------------------------------------------------------------------

def op_validate(nodes, edges, _args=None):
    _, is_dag, cycle = topo_order(nodes, edges)
    return {"is_dag": is_dag, "example_cycle": cycle, "node_count": len(nodes), "edge_count": len(edges)}


def op_cone(nodes, edges, node):
    if node not in set(nodes):
        raise InputError("unknown node %r" % node)
    require_dag(nodes, edges, "cone")
    anc = sorted(reachable_from(node, adjacency(nodes, edges, reverse=True)))
    desc = sorted(reachable_from(node, adjacency(nodes, edges)))
    return {"node": node, "ancestors": anc, "descendants": desc,
            "ancestor_count": len(anc), "descendant_count": len(desc)}


def op_reduce(nodes, edges, _args=None):
    require_dag(nodes, edges, "reduce")
    idx, reach = closure_masks(nodes, edges)
    adj = adjacency(nodes, edges)
    removed, kept = [], []
    for a, b in edges:
        bi = idx[b]
        implied = any(m != b and (reach[idx[m]] >> bi) & 1 for m in adj[a])
        (removed if implied else kept).append([a, b])
    return {"removed_edges": removed, "kept_edges": kept,
            "stats": {"edges_before": len(edges), "edges_after": len(kept), "redundant": len(removed)}}


def max_matching(n, lists):
    """Maximum bipartite matching (left i to right j for every j in lists[i]); iterative augmenting paths."""
    match_l = [-1] * n
    match_r = [-1] * n
    for root in range(n):
        visited = set()
        stack = [(root, iter(lists[root]))]
        chosen = []
        while stack:
            u, it = stack[-1]
            advanced = False
            for v in it:
                if v in visited:
                    continue
                visited.add(v)
                if match_r[v] == -1:
                    chosen.append(v)
                    for (uu, _), vv in zip(stack, chosen):
                        match_l[uu] = vv
                        match_r[vv] = uu
                    stack = []
                    advanced = True
                    break
                chosen.append(v)
                stack.append((match_r[v], iter(lists[match_r[v]])))
                advanced = True
                break
            if not advanced:
                stack.pop()
                if chosen:
                    chosen.pop()
    return match_l, match_r


def op_width(nodes, edges, _args=None):
    require_dag(nodes, edges, "width")
    n = len(nodes)
    if n == 0:
        return {"width": 0, "antichain": [], "note": "empty graph"}
    _, reach = closure_masks(nodes, edges)
    lists = [bits(m) for m in reach]
    match_l, match_r = max_matching(n, lists)
    # Dilworth: width = n - maximum matching on the transitive closure. The antichain comes from the Konig
    # witness: alternating search from the unmatched left vertices.
    seen_l = set(i for i in range(n) if match_l[i] == -1)
    seen_r = set()
    q = deque(seen_l)
    while q:
        u = q.popleft()
        for v in lists[u]:
            if v not in seen_r:
                seen_r.add(v)
                w = match_r[v]
                if w != -1 and w not in seen_l:
                    seen_l.add(w)
                    q.append(w)
    chain = sorted(nodes[i] for i in range(n) if i in seen_l and i not in seen_r)
    size = n - sum(1 for x in match_l if x != -1)
    return {"width": size, "antichain": chain,
            "note": "width = largest set with no dependency path between any two members"}


def op_critical_path(nodes, edges, _args=None):
    require_dag(nodes, edges, "critical-path")
    if not nodes:
        return {"length": 0, "path": [], "note": "empty graph"}
    order, _, _ = topo_order(nodes, edges)
    radj = adjacency(nodes, edges, reverse=True)
    best = {n: (1, None) for n in nodes}
    for n in order:
        for p in radj[n]:
            if best[p][0] + 1 > best[n][0]:
                best[n] = (best[p][0] + 1, p)
    end = max(nodes, key=lambda n: best[n][0])
    path, cur = [], end
    while cur is not None:
        path.append(cur)
        cur = best[cur][1]
    path.reverse()
    return {"length": best[end][0], "path": path,
            "note": "longest dependency chain; adding workers does not shorten it"}


# ---- tracks mode: the same ownership rules as the workflow scripts ----------------------------------------------

def clean_root(repo):
    if not isinstance(repo, str) or not repo.strip():
        return ""
    s = re.sub(r"/{2,}", "/", repo.strip().replace("\\", "/"))
    return s.rstrip("/").lower()


def norm_entry(raw, repo):
    """Return (normalised path, None) or (None, error). Same rules as normEntry in workflows/build.js."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty or non-string path"
    original = raw.strip()
    if any(c in original for c in "*?[]"):
        return None, "glob characters are not allowed: " + original
    s = re.sub(r"/{2,}", "/", original.replace("\\", "/"))
    if s[:1] == "/" or re.match(r"^[A-Za-z]:/", s):
        root = clean_root(repo)
        low = s.lower()
        if not root or (low != root and not low.startswith(root + "/")):
            return None, "absolute path outside the repo: " + original
        s = s[len(root):]
    segs = [x for x in s.split("/") if x not in ("", ".")]
    if ".." in segs:
        return None, 'a ".." segment is not allowed: ' + original
    if not segs:
        return None, "path names the repo root or nothing: " + original
    return "/".join(segs).lower(), None


def paths_overlap(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def check_ownership(tracks, repo, reserved=None):
    errors, entries, seen = [], [], set()
    for i, t in enumerate(tracks):
        name = t.get("name") if isinstance(t.get("name"), str) else ""
        name = name.strip()
        if not name:
            errors.append("track #%d has no name" % (i + 1))
            continue
        key = name.lower()
        if key in seen:
            errors.append("duplicate track name: " + name)
        seen.add(key)
        if key == "contract":
            errors.append('the track name "contract" is reserved')
        files = t.get("files")
        if not isinstance(files, list) or not files:
            errors.append("track %s lists no files" % name)
            continue
        for f in files:
            p, err = norm_entry(f, repo)
            if err:
                errors.append("track %s: %s" % (name, err))
            else:
                entries.append((name, p, str(f).strip()))
    if reserved:
        p, err = norm_entry(reserved, repo)
        if not err:
            entries.append(("contract", p, reserved))
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            a, b = entries[i], entries[j]
            if a[0] != b[0] and paths_overlap(a[1], b[1]):
                errors.append("overlap: %s (%s) and %s (%s)" % (a[2], a[0], b[2], b[0]))
    owned = {}
    for owner, p, _ in entries:
        owned.setdefault(owner, [])
        if p not in owned[owner]:
            owned[owner].append(p)
    return errors, owned


def op_tracks(obj, repo=None, contract=None):
    """Returns (result, exit_code)."""
    if isinstance(obj, dict):
        tracks = obj.get("tracks")
        repo = repo if repo is not None else obj.get("repo")
        contract = contract if contract is not None else obj.get("contractPath")
    else:
        tracks = obj
    if not isinstance(tracks, list) or not tracks:
        raise InputError("tracks must be a non-empty list (or an object with a \"tracks\" list)")
    for t in tracks:
        if not isinstance(t, dict):
            raise InputError("every track must be an object with name and files")
    if len(tracks) > MAX_NODES:
        raise InputError("too many tracks")
    errors, owned = check_ownership(tracks, repo, contract)
    names = [t["name"].strip() for t in tracks if isinstance(t.get("name"), str) and t["name"].strip()]
    nameset = set(names)
    edges = []
    for t in tracks:
        deps = t.get("deps", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise InputError("deps must be a list of track names")
        me = t.get("name", "").strip() if isinstance(t.get("name"), str) else ""
        for d in deps:
            d = d.strip()
            if d not in nameset:
                raise InputError("track %r depends on %r, which is not a track name" % (me, d))
            if me and (d, me) not in edges:
                edges.append((d, me))
    result = {"ok": not errors, "errors": errors, "ownership_map": owned, "track_count": len(tracks)}
    if errors:
        return result, 1
    nodes = list(dict.fromkeys(names))
    _, is_dag, cycle = topo_order(nodes, edges)
    result["graph"] = {"nodes": nodes, "edges": [list(e) for e in edges]}
    if not is_dag:
        result["ok"] = False
        result["errors"] = ["the dependencies form a cycle: " + " -> ".join(cycle)]
        result["example_cycle"] = cycle
        return result, 1
    w = op_width(nodes, edges)
    result["width"] = w["width"]
    result["antichain"] = w["antichain"]
    result["critical_path"] = op_critical_path(nodes, edges)["path"]
    result["fan_out_is_real"] = w["width"] == len(nodes)
    result["note"] = ("width equals the track count: the tracks can run side by side" if w["width"] == len(nodes)
                      else "width is below the track count: some tracks wait on others, so part of this fan-out is a chain")
    return result, 0


# ---- command line -----------------------------------------------------------------------------------------------

OPS = ("validate", "width", "critical-path", "cone", "reduce", "tracks")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("op", nargs="?", help="one of: " + ", ".join(OPS) + " (critical_path also works)")
    ap.add_argument("node", nargs="?", help="target node (cone only)")
    ap.add_argument("-f", "--file", help="JSON input file (default: stdin)")
    ap.add_argument("--json", dest="inline", help="JSON input given inline")
    ap.add_argument("--tracks", action="store_true", help="treat the input as workflow-style tracks")
    ap.add_argument("--repo", help="repo root, so absolute paths inside it can be normalised (tracks only)")
    ap.add_argument("--contract", help="contract file path to reserve (tracks only)")
    args = ap.parse_args(argv)
    op = args.op.replace("_", "-") if args.op else None
    if args.tracks and op is None:
        op = "tracks"
    if op not in OPS:
        ap.error("choose an operation: " + ", ".join(OPS))
    if op == "cone" and not args.node:
        ap.error("cone requires a NODE argument")
    try:
        obj = parse_json(read_text(args.file, args.inline))
        if op == "tracks":
            result, code = op_tracks(obj, args.repo, args.contract)
            print(json.dumps(result, indent=2))
            return code
        nodes, edges = build_graph(obj)
        if op == "validate":
            result = op_validate(nodes, edges)
        elif op == "cone":
            result = op_cone(nodes, edges, args.node)
        elif op == "reduce":
            result = op_reduce(nodes, edges)
        elif op == "width":
            result = op_width(nodes, edges)
        else:
            result = op_critical_path(nodes, edges)
        print(json.dumps(result, indent=2))
        return 0
    except Cyclic as exc:
        print(json.dumps({"error": "graph is cyclic; %s needs a DAG" % exc.op, "example_cycle": exc.cycle,
                          "remedy": "remove or reverse one edge on the cycle, then run it again"}, indent=2))
        return 1
    except InputError as exc:
        sys.stderr.write("dag_ops: %s\n" % exc)
        return 2
    except Exception as exc:  # last resort: a one-line message, never a traceback
        sys.stderr.write("dag_ops: unexpected error: %s: %s\n" % (type(exc).__name__, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
