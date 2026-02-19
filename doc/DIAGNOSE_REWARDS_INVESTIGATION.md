![1771519400687](image/DIAGNOSE_REWARDS_INVESTIGATION/1771519400687.png)# Diagnose Rewards Cross-Env Investigation

## Summary

**Steps are identical in both environments.** Both count `env.step()` calls; each step advances `frames_per_step` (4) physics ticks; dt per step is 0.013333 in both. The reward gap (-19 vs +114) is not from step/frame counting.

## What Differs

| Metric | qwop-python | qwop-wr |
|--------|-------------|---------|
| Total reward (1000 steps) | -19.01 | +114.52 |
| Final distance | 19.09 m | 68.57 m |
| Final time (protocol) | 13.33 | 4.06 |
| Resets / episodes | 0 (1 episode) | Multiple |
| Runner state at end | Stuck, crawling | Still running |

### qwop-python behavior

- Runner reaches ~19 m around step 300
- Then crawls very slowly (velocity ~0.04, dist barely increases)
- `terminated` never becomes True; `term` remains ""
- All 1000 steps run in a single episode
- Time accumulates for all 1000 steps (~13.3 protocol = 133 s)
- ~650 steps of pure time penalty (-0.0333 each) account for most of the negative reward

### qwop-wr behavior

- Runner falls and triggers game over
- Episode ends, env resets, new episode starts
- Multiple episodes in 1000 steps; only the last episode contributes to final `time` (4.06)
- Runner keeps progressing across episodes (68.5 m in the last segment)

## Root Causes

### 1. Fall detection

- **qwop-python:** Fall requires head, leftArm, rightArm, leftForearm, or rightForearm touching track (see [collision.py](qwop_python/collision.py) lines 147–148).
- **torso is not included.** If the runner ends up torso-down (belly slide, etc.) without head/arms on the ground, `fallen` may never be set.
- In the stuck/crawling state, no head/arm–track contact may be detected, so the episode never ends.

### 2. Physics differences

- qwop-python: PyBox2D (Python)
- qwop-wr: JavaScript Box2D in the browser
- Same actions can produce different poses and trajectories.
- The policy was trained in qwop-wr; in qwop-python the same actions can lead to a different (worse, stuck) state.

## Recommendation

1. **Include torso in fall detection** in qwop-python so torso + track counts as a fall, matching the “head or torso touches ground” idea in [QWOP_GAME_LOGIC.md](doc/reference/QWOP_GAME_LOGIC.md).
2. **Re-check step parity** after fixing fall detection (dt, time scaling already match).
3. **Optional:** Add “stuck” detection (e.g., flat distance and low velocity for N steps) as an extra termination signal.
