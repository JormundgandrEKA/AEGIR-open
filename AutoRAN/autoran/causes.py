"""Reasons are rarely one thing. This module reads a stop reason as a short story: what is said, in what order, and how the parts are linked.

A reason is cut into clauses at sentence ends and at connective words. Each link says how neighbouring clauses relate:

    cause    "X due to Y", "X because of Y", "X following Y"      Y is the cause of X
    effect   "X, resulting in Y", "X led to Y", "X so Y"           X is the cause of Y
    context  "despite X, Y", "although X, Y"                       X is background that did not prevent Y
    together "X and Y", "X; Y", "X, combined with Y"               the clauses are listed side by side

Each clause is classified on its own (so a negation in one clause cannot erase a cause in another), and a clause that says what the stop was NOT
about ("not related to any tolerability concern") removes those classes instead of adding them.

What comes out is a list of facets (label, clause, role, order), a list of edges (cause label -> effect label, with the connective that said so), and the
labels the reason itself calls primary. Edges come only from connectives in the text; two labels that merely appear together are reported as co-factors,
never as cause and effect. Standard library only.

Background (checked against published coding schemes): Williams et al. 2015 (PLOS ONE) coded one primary reason per terminated trial and found several
reasons in about 6% of them; Briel et al. 2016 (J Clin Epidemiol) found 28 interrelated reasons for recruitment failure, led by an overestimated number
of eligible patients, and judged most of them preventable at design time. The edges here keep several reasons and their order instead of choosing one.
"""
import re

from . import labeller as L

# order matters: longer phrases first
CAUSE = r"as a result of|as a consequence of|secondary to|resulting from|caused by|on account of|owing to|because of|because|due to|in light of|in view of|based on|following|since|given"
EFFECT = r"resulting in|leading to|which led to|which led|led to|so that|therefore|thus|hence|consequently|causing|which meant|so"
CONTEXT = r"despite|although|even though|even after|though|in spite of|nevertheless|however|but|while"
TOGETHER = r"combined with|together with|along with|as well as|in addition to|and also|and"
SPLIT = re.compile(r"(?<![\w])(" + "|".join([CAUSE, EFFECT, CONTEXT, TOGETHER]) + r")(?![\w])|([.;\n]+)", re.I)
KIND = [("cause", re.compile(r"^(?:" + CAUSE + r")$", re.I)), ("effect", re.compile(r"^(?:" + EFFECT + r")$", re.I)),
        ("context", re.compile(r"^(?:" + CONTEXT + r")$", re.I)), ("together", re.compile(r"^(?:" + TOGETHER + r")$", re.I))]
PRIMARY = re.compile(r"\b(?:primary|main|principal|chief|major|key|sole|only)\b[^.;]{0,20}\b(?:reason|cause|factor|driver)\b|\b(?:mainly|primarily|principally|mostly)\b", re.I)
# a clause that says what the stop was not about
NOT_ABOUT = re.compile(r"\b(?:not|never|no|without|nor|neither|unrelated|n't)\b[^.;]{0,30}\b(?:related|due|attributed|attributable|because|based|driven|linked|caused|result\w*|associated|owing|concern\w*|issues?)\b|"
                       r"\bunrelated to\b|\bnon-?(?:safety|clinical)\b|\bnot (?:for|on account of)\b", re.I)

# the negating words themselves, taken out so the thing that was denied can be named
NEGATORS = re.compile(r"\b(?:not|never|no|without|nor|neither|unrelated to|related to|due to|attributed to|attributable to|because of|based on|driven by|linked to|caused by|associated with)\b", re.I)


def clauses(text):
    """-> [(clause text, link that joined it to the previous clause or None, sentence index)]"""
    out, link, sent, pos = [], None, 0, 0
    t = text or ""
    for m in SPLIT.finditer(t):
        seg = t[pos:m.start()].strip(" ,:-")
        if seg:
            out.append((seg, link, sent))
        pos = m.end()
        if m.group(2):
            sent += 1
            link = None
        else:
            word = m.group(1).lower()
            link = next((k for k, rx in KIND if rx.match(word)), "together"), word
            # a leading connective ("Despite X, Y") links forward: the first clause is the context
    seg = t[pos:].strip(" ,:-")
    if seg:
        out.append((seg, link, sent))
    split = []
    for seg, lk, s in out:
        if lk and lk[0] == "context" and "," in seg:                      # "Despite X, Y": X is the context, Y what happened anyway
            a, b = seg.split(",", 1)
            split += [(a.strip(), lk, s), (b.strip(), ("outcome", ","), s)]
        else:
            split.append((seg, lk, s))
    return split


def analyse(text):
    """The story of one stop reason. See the module description."""
    cl = clauses(text)
    facets, per = [], []
    for i, (seg, link, sent) in enumerate(cl):
        negated = bool(NOT_ABOUT.search(seg))
        if negated:
            # what the clause says the stop was NOT about: read it again with the negating words taken out
            kept, said_not = [], set(L.classify_rules(NEGATORS.sub(" ", seg))[0]) | set(L.classify_rules(seg)[0])
        else:
            kept, said_not = L.classify_rules(seg)[0], set()
        per.append((seg, link, sent, kept, said_not))
        for c in kept:
            facets.append({"label": c, "clause": seg, "order": i, "sentence": sent, "link_before": link[1] if link else None,
                           "link_kind": link[0] if link else None, "primary_cue": bool(PRIMARY.search(seg))})
    # roles from the link that joins each clause to its neighbour
    roles = {}
    for i, (seg, link, sent, kept, _) in enumerate(per):
        nxt = per[i + 1][1] if i + 1 < len(per) else None
        role = "co_factor"
        if link and link[0] == "cause":
            role = "cause"                  # "... due to THIS"
        elif nxt and nxt[0] == "cause" and per[i + 1][2] == sent:
            role = "effect"                 # "THIS due to ..."
        elif nxt and nxt[0] == "effect" and per[i + 1][2] == sent:
            role = "cause"                  # "THIS, resulting in ..."
        elif link and link[0] == "effect":
            role = "effect"
        elif nxt and nxt[0] == "context" and per[i + 1][2] == sent:
            role = "context"                # "Despite THIS, ..." / "THIS, but ..."
        elif link and link[0] in ("context", "outcome"):
            role = "outcome_despite"
        roles[i] = role
    edges = []
    for i, (seg, link, sent, kept, _) in enumerate(per):
        if not link or link[0] not in ("cause", "effect") or i == 0:
            continue
        a, b = per[i - 1][3], kept
        for x in a:
            for y in b:
                if x == y:
                    continue
                # "X due to Y": Y -> X ; "X resulting in Y": X -> Y
                edges.append({"cause": y, "effect": x, "via": link[1]} if link[0] == "cause" else {"cause": x, "effect": y, "via": link[1]})
    for f in facets:
        f["role"] = roles[f["order"]]
    labels = []
    for f in facets:
        if f["label"] not in labels:
            labels.append(f["label"])
    stated = [f["label"] for f in facets if f["primary_cue"]]
    causes = {e["cause"] for e in edges}
    effects = {e["effect"] for e in edges}
    roots = [x for x in labels if x in causes and x not in effects]
    primary = list(dict.fromkeys(stated)) or roots or labels[:1]
    return {"clauses": [{"text": s, "link": (l[1] if l else None), "labels": k, "not_about": sorted(n)} for s, l, _, k, n in per],
            "facets": facets, "edges": [dict(t) for t in {tuple(sorted(e.items())) for e in edges}], "labels": labels, "primary": primary,
            "not_about": sorted({c for _, _, _, _, n in per for c in n})}
