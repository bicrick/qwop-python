# Methodology: chasing the QWOP world record

This is the story of *how* we went after the human HTML5 QWOP 100m record (**45.530s HUD**, [kurodo1916](https://www.speedrun.com/qwop/runs/y9vk0k2m)) — not just which YAML files exist. For the strategy matrix and current numbers, see [STRATEGIES.md](./STRATEGIES.md).

## 1. Build a fast Gym: `qwop-python`

The first bottleneck was sample throughput. Browser QWOP (or chromedriver wrappers) cannot feed serious RL volume.

So we built **`qwop-python`**: a pure Python + Box2D Gymnasium reimplementation of QWOP (forked in spirit from [qwop-gym](https://github.com/smanolloff/qwop-gym)), headless by default, with `n_envs` / `SubprocVecEnv` so we can run **many environments in parallel** on one machine. Same observation / action interface shape as the browser tooling, but orders of magnitude more steps per wall-clock hour.

That sim is the training muscle. Everything else is transfer and verification.

## 2. Stand up GCP as the training farm

Local laptops are fine for debugging; they are not a fleet. We stood up a **GCP project** (spot / preemptible VMs, shared GCS bucket as control plane) so trainers could run continuously: pull a code tarball, continue from a checkpoint zip, write TensorBoard + metrics back to `gs://…`.

Default posture: a small trainer fleet (on the order of a few workers) plus later a dedicated **browser spectate** VM — not infinite scale for its own sake, but enough parallel experiments to kill bad recipes quickly.

## 3. Autonomous iteration with Grok Bot

Once the farm existed, the loop needed a brain that did not wait for a human every 15 minutes. **Grok Bot** was wired to that GCP project so it could:

- deploy / replace workers with new configs,
- watch whether runs were actually dropping times,
- swap plateaued recipes for the next bet,
- keep the spectate hunt pointed at promising checkpoints,

…on a standing cadence (orchestrator routine) with human interrupts only for blockers, approvals, and milestones. Architecture notes: [ORCHESTRATION.md](./ORCHESTRATION.md).

## 4. TensorBoard for remote eyes

With several trainers alive, “SSH and guess” does not scale. We published **TensorBoard** (synced from GCS) so we could check finish clocks, splits, and learning curves remotely and compare siblings (stride vs grace vs start-pace, etc.) without downloading every run.

## 5. Steal structure from the WR video (not just the time)

After the farm was humming, we went after **how** the WR was run:

- Source run: [SRC](https://www.speedrun.com/qwop/runs/y9vk0k2m) · [YouTube](https://youtu.be/4g9x7QJYx0M)
- Extracted **per-frame Q/W/O/P presses** by watching the on-screen key UI (pressed vs up), producing `timeline.csv` / `timeline.json`
- Converted that into `.rec` demos and tried open-loop replay in sim
- Literal timings **did not transfer** → moved to **flexible gait imitation** (phase structure, soft holds)
- Separately OCR’d the **LiveSplit** bar for 10m segment splits

All of that lives under **[kurodo-extract/](./kurodo-extract/)** (timelines, scripts, notes, example frames). Segment table: [KURODO_WR_SPLITS.md](./KURODO_WR_SPLITS.md).

## 6. Keep training (and refuse cargo-cult reseeds)

Most of the wall time was boring in a good way: continue the best policies longer, stretch stride / grace / entropy one knob at a time, stop workers that were not dropping times, and treat **landed finishes** (`user/time`) as the score — not 100m split checkpoints.

Python-side we eventually saw finishes in the low–mid 40s on the sim clock *before* settle parity — which looked like “WR soon” until we learned a lot of that start was a **dive / free-fall spawn artifact**.

## 7. Transfer to the real browser

When Python looked strong enough, we started **authentic** evaluation: the official HTML/JS QWOP page, official physics, HUD `scoreTime` as ground truth.

That exposed the sim↔browser gap (start plant timing, then settle-spawn parity — see [SEGMENT_GAP_POST_SETTLE.md](./SEGMENT_GAP_POST_SETTLE.md)). The hunt target became: browser finishes under **45.530**, with a live PB in the mid-46s while mid-race pace already matched or beat the human WR splits — **start** remaining the main hole.

## 8. Parallel browser sessions on GCP

Finally we ran **many browser episodes in parallel** on a GCP spectate / hunt VM (policy zip → real page → keep only sub-WR HUD finishes, log splits, refresh the model when a new Python candidate earned a browser gate). That is the authenticity layer: Python for throughput, browser for the claim.

## Assets worth opening

| Path | Why |
|------|-----|
| [kurodo-extract/](./kurodo-extract/) | WR key timeline, converters, gait notes, UI examples |
| [KURODO_WR_SPLITS.md](./KURODO_WR_SPLITS.md) | LiveSplit 10m cumulatives vs our PB |
| [STRATEGIES.md](./STRATEGIES.md) | Config / era matrix and current policy |
| [SEGMENT_GAP_POST_SETTLE.md](./SEGMENT_GAP_POST_SETTLE.md) | Where the remaining seconds live |
| [ORCHESTRATION.md](./ORCHESTRATION.md) | GCS / fleet / bot control plane |

## One-line thesis

**Fast parallel sim → autonomous GCP farm → learn gait from the WR video → train until sim is honest → prove it on the real browser at scale.** The record is a browser number; everything else exists to buy attempts that have a chance.
