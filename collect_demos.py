#!/usr/bin/env python3
"""
Collect expert demonstrations from a trained model for DQNfD training.

Runs the expert model for N episodes and saves full transition tuples to a .npz
file. The format matches DQNfDCallback expectations: obs, actions, rewards,
next_obs, dones.

Usage:
    python collect_demos.py --model path/to/model.zip --output data/demonstrations/demos.npz --episodes 50
    python collect_demos.py --config config/collect_demos.yml
"""

import sys
import os
import argparse
import glob
from pathlib import Path

# Add src to path
sys.path.insert(0, "src")

import numpy as np
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import DQN

from qwop_env import QWOPEnv


ALGORITHMS = {
    "QRDQN": QRDQN,
    "DQN": DQN,
}


def detect_algorithm(model_path):
    """Detect algorithm type from model path."""
    path_str = str(model_path).upper()
    for algo_name in ALGORITHMS.keys():
        if algo_name in path_str:
            return algo_name
    print("Warning: Could not detect algorithm from path, defaulting to QRDQN")
    return "QRDQN"


def resolve_model_path(model_path):
    """
    Resolve model path, handling globs (e.g. data/models/QRDQN_*/final_model.zip).
    Returns the first matching path or raises if none found.
    """
    matches = glob.glob(model_path)
    if not matches:
        if "*" in model_path:
            raise FileNotFoundError(f"No files match: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        return model_path
    return sorted(matches)[0]


def collect_demonstrations(
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
    """
    Run expert model for N episodes and save transitions to .npz.

    Args:
        model_path: Path to trained model
        out_file: Output .npz file path
        n_episodes: Number of episodes to collect
        seed_start: Starting seed for episodes (episode i uses seed_start + i)
        max_episode_steps: Max steps per episode
        frames_per_step: Env frames per step
        reduced_action_set: Use 9 actions
        failure_cost: Env failure cost
        success_reward: Env success reward
        time_cost_mult: Env time cost multiplier
    """
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
            f"success={success}, "
            f"transitions={episode_transitions}"
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
    print(f"Successful:         {successful_episodes} ({100 * successful_episodes / n_episodes:.1f}%)")
    print(f"Total transitions:  {total_transitions}")
    print(f"Avg per episode:    {total_transitions / n_episodes:.1f}")
    print(f"Output file:        {out_file}")
    print(f"Output size:        {os.path.getsize(out_file) / 1024 / 1024:.2f} MB")
    print("=" * 70)
    print()
    print("Demonstrations saved successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Collect expert demonstrations for DQNfD training"
    )
    parser.add_argument("--model", type=str, help="Path to trained model (supports glob)")
    parser.add_argument(
        "--output",
        type=str,
        default="data/demonstrations/qrdqn_proven_demos.npz",
        help="Output .npz file path",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=50,
        help="Number of episodes to collect",
    )
    parser.add_argument(
        "--seed-start",
        type=int,
        default=10000,
        help="Starting seed for episodes",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML config (overrides CLI; model_file, out_file, n_episodes, env_kwargs)",
    )

    args = parser.parse_args()

    if args.config:
        import yaml

        with open(args.config) as f:
            cfg = yaml.safe_load(f)
        env_kwargs = cfg.get("env_kwargs", {})
        collect_demonstrations(
            model_path=cfg["model_file"],
            out_file=cfg["out_file"],
            n_episodes=cfg.get("n_episodes", 50),
            seed_start=cfg.get("seed_start", 10000),
            max_episode_steps=cfg.get("max_episode_steps", 1000),
            **env_kwargs,
        )
    else:
        if not args.model:
            parser.error("--model or --config is required")
        collect_demonstrations(
            model_path=args.model,
            out_file=args.output,
            n_episodes=args.episodes,
            seed_start=args.seed_start,
        )


if __name__ == "__main__":
    main()
