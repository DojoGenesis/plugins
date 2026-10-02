"""cost.py on hand-written fixture transcripts: dedupe, sidechain split, pricing, scope, time, robustness."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from _helpers import (CANARY, COST, M, NOW, PLUGIN_ROOT, PY, SCRIPTS, TESTS, Fixture, entry, rows_by, run_cost,
                      run_json, total)

import cost  # scripts/cost.py, importable through _helpers' sys.path entry


def epoch(text):
    return cost.parse_timestamp(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)


class Dedupe(Base):
    def test_blocks_of_one_response_count_once_and_keep_the_largest_value(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("m1", "r1", inp=100, out=10, read=300, write=50, block="thinking"),
            entry("m1", "r1", inp=100, out=50, read=300, write=50, block="text"),
            entry("m1", "r1", inp=100, out=30, read=300, write=50, block="tool_use"),
        ])
        data = run_json(self.fx)
        (row,) = data["rows"]
        self.assertEqual((row["requests"], row["input"], row["output"], row["cache_read"], row["cache_write"]),
                         (1, 100, 50, 300, 50))

    def test_the_same_response_in_two_files_counts_once(self):
        line = entry("m1", "r1", inp=100, out=20)
        self.fx.write("-p1/s1.jsonl", [line])
        self.fx.write("-p1/s2.jsonl", [line])  # a resumed session repeats history
        data = run_json(self.fx)
        self.assertEqual(total(data, "input"), 100)
        self.assertEqual(total(data, "requests"), 1)

    def test_an_id_seen_with_and_without_a_request_id_counts_once(self):
        self.fx.write("-p1/s1.jsonl", [entry("m1", "r1", inp=100, out=20), entry("m1", None, inp=100, out=20)])
        self.assertEqual(total(run_json(self.fx), "requests"), 1)

    def test_different_ids_count_separately(self):
        self.fx.write("-p1/s1.jsonl", [entry("m1", "r1", inp=100), entry("m2", "r2", inp=7)])
        data = run_json(self.fx)
        self.assertEqual((total(data, "requests"), total(data, "input")), (2, 107))

    def test_a_line_with_no_id_and_no_request_id_counts_as_it_stands(self):
        self.fx.write("-p1/s1.jsonl", [entry(None, None, inp=5), entry(None, None, inp=5)])
        self.assertEqual(total(run_json(self.fx), "input"), 10)

    def test_the_result_does_not_depend_on_the_order_files_are_read(self):
        def build(main_project, sub_project):
            fx = Fixture()
            self.addCleanup(fx.cleanup)
            dup = entry("m9", "r9", inp=100, out=40, read=7)
            fx.write("%s/sA.jsonl" % main_project, [dup, entry("m1", "r1", inp=1)])
            fx.write("%s/sB/subagents/agent-1.jsonl" % sub_project,
                     [entry("m9", "r9", inp=100, out=40, read=7, sidechain=True), entry("m2", "r2", inp=2, sidechain=True)])
            return run_cost(fx)
        first = build("-aaa", "-zzz")
        second = build("-zzz", "-aaa")
        self.assertEqual(first[0], 0)
        self.assertEqual(first[1], second[1])

    def test_a_copy_on_the_main_thread_makes_the_record_a_main_thread_record(self):
        self.fx.write("-p1/sA.jsonl", [entry("m9", "r9", inp=100)])
        self.fx.write("-p1/sA/subagents/agent-1.jsonl", [entry("m9", "r9", inp=100, sidechain=True)])
        data = run_json(self.fx)
        self.assertEqual((total(data, "input", "main"), total(data, "input", "sub")), (100, 0))


class Sidechain(Base):
    def test_path_and_flag_both_mark_a_subagent(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", inp=1), entry("f", "rf", inp=1000, sidechain=True)])
        self.fx.write("-p1/s1/subagents/agent-a.jsonl", [entry("b", "rb", inp=20, sidechain=True)])
        self.fx.write("-p1/s1/subagents/workflows/wf_1/agent-b.jsonl", [entry("c", "rc", inp=300, sidechain=True)])
        # A subagent file whose lines lost the flag is still a subagent by path.
        self.fx.write("-p1/s1/subagents/agent-c.jsonl", [entry("d", "rd", inp=40000, sidechain=False)])
        data = run_json(self.fx)
        self.assertEqual(total(data, "input", "main"), 1)
        self.assertEqual(total(data, "input", "sub"), 1000 + 20 + 300 + 40000)

    def test_the_two_threads_are_priced_independently(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-haiku-4-5", inp=M)])
        self.fx.write("-p1/s1/subagents/agent-a.jsonl", [entry("b", "rb", model="claude-haiku-4-5", out=M, sidechain=True)])
        data = run_json(self.fx)
        self.assertAlmostEqual(data["totals"]["main_usd"], 1.0)
        self.assertAlmostEqual(data["totals"]["subagent_usd"], 5.0)
        self.assertAlmostEqual(data["totals"]["usd"], 6.0)


class Injection(Base):
    def test_only_top_level_assistant_lines_with_a_usage_object_count(self):
        counted = entry("ok", "r-ok", inp=11)
        fake_inner = json.loads(entry("fake1", "r1", inp=999999))
        progress = json.dumps({"type": "progress", "data": {"message": fake_inner}})
        user_line = json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": entry("fake2", "r2", inp=888888)}]}})
        string_usage = entry("fake3", "r3", usage="not an object")
        list_usage = entry("fake4", "r4", usage=[1, 2, 3])
        assistant_like = entry("fake5", "r5", inp=777777, kind="summary")
        self.fx.write("-p1/s1.jsonl", [progress, user_line, string_usage, list_usage, assistant_like, counted])
        data = run_json(self.fx)
        self.assertEqual((total(data, "requests"), total(data, "input")), (1, 11))

    def test_adversarial_numbers_count_only_when_they_are_whole_non_negative_numbers(self):
        weird = entry("w1", "rw", usage={
            "input_tokens": True, "output_tokens": -5, "cache_read_input_tokens": "100",
            "cache_creation_input_tokens": None, "cache_creation": {"ephemeral_5m_input_tokens": 1.5,
                                                                    "ephemeral_1h_input_tokens": -1}})
        missing = entry("w2", "rw2", usage={"output_tokens": 7})
        floaty = entry("w3", "rw3", usage={"input_tokens": 1.5, "output_tokens": 3})
        self.fx.write("-p1/s1.jsonl", [weird, missing, floaty])
        code, out, err = run_cost(self.fx, "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(total(data, "output"), 10)  # 7 + 3
        for field in ("input", "cache_read", "cache_write"):
            self.assertEqual(total(data, field), 0)


class Models(Base):
    def test_normalizing_follows_the_shared_vectors(self):
        with open(os.path.join(TESTS, "model_vectors.json")) as handle:
            vectors = json.load(handle)
        pricing = cost.load_pricing()
        for raw, expected in vectors["normalize"]:
            self.assertEqual(cost.normalize_model(raw), expected, raw)
        for raw, priced in vectors["priced"]:
            norm = cost.normalize_model(raw)
            self.assertEqual(cost.price_key(pricing, norm), priced, raw)
            row = cost.price_for(pricing, norm)
            if priced is None:
                self.assertIsNone(row, raw)
            else:
                self.assertEqual(row, pricing["models"][priced], raw)
        for raw, tier in vectors["tiers"]:
            self.assertEqual(cost.tier_of(cost.normalize_model(raw)), tier, raw)
        self.assertEqual(cost.normalize_model(None), "")
        self.assertEqual(cost.normalize_model("x" * 500), "")

    def test_the_vectors_only_name_keys_that_exist_in_the_table(self):
        with open(os.path.join(TESTS, "model_vectors.json")) as handle:
            vectors = json.load(handle)
        models = cost.load_pricing()["models"]
        for raw, priced in vectors["priced"]:
            if priced is not None:
                self.assertIn(priced, models, raw)

    def test_an_id_is_priced_only_when_it_is_a_known_id_plus_a_known_decoration(self):
        pricing = cost.load_pricing()
        self.assertEqual(cost.price_key(pricing, "claude-opus-5-5"), "claude-opus-5-5")
        self.assertEqual(cost.price_key(pricing, "claude-opus-5-5-fast"), "claude-opus-5-5")
        self.assertEqual(cost.price_key(pricing, "claude-haiku-4-5-latest"), "claude-haiku-4-5")
        # A newer version number is a different model, never a variant of the nearby key.
        for unknown in ("claude-opus-5-6", "claude-opus-5-50", "claude-fable-5-2", "claude-sonnet-5-7",
                        "claude-opus-5-5-preview", "claude-opus-5-5junk", "claude-opus-5-5-fast-fast",
                        "claude-opus-50", "claude-opus-4", "claude-opus-4-9", "claude-future-9", "fast", ""):
            self.assertIsNone(cost.price_key(pricing, unknown), unknown)

    def test_a_decorated_known_id_is_priced_and_says_so_and_an_unknown_one_is_not(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-opus-5-5", inp=M),          # exact: 4
            entry("b", "rb", model="claude-opus-5-5-preview", inp=M),  # unknown suffix: unpriced
            entry("c", "rc", model="claude-opus-5", inp=M),            # exact: 5
            entry("d", "rd", model="claude-opus-5-6", inp=M),          # a different model: unpriced
            entry("e", "re", model="claude-opus-4-8-fast", inp=M),     # known id plus -fast: 5
            entry("f", "rf", model="claude-opus-5-50", inp=M),         # unpriced
            entry("g", "rg", model="claude-fable-5-2", inp=M),         # unpriced
        ])
        data = run_json(self.fx)
        by_model = {r["model"]: r for r in data["rows"]}
        self.assertAlmostEqual(by_model["claude-opus-5-5"]["usd"], 4.0)
        self.assertAlmostEqual(by_model["claude-opus-5"]["usd"], 5.0)
        self.assertAlmostEqual(by_model["claude-opus-4-8-fast"]["usd"], 5.0)
        for unknown in ("claude-opus-5-5-preview", "claude-opus-5-6", "claude-opus-5-50", "claude-fable-5-2"):
            self.assertIsNone(by_model[unknown]["usd"], unknown)
            self.assertFalse(by_model[unknown]["priced"], unknown)
            self.assertIsNone(by_model[unknown]["priced_as"], unknown)
        self.assertEqual(by_model["claude-opus-4-8-fast"]["priced_as"], "claude-opus-4-8")
        self.assertEqual(by_model["claude-opus-5-5"]["priced_as"], "claude-opus-5-5")
        totals = data["totals"]
        self.assertAlmostEqual(totals["usd"], 14.0)
        self.assertTrue(totals["partial"])
        self.assertEqual(totals["unpriced_tokens"], 4 * M)
        text = run_cost(self.fx)[1]
        self.assertIn("total $14.00 (partial)", text)
        note = [l for l in text.splitlines() if l.startswith("priced as the base id:")]
        self.assertEqual(len(note), 1)
        self.assertIn("claude-opus-4-8-fast as claude-opus-4-8", note[0])
        self.assertNotIn("claude-opus-5-5 as", note[0])  # an exact match needs no note
        self.assertNotIn("claude-opus-5-6", note[0])

    def test_no_base_id_note_when_every_id_matches_exactly(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-haiku-4-5-20251001", inp=M)])
        self.assertNotIn("priced as the base id", run_cost(self.fx)[1])

    def test_a_version_number_that_the_table_does_not_know_never_borrows_a_price(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-opus-5-6", inp=M, out=M)])
        out = run_cost(self.fx)[1]
        self.assertIn("main thread unpriced   subagents none   total unpriced", out)
        self.assertNotIn("$", out.split("Caveats:")[0])
        data = json.loads(run_cost(self.fx, "--json")[1])
        self.assertIsNone(data["totals"]["usd"])

    def test_dated_and_tagged_ids_are_priced(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-haiku-4-5-20251001", inp=M),
            entry("b", "rb", model="claude-sonnet-5-5[1m]", inp=M),
        ])
        data = run_json(self.fx)
        self.assertEqual(sorted(r["model"] for r in data["rows"]), ["claude-haiku-4-5", "claude-sonnet-5-5"])
        self.assertAlmostEqual(data["totals"]["usd"], 3.0)

    def test_unpriced_tokens_are_counted_and_flagged_never_zero(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-future-9", inp=1000, out=234),
            entry("b", "rb", model="claude-haiku-4-5", inp=M),
            entry("c", "rc", model=None, inp=50),
        ])
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0, err)
        line = [l for l in out.splitlines() if l.startswith("claude-future-9")][0]
        self.assertIn("unpriced", line)
        self.assertNotIn("$0", line)
        self.assertIn("+1284 tokens unpriced", out)  # 1000 + 234 + 50
        self.assertIn("unknown", out)
        data = json.loads(run_cost(self.fx, "--json")[1])
        self.assertAlmostEqual(data["totals"]["usd"], 1.0)  # the unpriced rows add nothing to the dollars
        self.assertEqual(data["totals"]["unpriced_tokens"], 1284)

    def test_a_scope_with_only_unpriced_models_never_prints_zero_dollars(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-mystery-9", inp=M, out=100000)])
        self.fx.write("-p1/s1/subagents/agent-a.jsonl",
                      [entry("b", "rb", model="claude-mystery-9", inp=5, sidechain=True)])
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0, err)
        self.assertNotIn("$0", out.split("Caveats:")[0])  # the caveat text itself says "never as $0"
        self.assertIn("main thread unpriced   subagents unpriced   total unpriced", out)
        self.assertIn("other unpriced", out)  # the tier line too
        self.assertNotIn("(partial)", out)    # nothing priced, so nothing is a partial dollar figure
        data = json.loads(run_cost(self.fx, "--json")[1])
        totals = data["totals"]
        for field in ("usd", "main_usd", "subagent_usd"):
            self.assertIsNone(totals[field], field)
        self.assertEqual((totals["unpriced_tokens"], totals["main_unpriced_tokens"], totals["subagent_unpriced_tokens"]),
                         (1100005, 1100000, 5))
        self.assertEqual(totals["by_tier_usd"], {"other": None})
        self.assertFalse(totals["partial"])

    def test_a_total_that_leaves_unpriced_tokens_out_is_labelled_partial(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-haiku-4-5", inp=M),
            entry("b", "rb", model="claude-mystery-9", inp=777),
        ])
        out = run_cost(self.fx)[1]
        self.assertIn("main thread $1.00 (partial)   subagents none   total $1.00 (partial)", out)
        self.assertIn("figures marked partial leave them out", out)
        data = json.loads(run_cost(self.fx, "--json")[1])
        totals = data["totals"]
        self.assertAlmostEqual(totals["usd"], 1.0)
        self.assertTrue(totals["partial"])
        self.assertTrue(totals["main_partial"])
        self.assertFalse(totals["subagent_partial"])
        self.assertEqual(totals["unpriced_tokens"], 777)
        self.assertAlmostEqual(totals["subagent_usd"], 0.0)  # no subagent traffic at all: a true zero, not unknown
        self.assertEqual(totals["subagent_unpriced_tokens"], 0)

    def test_each_bucket_is_judged_on_its_own_tokens(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-haiku-4-5", inp=M)])
        self.fx.write("-p1/s1/subagents/agent-a.jsonl",
                      [entry("b", "rb", model="claude-mystery-9", inp=40, sidechain=True)])
        out = run_cost(self.fx)[1]
        # The main thread is fully priced, the subagents are not priced at all, the total is partial.
        self.assertIn("main thread $1.00   subagents unpriced   total $1.00 (partial)", out)
        data = json.loads(run_cost(self.fx, "--json")[1])["totals"]
        self.assertFalse(data["main_partial"])
        self.assertIsNone(data["subagent_usd"])
        self.assertTrue(data["partial"])

    def test_a_zero_token_unpriced_scope_is_unpriced_not_zero_dollars(self):
        # The counts are unusable (a string, a negative number), so the model's tokens count as 0.
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-mystery-9",
                  usage={"input_tokens": "12", "output_tokens": -3}),
            entry("b", "rb", model="claude-mystery-9", usage={}),
        ])
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0, err)
        head = out.split("Caveats:")[0]
        self.assertIn("main thread unpriced   subagents none   total unpriced", head)
        self.assertIn("other unpriced", head)
        self.assertNotIn("$0", head)
        totals = json.loads(run_cost(self.fx, "--json")[1])["totals"]
        self.assertIsNone(totals["usd"])
        self.assertIsNone(totals["main_usd"])
        self.assertEqual(totals["by_tier_usd"], {"other": None})
        self.assertFalse(totals["partial"])

    def test_a_priced_row_with_no_tokens_does_not_make_an_unpriced_figure_partial(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-opus-5-5", usage={}),             # priced, but nothing behind it
            entry("b", "rb", model="claude-opus-5-6", inp=500),              # unpriced, with tokens
        ])
        out = run_cost(self.fx)[1]
        head = out.split("Caveats:")[0]
        summary = head.split("main thread")[1]  # the row table above it prints the true $0.00 of the empty priced row
        self.assertIn("total unpriced", summary)
        self.assertIn("by tier: opus unpriced", summary)
        self.assertNotIn("$0", summary)
        self.assertNotIn("(partial)", summary)
        totals = json.loads(run_cost(self.fx, "--json")[1])["totals"]
        self.assertIsNone(totals["usd"])
        self.assertIsNone(totals["by_tier_usd"]["opus"])
        self.assertEqual(totals["unpriced_tokens"], 500)
        self.assertFalse(totals["partial"])

    def test_a_priced_row_with_no_tokens_and_nothing_unpriced_is_a_true_zero(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="claude-opus-5-5", usage={})])
        head = run_cost(self.fx)[1].split("Caveats:")[0]
        self.assertIn("total $0.00", head)
        self.assertNotIn("unpriced", head.split("main thread")[1])

    def test_a_tier_with_unpriced_tokens_is_labelled_too(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-opus-5-5", inp=M),
            entry("b", "rb", model="claude-opus-9-9", inp=10),   # an opus that no known id covers
        ])
        out = run_cost(self.fx)[1]
        self.assertIn("by tier: opus $4.00 (partial)", out)
        data = json.loads(run_cost(self.fx, "--json")[1])["totals"]
        self.assertTrue(data["by_tier_partial"]["opus"])
        self.assertEqual(data["by_tier_unpriced_tokens"]["opus"], 10)

    def test_the_report_stays_compact_with_partial_labels(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-opus-5-5", inp=M), entry("b", "rb", model="claude-opus-9-9", inp=10),
            entry("c", "rc", model="claude-opus-5-6", inp=M),
        ])
        self.fx.write("-p1/s1/subagents/agent-a.jsonl",
                      [entry("d", "rd", model="claude-mystery-9", inp=40, sidechain=True)])
        lines = run_cost(self.fx)[1].splitlines()
        self.assertLessEqual(len(lines), 40)
        self.assertLessEqual(max(len(l) for l in lines), 100)

    def test_synthetic_entries_are_ignored(self):
        self.fx.write("-p1/s1.jsonl", [entry("a", "ra", model="<synthetic>", inp=999), entry("b", "rb", inp=1)])
        data = run_json(self.fx)
        self.assertEqual([r["model"] for r in data["rows"]], ["claude-sonnet-5-5"])


class Arithmetic(Base):
    def usd(self, *lines, **kw):
        self.fx.write("-p1/s1.jsonl", list(lines))
        return run_json(self.fx, **kw)["totals"]["usd"]

    def test_each_usage_field_at_its_price(self):
        # opus-5-5: input 4, output 20, cache read 0.20 (USD per million)
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", inp=M)), 4.00)

    def test_output_read_and_flat_write(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", out=M)), 20.00)

    def test_a_flat_cache_write_with_no_split_is_priced_at_the_five_minute_rate(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", write=M)), 5.00)  # 4 x 1.25

    def test_cache_read(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", read=M)), 0.20)

    def test_all_four_together_on_each_tier(self):
        lines = [
            entry("a", "ra", model="claude-opus-5-5", inp=M, out=M, read=M, write=M),     # 4+20+0.2+5   = 29.20
            entry("b", "rb", model="claude-sonnet-5-5", inp=M, out=M, read=M, write=M),   # 2+10+0.2+2.5 = 14.70
            entry("c", "rc", model="claude-haiku-4-5", inp=M, out=M, read=M, write=M),    # 1+5+0.1+1.25 = 7.35
            entry("d", "rd", model="claude-fable-5-1", inp=M, out=M, read=M, write=M),    # 10+50+0.25+12.5 = 72.75
        ]
        self.fx.write("-p1/s1.jsonl", lines)
        data = run_json(self.fx)
        by_tier = data["totals"]["by_tier_usd"]
        self.assertAlmostEqual(by_tier["opus"], 29.20)
        self.assertAlmostEqual(by_tier["sonnet"], 14.70)
        self.assertAlmostEqual(by_tier["haiku"], 7.35)
        self.assertAlmostEqual(by_tier["fable"], 72.75)
        self.assertAlmostEqual(data["totals"]["usd"], 124.00)
        text = run_cost(self.fx)[1]
        self.assertIn("total $124.00", text)
        self.assertIn("opus $29.20", text)

    def test_one_hour_writes_cost_twice_the_input_price(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", write=M, split=(0, M))), 8.00)

    def test_a_split_prices_each_part_at_its_own_rate(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", write=M, split=(400000, 600000))), 6.80)

    def test_a_split_that_does_not_sum_to_the_flat_count_prices_the_remainder_at_five_minutes(self):
        # 200k at 1.25x, 300k at 2x, the 500k remainder at 1.25x: 1.00 + 2.40 + 2.50
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", write=M, split=(200000, 300000))), 5.90)

    def test_a_split_larger_than_the_flat_count_uses_the_split(self):
        self.assertAlmostEqual(self.usd(entry(model="claude-opus-5-5", write=0, split=(0, M))), 8.00)

    def test_text_shows_cents_exactly(self):
        self.fx.write("-p1/s1.jsonl", [entry(model="claude-opus-5-5", inp=M, write=M, split=(200000, 300000))])
        self.assertIn("total $9.90", run_cost(self.fx)[1])  # 4.00 + 5.90

    def test_small_amounts_are_shown_as_small_not_zero(self):
        self.fx.write("-p1/s1.jsonl", [entry(model="claude-haiku-4-5", inp=10)])
        self.assertIn("<$0.01", run_cost(self.fx)[1])


class CacheShare(Base):
    def test_read_over_input_side_tokens(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=100, read=300, write=100, out=999)])
        self.assertIn("share of input-side tokens: 60.0%", run_cost(self.fx)[1])
        self.assertAlmostEqual(run_json(self.fx)["totals"]["cache_read_share"], 0.6)

    def test_no_input_side_traffic_prints_a_dash_not_a_crash(self):
        self.fx.write("-p1/s1.jsonl", [entry(out=5)])
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0, err)
        self.assertIn("share of input-side tokens: -", out)
        self.assertIsNone(run_json(self.fx)["totals"]["cache_read_share"])


class Scope(Base):
    def setUp(self):
        Base.setUp(self)
        self.fx.write("-p1/sess-a.jsonl", [entry("a1", "r", inp=1)])
        self.fx.write("-p1/sess-a/subagents/agent-1.jsonl", [entry("a2", "r", inp=10, sidechain=True)])
        self.fx.write("-p1/sess-a/subagents/workflows/wf_1/agent-2.jsonl", [entry("a3", "r", inp=100, sidechain=True)])
        self.fx.write("-p1/sess-b.jsonl", [entry("b1", "r", inp=1000)])
        self.fx.write("-p2/sess-c.jsonl", [entry("c1", "r", inp=10000)])

    def inputs(self, *args, **kw):
        return total(run_json(self.fx, *args, **kw), "input")

    def test_a_session_is_its_main_file_plus_its_subagent_files(self):
        self.assertEqual(self.inputs("--session", "sess-a"), 111)
        self.assertEqual(self.inputs("--session", "sess-b"), 1000)
        self.assertEqual(self.inputs("--session", "sess-c"), 10000)

    def test_all_covers_every_project(self):
        self.assertEqual(self.inputs("--all"), 11111)

    def test_a_session_id_that_could_leave_the_root_is_refused_before_anything_is_read(self):
        for bad in ("../x", "a/b", "..", "a b", "x" * 200, ""):
            code, out, err = run_cost(self.fx, "--session", bad)
            self.assertEqual(code, 2, bad)
            self.assertEqual(out, "", bad)
            self.assertIn("--session", err)

    def test_the_default_session_is_used_only_when_no_scope_flag_is_given(self):
        code, out, err = run_cost(self.fx, "--json", "--default-session", "sess-a")
        self.assertEqual(json.loads(out)["scope"], "this session")
        self.assertEqual(total(json.loads(out), "input"), 111)
        self.assertEqual(self.inputs("--default-session", "sess-a", "--session", "sess-b"), 1000)
        self.assertEqual(self.inputs("--default-session", "sess-a", "--all"), 11111)

    def test_an_unsubstituted_or_empty_default_session_falls_back_to_today(self):
        for value in ("${CLAUDE_SESSION_ID}", "", "   ", "../x"):
            code, out, err = run_cost(self.fx, "--json", "--default-session", value)
            self.assertEqual(code, 0, err)
            self.assertTrue(json.loads(out)["scope"].startswith("today"), value)

    def test_scope_flags_exclude_each_other(self):
        code, out, err = run_cost(self.fx, "--today", "--all")
        self.assertEqual(code, 2)

    def test_a_missing_session_reports_no_transcripts_and_exits_zero(self):
        code, out, err = run_cost(self.fx, "--session", "nope")
        self.assertEqual(code, 0)
        self.assertIn("no transcripts in scope", out)


class Time(Base):
    TZ = "America/Chicago"

    def stamped(self, *stamps, **kw):
        lines = [entry("t%d" % i, "r%d" % i, inp=10 ** i, ts=ts) for i, ts in enumerate(stamps)]
        self.fx.write("-p1/s1.jsonl", lines, mtime=epoch(NOW))
        return lines

    def test_today_starts_at_local_midnight(self):
        # 2026-10-02 05:00Z is local midnight in Chicago (UTC-5 in October).
        self.stamped("2026-10-02T04:59:00.000Z", "2026-10-02T05:01:00.000Z", "2026-10-02T14:00:00Z")
        data = run_json(self.fx, "--today", tz=self.TZ)
        self.assertEqual(total(data, "input"), 10 + 100)  # not the 23:59-yesterday entry
        self.assertTrue(data["scope"].startswith("today (since 2026-10-02"))

    def test_days_window_edges(self):
        lines = [
            entry("e0", "r0", inp=1, ts="2026-09-30T04:59:00Z"),  # local 23:59 on 09-29: outside --days 3
            entry("e1", "r1", inp=10, ts="2026-09-30T05:01:00Z"),  # local 00:01 on 09-30: inside --days 3
            entry("e2", "r2", inp=100, ts="2026-10-01T12:00:00Z"),
            entry("e3", "r3", inp=1000, ts="2026-10-02T12:00:00Z"),
        ]
        self.fx.write("-p1/s1.jsonl", lines, mtime=epoch(NOW))
        self.assertEqual(total(run_json(self.fx, "--days", "3", tz=self.TZ), "input"), 10 + 100 + 1000)
        self.assertEqual(total(run_json(self.fx, "--days", "2", tz=self.TZ), "input"), 100 + 1000)
        self.assertEqual(total(run_json(self.fx, "--days", "1", tz=self.TZ), "input"), 1000)

    def test_a_file_changed_inside_the_window_still_filters_by_entry(self):
        self.stamped("2026-08-01T12:00:00Z", "2026-10-02T12:00:00Z")
        self.assertEqual(total(run_json(self.fx, "--today", tz=self.TZ), "input"), 10)

    def test_a_file_untouched_since_before_the_window_is_skipped_by_mtime(self):
        self.fx.write("-p1/old.jsonl", [entry("o", "ro", inp=5, ts="2026-10-02T12:00:00Z")], mtime=epoch("2026-08-01T00:00:00Z"))
        code, out, err = run_cost(self.fx, "--today", tz=self.TZ)
        self.assertEqual(code, 0)
        self.assertIn("no transcripts in scope", out)
        self.assertEqual(total(run_json(self.fx, "--all", tz=self.TZ), "input"), 5)

    def test_malformed_timestamps_are_skipped_in_a_window_and_counted_without_one(self):
        lines = [
            entry("a", "ra", inp=1, ts="not a time"), entry("b", "rb", inp=10, ts=None),
            entry("c", "rc", inp=100, ts="2026-10-02T12:00:00Z"),
        ]
        self.fx.write("-p1/s1.jsonl", lines, mtime=epoch(NOW))
        self.assertEqual(total(run_json(self.fx, "--today", tz=self.TZ), "input"), 100)
        self.assertEqual(total(run_json(self.fx, "--all", tz=self.TZ), "input"), 111)
        self.assertEqual(total(run_json(self.fx, "--session", "s1", tz=self.TZ), "input"), 111)

    def test_the_transcript_timestamp_form_parses_on_this_interpreter(self):
        self.assertEqual(epoch("2026-10-02T12:34:56.789Z"), epoch("2026-10-02T12:34:56Z"))
        self.assertEqual(epoch("2026-10-02T14:34:56+02:00"), epoch("2026-10-02T12:34:56Z"))
        self.assertEqual(epoch("2026-10-02T12:34:56"), epoch("2026-10-02T12:34:56Z"))
        for bad in ("", "x", "2026-13-02T00:00:00Z", "2026-10-02", None, 12, "2026-10-02T25:00:00Z"):
            self.assertIsNone(epoch(bad), bad)

    def test_bad_day_counts_are_refused(self):
        for bad in ("0", "-1", "abc", "1.5", "99999", ""):
            code, out, err = run_cost(self.fx, "--days", bad)
            self.assertEqual(code, 2, bad)

    def test_a_bad_now_is_refused(self):
        code, out, err = run_cost(self.fx, "--today", now="yesterday-ish")
        self.assertEqual(code, 2)


class Project(Base):
    def test_a_dot_directory_encodes_with_a_double_dash(self):
        self.assertEqual(cost.encode_project("/nowhere/.cfg/app"), "-nowhere--cfg-app")
        self.fx.write("-nowhere--cfg-app/s1.jsonl", [entry("a", "ra", inp=7)])
        self.fx.write("-nowhere-cfg-app/s1.jsonl", [entry("b", "rb", inp=900)])
        self.assertEqual(total(run_json(self.fx, "--project", "/nowhere/.cfg/app"), "input"), 7)

    def test_a_long_path_matches_the_truncated_name_with_a_hash(self):
        path = "/x" + "/aaaaaaaaaa" * 21
        encoded = cost.encode_project(path)
        self.assertGreater(len(encoded), 200)
        self.fx.write("%s-zz9/s1.jsonl" % encoded[:200], [entry("a", "ra", inp=7)])
        self.fx.write("%s-zz9/s1.jsonl" % encoded[:199], [entry("b", "rb", inp=900)])
        self.assertEqual(total(run_json(self.fx, "--project", path), "input"), 7)

    def test_a_short_path_does_not_match_by_prefix(self):
        self.fx.write("-nowhere-app-extra/s1.jsonl", [entry("a", "ra", inp=7)])
        code, out, err = run_cost(self.fx, "--project", "/nowhere/app")
        self.assertEqual(code, 0)
        self.assertIn("no transcripts in scope", out)

    def test_a_project_combines_with_a_window(self):
        self.fx.write("-nowhere-app/s1.jsonl",
                      [entry("a", "ra", inp=7, ts="2026-10-02T12:00:00Z"), entry("b", "rb", inp=90, ts="2026-01-01T00:00:00Z")],
                      mtime=epoch(NOW))
        self.assertEqual(total(run_json(self.fx, "--project", "/nowhere/app", "--today"), "input"), 7)
        self.assertEqual(total(run_json(self.fx, "--project", "/nowhere/app"), "input"), 97)

    def test_a_missing_project_prints_no_transcripts_and_exits_zero(self):
        code, out, err = run_cost(self.fx, "--project", "/definitely/not/here")
        self.assertEqual(code, 0)
        self.assertIn("no transcripts in scope", out)


class Robustness(Base):
    def test_odd_lines_and_odd_files_are_skipped_and_the_run_exits_zero(self):
        project = os.path.join(self.fx.projects, CANARY)
        good = entry("g", "rg", inp=3)
        huge = '{"type":"assistant","message":{"id":"big","usage":{"output_tokens":1},"pad":"' + "x" * (5 * 1024 * 1024) + '"}}'
        self.fx.write(CANARY + "/s1.jsonl", [
            "", "   ", '{"type": "assistant", "message": {"id": "cut", "usage": {"input_tokens": 5', "[]", "42", "null",
            entry("nousage", "r", usage=None), json.dumps({"type": "user"}), huge, good,
        ])
        self.fx.write(CANARY + "/bad-utf8.jsonl", [], raw=b'\xff\xfe{"type":"assistant"}\n' + good.encode() + b"\n")
        os.makedirs(os.path.join(project, "dir.jsonl"))
        locked = self.fx.write(CANARY + "/locked.jsonl", [entry("l", "rl", inp=1000)])
        if os.geteuid() != 0:
            os.chmod(locked, 0)
        os.symlink(project, os.path.join(project, "loop"))
        os.symlink(os.path.join(project, "s1.jsonl"), os.path.join(project, "link.jsonl"))
        code, out, err = run_cost(self.fx, "--all")
        self.assertEqual(code, 0, err)
        self.assertNotIn("Traceback", err)
        data = json.loads(run_cost(self.fx, "--all", "--json")[1])
        self.assertEqual(total(data, "input"), 3)  # the one good id, seen in two files, once; the huge one has no input
        self.assertEqual(total(data, "output"), 1)

    def test_a_deeply_nested_line_is_skipped_without_a_traceback_or_a_path(self):
        depth = 5000
        deep = '{"type":"assistant","usage":' + "[" * depth + "]" * depth + "}"
        good = entry("g", "rg", inp=7)
        self.fx.write(CANARY + "/s1.jsonl", [deep, good, deep])
        for args in ((), ("--all",), ("--json", "--all")):
            code, out, err = run_cost(self.fx, *args)
            self.assertEqual(code, 0, (args, err))
            self.assertNotIn("Traceback", err)
            self.assertNotIn("Recursion", err + out)
            self.assertNotIn(PLUGIN_ROOT, err + out)
        data = json.loads(run_cost(self.fx, "--all", "--json")[1])
        self.assertEqual(total(data, "input"), 7)

    def test_nothing_printed_names_the_project_folder_or_a_path(self):
        self.fx.write(CANARY + "/s1.jsonl", [entry("a", "ra", inp=5)])
        self.fx.write(CANARY + "/s1/subagents/agent-1.jsonl", [entry("b", "rb", inp=5, sidechain=True)])
        for args in ((), ("--all",), ("--json",), ("--today",), ("--session", "s1"), ("--project", "/tmp/zz/meter/canary"),
                     ("--project", "/tmp/zz/meter/canary", "--json")):
            code, out, err = run_cost(self.fx, *args)
            self.assertEqual(code, 0, args)
            blob = out + err
            self.assertNotIn(CANARY, blob, args)
            self.assertNotIn("zz-meter", blob, args)
            self.assertNotIn(self.fx.root, blob, args)
            self.assertNotIn("/private", blob, args)

    def test_an_empty_root_says_so_and_exits_zero(self):
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0)
        self.assertIn("no transcripts in scope", out)
        code, out, err = run_cost(self.fx, "--json")
        self.assertEqual(json.loads(out)["rows"], [])

    def test_transcripts_with_no_usage_say_so(self):
        self.fx.write("-p1/s1.jsonl", [json.dumps({"type": "user", "message": {"content": "hi"}})])
        code, out, err = run_cost(self.fx, "--all")
        self.assertEqual(code, 0)
        self.assertIn("no usage entries in scope", out)

    def test_a_missing_root_is_the_same_as_an_empty_one(self):
        env = {"PATH": "/usr/bin:/bin", "HOME": self.fx.root}
        proc = subprocess.run([PY, COST, "--root", os.path.join(self.fx.root, "nope")], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"no transcripts in scope", proc.stdout)


class Output(Base):
    CAVEATS = (
        "Estimate at list prices",
        "Subscription plans bill differently",
        "Transcripts under-record some subagent output",
        'Unknown models are shown as "unpriced", never as $0',
    )

    def test_the_text_carries_every_mandated_caveat_and_stays_compact(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=5, out=5)])
        code, out, err = run_cost(self.fx)
        self.assertEqual(code, 0, err)
        for caveat in self.CAVEATS:
            self.assertIn(caveat, out)
        lines = out.splitlines()
        self.assertLessEqual(len(lines), 40)
        self.assertLessEqual(max(len(l) for l in lines), 100)
        self.assertIn("Anthropic list prices as cached 2026-09-25", out)

    def test_json_has_rows_totals_and_caveats(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=5, out=5), entry("m2", "r2", model="claude-future-9", inp=1)])
        data = run_json(self.fx)
        self.assertEqual({"scope", "price_source", "rows", "totals", "caveats"}, set(data))
        self.assertEqual(len(data["rows"]), 2)
        self.assertEqual(len(data["caveats"]), 5)
        for caveat in self.CAVEATS:
            self.assertTrue(any(caveat in c for c in data["caveats"]), caveat)

    def test_rows_are_ordered_by_tier_then_model_then_thread(self):
        self.fx.write("-p1/s1.jsonl", [
            entry("a", "ra", model="claude-haiku-4-5", inp=1), entry("b", "rb", model="claude-opus-5-5", inp=1),
            entry("c", "rc", model="claude-sonnet-5-5", inp=1),
            entry("d", "rd", model="claude-opus-5-5", inp=1, sidechain=True),
        ])
        rows = run_json(self.fx)["rows"]
        self.assertEqual([(r["tier"], r["who"]) for r in rows],
                         [("opus", "main"), ("opus", "sub"), ("sonnet", "main"), ("haiku", "main")])

    def test_it_runs_under_a_bare_environment_on_the_system_interpreter(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=5)])
        env = {"PATH": "/usr/bin:/bin", "HOME": self.fx.root}
        proc = subprocess.run([PY, COST, "--root", self.fx.root, "--all"], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(b"dojo-meter cost report", proc.stdout)

    def test_the_file_runs_directly_through_its_shebang(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=5)])
        env = {"PATH": "/usr/bin:/bin", "HOME": self.fx.root}
        proc = subprocess.run([COST, "--root", self.fx.root, "--all"], env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_the_config_dir_comes_from_the_environment_when_no_root_is_given(self):
        self.fx.write("-p1/s1.jsonl", [entry(inp=5)])
        env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(), "CLAUDE_CONFIG_DIR": self.fx.root}
        proc = subprocess.run([PY, COST, "--all", "--json"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["rows"][0]["input"], 5)


if __name__ == "__main__":
    unittest.main()
