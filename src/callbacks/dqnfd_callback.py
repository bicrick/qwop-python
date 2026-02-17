"""
DQN from Demonstrations (DQNfD) Callback for Stable-Baselines3.

This callback injects expert demonstrations into the replay buffer during
training, following Wesley Liao's approach to break through the knee-scraping
plateau in QWOP.

Based on: https://wesleyliao.medium.com/achieving-super-human-performance-in-qwop-9a4b968c4cc9
"""

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback


class DQNfDCallback(BaseCallback):
    """
    Injects expert demonstrations into the replay buffer during training.

    This implements the hybrid replay buffer approach from Wesley Liao's
    DQNfD agent, where expert transitions are mixed with the agent's own
    experience during training (not just pre-training).

    The key insight: continuously exposing the agent to expert behavior
    during training prevents it from forgetting good techniques while it
    explores variations.

    Args:
        demo_file: Path to .npz file containing demonstrations
            Expected keys: 'obs', 'actions', 'rewards', 'next_obs', 'dones'
        injection_ratio: Fraction of steps that inject expert transitions
            0.5 = inject 1 expert transition per 2 agent steps (Wesley's ratio)
            1.0 = inject 1 expert transition per agent step
            0.25 = inject 1 expert transition per 4 agent steps
        verbose: Whether to print injection progress (default: 1)

    Example:
        >>> callback = DQNfDCallback(
        ...     demo_file="data/expert_demos.npz",
        ...     injection_ratio=0.5,  # 50/50 mix
        ... )
        >>> model.learn(total_timesteps=10_000_000, callback=callback)
    """

    def __init__(
        self,
        demo_file: str,
        injection_ratio: float = 0.5,
        verbose: int = 1,
    ):
        super().__init__(verbose)

        # Load demonstrations
        print(f"Loading demonstrations from {demo_file}")
        demos = np.load(demo_file)

        self.demo_obs = demos["obs"]
        self.demo_actions = demos["actions"]
        self.demo_rewards = demos["rewards"]
        self.demo_next_obs = demos["next_obs"]
        self.demo_dones = demos["dones"]

        self.n_demos = len(self.demo_actions)
        self.demo_idx = 0
        self.demo_epoch = 0

        # Injection parameters
        self.injection_ratio = injection_ratio
        self.injection_interval = max(1, int(1 / injection_ratio))

        # Statistics
        self.total_injections = 0
        self.last_log_step = 0

        print(f"Loaded {self.n_demos} demonstration transitions")
        print(f"Injection ratio: {injection_ratio} (1 demo per {self.injection_interval} steps)")

    def _on_training_start(self) -> None:
        """Called at the beginning of training."""
        # Verify replay buffer exists
        if not hasattr(self.model, "replay_buffer") or self.model.replay_buffer is None:
            raise ValueError(
                "DQNfDCallback requires a model with a replay buffer. "
                "This callback is compatible with DQN, QRDQN, and similar off-policy algorithms."
            )

        # Log initial state
        if self.verbose > 0:
            print(f"\nDQNfD training started:")
            print(f"  Replay buffer size: {self.model.replay_buffer.buffer_size}")
            print(f"  Demonstrations: {self.n_demos} transitions")
            print(f"  Injection interval: {self.injection_interval} steps")

    def _on_step(self) -> bool:
        """
        Called after each environment step.

        Injects expert demonstrations into the replay buffer at the configured
        injection_ratio.

        Returns:
            True to continue training, False to stop
        """
        # Check if we should inject a demonstration this step
        if self.num_timesteps % self.injection_interval == 0:
            self._inject_demonstration()
            self.total_injections += 1

        # Log progress periodically
        if self.verbose > 0 and self.num_timesteps - self.last_log_step >= 50000:
            self._log_progress()
            self.last_log_step = self.num_timesteps

        return True

    def _inject_demonstration(self) -> None:
        """
        Inject one expert transition into the replay buffer.

        The demonstration is added exactly like a transition from the agent's
        own experience, so the learning algorithm treats it identically.
        """
        # Get current demonstration transition
        obs = self.demo_obs[self.demo_idx]
        action = self.demo_actions[self.demo_idx]
        reward = self.demo_rewards[self.demo_idx]
        next_obs = self.demo_next_obs[self.demo_idx]
        done = self.demo_dones[self.demo_idx]

        # Add to replay buffer
        # Note: SB3 replay buffers expect arrays with batch dimension
        self.model.replay_buffer.add(
            obs=obs.reshape(1, -1),
            next_obs=next_obs.reshape(1, -1),
            action=np.array([action]),
            reward=np.array([reward]),
            done=np.array([done]),
            infos=[{}],
        )

        # Move to next demonstration (cycle through)
        self.demo_idx += 1
        if self.demo_idx >= self.n_demos:
            self.demo_idx = 0
            self.demo_epoch += 1
            if self.verbose > 0:
                print(f"  [DQNfD] Completed epoch {self.demo_epoch} of demonstration data")

    def _log_progress(self) -> None:
        """Log injection statistics."""
        agent_steps = self.num_timesteps
        demo_ratio = self.total_injections / agent_steps if agent_steps > 0 else 0

        print(
            f"  [DQNfD] Step {agent_steps}: "
            f"injected {self.total_injections} demos "
            f"(ratio: {demo_ratio:.3f})"
        )

    def _on_training_end(self) -> None:
        """Called at the end of training."""
        if self.verbose > 0 and self.num_timesteps > 0:
            print(f"\nDQNfD training complete:")
            print(f"  Total agent steps: {self.num_timesteps}")
            print(f"  Total demonstrations injected: {self.total_injections}")
            print(f"  Final demo/agent ratio: {self.total_injections / self.num_timesteps:.3f}")
            print(f"  Completed {self.demo_epoch} epochs of demonstration data")
