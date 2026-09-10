import csv
import statistics
from collections import Counter, defaultdict

rows = []
with open("/workspace/qwop-wr-extract/timeline.csv") as f:
    for row in csv.DictReader(f):
        rows.append((float(row["t_sec"]), int(row["q"]), int(row["w"]), int(row["o"]), int(row["p"])))

race = [r for r in rows if 2.0 <= r[0] <= 47.45]
print("race samples", len(race), "dt", race[1][0] - race[0][0])


def series(ki):
    return [(t, r[ki + 1]) for t, q, w, o, p in race for r in [(q, w, o, p)]]


def edges(ki, rising=True):
    out = []
    prev = 0
    for t, q, w, o, p in race:
        v = (q, w, o, p)[ki]
        if rising and v and not prev:
            out.append(t)
        if (not rising) and (not v) and prev:
            out.append(t)
        prev = v
    return out


def holds_of(ki):
    holds = []
    run_start = None
    prev = 0
    last_t = None
    for t, q, w, o, p in race:
        v = (q, w, o, p)[ki]
        if v and not prev:
            run_start = t
        elif (not v) and prev:
            holds.append(t - run_start)
        prev = v
        last_t = t
    if prev and run_start is not None:
        holds.append(last_t - run_start + 1.0 / 60.0)
    return holds


print("=== rising intervals ===")
rises = {}
for ki, k in enumerate("qwop"):
    re = edges(ki, True)
    rises[k] = re
    iv = [re[i + 1] - re[i] for i in range(len(re) - 1)]
    print(
        k,
        "n",
        len(re),
        "first",
        round(re[0], 4),
        "med",
        round(statistics.median(iv), 4),
        "mean",
        round(statistics.mean(iv), 4),
        "min",
        round(min(iv), 4),
        "max",
        round(max(iv), 4),
    )
    buckets = Counter(round(x * 20) / 20 for x in iv)
    print("  hist", sorted(buckets.items()))

n = len(race)
print("\n=== duty ===")
for ki, k in enumerate("qwop"):
    down = sum(1 for r in race if r[ki + 1])
    h = holds_of(ki)
    print(
        k,
        "frac",
        round(down / n, 3),
        "holds",
        len(h),
        "med_hold",
        round(statistics.median(h), 4),
        "mean_hold",
        round(statistics.mean(h), 4),
    )

print("\n=== state occupancy ===")
c = Counter((q, w, o, p) for t, q, w, o, p in race)
for st, cnt in c.most_common():
    print(st, cnt, round(cnt / n, 3))

print("\n=== when key down, co-keys ===")
for ki, k in enumerate("qwop"):
    sub = [r for r in race if r[ki + 1]]
    print(k, "down", len(sub))
    cc = Counter((r[1], r[2], r[3], r[4]) for r in sub)
    for st, cnt in cc.most_common(8):
        print(" ", st, cnt, round(cnt / len(sub), 3))

events = []
prev = (0, 0, 0, 0)
for t, q, w, o, p in race:
    cur = (q, w, o, p)
    for ki, k in enumerate("qwop"):
        if cur[ki] and not prev[ki]:
            events.append((t, k, "rise"))
        if (not cur[ki]) and prev[ki]:
            events.append((t, k, "fall"))
    prev = cur

print("\nfirst 70 events")
for e in events[:70]:
    print("  %.4f %s %s" % e)

rises_ev = [(t, k) for t, k, kind in events if kind == "rise"]
s = "".join(k for _, k in rises_ev)
print("\nrise string len", len(s))
print("first", s[:80])
print("top 4", Counter(s[i : i + 4] for i in range(len(s) - 3)).most_common(12))
print("top 8", Counter(s[i : i + 8] for i in range(len(s) - 7)).most_common(8))

qr = rises["q"]
print("\n=== per Q-cycle rise order ===")
cyc = []
for i in range(len(qr) - 1):
    t0, t1 = qr[i], qr[i + 1]
    seq = [k for t, k in rises_ev if t0 - 1e-9 <= t < t1 - 1e-4]
    cyc.append("".join(seq))
print(Counter(cyc).most_common(15))
print("n", len(cyc), "unique", len(set(cyc)))

print("\n=== first 10 Q cycles events ===")
for i in range(min(10, len(qr) - 1)):
    t0, t1 = qr[i], qr[i + 1]
    ev = [(round(t - t0, 3), k, kind) for t, k, kind in events if t0 <= t < t1]
    print(i, "dur", round(t1 - t0, 3), ev)

print("\n=== phase of next rise after Q, as fraction of Q period ===")
per = statistics.median([qr[i + 1] - qr[i] for i in range(len(qr) - 1)])
print("median Q period", per)
for k in "wop":
    rel = []
    re = rises[k]
    for tq in qr[:-1]:
        cands = [t - tq for t in re if -0.02 <= t - tq < per * 0.98]
        if cands:
            rel.append(min(cands, key=lambda x: abs(x) if x >= -0.02 else 99))
            # take the earliest non-negative, else nearest
    # redo cleanly
    rel = []
    for tq in qr[:-1]:
        cands = [t - tq for t in re if 0 <= t - tq < per * 0.95]
        if cands:
            rel.append(min(cands))
    print(k, "n", len(rel), "med_s", round(statistics.median(rel), 4), "frac", round(statistics.median(rel) / per, 3))

print("\n=== Q vs O overlap: fraction of Q-down time O also down ===")
for a, b in [("q", "o"), ("w", "p"), ("q", "p"), ("w", "o"), ("q", "w")]:
    ia = "qwop".index(a)
    ib = "qwop".index(b)
    both = sum(1 for r in race if r[ia + 1] and r[ib + 1])
    aonly = sum(1 for r in race if r[ia + 1])
    print(a, b, "both/a", round(both / aonly, 3), "both samples", both)

# lag: O rise relative to Q rise (not just next after)
print("\n=== signed nearest rising lag (other - Q) ===")
for k in "wop":
    re = rises[k]
    offs = []
    for tq in qr:
        best = min(re, key=lambda t: abs(t - tq))
        offs.append(best - tq)
    print(k, "med", round(statistics.median(offs), 4), "mean", round(statistics.mean(offs), 4))

# start sequence before first Q
print("\n=== events before first Q ===")
t_first_q = qr[0]
for e in events:
    if e[0] <= t_first_q + 0.8:
        print("  %.4f %s %s" % e)
    else:
        break
print("first Q", t_first_q)
