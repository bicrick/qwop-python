#!/usr/bin/env python3
"""
QWOP Training Script

Trains RL agents using Stable-Baselines3 with YAML configuration files.
Supports parallel training with SubprocVecEnv for maximum speed.

Usage:
    python train.py --config config/train_qrdqn.yml
    python train.py --config config/train_qrdqn.yml --run-id my_experiment
"""

import sys
import os
import argparse
import yaml
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, 'src')

import numpy as np
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback, CallbackList
from stable_baselines3.common.monitor import Monitor
from gymnasium.wrappers import TimeLimit
from sb3_contrib import QRDQN
from stable_baselines3 import PPO, A2C, DQN

from qwop_env import QWOPEnv


# Algorithm registry
ALGORITHMS = {
    'QRDQN': QRDQN,
    'DQN': DQN,
    'PPO': PPO,
    'A2C': A2C,
}


def make_env(rank, seed, env_kwargs, max_episode_steps):
    """
    Create a single environment function for SubprocVecEnv.
    
    Args:
        rank: Unique ID for the environment
        seed: Base random seed
        env_kwargs: Keyword arguments for QWOPEnv
        max_episode_steps: Maximum steps per episode
        
    Returns:
        Function that creates environment
    """
    def _init():
        # Create environment
        env = QWOPEnv(**env_kwargs, seed=seed + rank)
        
        # Add time limit wrapper
        env = TimeLimit(env, max_episode_steps=max_episode_steps)
        
        # Add monitor wrapper for logging
        env = Monitor(env)
        
        return env
    
    return _init


def load_config(config_path):
    """
    Load training configuration from YAML file.
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Dictionary with configuration
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def create_output_dirs(config, run_id):
    """
    Create output directories for checkpoints, models, and logs.
    
    Args:
        config: Configuration dictionary
        run_id: Unique run identifier
        
    Returns:
        Dictionary with output paths
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{config['algorithm']}_{run_id}_{timestamp}"
    
    # Create directories
    checkpoint_dir = Path(config.get('checkpoint_dir', 'data/checkpoints')) / run_name
    model_dir = Path(config.get('model_dir', 'data/models')) / run_name
    log_dir = Path(config.get('log_dir', 'data/logs')) / run_name
    
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        'run_name': run_name,
        'checkpoint_dir': str(checkpoint_dir),
        'model_dir': str(model_dir),
        'log_dir': str(log_dir),
    }


def train(config_path, run_id='default', resume_from=None):
    """
    Train RL agent with specified configuration.
    
    Args:
        config_path: Path to YAML configuration file
        run_id: Unique identifier for this training run
        resume_from: Optional path to checkpoint to resume from
    """
    print("=" * 70)
    print("QWOP RL TRAINING")
    print("=" * 70)
    print()
    
    # Load configuration
    print(f"Loading config from: {config_path}")
    config = load_config(config_path)
    print(f"Algorithm: {config['algorithm']}")
    print(f"Total timesteps: {config['total_timesteps']:,}")
    print(f"Parallel environments: {config['n_envs']}")
    print()
    
    # Create output directories
    paths = create_output_dirs(config, run_id)
    print(f"Run name: {paths['run_name']}")
    print(f"Checkpoints: {paths['checkpoint_dir']}")
    print(f"Models: {paths['model_dir']}")
    print(f"Logs: {paths['log_dir']}")
    print()
    
    # Create vectorized environments
    print("Creating environments...")
    env_fns = [
        make_env(
            rank=i,
            seed=config.get('seed', 0),
            env_kwargs=config.get('env_kwargs', {}),
            max_episode_steps=config['max_episode_steps']
        )
        for i in range(config['n_envs'])
    ]
    
    venv = SubprocVecEnv(env_fns)
    venv = VecMonitor(venv, filename=str(Path(paths['log_dir']) / 'monitor'))
    print(f"✓ Created {config['n_envs']} parallel environments")
    print()
    
    # Get algorithm class
    algo_name = config['algorithm']
    if algo_name not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algo_name}. Available: {list(ALGORITHMS.keys())}")
    
    AlgorithmClass = ALGORITHMS[algo_name]
    
    # Create or load model
    if resume_from:
        print(f"Resuming from checkpoint: {resume_from}")
        model = AlgorithmClass.load(
            resume_from,
            env=venv,
            tensorboard_log=paths['log_dir'] if config.get('tensorboard', False) else None
        )
        print("✓ Model loaded")
    else:
        print(f"Creating new {algo_name} model...")
        learner_kwargs = config.get('learner_kwargs', {})
        
        model = AlgorithmClass(
            policy="MlpPolicy",
            env=venv,
            tensorboard_log=paths['log_dir'] if config.get('tensorboard', False) else None,
            verbose=0,  # Set to 0 to reduce console output (use TensorBoard)
            **learner_kwargs
        )
        print("✓ Model created")
    
    print()
    print("Model hyperparameters:")
    for key, value in config.get('learner_kwargs', {}).items():
        print(f"  {key}: {value}")
    print()
    
    # Create callbacks
    callbacks = []
    
    # Checkpoint callback
    save_freq = config.get('save_freq', 100_000) // config['n_envs']  # Per environment
    checkpoint_callback = CheckpointCallback(
        save_freq=save_freq,
        save_path=paths['checkpoint_dir'],
        name_prefix='model',
        save_replay_buffer=True,
        save_vecnormalize=True,
    )
    callbacks.append(checkpoint_callback)
    
    callback_list = CallbackList(callbacks)
    
    # Train
    print("=" * 70)
    print("STARTING TRAINING")
    print("=" * 70)
    print()
    
    try:
        model.learn(
            total_timesteps=config['total_timesteps'],
            callback=callback_list,
            progress_bar=False,  # Set to False to avoid tqdm/rich dependency
            reset_num_timesteps=False if resume_from else True,
        )
        
        print()
        print("=" * 70)
        print("TRAINING COMPLETE")
        print("=" * 70)
        print()
        
        # Save final model
        final_model_path = Path(paths['model_dir']) / 'final_model'
        model.save(final_model_path)
        print(f"✓ Final model saved to: {final_model_path}")
        
        # Save configuration
        config_save_path = Path(paths['model_dir']) / 'config.yml'
        with open(config_save_path, 'w') as f:
            yaml.dump(config, f)
        print(f"✓ Configuration saved to: {config_save_path}")
        
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("TRAINING INTERRUPTED")
        print("=" * 70)
        print()
        
        # Save interrupted model
        interrupted_model_path = Path(paths['model_dir']) / 'interrupted_model'
        model.save(interrupted_model_path)
        print(f"✓ Interrupted model saved to: {interrupted_model_path}")
    
    finally:
        # Clean up
        venv.close()
        print()
        print("✓ Training session ended")


def main():
    """Parse arguments and run training."""
    parser = argparse.ArgumentParser(description='Train QWOP RL agent')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to YAML configuration file'
    )
    parser.add_argument(
        '--run-id',
        type=str,
        default='default',
        help='Unique identifier for this training run'
    )
    parser.add_argument(
        '--resume-from',
        type=str,
        default=None,
        help='Path to checkpoint to resume training from'
    )
    
    args = parser.parse_args()
    
    # Check config file exists
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)
    
    # Run training
    train(
        config_path=args.config,
        run_id=args.run_id,
        resume_from=args.resume_from
    )


if __name__ == '__main__':
    main()
