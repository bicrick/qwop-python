"""Interactive gameplay for QWOP."""

import pygame

from ..game import QWOPGame
from ..renderer import QWOPRenderer
from ..data import SCREEN_WIDTH, SCREEN_HEIGHT


KEY_MAP = {
    pygame.K_q: "q",
    pygame.K_w: "w",
    pygame.K_o: "o",
    pygame.K_p: "p",
}


def run_play():
    """
    Main game loop. Runs at 30 FPS matching original QWOP.
    Physics runs at fixed 25 FPS (0.04s timestep) internally.
    """
    pygame.init()

    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("QWOP - Python Recreation")
    clock = pygame.time.Clock()

    print()
    print("=" * 70)
    print("QWOP - PYTHON RECREATION")
    print("=" * 70)
    print()

    game = QWOPGame(verbose=True, headless=False)
    game.initialize()
    renderer = QWOPRenderer(screen)

    print()
    print("=" * 70)
    print("CONTROLS")
    print("=" * 70)
    print("Q - Right thigh forward, left thigh back")
    print("W - Left thigh forward, right thigh back")
    print("O - Right calf forward, left calf back")
    print("P - Left calf forward, right calf back")
    print("R or Space - Reset game")
    print("ESC - Quit")
    print("=" * 70)
    print()
    print("Click or press Q/W/O/P to start!")
    print()

    running = True

    try:
        while running:
            dt = clock.tick(30) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if not game.first_click:
                        game.start()
                elif event.type == pygame.KEYDOWN:
                    if event.key in KEY_MAP:
                        key_char = KEY_MAP[event.key]
                        game.controls.key_down(key_char)
                        if not game.first_click:
                            game.start()
                    elif event.key in (pygame.K_r, pygame.K_SPACE):
                        game.reset()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                elif event.type == pygame.KEYUP:
                    if event.key in KEY_MAP:
                        game.controls.key_up(KEY_MAP[event.key])

            game.update(dt)
            renderer.render(game)
            pygame.display.flip()

    except KeyboardInterrupt:
        print("\nGame interrupted by user")
    except Exception as e:
        print(f"\nError during game loop: {e}")
        import traceback

        traceback.print_exc()
    finally:
        pygame.quit()
        print("\nThanks for playing QWOP!")
