# =============================================================================
# Copyright 2023 Simeon Manolov <s.manolloff@gmail.com>.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""Behavioral cloning from .rec demonstrations into a loadable policy zip.

Primary path: ``imitation.algorithms.bc.BC`` (gymnasium-compatible imitation>=1.0).
Fallback: minimal supervised ActorCriticPolicy trainer if imitation is missing
or incompatible with the installed stable-baselines3 pin.

Outputs (under out_dir):
  - model.zip — ActorCriticPolicy via torch.save (spectate with model_cls=BC)
  - ppo_warmup.zip — PPO wrapper with BC weights for on-policy RL finetune
    via model_load_file (NOT for WR QRDQN; do not load expert_dqnfd.zip there)
"""

from __future__ import annotations

import os
from typing import List, Sequence, Tuple

import gymnasium as gym
import numpy as np
import torch as th
from stable_baselines3 import PPO
from stable_baselines3.common.policies import ActorCriticPolicy

from . import common


def reconstruct_policy(policy_path: str, device: str = "auto") -> ActorCriticPolicy:
    """Load a policy saved by ``save_bc_policy`` / torch.save(policy)."""
    if device == "auto":
        device = "cuda" if th.cuda.is_available() else "cpu"
    # Full policy object (imitation-style); not weights_only.
    policy = th.load(policy_path, map_location=device, weights_only=False)
    if isinstance(policy, dict) and "state_dict" in policy and "data" in policy:
        # SB3 BasePolicy.save format
        data = dict(policy["data"])
        loaded = ActorCriticPolicy(**data)
        loaded.load_state_dict(policy["state_dict"])
        return loaded
    assert isinstance(policy, ActorCriticPolicy), type(policy)
    return policy


def save_bc_policy(path: str, policy: ActorCriticPolicy) -> None:
    """Save policy for reconstruct_policy / spectate model_cls=BC."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    th.save(policy, path)


def _replay_episode_actions(
    env, actions: Sequence[int], obs, skip: bool
) -> Tuple[List[np.ndarray], List[int], List[np.ndarray], List[bool], object]:
    """Step through one recorded episode.

    Returns (obs_list, act_list, next_obs_list, dones_list, final_obs).
    When skip=True, lists are empty.
    """
    obs_list: List[np.ndarray] = []
    act_list: List[int] = []
    next_obs_list: List[np.ndarray] = []
    dones_list: List[bool] = []

    for raw_action in actions:
        action = int(raw_action)
        next_obs, _reward, terminated, truncated, _info = env.step(action)
        done = bool(terminated or truncated)
        if not skip:
            obs_list.append(np.asarray(obs, dtype=np.float32).copy())
            act_list.append(action)
            next_obs_list.append(np.asarray(next_obs, dtype=np.float32).copy())
            dones_list.append(done)
        obs = next_obs
        if done:
            break

    return obs_list, act_list, next_obs_list, dones_list, obs


def collect_transitions_from_recordings(
    recordings,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Replay .rec files; return obs, acts, next_obs, dones arrays."""
    recs = common.load_recordings(recordings)
    all_obs: List[np.ndarray] = []
    all_acts: List[int] = []
    all_next: List[np.ndarray] = []
    all_dones: List[bool] = []

    env = gym.make("local/QWOP-v1")
    try:
        for rec in recs:
            print("Collecting transitions from %s" % rec["file"])
            obs, _ = env.reset(seed=rec["seed"])
            for i, episode in enumerate(rec["episodes"], 1):
                if episode["skip"]:
                    print("Skipping marked episode %d" % i)
                    _replay_episode_actions(env, episode["actions"], obs, skip=True)
                    obs, _ = env.reset()
                    continue

                obs_list, act_list, next_list, dones_list, _ = _replay_episode_actions(
                    env, episode["actions"], obs, skip=False
                )
                all_obs.extend(obs_list)
                all_acts.extend(act_list)
                all_next.extend(next_list)
                all_dones.extend(dones_list)
                print(
                    "Replayed episode %d: %d transitions (total=%d)"
                    % (i, len(act_list), len(all_acts))
                )
                obs, _ = env.reset()
    finally:
        env.close()

    if not all_acts:
        raise RuntimeError("No transitions collected from recordings")

    obs_arr = np.stack(all_obs).astype(np.float32)
    acts_arr = np.asarray(all_acts, dtype=np.int64)
    next_arr = np.stack(all_next).astype(np.float32)
    dones_arr = np.asarray(all_dones, dtype=bool)
    print("Collected a total of %d transitions" % len(acts_arr))
    return obs_arr, acts_arr, next_arr, dones_arr


def _train_with_imitation(
    obs_arr,
    acts_arr,
    next_obs_arr,
    dones_arr,
    observation_space,
    action_space,
    learner_kwargs,
    n_epochs,
    seed,
    out_dir,
    log_tensorboard,
):
    from imitation.algorithms import bc
    from imitation.data.types import Transitions
    from imitation.util import logger as imit_logger

    infos = np.empty(len(acts_arr), dtype=object)
    for i in range(len(acts_arr)):
        infos[i] = {}
    demos = Transitions(
        obs=obs_arr,
        acts=acts_arr,
        infos=infos,
        next_obs=next_obs_arr,
        dones=dones_arr,
    )

    log = None
    if log_tensorboard:
        os.makedirs(out_dir, exist_ok=True)
        log = imit_logger.configure(folder=out_dir, format_strs=["tensorboard"])

    rng = np.random.default_rng(seed)
    kwargs = {
        k: v
        for k, v in (learner_kwargs or {}).items()
        if v is not None and k not in ("policy",)
    }
    # imitation requires batch_size <= n_transitions
    n_trans = len(acts_arr)
    batch_size = int(kwargs.get("batch_size", 32) or 32)
    if batch_size > n_trans:
        print("Clamping BC batch_size %d -> %d (n_transitions)" % (batch_size, n_trans))
        kwargs["batch_size"] = n_trans

    trainer = bc.BC(
        observation_space=observation_space,
        action_space=action_space,
        demonstrations=demos,
        rng=rng,
        custom_logger=log,
        **kwargs,
    )
    trainer.train(n_epochs=int(n_epochs), progress_bar=True)
    return trainer.policy, "imitation.bc"


def _train_minimal_bc(
    obs_arr,
    acts_arr,
    observation_space,
    action_space,
    learner_kwargs,
    n_epochs,
    seed,
    batch_size=32,
    ent_weight=0.001,
    l2_weight=0.0,
    lr=0.001,
):
    """Smallest viable BC: CE on discrete actions with an SB3 MlpPolicy."""
    device = "cuda" if th.cuda.is_available() else "cpu"
    th.manual_seed(int(seed))
    batch_size = int(
        (learner_kwargs or {}).get("batch_size", batch_size) or batch_size
    )
    batch_size = max(1, min(batch_size, len(acts_arr)))
    ent_weight = float(
        (learner_kwargs or {}).get("ent_weight", ent_weight) or ent_weight
    )
    l2_weight = float((learner_kwargs or {}).get("l2_weight", l2_weight) or 0.0)

    # Match imitation FeedForward32Policy so ppo_warmup state_dict can align.
    policy = ActorCriticPolicy(
        observation_space,
        action_space,
        lr_schedule=lambda _: lr,
        net_arch=[32, 32],
    ).to(device)
    optimizer = th.optim.Adam(policy.parameters(), lr=lr)
    n = len(acts_arr)
    obs_t = th.as_tensor(obs_arr, device=device)
    acts_t = th.as_tensor(acts_arr, device=device)

    policy.train()
    for epoch in range(int(n_epochs)):
        perm = th.randperm(n, device=device)
        epoch_loss = 0.0
        n_batches = 0
        for start in range(0, n, batch_size):
            idx = perm[start : start + batch_size]
            batch_obs = obs_t[idx]
            batch_acts = acts_t[idx]
            values, log_prob, entropy = policy.evaluate_actions(batch_obs, batch_acts)
            loss = -log_prob.mean()
            if ent_weight:
                loss = loss - ent_weight * entropy.mean()
            if l2_weight:
                l2 = sum(p.pow(2).sum() for p in policy.parameters())
                loss = loss + l2_weight * l2
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.item())
            n_batches += 1
        if (epoch + 1) % max(1, int(n_epochs) // 10) == 0 or epoch == 0:
            print(
                "minimal_bc epoch %d/%d loss=%.4f"
                % (epoch + 1, n_epochs, epoch_loss / max(1, n_batches))
            )

    policy.eval()
    return policy, "minimal_bc"


def _wrap_policy_as_ppo(policy: ActorCriticPolicy, seed: int, out_path: str) -> None:
    """Save a PPO zip whose policy weights match BC (for on-policy RL finetune)."""
    venv = None
    try:
        from stable_baselines3.common.vec_env import DummyVecEnv

        def _make():
            return gym.make("local/QWOP-v1")

        venv = DummyVecEnv([_make])

        # Match imitation FeedForward32Policy / our minimal net_arch when possible.
        net_arch = getattr(policy, "net_arch", None) or [32, 32]
        model = PPO(
            "MlpPolicy",
            venv,
            seed=int(seed),
            n_steps=64,
            batch_size=32,
            policy_kwargs={"net_arch": net_arch},
            verbose=0,
        )
        missing, unexpected = model.policy.load_state_dict(
            policy.state_dict(), strict=False
        )
        if missing or unexpected:
            print(
                "Warning: PPO warmup state_dict mismatch "
                "(missing=%s unexpected=%s) — trying direct policy swap"
                % (list(missing)[:5], list(unexpected)[:5])
            )
            model.policy = policy
        model.save(out_path)
        print("Wrote PPO warmup checkpoint: %s" % out_path)
    finally:
        if venv is not None:
            venv.close()


def train_bc(
    seed,
    run_id,
    n_epochs,
    recordings,
    out_dir_template,
    learner_kwargs,
    log_tensorboard,
    save_ppo_warmup=True,
):
    seed = int(seed) if seed is not None else common.gen_seed()
    out_dir = common.out_dir_from_template(out_dir_template, seed, run_id)
    os.makedirs(out_dir, exist_ok=True)

    obs_arr, acts_arr, next_obs_arr, dones_arr = collect_transitions_from_recordings(
        recordings
    )

    # Probe spaces from a throwaway env (must match register_env kwargs).
    probe = gym.make("local/QWOP-v1")
    try:
        observation_space = probe.observation_space
        action_space = probe.action_space
    finally:
        probe.close()

    backend = None
    policy = None
    try:
        policy, backend = _train_with_imitation(
            obs_arr=obs_arr,
            acts_arr=acts_arr,
            next_obs_arr=next_obs_arr,
            dones_arr=dones_arr,
            observation_space=observation_space,
            action_space=action_space,
            learner_kwargs=learner_kwargs,
            n_epochs=n_epochs,
            seed=seed,
            out_dir=out_dir,
            log_tensorboard=log_tensorboard,
        )
    except Exception as exc:
        print(
            "imitation BC unavailable or failed (%s: %s); "
            "falling back to minimal supervised BC"
            % (type(exc).__name__, exc)
        )
        policy, backend = _train_minimal_bc(
            obs_arr=obs_arr,
            acts_arr=acts_arr,
            observation_space=observation_space,
            action_space=action_space,
            learner_kwargs=learner_kwargs,
            n_epochs=n_epochs,
            seed=seed,
        )

    policy_path = os.path.join(out_dir, "model.zip")
    save_bc_policy(policy_path, policy)
    print("Saved BC policy (%s) to %s" % (backend, policy_path))

    ppo_path = None
    if save_ppo_warmup:
        ppo_path = os.path.join(out_dir, "ppo_warmup.zip")
        try:
            _wrap_policy_as_ppo(policy, seed, ppo_path)
        except Exception as exc:
            print("Could not write ppo_warmup.zip (%s: %s)" % (type(exc).__name__, exc))
            ppo_path = None

    common.save_config(
        out_dir,
        {
            "seed": seed,
            "run_id": run_id,
            "n_epochs": n_epochs,
            "recordings": recordings,
            "learner_kwargs": learner_kwargs,
            "backend": backend,
            "n_transitions": int(len(acts_arr)),
            "policy_file": policy_path,
            "ppo_warmup_file": ppo_path,
        },
    )

    return {
        "out_dir": out_dir,
        "backend": backend,
        "n_transitions": int(len(acts_arr)),
        "policy_file": policy_path,
        "ppo_warmup_file": ppo_path,
    }
