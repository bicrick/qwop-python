"""
QWOP Action Mapping - RL Interface

Maps discrete action indices to Q/W/O/P key combinations for RL agents.
Implements the exact action space used by QWOPGYM.

Action space:
- 16 discrete actions (full set) or 9 actions (reduced set)
- Each action represents a unique combination of Q/W/O/P keys
"""

import itertools


class ActionMapper:
    """
    Maps discrete action indices to QWOP key combinations.
    
    Supports both full (16 actions) and reduced (9 actions) action sets
    matching QWOPGYM's implementation.
    
    Full action set (16 actions):
    0: none
    1-4: Q, W, O, P
    5-10: QW, QO, QP, WO, WP, OP
    11-14: QWO, QWP, QOP, WOP
    15: QWOP
    
    Reduced action set (9 actions):
    0: none
    1-4: Q, W, O, P
    5-8: QW, QP, WO, OP
    (Removes redundant combinations: QO, WP, QWO, QWP, QOP, WOP, QWOP)
    """
    
    def __init__(self, reduced_action_set=False):
        """
        Initialize action mapper.
        
        Args:
            reduced_action_set: If True, use 9 actions instead of 16
        """
        self.reduced_action_set = reduced_action_set
        self.action_to_keys = self._build_action_map()
        self.num_actions = len(self.action_to_keys)
    
    def _build_action_map(self):
        """
        Build mapping from action index to key combination.
        
        Returns:
            List where index is action and value is dict of key states
        """
        keys = ['q', 'w', 'o', 'p']
        
        # Generate all combinations using itertools.combinations
        # This matches QWOPGYM's exact approach
        key_combinations = (
            list(itertools.combinations(keys, 0)) +  # 1: none
            list(itertools.combinations(keys, 1)) +  # 4: Q, W, O, P
            list(itertools.combinations(keys, 2)) +  # 6: QW, QO, QP, WO, WP, OP
            list(itertools.combinations(keys, 3)) +  # 4: QWO, QWP, QOP, WOP
            list(itertools.combinations(keys, 4))    # 1: QWOP
        )
        
        if self.reduced_action_set:
            # Remove redundant combinations
            # These are considered redundant because they don't add useful control
            redundant = [
                ('q', 'o'),      # QO
                ('w', 'p'),      # WP
                ('q', 'w', 'o'), # QWO
                ('q', 'w', 'p'), # QWP
                ('q', 'o', 'p'), # QOP
                ('w', 'o', 'p'), # WOP
                ('q', 'w', 'o', 'p')  # QWOP
            ]
            key_combinations = [c for c in key_combinations if c not in redundant]
        
        # Convert combinations to action map
        action_map = []
        for combo in key_combinations:
            action = {
                'q': 'q' in combo,
                'w': 'w' in combo,
                'o': 'o' in combo,
                'p': 'p' in combo
            }
            action_map.append(action)
        
        return action_map
    
    def apply_action(self, action_index, controls_handler):
        """
        Apply action to controls handler.
        
        Args:
            action_index: Integer action index (0 to num_actions-1)
            controls_handler: ControlsHandler instance
            
        Raises:
            ValueError: If action_index is out of range
        """
        if action_index < 0 or action_index >= self.num_actions:
            raise ValueError(f"Action index {action_index} out of range [0, {self.num_actions-1}]")
        
        keys = self.action_to_keys[action_index]
        
        # Set all key states on controls handler
        controls_handler.q_down = keys['q']
        controls_handler.w_down = keys['w']
        controls_handler.o_down = keys['o']
        controls_handler.p_down = keys['p']
    
    def get_action_name(self, action_index):
        """
        Get human-readable name for action.
        
        Args:
            action_index: Integer action index
            
        Returns:
            String like "Q", "WO", "QWOP", or "none"
        """
        if action_index < 0 or action_index >= self.num_actions:
            return "invalid"
        
        keys = self.action_to_keys[action_index]
        pressed = [k.upper() for k, v in keys.items() if v]
        
        if not pressed:
            return "none"
        return "".join(pressed)
    
    def get_all_action_names(self):
        """
        Get list of all action names.
        
        Returns:
            List of action names in order
        """
        return [self.get_action_name(i) for i in range(self.num_actions)]
    
    def action_from_keys(self, q=False, w=False, o=False, p=False):
        """
        Get action index from key states.
        
        Useful for converting keyboard input or demonstrations to actions.
        
        Args:
            q, w, o, p: Boolean key states
            
        Returns:
            Action index, or None if combination not in action space
        """
        target = {'q': q, 'w': w, 'o': o, 'p': p}
        
        for i, keys in enumerate(self.action_to_keys):
            if keys == target:
                return i
        
        return None
    
    def print_action_space(self):
        """Print all actions in the action space (for debugging)."""
        print(f"Action space: {self.num_actions} actions")
        print(f"Reduced set: {self.reduced_action_set}")
        print("\nActions:")
        for i in range(self.num_actions):
            name = self.get_action_name(i)
            keys = self.action_to_keys[i]
            pressed = [k.upper() for k, v in keys.items() if v]
            print(f"  {i:2d}: {name:6s} -> {pressed if pressed else ['none']}")
