"""
QWOP RL Interface - Model Loading and Inference

Provides interface for loading and running Stable-Baselines3 trained models
with the Python QWOP implementation.

Supports:
- QRDQN and EnhancedQRDQN (EQRDQN) models
- DQN, PPO, A2C, SAC models from Stable-Baselines3
- Model loading from .zip checkpoints
- Prediction interface matching QWOPGYM
"""

import os
import importlib
import numpy as np


class ModelLoader:
    """
    Loads and manages Stable-Baselines3 models for QWOP.
    
    Supports loading models from the qwop-wr repository trained on QWOPGYM.
    """
    
    # Map algorithm names to (module, class) tuples
    ALGORITHMS = {
        'QRDQN': ('sb3_contrib', 'QRDQN'),
        # Note: EQRDQN is same as QRDQN with some enhancements, but the base
        # QRDQN class can load EQRDQN models (they're compatible)
        'EQRDQN': ('sb3_contrib', 'QRDQN'),
        'DQN': ('stable_baselines3', 'DQN'),
        'PPO': ('stable_baselines3', 'PPO'),
        'A2C': ('stable_baselines3', 'A2C'),
        'SAC': ('stable_baselines3', 'SAC'),
        'RPPO': ('sb3_contrib', 'RecurrentPPO'),
    }
    
    @staticmethod
    def load_model(model_path, algorithm=None):
        """
        Load a trained model from file.
        
        Args:
            model_path: Path to model .zip file
            algorithm: Algorithm name (e.g., 'QRDQN', 'PPO'). 
                      If None, infers from model_path.
        
        Returns:
            Loaded model instance
            
        Raises:
            ValueError: If algorithm not supported or model file not found
            ImportError: If required packages not installed
        """
        if not os.path.exists(model_path):
            raise ValueError(f"Model file not found: {model_path}")
        
        # Infer algorithm from path if not provided
        if algorithm is None:
            algorithm = ModelLoader._infer_algorithm(model_path)
        
        # Get module and class name
        if algorithm not in ModelLoader.ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}. "
                           f"Supported: {list(ModelLoader.ALGORITHMS.keys())}")
        
        module_name, class_name = ModelLoader.ALGORITHMS[algorithm]
        
        print(f"Loading {algorithm} model from: {model_path}")
        print(f"  Module: {module_name}")
        print(f"  Class: {class_name}")
        
        try:
            # Import module
            module = importlib.import_module(module_name)
            
            # Get model class
            model_class = getattr(module, class_name)
            
            # Load model
            model = model_class.load(model_path)
            
            print(f"✓ Model loaded successfully")
            return model
            
        except ImportError as e:
            raise ImportError(
                f"Failed to import {module_name}.{class_name}. "
                f"Make sure required packages are installed: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")
    
    @staticmethod
    def _infer_algorithm(model_path):
        """
        Infer algorithm from model path.
        
        Args:
            model_path: Path to model file or directory
            
        Returns:
            Algorithm name string
        """
        # Extract directory name or filename
        path = os.path.normpath(model_path)
        parts = path.split(os.sep)
        
        # Look for algorithm name in path
        for part in reversed(parts):
            part_upper = part.upper()
            
            # Special cases first
            # DQNfD and EQRDQN both use QRDQN (EQRDQN is just QRDQN with PER)
            if 'DQNFD' in part_upper or 'EQRDQN' in part_upper:
                return 'QRDQN'
            
            # Check other algorithms
            for algo in ModelLoader.ALGORITHMS.keys():
                if part_upper.startswith(algo):
                    return algo
        
        # Default to QRDQN (most common in qwop-wr)
        print(f"Warning: Could not infer algorithm from path, defaulting to QRDQN")
        return 'QRDQN'


class RLAgent:
    """
    Wrapper for running RL agents in QWOP.
    
    Provides a simple interface for:
    - Loading models
    - Getting actions from observations
    - Tracking episode statistics
    """
    
    def __init__(self, model_path, algorithm=None, deterministic=True):
        """
        Initialize RL agent.
        
        Args:
            model_path: Path to trained model .zip file
            algorithm: Algorithm name (optional, auto-detected if None)
            deterministic: If True, use deterministic policy (no exploration)
        """
        self.model = ModelLoader.load_model(model_path, algorithm)
        self.deterministic = deterministic
        self.reset_stats()
    
    def predict(self, observation):
        """
        Get action from observation.
        
        Args:
            observation: Numpy array observation (60 floats, normalized)
            
        Returns:
            action: Integer action index
        """
        action, _states = self.model.predict(observation, deterministic=self.deterministic)
        
        # Convert to int if it's an array
        if isinstance(action, np.ndarray):
            action = int(action.item())
        else:
            action = int(action)
        
        self.total_steps += 1
        
        return action
    
    def reset_stats(self):
        """Reset episode statistics."""
        self.total_steps = 0
        self.episodes = 0
    
    def get_stats(self):
        """Get agent statistics."""
        return {
            'total_steps': self.total_steps,
            'episodes': self.episodes,
        }


def list_available_models(data_dir):
    """
    List all available trained models in a directory.
    
    Args:
        data_dir: Directory containing model subdirectories (e.g., qwop-wr/data/)
        
    Returns:
        List of dicts with model info: {name, path, algorithm, checkpoints}
    """
    if not os.path.exists(data_dir):
        return []
    
    models = []
    
    for entry in os.listdir(data_dir):
        entry_path = os.path.join(data_dir, entry)
        
        if not os.path.isdir(entry_path):
            continue
        
        # Look for model.zip
        model_file = os.path.join(entry_path, 'model.zip')
        if not os.path.exists(model_file):
            # Try to find any .zip file
            zip_files = [f for f in os.listdir(entry_path) if f.endswith('.zip')]
            if not zip_files:
                continue
            model_file = os.path.join(entry_path, zip_files[0])
        
        # Count checkpoint files
        checkpoints = [f for f in os.listdir(entry_path) 
                      if f.endswith('.zip') and 'steps' in f]
        
        # Infer algorithm
        algorithm = ModelLoader._infer_algorithm(entry)
        
        models.append({
            'name': entry,
            'path': model_file,
            'algorithm': algorithm,
            'num_checkpoints': len(checkpoints),
            'checkpoints': sorted(checkpoints),
        })
    
    return sorted(models, key=lambda x: x['name'])


def print_model_list(data_dir):
    """
    Print formatted list of available models.
    
    Args:
        data_dir: Directory containing model subdirectories
    """
    models = list_available_models(data_dir)
    
    if not models:
        print(f"No models found in {data_dir}")
        return
    
    print(f"\nAvailable Models in {data_dir}:")
    print("="*80)
    print(f"{'Name':<40} {'Algorithm':<12} {'Checkpoints':<12}")
    print("-"*80)
    
    for model in models:
        print(f"{model['name']:<40} {model['algorithm']:<12} {model['num_checkpoints']:<12}")
    
    print("="*80)
    print(f"Total: {len(models)} models")


if __name__ == "__main__":
    """Example usage and testing."""
    import sys
    
    # Example: List models from qwop-wr data directory
    qwop_wr_data = "/Users/b407404/Desktop/Misc/qwop-wr/data"
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            print_model_list(qwop_wr_data)
        elif sys.argv[1] == "load":
            if len(sys.argv) < 3:
                print("Usage: python rl_interface.py load <model_path>")
                sys.exit(1)
            
            model_path = sys.argv[2]
            try:
                agent = RLAgent(model_path)
                print(f"\n✓ Successfully loaded model")
                print(f"  Observation space: {agent.model.observation_space}")
                print(f"  Action space: {agent.model.action_space}")
                
                # Test prediction with dummy observation
                dummy_obs = np.zeros(60, dtype=np.float32)
                action = agent.predict(dummy_obs)
                print(f"\n  Test prediction with zero observation: action = {action}")
                
            except Exception as e:
                print(f"\n❌ Failed to load model: {e}")
                sys.exit(1)
    else:
        print("Usage:")
        print("  python rl_interface.py list")
        print("  python rl_interface.py load <model_path>")
        print("\nExample:")
        print(f"  python rl_interface.py list")
        print(f"  python rl_interface.py load {qwop_wr_data}/QRDQN-PROVEN-k3jlgned/model.zip")
