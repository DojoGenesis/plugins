"""Run judge_files.py on every run of an eval JSON (amendment 1); append one JSON line per run.

    judge_runs.py <eval.json> <plugin-dir> <out.jsonl>
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
E = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(sys.argv[1], encoding="utf-8"))
plugin, out = sys.argv[2], sys.argv[3]
jobs = []
for c in d["cases"]:
    for arm, runs in c["arms"].items():
        for i, r in enumerate(runs):
            root = os.path.dirname(os.path.dirname(r["tracePath"]))
            jobs.append((c["name"], arm, i + 1, os.path.join(root, "home", "cwd")))
def one(j):
    name, arm, run, work = j
    cy = os.path.join(plugin, "evals", name, "case.yaml"); sc = os.path.join(plugin, "evals", name, "scaffold.sh")
    p = subprocess.run([sys.executable, os.path.join(E, "judge_files.py"), cy, sc, work], capture_output=True, text=True, encoding="utf-8")
    try: res = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: res = {"verdict": "COULD NOT RUN", "reason": (p.stderr or p.stdout)[-300:]}
    res.update(case=name, arm=arm, run=run, work=work)
    return res
with ThreadPoolExecutor(3) as ex, open(out, "a", encoding="utf-8") as f:
    for res in ex.map(one, jobs):
        f.write(json.dumps(res) + "\n"); f.flush()
        print(res["case"], res["arm"], res["run"], res["verdict"], res.get("cost_usd"))
