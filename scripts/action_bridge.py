"""
Bridge between qwop-wr discrete actions and qwop-python key-state controls.

Maps discrete action indices to Q/W/O/P key sets and applies them to ControlsHandler.
"""

import itertools
import functools

# WSProto.CMD_K_* values from qwop-wr wsproto.py
CMD_K_Q = 0b00000010
CMD_K_W = 0b00000100
CMD_K_O = 0b00001000
CMD_K_P = 0b00010000

KEYMAP = {"q": CMD_K_Q, "w": CMD_K_W, "o": CMD_K_O, "p": CMD_K_P}
KEYMAP_INV = {CMD_K_Q: "q", CMD_K_W: "w", CMD_K_O: "o", CMD_K_P: "p"}


def _build_action_cmdflags(reduced):
    """Build action index -> cmdflags mapping matching qwop-wr QwopEnv._set_keycodes."""
    keyflags = list(KEYMAP.values())
    keyflags_c = (
        list(itertools.combinations(keyflags, 0))
        + list(itertools.combinations(keyflags, 1))
        + list(itertools.combinations(keyflags, 2))
        + list(itertools.combinations(keyflags, 3))
        + list(itertools.combinations(keyflags, 4))
    )
    if reduced:
        redundant = [
            (CMD_K_Q, CMD_K_O),
            (CMD_K_W, CMD_K_P),
            (CMD_K_Q, CMD_K_W, CMD_K_O),
            (CMD_K_Q, CMD_K_W, CMD_K_P),
            (CMD_K_Q, CMD_K_O, CMD_K_P),
            (CMD_K_W, CMD_K_O, CMD_K_P),
            (CMD_K_Q, CMD_K_W, CMD_K_O, CMD_K_P),
        ]
        keyflags_c = [t for t in keyflags_c if t not in redundant]
    action_cmdflags = [
        functools.reduce(lambda a, e: a | e, t, 0) for t in keyflags_c
    ]
    return action_cmdflags


ACTION_CMDFLAGS_FULL = _build_action_cmdflags(reduced=False)
ACTION_CMDFLAGS_REDUCED = _build_action_cmdflags(reduced=True)


def action_to_keys(discrete_action, reduced=True):
    """
    Map discrete action index to set of key names held.

    Args:
        discrete_action: Action index (0..15 full, 0..8 reduced).
        reduced: Use reduced action set (default True).

    Returns:
        frozenset of "q", "w", "o", "p" (empty for noop).
    """
    mapping = ACTION_CMDFLAGS_REDUCED if reduced else ACTION_CMDFLAGS_FULL
    if discrete_action < 0 or discrete_action >= len(mapping):
        return frozenset()
    cmdflags = mapping[discrete_action]
    keys = set()
    for flag, k in KEYMAP_INV.items():
        if cmdflags & flag:
            keys.add(k)
    return frozenset(keys)


def apply_keys_to_controls(controls, keys_prev, keys_now):
    """
    Update ControlsHandler to reflect key state change.

    Calls key_up for keys released and key_down for keys pressed.

    Args:
        controls: ControlsHandler instance.
        keys_prev: Previous key set (frozenset or set of "q","w","o","p").
        keys_now: Current key set.
    """
    keys_prev = set(keys_prev) if keys_prev else set()
    keys_now = set(keys_now) if keys_now else set()
    for k in keys_prev - keys_now:
        controls.key_up(k)
    for k in keys_now - keys_prev:
        controls.key_down(k)


def key_sequence_to_actions(key_sequences):
    """
    Convert list of key sets to discrete action indices (reduced set).

    Args:
        key_sequences: List of sets/frozensets of "q","w","o","p".

    Returns:
        List of action indices.
    """
    keys_to_cmd = lambda ks: functools.reduce(
        lambda a, e: a | KEYMAP[e], ks or set(), 0
    )
    cmd_to_action = {c: i for i, c in enumerate(ACTION_CMDFLAGS_REDUCED)}
    out = []
    for ks in key_sequences:
        cmd = keys_to_cmd(ks)
        out.append(cmd_to_action.get(cmd, 0))
    return out
