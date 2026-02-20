"""
Runtime verification: Python vs JS spawn and layout parity.

- At spawn (after start): all 12 body positions and angles vs BODY_PARTS (min.js create_player).
- After the first game update: torso worldCenter, camera, ground segment X.
Expected (match QWOP.min.js):
  - Each body position/angle within tolerance of BODY_PARTS
  - initial camera (-200, -200)
  - after 1 update: torso ~ (2.51, -1.87), ground segment X: -32, 0, 32 (meters)

Run from repo root: python -m qwop_python.tools.verify_spawn_layout
"""

from qwop_python.game import QWOPGame
from qwop_python.data import INITIAL_CAMERA_X, INITIAL_CAMERA_Y, BODY_PARTS

# Body order must match physics.create_bodies
BODY_ORDER = [
    "torso", "head",
    "leftArm", "rightArm",
    "leftForearm", "rightForearm",
    "leftThigh", "rightThigh",
    "leftCalf", "rightCalf",
    "leftFoot", "rightFoot",
]

# Tolerances: spawn positions/angles from BODY_PARTS (min.js create_player)
SPAWN_POS_TOL = 1e-6
SPAWN_ANGLE_TOL = 1e-6


def main():
    game = QWOPGame(verbose=False, headless=True)
    game.initialize()
    game.start()

    # Before first update: camera and all 12 body positions/angles vs BODY_PARTS
    print("Spawn/layout parity check:")
    print(f"  initial camera: ({game.camera_x}, {game.camera_y}) [expected ({INITIAL_CAMERA_X}, {INITIAL_CAMERA_Y})]")
    initial_camera_ok = (
        abs(game.camera_x - INITIAL_CAMERA_X) <= 1
        and abs(game.camera_y - INITIAL_CAMERA_Y) <= 1
    )

    spawn_ok = True
    for name in BODY_ORDER:
        body = game.physics.get_body(name)
        if body is None:
            print(f"  FAIL: body '{name}' not found")
            spawn_ok = False
            continue
        gold = BODY_PARTS[name]
        pos = body.position
        px = pos.x if hasattr(pos, "x") else pos[0]
        py = pos.y if hasattr(pos, "y") else pos[1]
        gx, gy = gold["position"]
        ax, ay = body.angle, gold["angle"]
        pos_ok = (
            abs(px - gx) <= SPAWN_POS_TOL and abs(py - gy) <= SPAWN_POS_TOL
        )
        angle_ok = abs(ax - ay) <= SPAWN_ANGLE_TOL
        if not pos_ok or not angle_ok:
            print(f"  {name}: pos ({px},{py}) vs ({gx},{gy}), angle {ax} vs {ay}")
            spawn_ok = False
    if spawn_ok:
        print("  all 12 body positions and angles match BODY_PARTS (min.js create_player)")

    game.update(1 / 60.0)

    torso = game.physics.get_body("torso")
    torso_center = torso.worldCenter if torso else (None, None)
    segment_xs = [b.position[0] for b in game.physics.ground_segments]

    print(f"  after 1 update:")
    print(f"    torso worldCenter: ({torso_center[0]:.4f}, {torso_center[1]:.4f}) [expected ~ (2.51, -1.87)]")
    print(f"    camera: ({game.camera_x}, {game.camera_y}) [follows torso]")
    print(f"    ground segment X (m): {[round(x, 2) for x in segment_xs]} [expected -32, 0, 32]")
    print()

    tol_pos = 0.02
    tol_seg = 0.5
    expected_seg = [-32.0, 0.0, 32.0]
    torso_ok = (
        abs(torso_center[0] - 2.511) <= tol_pos
        and abs(torso_center[1] - (-1.871)) <= tol_pos
    )
    segment_ok = (
        len(segment_xs) == 3
        and all(abs(segment_xs[i] - expected_seg[i]) <= tol_seg for i in range(3))
    )
    ok = initial_camera_ok and spawn_ok and torso_ok and segment_ok
    if not initial_camera_ok:
        print("FAIL: initial camera position mismatch")
    if not spawn_ok:
        print("FAIL: one or more body spawn position/angle mismatch")
    if not torso_ok:
        print("FAIL: torso position mismatch after 1 update")
    if not segment_ok:
        print("FAIL: ground segment positions mismatch")
    if ok:
        print("PASS: spawn and layout match JS 1:1")


if __name__ == "__main__":
    main()
