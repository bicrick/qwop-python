"""Collect expert demonstrations for DQNfD training."""

import glob
import os

import numpy as np
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import DQN

from .. import QWOPEnv


ALGORITHMS = {"QRDQN": QRDQN, "DQN": DQN}


def detect_algorithm(model_path):
    path_str = str(model_path).upper()
    for algo_name in ALGORITHMS:
        if algo_name in path_str:
            return algo_name
    print("Warning: Could not detect algorithm from path, defaulting to QRDQN")
    return "QRDQN"


def resolve_model_path(model_path):
    matches = glob.glob(model_path)
    if not matches:
        if "*" in model_path:
            raise FileNotFoundError(f"No files match: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        return model_path
    return sorted(matches)[0]


def run_collect_demos(
    model_path,
    out_file,
    n_episodes=50,
    seed_start=10000,
    max_episode_steps=1000,
    frames_per_step=4,
    reduced_action_set=True,
    failure_cost=10.0,
    success_reward=50.0,
    time_cost_mult=10.0,
):
    model_path = resolve_model_path(model_path)
    algo_name = detect_algorithm(model_path)
    AlgorithmClass = ALGORITHMS[algo_name]

    print(f"Loading {algo_name} model from {model_path}")
    model = AlgorithmClass.load(model_path)

    env_kwargs = {
        "frames_per_step": frames_per_step,
        "reduced_action_set": reduced_action_set,
        "failure_cost": failure_cost,
        "success_reward": success_reward,
        "time_cost_mult": time_cost_mult,
    }
    env = QWOPEnv(**env_kwargs)
    env = TimeLimit(env, max_episode_steps=max_episode_steps)

    all_obs = []
    all_actions = []
    all_rewards = []
    all_next_obs = []
    all_dones = []

    print()
    print("=" * 70)
    print(f"Collecting demonstrations: {n_episodes} episodes")
    print(f"Model: {model_path}")
    print(f"Output: {out_file}")
    print("=" * 70)
    print()

    total_transitions = 0
    successful_episodes = 0

    for ep in range(n_episodes):
        obs, info = env.reset(seed=seed_start + ep)
        episode_transitions = 0
        done = False

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            next_obs, reward, terminated, truncated, info = env.step(int(action))

            all_obs.append(obs.copy())
            all_actions.append(int(action))
            all_rewards.append(float(reward))
            all_next_obs.append(next_obs.copy())
            all_dones.append(bool(terminated or truncated))

            episode_transitions += 1
            total_transitions += 1
            done = terminated or truncated
            obs = next_obs

        success = info.get("jump_landed", False) and not info.get("fallen", False)
        if success:
            successful_episodes += 1

        print(
            f"Episode {ep + 1}/{n_episodes}: "
            f"time={info.get('time', 0):.2f}s, "
            f"distance={info.get('distance', 0):.1f}m, "
            f"success={success}, transitions={episode_transitions}"
        )

    env.close()

    obs_array = np.array(all_obs, dtype=np.float32)
    actions_array = np.array(all_actions, dtype=np.int32)
    rewards_array = np.array(all_rewards, dtype=np.float32)
    next_obs_array = np.array(all_next_obs, dtype=np.float32)
    dones_array = np.array(all_dones, dtype=bool)

    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    np.savez_compressed(
        out_file,
        obs=obs_array,
        actions=actions_array,
        rewards=rewards_array,
        next_obs=next_obs_array,
        dones=dones_array,
    )

    print()
    print("=" * 70)
    print("COLLECTION SUMMARY")
    print("=" * 70)
    print(f"Total episodes:     {n_episodes}")
    print(f"Successful:        {successful_episodes} ({100 * successful_episodes / n_episodes:.1f}%)")
    print(f"Total transitions:  {total_transitions}")
    print(f"Avg per episode:    {total_transitions / n_episodes:.1f}")
    print(f"Output file:        {out_file}")
    print(f"Output size:        {os.path.getsize(out_file) / 1024 / 1024:.2f} MB")
    print("=" * 70)
    print()
    print("Demonstrations saved successfully!")
