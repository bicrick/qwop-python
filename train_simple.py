#!/usr/bin/env python3
"""
Simple QWOP Training Script (No Multiprocessing)

Simplified version of train.py that uses DummyVecEnv instead of SubprocVecEnv.
Use this for testing or on systems with multiprocessing issues.

Usage:
    python train_simple.py
"""

import sys
sys.path.insert(0, 'src')

from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN

from qwop_env import QWOPEnv


def make_env():
    """Create and wrap environment."""
    env = QWOPEnv(
        frames_per_step=4,
        reduced_action_set=True,
        failure_cost=10.0,
        success_reward=50.0,
        time_cost_mult=10.0
    )
    env = TimeLimit(env, max_episode_steps=1000)
    env = Monitor(env)
    return env


def main():
    import os
    from pathlib import Path
    from datetime import datetime
    
    print("=" * 70)
    print("QWOP RL TRAINING (SIMPLE)")
    print("=" * 70)
    print()
    
    # Create output directories with timestamp (matching train.py structure)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"QRDQN_simple_{timestamp}"
    
    checkpoint_dir = Path("data/checkpoints") / run_name
    model_dir = Path("data/models") / run_name
    log_dir = Path("data/logs") / run_name
    
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create single environment
    print("Creating environment...")
    venv = DummyVecEnv([make_env])
    print("✓ Environment created")
    print()
    
    # Create model with TensorBoard logging
    print("Creating QRDQN model...")
    print(f"Run name: {run_name}")
    print(f"  Checkpoints: {checkpoint_dir}")
    print(f"  Models: {model_dir}")
    print(f"  Logs: {log_dir}")
    model = QRDQN(
        policy="MlpPolicy",
        env=venv,
        buffer_size=100_000,
        learning_starts=10_000,
        batch_size=64,
        gamma=0.997,
        learning_rate=0.001,
        target_update_interval=512,
        exploration_fraction=0.3,
        exploration_initial_eps=0.2,
        exploration_final_eps=0.0,
        train_freq=4,
        gradient_steps=1,
        tensorboard_log=str(log_dir),
        verbose=0  # Set to 0 to reduce console output
    )
    print("✓ Model created")
    print()
    print("To monitor training, run:")
    print(f"  tensorboard --logdir {log_dir}")
    print()
    
    # Train
    print("Training for 100k timesteps...")
    print("(Training logs will be minimal - use TensorBoard to monitor)")
    print()
    
    try:
        model.learn(
            total_timesteps=100_000,
            progress_bar=True  # Enable progress bar for clean training tracking
        )
        
        print()
        print("=" * 70)
        print("TRAINING COMPLETE")
        print("=" * 70)
        print()
        
        # Save model
        final_model_path = model_dir / "final_model"
        model.save(str(final_model_path))
        print(f"✓ Model saved to {final_model_path}.zip")
        
    except KeyboardInterrupt:
        print()
        print("Training interrupted")
        interrupted_model_path = model_dir / "interrupted_model"
        model.save(str(interrupted_model_path))
        print(f"✓ Model saved to {interrupted_model_path}.zip")
    
    venv.close()


if __name__ == '__main__':
    main()
