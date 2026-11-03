"""Was Mercury in apparent retrograde on a given day? A joke measure for the source ledger, and a real check that the pipeline does not invent signal.

Computed, not looked up: heliocentric positions of Mercury and Earth from the JPL approximate Keplerian elements (Standish, valid 1800-2050), then the
apparent (geocentric) ecliptic longitude. Retrograde = that longitude is falling. Matches published retrograde dates to within about a day.
Standard library only.
"""
import datetime
import math

_EL = {"mercury": [0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749, 252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081],
       "earth": [1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668, 100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0]}


def _helio(name, jd):
    a0, ar, e0, er, i0, ir, L0, Lr, w0, wr, n0, nr = _EL[name]
    T = (jd - 2451545.0) / 36525.0
    a, e, I, L, wbar, node = a0 + ar * T, e0 + er * T, math.radians(i0 + ir * T), L0 + Lr * T, w0 + wr * T, n0 + nr * T
    w = math.radians(wbar - node)
    M = math.radians((L - wbar) % 360.0)
    E = M
    for _ in range(12):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    x, y = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
    Om = math.radians(node)
    xe = (math.cos(w) * math.cos(Om) - math.sin(w) * math.sin(Om) * math.cos(I)) * x + (-math.sin(w) * math.cos(Om) - math.cos(w) * math.sin(Om) * math.cos(I)) * y
    ye = (math.cos(w) * math.sin(Om) + math.sin(w) * math.cos(Om) * math.cos(I)) * x + (-math.sin(w) * math.sin(Om) + math.cos(w) * math.cos(Om) * math.cos(I)) * y
    return xe, ye


def _lon(jd):
    mx, my = _helio("mercury", jd)
    ex, ey = _helio("earth", jd)
    return math.atan2(my - ey, mx - ex)


def retrograde_on(d):
    """True if Mercury is in apparent retrograde on date `d` (datetime.date)."""
    jd = d.toordinal() + 1721424.5 + 0.5
    delta = (_lon(jd + 0.5) - _lon(jd - 0.5) + math.pi) % (2 * math.pi) - math.pi
    return delta < 0


def periods(y0, y1):
    """[(first day, last day)] of each retrograde, for a sanity check."""
    out, cur, d = [], None, datetime.date(y0, 1, 1)
    while d <= datetime.date(y1, 12, 31):
        r = retrograde_on(d)
        if r and cur is None:
            cur = d
        if not r and cur is not None:
            out.append((cur, d - datetime.timedelta(days=1)))
            cur = None
        d += datetime.timedelta(days=1)
    return out
