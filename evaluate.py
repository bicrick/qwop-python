#!/usr/bin/env python3
"""
QWOP Evaluation Script

Evaluates trained RL agents over multiple episodes and generates statistics.
Tracks success rate, average distance, average time, and best performance.

Usage:
    python evaluate.py --model data/models/QRDQN_default_*/final_model.zip --episodes 100
    python evaluate.py --model path/to/model.zip --episodes 50 --render
"""

import sys
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

import numpy as np
from tqdm import tqdm
from stable_baselines3.common.monitor import Monitor
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import PPO, A2C, DQN

from qwop_env import QWOPEnv
from game import QWOPGame
from renderer import QWOPRenderer
from observations import ObservationExtractor
from actions import ActionMapper
from data import PHYSICS_TIMESTEP, SCREEN_WIDTH, SCREEN_HEIGHT


# Algorithm registry
ALGORITHMS = {
    'QRDQN': QRDQN,
    'DQN': DQN,
    'PPO': PPO,
    'A2C': A2C,
}


def detect_algorithm(model_path):
    """
    Detect algorithm type from model path.
    
    Args:
        model_path: Path to model file
        
    Returns:
        Algorithm name (e.g., 'QRDQN')
    """
    path_str = str(model_path).upper()
    for algo_name in ALGORITHMS.keys():
        if algo_name in path_str:
            return algo_name
    
    # Default to QRDQN
    print("Warning: Could not detect algorithm from path, defaulting to QRDQN")
    return 'QRDQN'


def _run_episode_with_render(
    game, renderer, model, obs_extractor, action_mapper,
    frames_per_step, max_steps, clock
):
    """Run one episode with pygame rendering. Returns episode stats dict."""
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
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    return None  # User quit

        obs = obs_extractor.extract(game.physics)
        done = game.game_state.game_ended
        steps += 1

    return {
        'distance': game.game_state.score,
        'time': game.score_time,
        'steps': steps,
        'reward': total_reward,
        'success': game.game_state.jump_landed and not game.game_state.fallen,
        'fallen': game.game_state.fallen,
        'jump_landed': game.game_state.jump_landed,
    }


def evaluate_episode(env, model, render=False, max_steps=1000):
    """
    Run a single evaluation episode.
    
    Args:
        env: QWOP environment
        model: Trained model
        render: Whether to render (not implemented for headless env)
        max_steps: Maximum steps per episode
        
    Returns:
        Dictionary with episode statistics
    """
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
        'distance': info['distance'],
        'time': info['time'],
        'steps': steps,
        'reward': total_reward,
        'success': info['jump_landed'] and not info['fallen'],
        'fallen': info['fallen'],
        'jump_landed': info['jump_landed'],
    }


def evaluate(
    model_path,
    n_episodes=100,
    seed=42,
    render=False,
    max_episode_steps=1000,
    frames_per_step=4,
    reduced_action_set=True,
    output_dir=None
):
    """
    Evaluate a trained model over multiple episodes.
    
    Args:
        model_path: Path to saved model
        n_episodes: Number of episodes to evaluate
        seed: Random seed for reproducibility
        render: Whether to render episodes
        max_episode_steps: Maximum steps per episode
        frames_per_step: Frames per step in environment
        reduced_action_set: Whether to use reduced action set
        output_dir: Directory to save results (optional)
        
    Returns:
        Dictionary with evaluation statistics
    """
    print("=" * 70)
    print("QWOP MODEL EVALUATION")
    print("=" * 70)
    print()
    
    # Detect algorithm
    algo_name = detect_algorithm(model_path)
    print(f"Algorithm: {algo_name}")
    print(f"Model: {model_path}")
    print(f"Episodes: {n_episodes}")
    print(f"Seed: {seed}")
    print()
    
    # Load model
    print("Loading model...")
    AlgorithmClass = ALGORITHMS[algo_name]
    model = AlgorithmClass.load(model_path)
    print("✓ Model loaded")
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
        print("✓ Render mode ready (frameskip=4, reduced action set)")
        print("  Press ESC to quit")
        print()

        results = []
        for episode in range(n_episodes):
            game.seed = seed + episode
            result = _run_episode_with_render(
                game, renderer, model, obs_extractor, action_mapper,
                frames_per_step, max_episode_steps, clock
            )
            if result is None:
                break
            results.append(result)
            print(f"Episode {episode + 1}/{n_episodes}: {result['distance']:.1f}m, {result['time']:.2f}s, success={result['success']}")
        pygame.quit()
    else:
        # Create environment
        print("Creating environment...")
        env = QWOPEnv(
            frames_per_step=frames_per_step,
            reduced_action_set=reduced_action_set,
            seed=seed
        )
        env = TimeLimit(env, max_episode_steps=max_episode_steps)
        env = Monitor(env)
        print("✓ Environment created")
        print()

        # Run evaluation
        print("Running evaluation...")
        print()

        results = []
        for episode in tqdm(range(n_episodes), desc="Evaluating"):
            result = evaluate_episode(env, model, render=False, max_steps=max_episode_steps)
            results.append(result)
        env.close()

    if not results:
        return {}, []

    # Calculate statistics
    distances = [r['distance'] for r in results]
    times = [r['time'] for r in results]
    rewards = [r['reward'] for r in results]
    successes = [r['success'] for r in results]
    
    stats = {
        'n_episodes': n_episodes,
        'success_rate': np.mean(successes) * 100,
        'mean_distance': np.mean(distances),
        'std_distance': np.std(distances),
        'max_distance': np.max(distances),
        'min_distance': np.min(distances),
        'mean_time': np.mean(times),
        'std_time': np.std(times),
        'mean_reward': np.mean(rewards),
        'std_reward': np.std(rewards),
    }
    
    # Calculate success-only statistics
    successful_episodes = [r for r in results if r['success']]
    if successful_episodes:
        success_times = [r['time'] for r in successful_episodes]
        stats['success_mean_time'] = np.mean(success_times)
        stats['success_best_time'] = np.min(success_times)
        stats['success_worst_time'] = np.max(success_times)
    
    # Print results
    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    print()
    print(f"Success Rate: {stats['success_rate']:.1f}% ({int(stats['success_rate'] * n_episodes / 100)}/{n_episodes})")
    print()
    print(f"Distance:")
    print(f"  Mean:   {stats['mean_distance']:.2f}m ± {stats['std_distance']:.2f}m")
    print(f"  Max:    {stats['max_distance']:.2f}m")
    print(f"  Min:    {stats['min_distance']:.2f}m")
    print()
    print(f"Time:")
    print(f"  Mean:   {stats['mean_time']:.2f}s ± {stats['std_time']:.2f}s")
    print()
    if successful_episodes:
        print(f"Successful Episodes:")
        print(f"  Count:      {len(successful_episodes)}")
        print(f"  Mean Time:  {stats['success_mean_time']:.2f}s")
        print(f"  Best Time:  {stats['success_best_time']:.2f}s")
        print(f"  Worst Time: {stats['success_worst_time']:.2f}s")
        print()
    print(f"Reward:")
    print(f"  Mean:   {stats['mean_reward']:.2f} ± {stats['std_reward']:.2f}")
    print()
    
    # Save results if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save summary statistics
        summary_path = output_path / 'evaluation_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(stats, f, indent=2)
        print(f"✓ Summary saved to: {summary_path}")
        
        # Save detailed results
        details_path = output_path / 'evaluation_details.json'
        with open(details_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✓ Details saved to: {details_path}")
        print()
    
    env.close()
    
    return stats, results


def main():
    """Parse arguments and run evaluation."""
    parser = argparse.ArgumentParser(description='Evaluate QWOP RL agent')
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help='Path to trained model file (.zip)'
    )
    parser.add_argument(
        '--episodes',
        type=int,
        default=100,
        help='Number of episodes to evaluate (default: 100)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )
    parser.add_argument(
        '--render',
        action='store_true',
        help='Render episodes (uses frameskip 4 and reduced action set)'
    )
    parser.add_argument(
        '--max-steps',
        type=int,
        default=1000,
        help='Maximum steps per episode (default: 1000)'
    )
    parser.add_argument(
        '--frames-per-step',
        type=int,
        default=4,
        help='Physics frames per environment step (default: 4)'
    )
    parser.add_argument(
        '--full-action-set',
        action='store_true',
        help='Use full 16-action set instead of reduced 9-action set'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for results (optional)'
    )
    
    args = parser.parse_args()
    
    # Check model file exists
    if not os.path.exists(args.model):
        print(f"Error: Model file not found: {args.model}")
        sys.exit(1)

    # When rendering, enforce frameskip 4 and reduced action set (match training config)
    frames_per_step = 4 if args.render else args.frames_per_step
    reduced_action_set = True if args.render else (not args.full_action_set)

    # Run evaluation
    evaluate(
        model_path=args.model,
        n_episodes=args.episodes,
        seed=args.seed,
        render=args.render,
        max_episode_steps=args.max_steps,
        frames_per_step=frames_per_step,
        reduced_action_set=reduced_action_set,
        output_dir=args.output
    )


if __name__ == '__main__':
    main()
