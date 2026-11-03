"""Gold review: one case at a time, a verdict of yes / no / other, stored in a CSV.

A case is a stop reason whose label the current rules change compared with the last label run (the "before" and "after" calls), or an unchanged
call used as a control. A sample is 100 cases by default: 70 the labeller is least sure about and 30 it is fairly sure about. Which is which is stored
but never shown on the card, so the control group stays honest.

Verdicts are about the AFTER call:
    yes   the new classification is right
    no    the new classification is wrong
    other not wrong, but classified poorly (neither a good change nor a bad one)

Everything is append-only: data/labels/gold/gold_sample_<stamp>.json (the cases) and gold_verdicts.csv (one row per verdict, one per undo).
Texts that fall in the frozen Open Targets test part are never drawn, so these verdicts can later be used for training.
"""
import csv
import json
import random
import re
from collections import Counter

from . import __version__, causes, labeller as L, taxonomy
from .core import Paths, iso_now, iter_jsonl, read_gz_json, stable_hash, utc_stamp
from .opentargets import normalise_reason

VERDICTS = ("yes", "no", "other")
COLUMNS = ["reviewed_at", "sample", "item", "nct_id", "verdict", "note", "why_stopped", "before", "after", "rules_added", "rules_removed",
           "sublabels", "land_mine", "stratum", "bucket", "concern", "autoran_version", "blind", "own", "own_matches_after"]
BLIND_SHARE = 0.5          # about half the cards hide the machine's answer until the reviewer has written their own (design principle A11)
ALL_CLASSES = [c for cs in taxonomy.SUPER.values() for c in cs]
_PENDING = {}              # item -> the classes the reviewer locked in before seeing the machine's answer
IE = "Insufficient_Enrollment"


def gold_dir(paths):
    d = paths.data / "labels" / "gold"
    d.mkdir(parents=True, exist_ok=True)
    return d


def verdict_file(paths):
    return gold_dir(paths) / "gold_verdicts.csv"


def latest_sample(paths):
    fs = sorted(gold_dir(paths).glob("gold_sample_*.json"))
    return (json.loads(fs[-1].read_text(encoding="utf-8")), fs[-1]) if fs else (None, None)


def read_verdicts(paths):
    f = verdict_file(paths)
    if not f.is_file():
        return []
    with open(f, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def current_verdicts(paths, sample_id=None):
    """{item: row} with undone verdicts removed; the last row for an item wins."""
    out = {}
    for r in read_verdicts(paths):
        if sample_id and r["sample"] != sample_id:
            continue
        out.pop(r["item"], None)                            # file order is the order of judging, so a re-judged case moves to the end
        if r["verdict"] != "undo":
            out[r["item"]] = r
    return out


def is_blind(item_id):
    """Fixed per case, so a reload cannot turn a blind card into an open one."""
    return stable_hash(item_id, "gold-blind-mode") < BLIND_SHARE


def _migrate(f):
    """Older files lack the newer columns; rewrite once with the full header so appended rows stay aligned."""
    with open(f, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
        head = rows and list(rows[0].keys())
    if not rows:
        return
    if head != COLUMNS:
        with open(f, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore", restval="")
            w.writeheader()
            w.writerows(rows)


def _append(paths, row):
    f = verdict_file(paths)
    new = not f.is_file()
    if not new:
        _migrate(f)
    with open(f, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore", restval="")
        if new:
            w.writeheader()
        w.writerow(row)


def _full_why(root, row):
    """The index keeps 240 characters; read the whole text from the stored page when the index text may be cut."""
    try:
        study = read_gz_json(root / row[20])["studies"][row[21]]
        return study["protocolSection"]["statusModule"].get("whyStopped") or row[16]
    except (OSError, KeyError, IndexError, ValueError, TypeError):
        return row[16]


def _in_frozen_test(text, cfg):
    sp = cfg["opentargets"]["split"]
    return stable_hash(normalise_reason(text), sp["seed"]) < sp["test"]


def candidates(ctx, cfg):
    """Every stopped trial with its old call (last label run) and its new call (current code), tree fields included."""
    from .labelstage import Labeller, load_labeller, load_labels, load_voter
    from .opentargets import load
    paths = Paths(ctx.root).ensure()
    got = load_labeller(paths)
    f = paths.latest("index_*.jsonl")
    if not got or not f:
        raise FileNotFoundError("nothing to review yet: run the pipeline (fetch, label, metrics) first")
    manifest, mfile = got
    lab = Labeller(manifest, load(paths), load_voter(paths))
    old = load_labels(paths)
    seen, out = set(), []
    for row in iter_jsonl(f):
        nct, status = row[0], row[2]
        why = row[16]
        if status not in ("TERMINATED", "WITHDRAWN", "SUSPENDED") or not (why or "").strip() or nct not in old:
            continue
        if len(why) >= 240:
            why = _full_why(ctx.root, row)
        key = normalise_reason(why)
        if key in seen or _in_frozen_test(why, cfg):
            continue
        seen.add(key)
        o = old[nct]
        n = lab.label(why)
        tree = taxonomy.classify_tree(why, status, row[19])
        out.append({"nct_id": nct, "why_stopped": why, "status": status, "before": sorted(o["stop_classes"]), "after": sorted(n["stop_classes"]),
                    "rules_before": sorted(o["rule_ids"]), "rules_after": sorted(n["rule_ids"]), "source_before": o["label_source"], "source_after": n["label_source"],
                    "conf": n["confidence"], "disagree": bool(n["disagree"]), "tree": tree, "rule_prec": lab.rule_prec,
                    "votes": n.get("votes"), "agree": n.get("agree"), "story": (lambda a: {"primary": a["primary"], "edges": a["edges"], "not_about": a["not_about"]})(causes.analyse(why))})
    return out, mfile.name


def concern(c):
    """How worried the labeller is about a changed call. Higher means look first. Returns (score, reasons)."""
    s, why = 0.0, []
    b, a = set(c["before"]), set(c["after"])
    if (IE in b) != (IE in a):
        s += 3; why.append("recruitment call flipped")
    if c["tree"].get("land_mine") and c["tree"]["land_mine"] != "ethical_concern":
        s += 2; why.append("land-mine flag")
    if c["disagree"]:
        s += 2; why.append("rules and model disagree")
    ch = len(b ^ a)
    s += min(ch, 3) * 0.7
    if not b and a:
        s += 1; why.append("had no class before")
    if b and not a:
        s += 1.5; why.append("lost every class")
    prec = [c["rule_prec"].get(r) for r in c["rules_after"] if c["rule_prec"].get(r) is not None]
    if prec and max(prec) < 0.6:
        s += 1; why.append("only weak rules fired")
    if any(r not in c["rule_prec"] for r in c["rules_after"]):
        s += 0.5; why.append("new rule, not yet measured")
    if c["source_after"] == "nb":
        s += 1; why.append("statistical model only")
    if len(c["why_stopped"].split()) > 40:
        s += 0.5
    return round(s, 2), why


# the concerning cases are drawn from kinds of change, so one kind (for example "lost every class") cannot fill the whole sample
QUOTA = {"recruitment_gained": 12, "recruitment_lost": 12, "lost_every_class": 8, "land_mine": 8, "rules_vs_model": 10, "new_rule": 10, "other_change": 10}


def bucket(c):
    b, a = set(c["before"]), set(c["after"])
    if IE in a and IE not in b:
        return "recruitment_gained"
    if IE in b and IE not in a:
        return "recruitment_lost"
    if b and not a:
        return "lost_every_class"
    if c["tree"].get("land_mine") in ("harm_to_participants", "misconduct_or_noncompliance", "ordered_by_authority"):
        return "land_mine"
    if c["disagree"]:
        return "rules_vs_model"
    if any(r not in c["rule_prec"] for r in c["rules_after"]):
        return "new_rule"
    return "other_change"


def confident(c):
    """An unchanged call the labeller trusts: same classes before and after, a rule or exact match, no disagreement, a high-precision rule."""
    if c["before"] != c["after"] or c["disagree"] or not c["after"] or c["source_after"] not in ("exact", "rules"):
        return False
    if c["source_after"] == "exact":
        return True
    prec = [c["rule_prec"].get(r) for r in c["rules_after"] if c["rule_prec"].get(r) is not None]
    return bool(prec) and max(prec) >= 0.9 and c["conf"] >= 0.9


def draw(ctx, cfg, n_concerning=70, n_control=30, seed=28):
    paths = Paths(ctx.root).ensure()
    cands, mname = candidates(ctx, cfg)
    done = {r["nct_id"] for r in read_verdicts(paths) if r["verdict"] in VERDICTS}
    rnd = random.Random(seed)
    pool = [c for c in cands if c["nct_id"] not in done]
    changed = [c for c in pool if c["before"] != c["after"]]
    for c in changed:
        c["concern"], c["concern_why"] = concern(c)
    changed.sort(key=lambda c: (-c["concern"], rnd.random()))
    for c in changed:
        c["bucket"] = bucket(c)
    scale = n_concerning / sum(QUOTA.values())
    top = []
    for k, q in QUOTA.items():
        top += [c for c in changed if c["bucket"] == k][:max(1, round(q * scale))]
    top = top[:n_concerning]
    taken = {c["nct_id"] for c in top}
    top += [c for c in changed if c["nct_id"] not in taken][:max(0, n_concerning - len(top))]      # a short bucket is topped up by the next most worrying changes
    taken = {c["nct_id"] for c in top}
    # fill from unchanged-but-uncertain cases if too few calls changed
    if len(top) < n_concerning:
        rest = [c for c in pool if c["nct_id"] not in taken and c["before"] == c["after"] and not confident(c) and (c["after"] or c["disagree"])]
        for c in rest:
            c["concern"], c["concern_why"] = concern(c)
            c["bucket"] = "unchanged_but_doubtful"
        rest.sort(key=lambda c: (-c["concern"], rnd.random()))
        top += rest[:n_concerning - len(top)]
        taken = {c["nct_id"] for c in top}
    conf = [c for c in pool if c["nct_id"] not in taken and confident(c)]
    ie = [c for c in conf if IE in c["after"]]
    other = [c for c in conf if IE not in c["after"]]
    rnd.shuffle(ie); rnd.shuffle(other)
    ctrl = ie[:n_control // 2] + other[:n_control - min(len(ie), n_control // 2)]
    ctrl = ctrl[:n_control]
    for c in ctrl:
        c["concern"], c["concern_why"], c["bucket"] = 0.0, ["controlled: unchanged and trusted"], "control"
    items = [dict(c, stratum="concern") for c in top] + [dict(c, stratum="control") for c in ctrl]
    rnd.shuffle(items)
    sid = utc_stamp()
    keep = ("nct_id", "why_stopped", "status", "before", "after", "rules_before", "rules_after", "source_before", "source_after", "conf", "stratum", "bucket", "concern", "concern_why", "votes", "agree", "story")
    sample = {"id": sid, "created": iso_now(), "seed": seed, "labeller_file": mname, "autoran_version": __version__,
              "n": len(items), "n_concerning": len(top), "n_control": len(ctrl), "candidates": len(cands), "changed": len(changed),
              "items": [dict({k: c[k] for k in keep}, item=f"{sid}-{i + 1:03d}", tree={k: c["tree"].get(k) for k in ("supers", "sublabels", "stage", "land_mine", "withdrawn_kind")})
                        for i, c in enumerate(items)]}
    _PENDING.clear()
    f = gold_dir(paths) / f"gold_sample_{sid}.json"
    f.write_text(json.dumps(sample, ensure_ascii=True), encoding="utf-8")
    return {"file": str(f), "n": len(items), "concerning": len(top), "control": len(ctrl), "candidates": len(cands), "changed": len(changed)}


def blind_card(item):
    """A blind card: the registry text only. No before, after, votes, rules or finer labels."""
    return {"item": item["item"], "nct_id": item["nct_id"], "why_stopped": item["why_stopped"], "status": item["status"], "blind": True, "classes": ALL_CLASSES}


def reveal(paths, item_id, own):
    """The reviewer has written their own classes; lock them, then show the full card."""
    sample, _ = latest_sample(paths)
    it = next((i for i in (sample or {}).get("items", []) if i["item"] == item_id), None)
    if it is None:
        raise ValueError("unknown case")
    own = sorted(set(own or []))
    bad = [c for c in own if c not in ALL_CLASSES]
    if bad:
        raise ValueError("unknown class: " + bad[0])
    _PENDING[item_id] = own
    c = card(it)
    c["blind"], c["own"] = True, own
    return c


def card(item):
    """What the reviewer sees: no stratum, no concern score."""
    b, a = set(item["before"]), set(item["after"])
    return {"item": item["item"], "nct_id": item["nct_id"], "why_stopped": item["why_stopped"], "status": item["status"],
            "before": item["before"], "after": item["after"], "added": sorted(a - b), "removed": sorted(b - a),
            "rules_added": sorted(set(item["rules_after"]) - set(item["rules_before"])), "rules_removed": sorted(set(item["rules_before"]) - set(item["rules_after"])),
            "votes": item.get("votes"), "agree": item.get("agree"), "story": item.get("story"),
            "rules_after": item["rules_after"], "source_before": item["source_before"], "source_after": item["source_after"], "tree": item["tree"]}


def state(paths):
    sample, f = latest_sample(paths)
    base = {"file": str(verdict_file(paths)), "sample": None, "next": None, "counts": {v: 0 for v in VERDICTS}, "done": 0, "n": 0}
    if not sample:
        return base
    cur = current_verdicts(paths, sample["id"])
    counts = Counter(r["verdict"] for r in cur.values())
    left = [i for i in sample["items"] if i["item"] not in cur]
    base.update(sample={"id": sample["id"], "created": sample["created"], "n": sample["n"], "n_concerning": sample["n_concerning"], "n_control": sample["n_control"],
                        "changed": sample["changed"], "candidates": sample["candidates"]},
                next=((blind_card(left[0]) if is_blind(left[0]["item"]) and left[0]["item"] not in _PENDING else card(left[0])) if left else None), counts={v: counts.get(v, 0) for v in VERDICTS}, done=len(cur), n=sample["n"],
                last=(list(cur.values())[-1]["item"] if cur else None))
    if base["next"] and base["next"]["item"] in _PENDING:
        base["next"]["blind"], base["next"]["own"] = True, _PENDING[base["next"]["item"]]
    if not left:
        base["summary"] = summary(sample, cur)
    return base


def record(paths, item_id, verdict, note=""):
    if verdict not in VERDICTS:
        raise ValueError("verdict must be yes, no or other")
    sample, _ = latest_sample(paths)
    if not sample:
        raise ValueError("no sample drawn yet")
    it = next((i for i in sample["items"] if i["item"] == item_id), None)
    if it is None:
        raise ValueError("unknown case")
    c = card(it)
    blind = is_blind(item_id)
    if blind and item_id not in _PENDING:
        raise ValueError("this case is blind: write your own classes first")
    own = _PENDING.pop(item_id, None)
    _append(paths, {"blind": int(blind), "own": "|".join(own) if own is not None else "", "own_matches_after": (int(set(own) == set(it["after"])) if own is not None else ""),
                    "reviewed_at": iso_now(), "sample": sample["id"], "item": item_id, "nct_id": it["nct_id"], "verdict": verdict, "note": (note or "")[:500],
                    "why_stopped": it["why_stopped"], "before": "|".join(it["before"]), "after": "|".join(it["after"]), "rules_added": "|".join(c["rules_added"]),
                    "rules_removed": "|".join(c["rules_removed"]), "sublabels": "|".join(it["tree"].get("sublabels") or []), "land_mine": it["tree"].get("land_mine") or "",
                    "stratum": it["stratum"], "bucket": it.get("bucket", ""), "concern": it["concern"], "autoran_version": __version__})
    return state(paths)


def undo(paths):
    sample, _ = latest_sample(paths)
    if not sample:
        raise ValueError("no sample drawn yet")
    cur = current_verdicts(paths, sample["id"])
    if not cur:
        return state(paths)
    last = list(cur.values())[-1]                            # the file is append-only, so the last row is the latest verdict (timestamps only have second resolution)
    _append(paths, {"reviewed_at": iso_now(), "sample": sample["id"], "item": last["item"], "nct_id": last["nct_id"], "verdict": "undo", "note": "", "autoran_version": __version__})
    return state(paths)


def summary(sample, cur):
    """Agreement with the AFTER call, by group. Shown only when every case is done."""
    out = {}
    for g in ("concern", "control"):
        rows = [r for r in cur.values() if r["stratum"] == g]
        c = Counter(r["verdict"] for r in rows)
        n = len(rows)
        out[g] = {"n": n, "yes": c.get("yes", 0), "no": c.get("no", 0), "other": c.get("other", 0),
                  "yes_rate": round(c.get("yes", 0) / n, 3) if n else None, "no_rate": round(c.get("no", 0) / n, 3) if n else None}
    # anchoring check: does seeing the machine's answer first change how often the reviewer agrees with it?
    for k, flag in (("blind", "1"), ("open", "0")):
        rows = [r for r in cur.values() if r.get("blind", "") == flag] if any(r.get("blind", "") for r in cur.values()) else []
        n = len(rows)
        out[k] = {"n": n, "yes_rate": round(sum(r["verdict"] == "yes" for r in rows) / n, 3) if n else None}
    own = [r for r in cur.values() if r.get("own_matches_after", "") != ""]
    out["own_answer_matches_machine"] = {"n": len(own), "rate": round(sum(r["own_matches_after"] == "1" for r in own) / len(own), 3) if own else None}
    return out
