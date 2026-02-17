"""
Test Trained Model

Run a trained RL model in the Python QWOP environment and validate performance.
This script tests:
1. Model loading
2. Observation extraction
3. Action execution
4. Episode completion
5. Performance metrics

Visual validation: Watch the agent play and verify it looks reasonable
Metric validation: Compare distance, time, success rate with expected values
Deterministic validation: Same seed should produce same results
"""

import sys
import os
import time
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from game import QWOPGame
from observations import ObservationExtractor
from actions import ActionMapper
from rl_interface import RLAgent
from renderer import QWOPRenderer

# Try to import pygame for rendering
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not available, rendering disabled")


class EpisodeMetrics:
    """Track metrics for an episode."""
    
    def __init__(self):
        self.distance = 0.0
        self.time = 0.0
        self.success = False
        self.fallen = False
        self.actions = []
        self.observations = []
        self.num_steps = 0
    
    def __str__(self):
        status = "SUCCESS" if self.success else ("FALLEN" if self.fallen else "RUNNING")
        return (f"Distance: {self.distance:.2f}m, Time: {self.time:.2f}s, "
                f"Steps: {self.num_steps}, Status: {status}")


def run_episode(game, agent, obs_extractor, action_mapper, renderer=None, 
                max_steps=10000, render=True, seed=None, verbose=True, 
                frames_per_step=1):
    """
    Run a single episode with a trained agent.
    
    Args:
        game: QWOPGame instance
        agent: RLAgent instance
        obs_extractor: ObservationExtractor instance
        action_mapper: ActionMapper instance
        renderer: QWOPRenderer instance (optional)
        max_steps: Maximum steps before truncating episode
        render: Whether to render (requires pygame)
        seed: Optional seed for episode
        verbose: Print progress
        frames_per_step: Number of game frames per action (default 1)
        
    Returns:
        EpisodeMetrics instance
    """
    metrics = EpisodeMetrics()
    
    # Reset game
    game.reset(seed=seed)
    game.start()
    
    if verbose:
        print(f"\nRunning episode (seed={seed})...")
    
    # Game loop
    step = 0
    clock = None
    if render and renderer is not None and PYGAME_AVAILABLE:
        clock = pygame.time.Clock()
    
    while step < max_steps:
        # Handle pygame events if rendering
        if render and PYGAME_AVAILABLE:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return metrics
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return metrics
        
        # Extract observation
        obs = obs_extractor.extract(game.physics)
        metrics.observations.append(obs.copy())
        
        # Get action from agent
        action = agent.predict(obs)
        metrics.actions.append(action)
        
        # Apply action and run for frames_per_step frames
        action_mapper.apply_action(action, game.controls)
        
        for _ in range(frames_per_step):
            # Update game
            game.update(1/30.0)  # 30 FPS
            
            # Check termination after each frame
            if game.game_state.game_ended:
                break
        
        # Render
        if render and renderer is not None:
            renderer.render(game)
            pygame.display.flip()  # Actually update the display
            if clock is not None:
                clock.tick(30)  # Cap at 30 FPS
        
        # Update metrics
        metrics.num_steps = step + 1
        metrics.distance = game.game_state.score
        metrics.time = game.score_time
        metrics.success = game.game_state.jump_landed and not game.game_state.fallen
        metrics.fallen = game.game_state.fallen
        
        # Check termination
        if game.game_state.game_ended:
            break
        
        step += 1
        
        # Print progress
        if verbose and step % 100 == 0:
            print(f"  Step {step}: {metrics}")
    
    if verbose:
        print(f"  Final: {metrics}")
    
    return metrics


def run_multiple_episodes(model_path, num_episodes=5, render=True, 
                         seed=10000, check_determinism=True, frames_per_step=4,
                         reduced_action_set=True):
    """
    Run multiple episodes and collect statistics.
    
    Args:
        model_path: Path to trained model
        num_episodes: Number of episodes to run
        render: Whether to render episodes
        seed: Base seed (incremented for each episode)
        check_determinism: Run episode twice with same seed to verify determinism
        frames_per_step: Number of game frames per action (default 4 for QRDQN-PROVEN)
        reduced_action_set: Use reduced 9-action set (default True for QRDQN-PROVEN)
        
    Returns:
        List of EpisodeMetrics
    """
    print("\n" + "="*70)
    print("TRAINED MODEL TEST")
    print("="*70)
    print(f"Model: {model_path}")
    print(f"Episodes: {num_episodes}")
    print(f"Rendering: {render}")
    print(f"Base seed: {seed}")
    print(f"Frames per step: {frames_per_step}")
    print(f"Reduced action set: {reduced_action_set}")
    print("="*70)
    
    # Initialize components
    print("\nInitializing...")
    
    # Load model
    agent = RLAgent(model_path, deterministic=True)
    
    # Create game components
    game = QWOPGame(seed=seed)
    game.initialize()
    
    obs_extractor = ObservationExtractor()
    action_mapper = ActionMapper(reduced_action_set=reduced_action_set)
    
    renderer = None
    if render and PYGAME_AVAILABLE:
        pygame.init()
        screen = pygame.display.set_mode((640, 400))
        pygame.display.set_caption("QWOP - RL Agent Test")
        renderer = QWOPRenderer(screen)
    
    print("✓ Initialization complete")
    
    # Run episodes
    all_metrics = []
    
    for i in range(num_episodes):
        episode_seed = seed + i
        print(f"\n{'='*70}")
        print(f"Episode {i+1}/{num_episodes}")
        print(f"{'='*70}")
        
        metrics = run_episode(game, agent, obs_extractor, action_mapper, 
                            renderer, seed=episode_seed, render=render,
                            frames_per_step=frames_per_step)
        all_metrics.append(metrics)
        
        time.sleep(0.5)  # Brief pause between episodes
    
    # Determinism check
    if check_determinism and num_episodes > 0:
        print(f"\n{'='*70}")
        print("DETERMINISM CHECK")
        print(f"{'='*70}")
        print("Running episode 1 again with same seed...")
        
        metrics2 = run_episode(game, agent, obs_extractor, action_mapper,
                             renderer=None, seed=seed, render=False, verbose=False,
                             frames_per_step=frames_per_step)
        
        metrics1 = all_metrics[0]
        
        # Compare
        if len(metrics1.actions) == len(metrics2.actions):
            actions_match = all(a1 == a2 for a1, a2 in zip(metrics1.actions, metrics2.actions))
            obs_diff = np.max([np.max(np.abs(o1 - o2)) 
                              for o1, o2 in zip(metrics1.observations, metrics2.observations)])
            
            print(f"  Actions match: {actions_match}")
            print(f"  Max observation diff: {obs_diff:.2e}")
            print(f"  Distance diff: {abs(metrics1.distance - metrics2.distance):.6f}")
            
            if actions_match and obs_diff < 1e-6:
                print("  ✓ DETERMINISTIC: Results are identical")
            else:
                print("  ⚠️  WARNING: Results differ (may indicate non-determinism)")
        else:
            print(f"  ❌ Episode lengths differ: {len(metrics1.actions)} vs {len(metrics2.actions)}")
    
    # Summary statistics
    print(f"\n{'='*70}")
    print("SUMMARY STATISTICS")
    print(f"{'='*70}")
    
    distances = [m.distance for m in all_metrics]
    times = [m.time for m in all_metrics]
    successes = [m.success for m in all_metrics]
    
    print(f"Episodes: {len(all_metrics)}")
    print(f"\nDistance:")
    print(f"  Mean: {np.mean(distances):.2f}m")
    print(f"  Std:  {np.std(distances):.2f}m")
    print(f"  Min:  {np.min(distances):.2f}m")
    print(f"  Max:  {np.max(distances):.2f}m")
    
    print(f"\nTime:")
    print(f"  Mean: {np.mean(times):.2f}s")
    print(f"  Std:  {np.std(times):.2f}s")
    print(f"  Min:  {np.min(times):.2f}s")
    print(f"  Max:  {np.max(times):.2f}s")
    
    success_rate = np.mean(successes) * 100
    print(f"\nSuccess Rate: {success_rate:.1f}% ({sum(successes)}/{len(successes)})")
    
    print("="*70)
    
    # Cleanup
    if renderer is not None and PYGAME_AVAILABLE:
        pygame.quit()
    
    return all_metrics


def quick_test(model_path, seed=10000):
    """
    Quick test without rendering - just verify model can run.
    
    Args:
        model_path: Path to trained model
        seed: Seed to use
        
    Returns:
        True if test passes, False otherwise
    """
    print("\n" + "="*70)
    print("QUICK TEST (No Rendering)")
    print("="*70)
    
    # Set SDL to not require video (for headless testing)
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    
    try:
        # Load model
        print("Loading model...")
        agent = RLAgent(model_path, deterministic=True)
        print("✓ Model loaded")
        
        # Create game
        print("Initializing game...")
        game = QWOPGame(seed=seed)
        game.initialize()
        obs_extractor = ObservationExtractor()
        action_mapper = ActionMapper(reduced_action_set=True)  # QRDQN-PROVEN uses reduced
        print("✓ Game initialized")
        
        # Run brief episode (no rendering, no pygame)
        frames_per_step = 4  # QRDQN-PROVEN uses 4 frames per step
        print(f"Running test episode (300 steps, {frames_per_step} frames/step)...")
        game.reset(seed=seed)
        game.start()
        
        step = 0
        max_steps = 300
        
        while step < max_steps:
            # Extract observation
            obs = obs_extractor.extract(game.physics)
            
            # Get action from agent
            action = agent.predict(obs)
            
            # Apply action for multiple frames
            action_mapper.apply_action(action, game.controls)
            
            for _ in range(frames_per_step):
                # Update game
                game.update(1/30.0)
                
                if game.game_state.game_ended:
                    break
            
            # Check termination
            if game.game_state.game_ended:
                break
            
            step += 1
            
            if step % 100 == 0:
                print(f"  Step {step}: Distance={game.game_state.score:.2f}m, Time={game.score_time:.2f}s")
        
        # Collect final metrics
        distance = game.game_state.score
        time_elapsed = game.score_time
        success = game.game_state.jump_landed and not game.game_state.fallen
        fallen = game.game_state.fallen
        
        print(f"\n✓ Test completed successfully")
        print(f"  Distance: {distance:.2f}m")
        print(f"  Time: {time_elapsed:.2f}s")
        print(f"  Steps: {step}")
        print(f"  Success: {success}")
        print(f"  Fallen: {fallen}")
        
        # Basic validation
        if distance < 0 or distance > 110:
            print(f"  ⚠️  Warning: Distance out of expected range: {distance:.2f}m")
        
        if step == 0:
            print(f"  ❌ Error: No steps executed")
            return False
        
        print("\n✓ All checks passed")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test trained QWOP model")
    parser.add_argument('model_path', type=str, 
                       help='Path to model .zip file')
    parser.add_argument('--episodes', type=int, default=3,
                       help='Number of episodes to run (default: 3)')
    parser.add_argument('--seed', type=int, default=10000,
                       help='Random seed (default: 10000)')
    parser.add_argument('--no-render', action='store_true',
                       help='Disable rendering')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test only (no rendering, 1 episode)')
    parser.add_argument('--frames-per-step', type=int, default=4,
                       help='Frames per step (default: 4 for QRDQN-PROVEN)')
    parser.add_argument('--full-actions', action='store_true',
                       help='Use full 16-action set instead of reduced 9-action set')
    
    args = parser.parse_args()
    
    # Check model exists
    if not os.path.exists(args.model_path):
        print(f"Error: Model file not found: {args.model_path}")
        print("\nAvailable models in qwop-wr/data:")
        
        qwop_wr_data = "/Users/b407404/Desktop/Misc/qwop-wr/data"
        if os.path.exists(qwop_wr_data):
            from rl_interface import print_model_list
            print_model_list(qwop_wr_data)
        
        return 1
    
    # Run test
    if args.quick:
        success = quick_test(args.model_path, args.seed)
        return 0 if success else 1
    else:
        render = not args.no_render and PYGAME_AVAILABLE
        if args.no_render:
            print("Rendering disabled by user")
        elif not PYGAME_AVAILABLE:
            print("Rendering disabled (pygame not available)")
        
        metrics = run_multiple_episodes(
            args.model_path,
            num_episodes=args.episodes,
            render=render,
            seed=args.seed,
            frames_per_step=args.frames_per_step,
            reduced_action_set=not args.full_actions
        )
        
        return 0


if __name__ == "__main__":
    sys.exit(main())
