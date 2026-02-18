"""
Quick check: print initial observation from Python env to verify format.
"""
import sys
import os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from qwop_gym_env import QWOPPythonEnv

env = QWOPPythonEnv(frames_per_step=4, reduced_action_set=True)
obs, info = env.reset(seed=42)
env.close()

print("Initial observation (normalized):")
print(f"  shape: {obs.shape}, dtype: {obs.dtype}")
print(f"  mean: {obs.mean():.4f}, std: {obs.std():.4f}")
print(f"  min: {obs.min():.4f}, max: {obs.max():.4f}")
print(f"  Torso (indices 0-4): pos_x={obs[0]:.4f} pos_y={obs[1]:.4f} angle={obs[2]:.4f} vel_x={obs[3]:.4f} vel_y={obs[4]:.4f}")
print(f"  Info: distance={info['distance']:.2f} time={info['time']:.2f}")
