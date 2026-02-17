#!/usr/bin/env python3
"""
QWOP - Python Recreation

Main entry point that ties all subsystems together into a playable game.
Implements exact timing from original QWOP (30 FPS main loop, 25 FPS physics).

Usage:
    python main.py
    
Controls:
    Q - Right thigh forward, left thigh back
    W - Left thigh forward, right thigh back
    O - Right calf forward, left calf back
    P - Left calf forward, right calf back
    R - Reset game
    ESC - Quit
"""

import sys
import pygame

# Add src to path for imports
sys.path.insert(0, 'src')

from game import QWOPGame
from renderer import QWOPRenderer
from data import SCREEN_WIDTH, SCREEN_HEIGHT


# Key mapping from pygame constants to string format
KEY_MAP = {
    pygame.K_q: 'q',
    pygame.K_w: 'w',
    pygame.K_o: 'o',
    pygame.K_p: 'p'
}


def main():
    """
    Main game loop.
    
    Runs at 30 FPS matching the original QWOP game.
    Physics runs at fixed 25 FPS (0.04s timestep) internally.
    """
    # Initialize Pygame
    pygame.init()
    
    # Create window
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("QWOP - Python Recreation")
    
    # Create clock for timing (30 FPS)
    clock = pygame.time.Clock()
    
    # Create game subsystems
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
    print("R - Reset game")
    print("ESC - Quit")
    print("=" * 70)
    print()
    print("Press any movement key (Q/W/O/P) to start!")
    print()
    
    # Main game loop
    running = True
    
    try:
        while running:
            # Tick at 30 FPS (matching original QWOP)
            # Returns milliseconds since last tick
            dt = clock.tick(30) / 1000.0  # Convert to seconds
            
            # Handle events
            for event in pygame.event.get():
                # Window close
                if event.type == pygame.QUIT:
                    running = False
                
                # Key press
                elif event.type == pygame.KEYDOWN:
                    # Movement keys (Q/W/O/P)
                    if event.key in KEY_MAP:
                        key_char = KEY_MAP[event.key]
                        game.controls.key_down(key_char)
                        # Start game on first key press
                        if not game.first_click:
                            game.start()
                    
                    # Reset key (R)
                    elif event.key == pygame.K_r:
                        game.reset()
                    
                    # Quit key (ESC)
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                
                # Key release
                elif event.type == pygame.KEYUP:
                    # Movement keys (Q/W/O/P)
                    if event.key in KEY_MAP:
                        key_char = KEY_MAP[event.key]
                        game.controls.key_up(key_char)
            
            # Update game logic (physics runs at fixed 0.04s internally)
            game.update(dt)
            
            # Render frame
            renderer.render(game)
            
            # Update display
            pygame.display.flip()
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user")
    
    except Exception as e:
        print(f"\nError during game loop: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean shutdown
        pygame.quit()
        print("\nThanks for playing QWOP!")


if __name__ == "__main__":
    main()
