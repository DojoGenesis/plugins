#!/usr/bin/env python3
"""dojo-meter cost report: what a session, a day or a project cost, from your own transcripts.

Reads Claude Code transcripts (`projects/**/*.jsonl`, subagent and workflow-agent files included) under the
Claude Code config directory, counts the four usage fields per model and per thread (main or subagent), and
prices them from scripts/pricing.json. Read-only. Standard library only, Python 3.9 or newer.

Scope (pick one; with no flag the command reports the session it was started from, else today):
  --session ID   one session: <ID>.jsonl plus its subagent files
  --today        entries since local midnight
  --days N       entries since local midnight N-1 days ago (N calendar days including today)
  --all          every entry
  --project PATH only transcripts of the project at PATH (combines with the scopes above; alone = all time)
Other flags: --json (machine-readable), --root DIR (config dir, for tests), --default-session ID (used by the
command, only when no scope flag is given).

Counting rules, in order:
  * only lines whose top-level type is "assistant" with a message.usage object count;
  * one API response is written as several lines that repeat the same usage, and a resumed session repeats
    history in another file, so lines are de-duplicated across every file on message.id (requestId when the
    id is missing), keeping the largest value of each field, so the result does not depend on read order;
  * a "<synthetic>" model is skipped; usage fields count only when they are non-negative integers;
  * main versus subagent: the file path (a "subagents" folder) or isSidechain true;
  * model ids are normalised (case, provider prefix, @date, -date, -vN tags, [..] tags) and are priced only when
    the result equals a pricing.json id, optionally after one more known decoration: "-fast" or "-latest".
    Anything else is "unpriced", never a guess: claude-opus-5-6 is not claude-opus-5, and a suffix such as
    "-preview" is not known either. An id that matches nothing is "unpriced", never $0;
  * a total that leaves unpriced tokens out says "partial"; with nothing priced it reads "unpriced".
Nothing here prints a project folder name or a path.
"""
import argparse
import calendar
import json
import os
import re
import sys
import time
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
PRICING_PATH = os.path.join(HERE, "pricing.json")

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?\s*(Z|z|[+-]\d{2}:?\d{2})?$"
)
TIERS = ("opus", "sonnet", "haiku", "fable")
MAX_MODEL_LEN = 200

CAVEATS = (
    "Estimate at list prices (see scripts/pricing.json), not an invoice.",
    "Subscription plans bill differently: read the dollars as relative weight, not as what you pay.",
    "Transcripts under-record some subagent output, so subagent rows are lower bounds.",
    'Unknown models are shown as "unpriced", never as $0; totals that leave them out say "partial".',
    "The live band (mod) prices every cache write at the 5-minute rate, so this report can read higher.",
)


# ---------------------------------------------------------------- pricing and model ids

def load_pricing(path=PRICING_PATH):
    with open(path, "r") as handle:
        return json.load(handle, parse_float=Decimal, parse_int=Decimal)


def normalize_model(raw):
    """Lower-case, drop a provider prefix, [..] tags, @date, -vN[:N] and -date suffixes. '' when unusable."""
    if not isinstance(raw, str):
        return ""
    text = raw.strip().lower()
    if not text or len(text) > MAX_MODEL_LEN:
        return ""
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"^(?:[a-z0-9_-]+[./])+(?=claude-)", "", text)
    text = re.sub(r"@\d{8}$", "", text)
    text = re.sub(r"-v\d+(?::\d+)?$", "", text)
    text = re.sub(r"-\d{8}$", "", text)
    return text.strip()


def tier_of(normalized):
    for tier in TIERS:
        if tier in normalized:
            return tier
    return "other"


VARIANT_RE = re.compile(r"-(?:fast|latest)$")


def price_key(pricing, normalized):
    """The pricing.json key a normalised id is priced as, or None (unpriced).

    An id is priced only when it IS a known id, or a known id plus one known variant decoration ("-fast" or
    "-latest"; the date, bracket and provider tags are already gone after normalize_model). It is never priced by
    resemblance: a newer version number (claude-opus-5-6, claude-opus-5-50), an unknown suffix ("-preview") or
    junk after a known id stays unpriced. tests/model_vectors.json drives this and hooks/ledger.ts priceKeyFor.
    """
    models = pricing["models"]
    if normalized in models:
        return normalized
    base = VARIANT_RE.sub("", normalized, count=1)
    if base != normalized and base in models:
        return base
    return None


def price_for(pricing, normalized):
    """The pricing.json row for a normalised id (see price_key), else None (unpriced)."""
    key = price_key(pricing, normalized)
    return None if key is None else pricing["models"][key]


def display_model(normalized):
    if not normalized:
        return "unknown"
    cleaned = re.sub(r"[^a-z0-9._:-]", "?", normalized)
    return cleaned[:40]


# ---------------------------------------------------------------- time

def parse_timestamp(value):
    """Epoch seconds for an ISO-8601 string ('Z' and fractions included; no zone = UTC), else None."""
    if not isinstance(value, str):
        return None
    match = TS_RE.match(value.strip())
    if not match:
        return None
    year, month, day, hour, minute, second = [int(match.group(i)) for i in range(1, 7)]
    if not (1 <= month <= 12 and 1 <= day <= 31 and hour < 24 and minute < 60 and second < 61):
        return None
    try:
        epoch = calendar.timegm((year, month, day, hour, minute, second, 0, 0, 0))
    except (OverflowError, ValueError, IndexError):
        return None
    zone = match.group(8)
    offset = 0
    if zone and zone not in ("Z", "z"):
        sign = 1 if zone[0] == "+" else -1
        digits = zone[1:].replace(":", "")
        offset = sign * (int(digits[:2]) * 3600 + int(digits[2:]) * 60)
    return float(epoch - offset)


def local_midnight(now_epoch, days_back):
    """Epoch of local midnight `days_back` days before the local day of now_epoch (DST-safe via mktime)."""
    lt = time.localtime(now_epoch)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - days_back, 0, 0, 0, 0, 0, -1))


def local_date_label(epoch):
    lt = time.localtime(epoch)
    return "%04d-%02d-%02d" % (lt.tm_year, lt.tm_mon, lt.tm_mday)


# ---------------------------------------------------------------- scope

class Scope(object):
    def __init__(self, kind, window_start=None, session_id=None, project=None, label=""):
        self.kind = kind
        self.window_start = window_start
        self.session_id = session_id
        self.project = project
        self.label = label


def encode_project(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def project_encodings(path):
    out = []
    expanded = os.path.expanduser(path)
    for candidate in (os.path.abspath(expanded), os.path.realpath(expanded)):
        enc = encode_project(candidate)
        if enc not in out:
            out.append(enc)
    return out


def project_matches(dirname, encodings):
    for enc in encodings:
        if dirname == enc:
            return True
        # The engine cuts long names to 200 characters and appends a hash it does not share with us.
        if len(enc) > 200 and dirname.startswith(enc[:200] + "-"):
            return True
    return False


def build_scope(args, now_epoch):
    session_id = None
    window_start = None
    kind = None
    label = ""
    if args.session is not None:
        kind, session_id, label = "session", args.session, "session %s" % args.session
    elif args.all:
        kind, label = "all", "all transcripts"
    elif args.days is not None:
        window_start = local_midnight(now_epoch, args.days - 1)
        kind = "days"
        label = "last %d day%s (since %s, local)" % (args.days, "" if args.days == 1 else "s",
                                                      local_date_label(window_start))
    elif args.today:
        window_start = local_midnight(now_epoch, 0)
        kind, label = "today", "today (since %s 00:00 local)" % local_date_label(window_start)
    elif args.project is not None:
        kind, label = "all", "all transcripts"
    else:
        default = (args.default_session or "").strip()
        if default and not default.startswith("${") and SESSION_ID_RE.match(default):
            kind, session_id, label = "session", default, "this session"
        else:
            window_start = local_midnight(now_epoch, 0)
            kind = "today"
            label = "today (since %s 00:00 local)" % local_date_label(window_start)
    scope = Scope(kind, window_start, session_id, args.project, label)
    if args.project is not None:
        scope.label += ", one project"
    return scope


# ---------------------------------------------------------------- reading transcripts

def non_negative_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def walk_files(projects_dir, scope):
    """Yield (path, is_sidechain_path) for each transcript file in scope. Never follows symlinks."""
    encodings = project_encodings(scope.project) if scope.project is not None else None
    prefilter = None
    if scope.window_start is not None:
        prefilter = scope.window_start - 86400.0  # a day of slack for clock skew
    for dirpath, dirnames, filenames in os.walk(projects_dir, followlinks=False):
        dirnames.sort()
        rel = os.path.relpath(dirpath, projects_dir)
        parts = [] if rel == "." else rel.split(os.sep)
        if not parts and encodings is not None:
            dirnames[:] = [d for d in dirnames if project_matches(d, encodings)]
        for name in sorted(filenames):
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            file_parts = parts + [name]
            if len(file_parts) < 2:
                continue
            if scope.session_id is not None:
                wanted = scope.session_id
                is_main = len(file_parts) == 2 and name == wanted + ".jsonl"
                is_sub = len(file_parts) >= 4 and file_parts[1] == wanted and file_parts[2] == "subagents"
                if not (is_main or is_sub):
                    continue
            try:
                if os.path.islink(full) or not os.path.isfile(full):
                    continue
                if prefilter is not None and os.path.getmtime(full) < prefilter:
                    continue
            except OSError:
                continue
            yield full, ("subagents" in file_parts[1:-1])


def read_usage_entries(path, side_by_path, window_start, store, counters):
    """Fold one file's assistant usage lines into `store` (key -> record list). Fail soft on anything odd."""
    try:
        handle = open(path, "rb")
    except OSError:
        return False
    counters["files"] += 1
    with handle:
        line_no = 0
        try:
            for raw in handle:
                line_no += 1
                # Speed gate only: the decision is made on the parsed object below.
                if b'"usage"' not in raw or b'"assistant"' not in raw:
                    continue
                try:
                    obj = json.loads(raw.decode("utf-8", "replace"))
                except (ValueError, RecursionError, MemoryError):
                    continue  # not JSON, or nested so deeply that the parser gave up: skip the line
                fold_entry(obj, side_by_path, window_start, store, path, line_no)
        except (OSError, MemoryError):
            return True
    return True


def fold_entry(obj, side_by_path, window_start, store, path, line_no):
    if not isinstance(obj, dict) or obj.get("type") != "assistant":
        return
    message = obj.get("message")
    if not isinstance(message, dict):
        return
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return
    model = message.get("model")
    if isinstance(model, str) and model.strip().lower() == "<synthetic>":
        return
    if window_start is not None:
        stamp = parse_timestamp(obj.get("timestamp"))
        if stamp is None or stamp < window_start:
            return
    message_id = message.get("id")
    request_id = obj.get("requestId")
    if isinstance(message_id, str) and message_id:
        key = ("m", message_id)
    elif isinstance(request_id, str) and request_id:
        key = ("r", request_id)
    else:
        key = ("l", path, line_no)  # nothing to de-duplicate on: count it as it stands
    split = usage.get("cache_creation")
    split = split if isinstance(split, dict) else {}
    values = (
        non_negative_int(usage.get("input_tokens")),
        non_negative_int(usage.get("output_tokens")),
        non_negative_int(usage.get("cache_read_input_tokens")),
        non_negative_int(usage.get("cache_creation_input_tokens")),
        non_negative_int(split.get("ephemeral_5m_input_tokens")),
        non_negative_int(split.get("ephemeral_1h_input_tokens")),
    )
    sidechain = side_by_path or obj.get("isSidechain") is True
    model_text = model if isinstance(model, str) else ""
    current = store.get(key)
    if current is None:
        store[key] = [model_text, list(values), sidechain]
        return
    merged = [max(a, b) for a, b in zip(current[1], values)]
    # Keep the model of the larger-output copy; ties go to the smaller string so order never matters.
    if (values[1], model_text) > (current[1][1], current[0]):
        current[0] = model_text
    current[1] = merged
    # A copy seen on the main thread makes the record a main-thread record.
    current[2] = current[2] and sidechain


def collect(projects_dir, scope):
    store = {}
    counters = {"files": 0}
    if not os.path.isdir(projects_dir):
        return store, counters
    for path, side_by_path in walk_files(projects_dir, scope):
        read_usage_entries(path, side_by_path, scope.window_start, store, counters)
    return store, counters


# ---------------------------------------------------------------- aggregation and pricing

def new_row():
    return {"requests": 0, "input": 0, "output": 0, "read": 0, "w5": 0, "w1": 0}


def aggregate(store):
    """(normalised model, 'main'|'sub') -> row. Cache writes split into 5-minute (w5) and 1-hour (w1)."""
    rows = {}
    for model, values, sidechain in store.values():
        norm = normalize_model(model)
        who = "sub" if sidechain else "main"
        row = rows.setdefault((norm, who), new_row())
        inp, out, read, flat, s5, s1 = values
        write_total = max(flat, s5 + s1)
        row["requests"] += 1
        row["input"] += inp
        row["output"] += out
        row["read"] += read
        row["w1"] += s1
        row["w5"] += write_total - s1
    return rows


def row_usd(pricing, norm, row):
    """Decimal USD for a row, or None when the model is not in pricing.json."""
    price = price_for(pricing, norm)
    if price is None:
        return None
    m5 = pricing["cache_write_5m_multiplier"]
    m1 = pricing["cache_write_1h_multiplier"]
    total = (
        row["input"] * price["input"]
        + row["output"] * price["output"]
        + row["read"] * price["cache_read"]
        + row["w5"] * price["input"] * m5
        + row["w1"] * price["input"] * m1
    )
    return total / Decimal(1000000)


def row_tokens(row):
    return row["input"] + row["output"] + row["read"] + row["w5"] + row["w1"]


def format_usd(value):
    if value is None:
        return "unpriced"
    if value > 0 and value < Decimal("0.01"):
        return "<$0.01"
    return "$%s" % value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_tokens(count):
    if count >= 1000000:
        return "%.1fM" % (count / 1e6)
    if count >= 10000:
        return "%dk" % int(round(count / 1e3))
    if count >= 1000:
        return "%.1fk" % (count / 1e3)
    return str(count)


def share_text(read, input_side):
    if input_side <= 0:
        return "-"
    return "%.1f%%" % (100.0 * read / input_side)


class Bucket(object):
    """One dollar figure (the main thread, the subagents, the total, or one tier) and what it leaves out.

    Judged on tokens, not rows: a priced row with no tokens behind it prices nothing, and an unpriced row with
    unusable counts is still an unpriced model, so neither may turn into a bare $0.00.
    """

    def __init__(self):
        self.usd = Decimal(0)
        self.priced_tokens = 0
        self.unpriced_rows = 0
        self.rows = 0
        self.unpriced_tokens = 0

    def add(self, usd, tokens):
        self.rows += 1
        if usd is None:
            self.unpriced_rows += 1
            self.unpriced_tokens += tokens
        else:
            self.priced_tokens += tokens
            self.usd += usd

    @property
    def partial(self):
        """True when the dollars are real but leave some tokens out."""
        return self.priced_tokens > 0 and self.unpriced_tokens > 0

    @property
    def value(self):
        """The Decimal dollars, or None when nothing in the bucket could be priced and an unpriced model is in it."""
        if self.priced_tokens == 0 and self.unpriced_rows > 0:
            return None
        return self.usd

    def text(self):
        if self.rows == 0:
            return "none"
        value = self.value
        if value is None:
            return "unpriced"
        return format_usd(value) + (" (partial)" if self.partial else "")


def summarize(pricing, rows):
    """Everything the text and JSON views need, computed once."""
    out_rows = []
    buckets = {"main": Bucket(), "sub": Bucket(), "total": Bucket()}
    by_tier = {}
    read_total = input_side_total = 0
    for (norm, who), row in rows.items():
        usd = row_usd(pricing, norm, row)
        tier = tier_of(norm)
        tokens = row_tokens(row)
        write = row["w5"] + row["w1"]
        buckets[who].add(usd, tokens)
        buckets["total"].add(usd, tokens)
        by_tier.setdefault(tier, Bucket()).add(usd, tokens)
        read_total += row["read"]
        input_side_total += row["input"] + write + row["read"]
        out_rows.append({
            "model": display_model(norm), "tier": tier, "who": who, "requests": row["requests"],
            "input": row["input"], "cache_write": write, "cache_read": row["read"], "output": row["output"],
            "cache_write_1h": row["w1"], "usd": usd, "priced_as": price_key(pricing, norm),
        })
    rank = {name: i for i, name in enumerate(TIERS + ("other",))}
    out_rows.sort(key=lambda r: (rank[r["tier"]], r["model"], r["who"]))
    return {
        "rows": out_rows, "main": buckets["main"], "sub": buckets["sub"], "total": buckets["total"],
        "by_tier": by_tier, "read": read_total, "input_side": input_side_total,
    }


# ---------------------------------------------------------------- output

MAX_PREFIX_NOTES = 4


def prefix_notes(summary):
    """One line naming each id that was priced as a known id plus a variant decoration (-fast, -latest), or nothing."""
    seen = []
    for row in summary["rows"]:
        if row["priced_as"] is not None and row["priced_as"] != row["model"]:
            pair = (row["model"], row["priced_as"])
            if pair not in seen:
                seen.append(pair)
    if not seen:
        return None
    shown = ["%s as %s" % pair for pair in seen[:MAX_PREFIX_NOTES]]
    more = len(seen) - len(shown)
    return "priced as the base id: " + ", ".join(shown) + (" (+%d more)" % more if more > 0 else "")


def render_text(pricing, scope, summary):
    lines = ["dojo-meter cost report: %s" % scope.label]
    lines.append("%-22s %-4s %5s %7s %7s %7s %7s %11s" % (
        "model", "who", "reqs", "input", "write", "read", "output", "est USD"))
    for row in summary["rows"]:
        lines.append("%-22s %-4s %5d %7s %7s %7s %7s %11s" % (
            row["model"][:22], row["who"], row["requests"], format_tokens(row["input"]),
            format_tokens(row["cache_write"]), format_tokens(row["cache_read"]),
            format_tokens(row["output"]), format_usd(row["usd"])))
    lines.append("")
    lines.append("main thread %s   subagents %s   total %s" % (
        summary["main"].text(), summary["sub"].text(), summary["total"].text()))
    if summary["total"].unpriced_tokens:
        lines.append("+%d tokens unpriced (no price for the model)%s" % (
            summary["total"].unpriced_tokens,
            "; figures marked partial leave them out" if summary["total"].partial else ""))
    note = prefix_notes(summary)
    if note:
        lines.append(note)
    tiers = [t for t in TIERS + ("other",) if t in summary["by_tier"]]
    if tiers:
        lines.append("by tier: " + "  ".join("%s %s" % (t, summary["by_tier"][t].text()) for t in tiers))
    lines.append("cache-read share of input-side tokens: %s  (read / (input + write + read))"
                 % share_text(summary["read"], summary["input_side"]))
    lines.append("prices: %s" % pricing["source"])
    lines.append("cache writes: 1.25x input (5-minute), 2x input (1-hour, when the transcript records it)")
    lines.append("")
    lines.append("Caveats:")
    for caveat in CAVEATS:
        lines.append("- " + caveat)
    return "\n".join(lines)


def render_json(pricing, scope, summary):
    def num(value):
        return None if value is None else float(value)

    main, sub, whole = summary["main"], summary["sub"], summary["total"]
    payload = {
        "scope": scope.label,
        "price_source": pricing["source"],
        "rows": [{
            "model": r["model"], "tier": r["tier"], "who": r["who"], "requests": r["requests"],
            "input": r["input"], "cache_write": r["cache_write"], "cache_write_1h": r["cache_write_1h"],
            "cache_read": r["cache_read"], "output": r["output"], "usd": num(r["usd"]),
            "priced": r["usd"] is not None, "priced_as": r["priced_as"],
        } for r in summary["rows"]],
        # A usd figure is null when tokens were counted and none could be priced; "partial" is true when the
        # figure is a number that leaves some tokens out (see the matching unpriced_tokens).
        "totals": {
            "main_usd": num(main.value), "main_unpriced_tokens": main.unpriced_tokens, "main_partial": main.partial,
            "subagent_usd": num(sub.value), "subagent_unpriced_tokens": sub.unpriced_tokens,
            "subagent_partial": sub.partial,
            "usd": num(whole.value), "unpriced_tokens": whole.unpriced_tokens, "partial": whole.partial,
            "by_tier_usd": {k: num(v.value) for k, v in summary["by_tier"].items()},
            "by_tier_unpriced_tokens": {k: v.unpriced_tokens for k, v in summary["by_tier"].items()},
            "by_tier_partial": {k: v.partial for k, v in summary["by_tier"].items()},
            "cache_read_share": (summary["read"] / float(summary["input_side"])) if summary["input_side"] else None,
        },
        "caveats": list(CAVEATS),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------- command line

def positive_days(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("--days expects a whole number of days, 1 or more")
    if value < 1 or value > 3650:
        raise argparse.ArgumentTypeError("--days expects a whole number of days, 1 to 3650")
    return value


def session_id_arg(text):
    if not SESSION_ID_RE.match(text):
        raise argparse.ArgumentTypeError("--session expects an id of letters, digits, _ or - (up to 128)")
    return text


def timestamp_arg(text):
    stamp = parse_timestamp(text)
    if stamp is None:
        raise argparse.ArgumentTypeError("--now expects an ISO-8601 time")
    return stamp


def build_parser():
    parser = argparse.ArgumentParser(
        prog="cost.py", description="Cost report from Claude Code transcripts (estimate at list prices).")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--session", type=session_id_arg, metavar="ID", help="one session, by id")
    group.add_argument("--today", action="store_true", help="since local midnight")
    group.add_argument("--days", type=positive_days, metavar="N", help="the last N calendar days")
    group.add_argument("--all", action="store_true", help="every transcript entry")
    parser.add_argument("--project", metavar="PATH", help="only the project at PATH")
    parser.add_argument("--json", action="store_true", help="print JSON instead of the table")
    parser.add_argument("--root", metavar="DIR", help=argparse.SUPPRESS)
    parser.add_argument("--default-session", metavar="ID", default="", help=argparse.SUPPRESS)
    parser.add_argument("--now", type=timestamp_arg, default=None, help=argparse.SUPPRESS)
    return parser


def config_root(args):
    if args.root:
        return args.root
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def main(argv=None):
    args = build_parser().parse_args(argv)
    now_epoch = args.now if args.now is not None else time.time()
    try:
        pricing = load_pricing()
    except (OSError, ValueError, KeyError):
        sys.stderr.write("dojo-meter: could not read scripts/pricing.json, so no estimate can be made.\n")
        return 1
    scope = build_scope(args, now_epoch)
    store, counters = collect(os.path.join(config_root(args), "projects"), scope)
    if counters["files"] == 0:
        message = ("dojo-meter: no transcripts in scope (%s). Try --today, --days N or --all." % scope.label)
        sys.stdout.write((json.dumps({"scope": scope.label, "rows": [], "message": "no transcripts in scope"})
                          if args.json else message) + "\n")
        return 0
    if not store:
        message = "dojo-meter: no usage entries in scope (%s). Try a wider scope: --days N or --all." % scope.label
        sys.stdout.write((json.dumps({"scope": scope.label, "rows": [], "message": "no usage entries in scope"})
                          if args.json else message) + "\n")
        return 0
    summary = summarize(pricing, aggregate(store))
    sys.stdout.write((render_json(pricing, scope, summary) if args.json else render_text(pricing, scope, summary)) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as err:  # fail soft: a short line, never a traceback (it would print the install path)
        sys.stderr.write("dojo-meter: the report could not be finished (%s).\n" % type(err).__name__)
        sys.exit(1)
