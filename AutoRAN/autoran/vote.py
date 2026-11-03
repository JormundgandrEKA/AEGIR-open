"""Several independent checks for every label, combined by a vote.

A stop reason is read six ways. For each class every reader says how strongly it sees that class (0 to 1):

    rules      the ordered keyword rules on the whole text                         (labeller.classify_rules)
    clauses    the same rules clause by clause, with negations scoped to a clause    (causes.analyse)
    nb         the multi-label naive Bayes model                                     (labeller.NB)
    lr_words   logistic regression on word and word-pair features, one class at a time
    lr_chars   logistic regression on character 3 to 5-grams (robust to typos, "inclusion" for enrolment, other languages)
    lexicon    cue words taken from published coding schemes (Williams 2015, Briel 2016, Kasenda 2014), not from the curated labels

A small stacker per class (logistic regression on the six scores) turns them into one probability. The stacker is fitted on out-of-fold scores, so it
learns how far to trust each reader for each class without seeing a reader's score on text that reader was trained on. A class is included when its
probability passes a threshold chosen on the dev part. The result keeps the vote per reader, so a reviewer can see which checks agreed, and flags
contested cases (probability near the threshold) for human review.

Numpy only. No file outside the curated training rows is read.
"""
import json
import re
import zlib

import numpy as np

from . import causes, labeller as L
from .opentargets import normalise_reason

DETECTORS = ["rules", "clauses", "nb", "lr_words", "lr_chars", "lexicon"]
D_WORDS, D_CHARS = 1 << 14, 1 << 15

# cue words from the literature, written independently of the curated rows
LEXICON = {
    "Insufficient_Enrollment": r"\b(?:poor|slow|low|insufficient|inadequate|lack of|failure to|unable to|difficult\w*)\b[^.;]{0,30}\b(?:accru\w*|recruit\w*|enrol\w*|enroll\w*|inclusion|participants?|patients?)\b|\bprevalence\b[^.;]{0,20}\b(?:lower|overestimat\w+)|\bnot enough (?:patients|subjects|participants)\b|\bunwilling\b|\bconsent\b[^.;]{0,20}\b(?:declin\w+|refus\w+)",
    "Business_Administrative": r"\bbusiness\b|\bstrateg\w+|\bportfolio\b|\bprioriti\w+|\bsponsor\b[^.;]{0,15}\b(?:decision|decided)|\bfunding\b|\bfunds?\b|\bbudget\b|\bcommercial\b|\bcorporate\b|\bmerger\b|\badministrative\b",
    "Logistics_Resources": r"\b(?:drug|product|vaccine|study medication) supply\b|\bshortage\b|\bmanufactur\w+|\bsupply (?:issue|problem|chain)|\bstaff\w* (?:shortage|issue)|\bequipment\b|\blogistic\w+",
    "Study_Staff_Moved": r"\b(?:investigator|pi|physician|coordinator|staff)\b[^.;]{0,40}\b(?:left|moved|retired|resigned|relocat\w+|departed|unavailable|deceased)",
    "Another_Study": r"\b(?:other|another|competing|similar|parallel|identical)\b[^.;]{0,15}\b(?:trial|study|studies|trials)\b|\bstandard of care\b|\bpublished\b|\bnew (?:data|evidence|guidelines?)\b|\bsuperseded\b|\bexternal information\b",
    "Negative": r"\bfutil\w+|\black of (?:efficacy|effect|benefit|activity)\b|\bno (?:significant )?(?:benefit|difference|efficacy)\b|\bnot (?:effective|efficacious)\b|\bdid not (?:meet|show|demonstrate) (?:the )?(?:primary )?(?:endpoint|efficacy)|\brisk[- /]*benefit|\bbenefit[- /]*risk",
    "Safety_Sideeffects": r"\btoxicit\w+|\badverse (?:event|reaction)s?\b|\bsafety (?:signal|concern|issue)s?\b|\bdeaths?\b|\bserious adverse\b|\bside effects?\b|\bhepatotox\w+|\bunexpected (?:\w+ ){0,2}(?:events?|toxicit\w+)",
    "Regulatory": r"\bclinical hold\b|\bfda\b|\bregulat\w+|\bhealth authorit\w+|\bethics committee\b|\birb\b|\bmarketing authori[sz]ation\b|\brecall\w*",
    "Study_Design": r"\bprotocol (?:amend\w+|change\w*|revis\w+|redesign\w*)|\bdesign (?:flaw|issue|problem|change)\w*|\bredesign\w*|\btoo (?:complex|burdensome|restrictive)\b|\beligibility criteria\b[^.;]{0,20}\b(?:too|strict|restrictive|narrow)|\binclusion criteria\b[^.;]{0,20}\b(?:too|strict|restrictive|narrow)",
    "Covid19": r"\bcovid\w*|\bsars-?cov\w*|\bpandemic\b|\bcoronavirus\b",
    "Interim_Analysis": r"\b(?:pending|awaiting|await\w*)\b[^.;]{0,30}\b(?:analysis|review|results|data)\b|\bunder review\b|\bon hold\b[^.;]{0,20}\b(?:analysis|review)",
    "Endpoint_Met": r"\bendpoint\w*\b[^.;]{0,15}\b(?:met|achieved|reached)\b|\bobjectives? (?:were |was )?(?:met|achieved)\b|\bstopping (?:rule|criteri\w+) (?:was |were )?met\b",
    "Insufficient_Data": r"\b(?:insufficient|inadequate|lack of|poor) (?:\w+ )?(?:data|evidence|follow-?up)\b|\bdata (?:quality|integrity) (?:issue|problem)s?\b",
    "Ethical_Reason": r"\bethic\w+|\bunethical\b|\bequipoise\b|\bmisconduct\b|\bconsent (?:violation|problem)s?\b",
    "Invalid_Reason": r"\bnever (?:started|opened|initiated|activated)\b|\bnot (?:been )?(?:started|initiated|opened)\b|\bcancell?ed (?:before|prior to)\b|\bduplicate\b|\bentered in error\b",
    "No_Context": r"^\W*(?:see|refer)\b[^.;]{0,40}(?:description|above|below|protocol)",
    "Success": r"\bsuccessful(?:ly)?\b|\bgoals? (?:were |was )?(?:met|achieved)\b",
}
_LEX = {c: re.compile(p, re.I) for c, p in LEXICON.items()}


# ---------------------------------------------------------------- sparse features and logistic regression (numpy only)
def _h(tok, dim):
    return zlib.crc32(tok.encode("utf-8")) % dim


def feats_words(text):
    toks = re.findall(r"[a-z0-9]+", normalise_reason(L.fix_typos(normalise_reason(text))))
    f = {}
    for t in toks:
        f[_h("w:" + t, D_WORDS)] = 1.0
    for a, b in zip(toks, toks[1:]):
        f[_h("b:" + a + " " + b, D_WORDS)] = 1.0
    return f


def feats_chars(text):
    t = " " + normalise_reason(L.fix_typos(normalise_reason(text))) + " "
    f = {}
    for n in (3, 4, 5):
        for i in range(len(t) - n + 1):
            f[_h(f"c{n}:" + t[i:i + n], D_CHARS)] = 1.0
    return f


class Csr:
    def __init__(self, rows, dim):
        self.dim = dim
        idx, val, ptr = [], [], [0]
        for f in rows:
            n = np.sqrt(len(f)) or 1.0                       # L2-normalise each row
            for k, v in f.items():
                idx.append(k); val.append(v / n)
            ptr.append(len(idx))
        self.idx, self.val, self.ptr = np.array(idx, dtype=np.int64), np.array(val, dtype=np.float32), np.array(ptr, dtype=np.int64)
        self.n = len(rows)
        self.row = np.repeat(np.arange(self.n), np.diff(self.ptr))

    def dot(self, w, b):
        z = np.bincount(self.row, weights=self.val * w[self.idx], minlength=self.n)
        return z + b

    def grad(self, err):
        return np.bincount(self.idx, weights=self.val * err[self.row], minlength=self.dim)


def fit_lr(X, y, l2=1e-3, iters=120, lr=0.5):
    """One-vs-rest logistic regression by Adam on a Csr matrix. Positives are up-weighted up to 8x so rare classes are not ignored."""
    y = np.asarray(y, dtype=np.float64)
    n1 = y.sum()
    if n1 == 0 or n1 == len(y):
        return np.zeros(X.dim), -8.0 if n1 == 0 else 8.0
    pw = min(8.0, (len(y) - n1) / n1)
    sw = np.where(y > 0, pw, 1.0)
    w, b = np.zeros(X.dim), 0.0
    m = np.zeros(X.dim); v = np.zeros(X.dim); mb = vb = 0.0
    for t in range(1, iters + 1):
        p = 1 / (1 + np.exp(-np.clip(X.dot(w, b), -30, 30)))
        err = (p - y) * sw / len(y)
        g = X.grad(err) + l2 * w
        gb = err.sum()
        m = 0.9 * m + 0.1 * g; v = 0.999 * v + 0.001 * g * g
        mb = 0.9 * mb + 0.1 * gb; vb = 0.999 * vb + 0.001 * gb * gb
        w -= lr * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
        b -= lr * (mb / (1 - 0.9 ** t)) / (np.sqrt(vb / (1 - 0.999 ** t)) + 1e-8)
    return w, b


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


class Voter:
    def __init__(self):
        self.classes = list(L.CLASSES)
        self.nb = None
        self.lrw, self.lrc, self.stack, self.thresh = {}, {}, {}, {}
        self.min_agree = 2                      # a class needs the stacked probability AND at least this many readers (of six) that see it on their own
        self.meta = {}

    # ------------------------------------------------------------ readers
    def _fixed(self, text):
        """The three readers that need no training: {detector: {class: score}}"""
        rules = set(L.classify_rules(text)[0])
        clause = set(causes.analyse(text)["labels"])
        lex = {c for c, rx in _LEX.items() if rx.search(normalise_reason(text))}
        z = lambda s: {c: float(c in s) for c in self.classes}
        return {"rules": z(rules), "clauses": z(clause), "lexicon": z(lex)}

    def _nb_scores(self, nb, text):
        sc = nb.score(text)
        return {c: float(sigmoid((sc[c] - nb.thresh.get(c, 0.0)) / 2.0)) for c in self.classes}

    def _lr_scores(self, csr_w, csr_c, models=None):
        out_w = {c: sigmoid(csr_w.dot(*self.lrw[c])) for c in self.classes}
        out_c = {c: sigmoid(csr_c.dot(*self.lrc[c])) for c in self.classes}
        return out_w, out_c

    # ------------------------------------------------------------ training
    def fit(self, train, dev=None, folds=5, seed=28, tune=True):
        """train, dev: rows {text, labels}. Fits the readers on `train`, the stacker on out-of-fold scores, thresholds on `dev` (if given)."""
        cls = self.classes
        Y = {c: np.array([c in r["labels"] for r in train], dtype=float) for c in cls}
        fw = [feats_words(r["text"]) for r in train]
        fc = [feats_chars(r["text"]) for r in train]
        fixed = [self._fixed(r["text"]) for r in train]
        rng = np.random.RandomState(seed)
        fold = rng.randint(0, folds, len(train))
        oof = {d: {c: np.zeros(len(train)) for c in cls} for d in DETECTORS}
        for i, fx in enumerate(fixed):
            for d in ("rules", "clauses", "lexicon"):
                for c in cls:
                    oof[d][c][i] = fx[d][c]
        for k in range(folds):
            tr = [i for i in range(len(train)) if fold[i] != k]
            te = [i for i in range(len(train)) if fold[i] == k]
            nb = L.NB().train([train[i] for i in tr], cls)
            for i in te:
                s = self._nb_scores(nb, train[i]["text"])
                for c in cls:
                    oof["nb"][c][i] = s[c]
            Xw, Tw = Csr([fw[i] for i in tr], D_WORDS), Csr([fw[i] for i in te], D_WORDS)
            Zc, Tc = Csr([fc[i] for i in tr], D_CHARS), Csr([fc[i] for i in te], D_CHARS)
            for c in cls:
                y = Y[c][tr]
                ww, bw = fit_lr(Xw, y)
                oof["lr_words"][c][te] = sigmoid(Tw.dot(ww, bw))
                wc, bc = fit_lr(Zc, y)
                oof["lr_chars"][c][te] = sigmoid(Tc.dot(wc, bc))
        # readers on all of train
        self.nb = L.NB().train(train, cls)
        self.nb.tune(dev or train, cls)
        Xw, Zc = Csr(fw, D_WORDS), Csr(fc, D_CHARS)
        for c in cls:
            self.lrw[c] = fit_lr(Xw, Y[c]); self.lrc[c] = fit_lr(Zc, Y[c])
        # stacker per class on the out-of-fold scores
        for c in cls:
            F = np.stack([oof[d][c] for d in DETECTORS], axis=1)
            self.stack[c] = self._fit_stack(F, Y[c])
        # thresholds on dev
        self.thresh = {c: 0.5 for c in cls}
        if dev and tune:
            P = self.predict_proba_rows(dev)
            for c in cls:
                y = np.array([c in r["labels"] for r in dev], dtype=float)
                if y.sum() < 10:
                    continue                                          # too few cases to tune on: keep 0.5
                best, bt = -1, 0.5
                for t in np.arange(0.2, 0.81, 0.05):
                    p = P[c] >= t
                    tp, fp, fn = (p & (y > 0)).sum(), (p & (y == 0)).sum(), ((~p) & (y > 0)).sum()
                    f1 = 2 * tp / max(1, 2 * tp + fp + fn)
                    if f1 > best:
                        best, bt = f1, float(t)
                self.thresh[c] = bt
        return self

    @staticmethod
    def _fit_stack(F, y, l2=1e-2, iters=300, lr=0.2):
        n, d = F.shape
        if y.sum() == 0:
            return np.zeros(d), -8.0
        w = np.ones(d) * 0.5
        b = -0.5 * d / 2
        pw = min(4.0, (n - y.sum()) / max(1, y.sum()))
        sw = np.where(y > 0, pw, 1.0)
        for _ in range(iters):
            p = sigmoid(F @ w + b)
            err = (p - y) * sw / n
            w -= lr * (F.T @ err + l2 * w) * 10
            b -= lr * err.sum() * 10
        return w, b

    # ------------------------------------------------------------ prediction
    def readers(self, texts):
        """{detector: {class: np.array over texts}}"""
        fixed = [self._fixed(t) for t in texts]
        out = {d: {c: np.zeros(len(texts)) for c in self.classes} for d in DETECTORS}
        for i, fx in enumerate(fixed):
            for d in ("rules", "clauses", "lexicon"):
                for c in self.classes:
                    out[d][c][i] = fx[d][c]
            nbs = self._nb_scores(self.nb, texts[i])
            for c in self.classes:
                out["nb"][c][i] = nbs[c]
        Xw, Zc = Csr([feats_words(t) for t in texts], D_WORDS), Csr([feats_chars(t) for t in texts], D_CHARS)
        for c in self.classes:
            out["lr_words"][c] = sigmoid(Xw.dot(*self.lrw[c]))
            out["lr_chars"][c] = sigmoid(Zc.dot(*self.lrc[c]))
        return out

    def predict_proba_rows(self, rows):
        r = self.readers([x["text"] for x in rows])
        return {c: sigmoid(np.stack([r[d][c] for d in DETECTORS], axis=1) @ self.stack[c][0] + self.stack[c][1]) for c in self.classes}

    def predict(self, texts, return_votes=False):
        if isinstance(texts, str):
            texts = [texts]
        r = self.readers(texts)
        res = []
        for i in range(len(texts)):
            row = {}
            for c in self.classes:
                f = np.array([r[d][c][i] for d in DETECTORS])
                p = float(sigmoid(f @ self.stack[c][0] + self.stack[c][1]))
                t = self.thresh.get(c, 0.5)
                agree = int((f >= 0.5).sum())
                row[c] = {"p": round(p, 3), "include": bool(p >= t and agree >= self.min_agree), "contested": abs(p - t) < 0.12, "agree": agree,
                          "votes": {d: round(float(v), 2) for d, v in zip(DETECTORS, f)}}
            res.append(row)
        return res if return_votes else [[c for c, v in row.items() if v["include"]] for row in res]

    # ------------------------------------------------------------ persistence
    def save(self, path, meta=None):
        cls = self.classes
        np.savez_compressed(
            path, classes=np.array(cls), thresh=np.array([self.thresh.get(c, 0.5) for c in cls]),
            lrw_w=np.stack([self.lrw[c][0] for c in cls]).astype(np.float32), lrw_b=np.array([self.lrw[c][1] for c in cls]),
            lrc_w=np.stack([self.lrc[c][0] for c in cls]).astype(np.float32), lrc_b=np.array([self.lrc[c][1] for c in cls]),
            st_w=np.stack([self.stack[c][0] for c in cls]), st_b=np.array([self.stack[c][1] for c in cls]),
            nb=np.frombuffer(json.dumps(self.nb.dump()).encode("utf-8"), dtype=np.uint8), meta=np.frombuffer(json.dumps(dict(meta or {}, min_agree=self.min_agree)).encode("utf-8"), dtype=np.uint8))

    @classmethod
    def load(cls_, path):
        z = np.load(path, allow_pickle=False)
        v = cls_()
        v.classes = [str(c) for c in z["classes"]]
        v.thresh = {c: float(t) for c, t in zip(v.classes, z["thresh"])}
        v.lrw = {c: (z["lrw_w"][i].astype(np.float64), float(z["lrw_b"][i])) for i, c in enumerate(v.classes)}
        v.lrc = {c: (z["lrc_w"][i].astype(np.float64), float(z["lrc_b"][i])) for i, c in enumerate(v.classes)}
        v.stack = {c: (z["st_w"][i], float(z["st_b"][i])) for i, c in enumerate(v.classes)}
        v.nb = L.NB.load(json.loads(bytes(z["nb"]).decode("utf-8")))
        v.meta = json.loads(bytes(z["meta"]).decode("utf-8"))
        v.min_agree = int(v.meta.get("min_agree", 2))
        return v
