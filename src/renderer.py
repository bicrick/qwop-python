"""
QWOP Renderer - Pygame-based Visual Output

Handles all rendering for the QWOP game:
- Body parts as colored rectangles (depth-sorted, rotated)
- Ground/track
- Camera transform (world-to-screen coordinates)
- HUD (score, time, game-over message)
- Q/W/O/P key indicators

This is a read-only module - it does not modify game state.
"""

import pygame
import math

from data import (
    BODY_PARTS,
    WORLD_SCALE,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    TRACK_Y
)


class QWOPRenderer:
    """
    Pygame-based renderer for QWOP game.
    
    Draws:
    - Background (sky + track)
    - Body parts as colored rotated rectangles in depth order
    - HUD overlay with score, time, game-over message
    - Q/W/O/P key state indicators
    
    All rendering uses camera-relative coordinates from QWOPGame.
    """
    
    def __init__(self, screen):
        """
        Initialize renderer.
        
        Args:
            screen: pygame.Surface (640x400) to draw on
        """
        self.screen = screen
        
        # Fonts
        pygame.font.init()
        self.font = pygame.font.SysFont('arial', 32, bold=True)
        self.small_font = pygame.font.SysFont('arial', 20)
        self.tiny_font = pygame.font.SysFont('arial', 14)
        
        # Colors (no purple per user rules)
        self.colors = {
            'sky': (135, 206, 235),      # Light blue
            'track': (139, 90, 43),      # Brown
            'text': (255, 255, 255),     # White
            'text_shadow': (0, 0, 0),    # Black
            'game_over': (220, 50, 50),  # Red
        }
        
        # Body part colors - distinct and visually clear
        self.body_colors = {
            'torso': (0, 128, 128),         # Dark teal
            'head': (245, 222, 179),        # Light beige/wheat
            'leftArm': (70, 100, 140),      # Dark blue-gray
            'leftForearm': (80, 110, 150),  # Medium blue-gray
            'leftThigh': (90, 60, 40),      # Dark brown
            'leftCalf': (110, 75, 50),      # Medium brown
            'leftFoot': (50, 50, 50),       # Dark gray (shoe)
            'rightArm': (200, 120, 80),     # Light orange-brown
            'rightForearm': (220, 140, 100), # Lighter orange
            'rightThigh': (160, 100, 70),   # Medium brown-orange
            'rightCalf': (180, 115, 85),    # Light brown-orange
            'rightFoot': (60, 60, 60),      # Dark gray (shoe)
        }
        
        # Render order (sorted by depth, ascending)
        # Lower depth = drawn first = farther back
        self.render_order = sorted(BODY_PARTS.keys(), key=lambda name: BODY_PARTS[name]['depth'])
        
        print("✓ Renderer initialized")
        print(f"  Render order: {self.render_order}")
    
    def render(self, game):
        """
        Main render method - draws complete frame.
        
        Args:
            game: QWOPGame instance with current state
        """
        # Clear screen
        self.screen.fill(self.colors['sky'])
        
        # Draw layers in order
        self._draw_background(game)
        self._draw_body_parts(game)
        self._draw_hud(game)
        self._draw_key_indicators(game)
    
    def _draw_background(self, game):
        """
        Draw background elements: sky (already filled) and track.
        
        Args:
            game: QWOPGame instance
        """
        # Track/ground - draw as long horizontal strip
        # Position is at TRACK_Y in world coords
        track_world_x = game.camera_x / WORLD_SCALE - 100  # Start well before camera
        track_world_y = TRACK_Y
        track_width_meters = (SCREEN_WIDTH / WORLD_SCALE) + 200  # Extend past screen
        track_height_meters = 5  # Thick track
        
        # Transform to screen coordinates
        screen_x, screen_y = self._world_to_screen(track_world_x, track_world_y, game)
        track_width_px = track_width_meters * WORLD_SCALE
        track_height_px = track_height_meters * WORLD_SCALE
        
        # Draw track
        pygame.draw.rect(
            self.screen,
            self.colors['track'],
            (screen_x, screen_y, track_width_px, track_height_px)
        )
    
    def _draw_body_parts(self, game):
        """
        Draw all 12 body parts as rotated colored rectangles in depth order.
        
        Args:
            game: QWOPGame instance
        """
        # Draw in depth order (back to front)
        for body_name in self.render_order:
            body = game.physics.get_body(body_name)
            if body is None:
                continue
            
            config = BODY_PARTS[body_name]
            color = self.body_colors.get(body_name, (128, 128, 128))  # Gray default
            
            self._draw_body_rect(body, config, color, game)
    
    def _draw_body_rect(self, body, config, color, game):
        """
        Draw a single body part as a rotated rectangle.
        
        Args:
            body: Box2D body (b2Body)
            config: Body part config dict from BODY_PARTS
            color: RGB tuple
            game: QWOPGame instance
        """
        # Get body dimensions in pixels
        width_px = config['half_width'] * 2 * WORLD_SCALE
        height_px = config['half_height'] * 2 * WORLD_SCALE
        
        # Create surface for this body part
        surf = pygame.Surface((width_px, height_px), pygame.SRCALPHA)
        surf.fill(color)
        
        # Rotate the surface
        # Pygame rotates counter-clockwise, Box2D angle is in radians
        # Need to negate angle for correct rotation
        angle_degrees = -math.degrees(body.angle)
        rotated = pygame.transform.rotate(surf, angle_degrees)
        
        # Get center position in world coords
        world_x, world_y = body.position
        
        # Transform to screen coords
        screen_x, screen_y = self._world_to_screen(world_x, world_y, game)
        
        # Get rotated rect to properly center it
        rotated_rect = rotated.get_rect(center=(screen_x, screen_y))
        
        # Draw
        self.screen.blit(rotated, rotated_rect)
    
    def _world_to_screen(self, world_x, world_y, game):
        """
        Transform world coordinates to screen coordinates.
        
        Args:
            world_x: X position in world/Box2D coordinates (meters)
            world_y: Y position in world/Box2D coordinates (meters)
            game: QWOPGame instance (for camera position)
            
        Returns:
            (screen_x, screen_y) tuple in pixels
        """
        screen_x = (world_x * WORLD_SCALE) - game.camera_x
        screen_y = (world_y * WORLD_SCALE) - game.camera_y
        return (screen_x, screen_y)
    
    def _draw_hud(self, game):
        """
        Draw HUD overlay: score, time, high score, game-over message.
        
        Args:
            game: QWOPGame instance
        """
        # Score (top center)
        score_text = f"{game.game_state.score:.1f} metres"
        self._draw_text_with_shadow(
            score_text,
            self.font,
            SCREEN_WIDTH // 2,
            30,
            self.colors['text'],
            center=True
        )
        
        # Time (below score)
        time_text = f"{game.score_time:.1f}s"
        self._draw_text_with_shadow(
            time_text,
            self.small_font,
            SCREEN_WIDTH // 2,
            65,
            self.colors['text'],
            center=True
        )
        
        # High score (top right)
        high_score_text = f"Best: {game.game_state.high_score:.1f}m"
        self._draw_text_with_shadow(
            high_score_text,
            self.small_font,
            SCREEN_WIDTH - 10,
            10,
            self.colors['text'],
            right_align=True
        )
        
        # Game over message (center of screen)
        if game.game_state.game_ended:
            # Semi-transparent overlay
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 128))  # Black with 50% alpha
            self.screen.blit(overlay, (0, 0))
            
            # Game over text
            if game.game_state.jump_landed and not game.game_state.fallen:
                message = "SUCCESS!"
                sub_message = "You cleared the hurdle!"
            else:
                message = "GAME OVER"
                sub_message = "You fell!"
            
            self._draw_text_with_shadow(
                message,
                self.font,
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 - 40,
                self.colors['game_over'],
                center=True
            )
            
            self._draw_text_with_shadow(
                sub_message,
                self.small_font,
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2,
                self.colors['text'],
                center=True
            )
            
            # Final score
            final_score = f"Distance: {game.game_state.score:.1f}m"
            self._draw_text_with_shadow(
                final_score,
                self.small_font,
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 + 40,
                self.colors['text'],
                center=True
            )
            
            # Reset instruction
            reset_text = "Press 'R' to reset"
            self._draw_text_with_shadow(
                reset_text,
                self.small_font,
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT // 2 + 80,
                self.colors['text'],
                center=True
            )
        
        # Start instruction (before game starts)
        elif not game.first_click:
            start_text = "Press any key to start"
            self._draw_text_with_shadow(
                start_text,
                self.small_font,
                SCREEN_WIDTH // 2,
                SCREEN_HEIGHT - 100,
                self.colors['text'],
                center=True
            )
    
    def _draw_key_indicators(self, game):
        """
        Draw Q/W/O/P key state indicators at bottom of screen.
        
        Args:
            game: QWOPGame instance
        """
        # Key positions (bottom of screen, evenly spaced)
        key_y = SCREEN_HEIGHT - 40
        key_spacing = 80
        start_x = (SCREEN_WIDTH - (key_spacing * 3)) // 2
        
        keys = [
            ('Q', game.controls.q_down, start_x),
            ('W', game.controls.w_down, start_x + key_spacing),
            ('O', game.controls.o_down, start_x + key_spacing * 2),
            ('P', game.controls.p_down, start_x + key_spacing * 3)
        ]
        
        for key_char, is_pressed, x in keys:
            # Draw key background
            key_rect = pygame.Rect(x, key_y, 60, 30)
            
            # Color based on pressed state
            if is_pressed:
                bg_color = (100, 200, 100)  # Green when pressed
                text_color = (0, 0, 0)       # Black text
            else:
                bg_color = (60, 60, 60)      # Dark gray when not pressed
                text_color = (200, 200, 200) # Light gray text
            
            pygame.draw.rect(self.screen, bg_color, key_rect)
            pygame.draw.rect(self.screen, (255, 255, 255), key_rect, 2)  # White border
            
            # Draw key letter
            text_surf = self.small_font.render(key_char, True, text_color)
            text_rect = text_surf.get_rect(center=key_rect.center)
            self.screen.blit(text_surf, text_rect)
    
    def _draw_text_with_shadow(self, text, font, x, y, color, center=False, right_align=False):
        """
        Draw text with a drop shadow for better visibility.
        
        Args:
            text: String to draw
            font: pygame.font.Font instance
            x: X position
            y: Y position
            color: RGB tuple for text color
            center: If True, center text at (x, y)
            right_align: If True, right-align text at x
        """
        # Draw shadow (offset by 2 pixels)
        shadow_surf = font.render(text, True, self.colors['text_shadow'])
        shadow_rect = shadow_surf.get_rect()
        
        if center:
            shadow_rect.center = (x + 2, y + 2)
        elif right_align:
            shadow_rect.topright = (x + 2, y + 2)
        else:
            shadow_rect.topleft = (x + 2, y + 2)
        
        self.screen.blit(shadow_surf, shadow_rect)
        
        # Draw actual text
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        
        if center:
            text_rect.center = (x, y)
        elif right_align:
            text_rect.topright = (x, y)
        else:
            text_rect.topleft = (x, y)
        
        self.screen.blit(text_surf, text_rect)
