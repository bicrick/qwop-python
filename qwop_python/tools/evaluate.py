"""Evaluate trained QWOP RL agents."""

import glob
import os

import numpy as np
from tqdm import tqdm
from stable_baselines3.common.monitor import Monitor
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import PPO, A2C, DQN

from .. import QWOPEnv
from ..game import QWOPGame
from ..renderer import QWOPRenderer
from ..observations import ObservationExtractor
from ..actions import ActionMapper
from ..data import PHYSICS_TIMESTEP, SCREEN_WIDTH, SCREEN_HEIGHT


ALGORITHMS = {"QRDQN": QRDQN, "DQN": DQN, "PPO": PPO, "A2C": A2C}
SPECTATE_STEPS_PER_STEP = 1
SPECTATE_FRAMES_PER_STEP = 4


def resolve_model_path(model_path):
    matches = glob.glob(model_path)
    if not matches:
        if "*" in model_path:
            raise FileNotFoundError(f"No files match: {model_path}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        return model_path
    return sorted(matches)[0]


def detect_algorithm(model_path):
    path_str = str(model_path).upper()
    if "DQNFD" in path_str or "ENHANCEDQRDQN" in path_str or "EQRDQN" in path_str:
        return "QRDQN"
    for algo_name in ALGORITHMS:
        if algo_name in path_str:
            return algo_name
    print("Warning: Could not detect algorithm from path, defaulting to QRDQN")
    return "QRDQN"


def _run_episode_with_render(
    game, renderer, model, obs_extractor, action_mapper,
    steps_per_step, frames_per_step, max_steps, clock
):
    import pygame

    game.reset(seed=game.seed)
    game.start()
    obs = obs_extractor.extract(game.physics)
    total_reward = 0.0
    steps = 0
    done = False

    while not done and steps < max_steps:
        action, _ = model.predict(obs, deterministic=True)
        action_mapper.apply_action(int(action), game.controls)

        for _ in range(frames_per_step):
            if game.game_state.game_ended:
                break
            game.update(dt=PHYSICS_TIMESTEP)
            renderer.render(game)
            pygame.display.flip()
            clock.tick(30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE
                ):
                    return None

        obs = obs_extractor.extract(game.physics)
        done = game.game_state.game_ended
        steps += 1

    return {
        "distance": game.game_state.score,
        "time": game.score_time,
        "steps": steps,
        "reward": total_reward,
        "success": game.game_state.jump_landed and not game.game_state.fallen,
        "fallen": game.game_state.fallen,
        "jump_landed": game.game_state.jump_landed,
    }


def _evaluate_episode(env, model, max_steps=1000):
    obs, info = env.reset()
    total_reward = 0.0
    steps = 0
    done = False

    while not done and steps < max_steps:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        steps += 1
        done = terminated or truncated

    return {
        "distance": info["distance"],
        "time": info["time"],
        "steps": steps,
        "reward": total_reward,
        "success": info["jump_landed"] and not info["fallen"],
        "fallen": info["fallen"],
        "jump_landed": info["jump_landed"],
    }


def run_evaluate(
    model_path,
    n_episodes=100,
    seed=42,
    render=False,
    max_episode_steps=1000,
    steps_per_step=1,
    frames_per_step=4,
    reduced_action_set=True,
    output_dir=None,
    algorithm=None,
):
    import json
    from pathlib import Path

    print("=" * 70)
    print("QWOP MODEL EVALUATION")
    print("=" * 70)
    print()

    model_path = resolve_model_path(model_path)
    algo_name = algorithm if algorithm is not None else detect_algorithm(model_path)
    print(f"Algorithm: {algo_name}")
    print(f"Model: {model_path}")
    print(f"Episodes: {n_episodes}")
    print(f"Seed: {seed}")
    print()

    print("Loading model...")
    AlgorithmClass = ALGORITHMS[algo_name]
    model = AlgorithmClass.load(model_path)
    print("Model loaded")
    print()

    if render:
        import pygame

        pygame.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("QWOP - Agent Evaluation")
        clock = pygame.time.Clock()
        game = QWOPGame(seed=seed, verbose=False, headless=False)
        game.initialize()
        renderer = QWOPRenderer(screen)
        obs_extractor = ObservationExtractor()
        action_mapper = ActionMapper(reduced_action_set=reduced_action_set)
        print("Render mode ready (1 action/step, 4 frames/step, reduced action set)")
        print("Press ESC to quit")
        print()

        results = []
        for episode in range(n_episodes):
            game.seed = seed + episode
            result = _run_episode_with_render(
                game, renderer, model, obs_extractor, action_mapper,
                steps_per_step, frames_per_step, max_episode_steps, clock,
            )
            if result is None:
                break
            results.append(result)
            print(
                f"Episode {episode + 1}/{n_episodes}: "
                f"{result['distance']:.1f}m, {result['time']:.2f}s, "
                f"success={result['success']}"
            )
        pygame.quit()
    else:
        print("Creating environment...")
        env = QWOPEnv(
            frames_per_step=frames_per_step,
            reduced_action_set=reduced_action_set,
            seed=seed,
        )
        env = TimeLimit(env, max_episode_steps=max_episode_steps)
        env = Monitor(env)
        print("Environment created")
        print()

        print("Running evaluation...")
        print()
        results = []
        for episode in tqdm(range(n_episodes), desc="Evaluating"):
            result = _evaluate_episode(
                env, model, max_steps=max_episode_steps
            )
            results.append(result)
        env.close()

    if not results:
        return {}, []

    distances = [r["distance"] for r in results]
    times = [r["time"] for r in results]
    rewards = [r["reward"] for r in results]
    successes = [r["success"] for r in results]
    successful_episodes = [r for r in results if r["success"]]

    stats = {
        "n_episodes": n_episodes,
        "success_rate": np.mean(successes) * 100,
        "mean_distance": np.mean(distances),
        "std_distance": np.std(distances),
        "max_distance": np.max(distances),
        "min_distance": np.min(distances),
        "mean_time": np.mean(times),
        "std_time": np.std(times),
        "mean_reward": np.mean(rewards),
        "std_reward": np.std(rewards),
    }
    if successful_episodes:
        success_times = [r["time"] for r in successful_episodes]
        stats["success_mean_time"] = np.mean(success_times)
        stats["success_best_time"] = np.min(success_times)
        stats["success_worst_time"] = np.max(success_times)

    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    print()
    print(
        f"Success Rate: {stats['success_rate']:.1f}% "
        f"({int(stats['success_rate'] * n_episodes / 100)}/{n_episodes})"
    )
    print()
    print(f"Distance: Mean {stats['mean_distance']:.2f}m +/- {stats['std_distance']:.2f}m")
    print(f"  Max: {stats['max_distance']:.2f}m, Min: {stats['min_distance']:.2f}m")
    print()
    print(f"Time: Mean {stats['mean_time']:.2f}s +/- {stats['std_time']:.2f}s")
    if successful_episodes:
        print(f"Successful: {len(successful_episodes)} episodes")
        print(f"  Mean: {stats['success_mean_time']:.2f}s, Best: {stats['success_best_time']:.2f}s")
    print()

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        summary_path = output_path / "evaluation_summary.json"
        with open(summary_path, "w") as f:
            json.dump(stats, f, indent=2)
        print(f"Summary saved to: {summary_path}")
        details_path = output_path / "evaluation_details.json"
        with open(details_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Details saved to: {details_path}")
        print()

    return stats, results
