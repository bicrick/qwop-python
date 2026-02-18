"""
QWOP Renderer - Pygame-based Visual Output

Handles all rendering for the QWOP game:
- Body parts as sprites from playercolor.png atlas (or colored rects fallback)
- Ground/track (textured with underground.png when available)
- Camera transform (world-to-screen coordinates)
- HUD (score, time, game-over message)
- Q/W/O/P key indicators

This is a read-only module - it does not modify game state.
"""

import json
import os
import pygame
import math

from data import (
    BODY_PARTS,
    WORLD_SCALE,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    SAND_PIT_AT,
    HURDLES_ENABLED,
    HURDLE_BASE_SIZE,
    HURDLE_TOP_SIZE
)

# Body part to playercolor.json frame index (matches JS create_player order)
BODY_PART_TO_FRAME_INDEX = {
    'torso': 0,
    'head': 1,
    'leftForearm': 2,
    'leftThigh': 3,
    'leftArm': 4,
    'leftCalf': 5,
    'leftFoot': 6,
    'rightForearm': 7,
    'rightArm': 8,
    'rightCalf': 9,
    'rightFoot': 10,
    'rightThigh': 11,
}


class QWOPRenderer:
    """
    Pygame-based renderer for QWOP game.

    Draws:
    - Background (sky + track)
    - Body parts as sprites from playercolor.png (or colored rects if assets missing)
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
            'hurdle_base': (139, 90, 43),  # Dark brown (same as track)
            'hurdle_top': (180, 120, 70),  # Lighter brown
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

        # Asset directory (src/assets/)
        self._assets_dir = os.path.join(os.path.dirname(__file__), 'assets')

        # Ground texture (from original QWOP assets)
        self.track_texture = None
        _tex_path = os.path.join(self._assets_dir, 'underground.png')
        if os.path.exists(_tex_path):
            try:
                self.track_texture = pygame.image.load(_tex_path).convert_alpha()
            except pygame.error:
                pass
        if self.track_texture is None:
            self.track_texture = pygame.Surface((128, 64))
            self.track_texture.fill(self.colors['track'])

        # Player sprite atlas (playercolor.png + playercolor.json)
        self._player_atlas = None
        self._player_frames = None
        self._load_player_atlas()

        # Background textures
        self._sprintbg_texture = None
        self._sky_texture = None
        self._sand_texture = None
        self._sandtape_texture = None
        self._load_background_textures()

        # UISprites for sand pit (SandBoard frame 16, sandpit frame 24)
        self._ui_atlas = None
        self._ui_frames = None
        self._load_ui_atlas()

        print("✓ Renderer initialized")
        print(f"  Render order: {self.render_order}")

    def _load_player_atlas(self):
        """Load playercolor.png and parse playercolor.json. Falls back to None if missing."""
        atlas_path = os.path.join(self._assets_dir, 'playercolor.png')
        json_path = os.path.join(self._assets_dir, 'playercolor.json')
        if not os.path.exists(atlas_path) or not os.path.exists(json_path):
            return
        try:
            self._player_atlas = pygame.image.load(atlas_path).convert_alpha()
            with open(json_path, 'r') as f:
                data = json.load(f)
            self._player_frames = data.get('frames', [])
        except (pygame.error, json.JSONDecodeError):
            self._player_atlas = None
            self._player_frames = None

    def _load_background_textures(self):
        """Load sprintbg, sky, sand, sandtape. Scale sprintbg to 640x400."""
        try:
            sprintbg_path = os.path.join(self._assets_dir, 'sprintbg.jpg')
            if os.path.exists(sprintbg_path):
                tex = pygame.image.load(sprintbg_path).convert()
                self._sprintbg_texture = pygame.transform.smoothscale(tex, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except pygame.error:
            pass
        try:
            sky_path = os.path.join(self._assets_dir, 'sky.png')
            if os.path.exists(sky_path):
                self._sky_texture = pygame.image.load(sky_path).convert_alpha()
        except pygame.error:
            pass
        try:
            sand_path = os.path.join(self._assets_dir, 'sand.png')
            if os.path.exists(sand_path):
                self._sand_texture = pygame.image.load(sand_path).convert_alpha()
        except pygame.error:
            pass
        try:
            sandtape_path = os.path.join(self._assets_dir, 'sandtape.png')
            if os.path.exists(sandtape_path):
                self._sandtape_texture = pygame.image.load(sandtape_path).convert_alpha()
        except pygame.error:
            pass

    def _load_ui_atlas(self):
        """Load UISprites.png and UISprites.json for sand pit elements."""
        atlas_path = os.path.join(self._assets_dir, 'UISprites.png')
        json_path = os.path.join(self._assets_dir, 'UISprites.json')
        if not os.path.exists(atlas_path) or not os.path.exists(json_path):
            return
        try:
            self._ui_atlas = pygame.image.load(atlas_path).convert_alpha()
            with open(json_path, 'r') as f:
                data = json.load(f)
            self._ui_frames = data.get('frames', [])
        except (pygame.error, json.JSONDecodeError):
            self._ui_atlas = None
            self._ui_frames = None

    def render(self, game):
        """
        Main render method - draws complete frame.
        
        Args:
            game: QWOPGame instance with current state
        """
        # Clear screen (solid sky fallback if no sprintbg)
        if self._sprintbg_texture is not None:
            self.screen.blit(self._sprintbg_texture, (0, 0))
        else:
            self.screen.fill(self.colors['sky'])

        # Draw layers in order: sky (world-scrolling), track, sand pit
        self._draw_background(game)
        self._draw_hurdle(game)
        self._draw_body_parts(game)
        self._draw_hud(game)
        self._draw_key_indicators(game)
    
    def _draw_background(self, game):
        """
        Draw background elements in JS order: sky (world-scrolling), track, sand pit.
        Sky tiles horizontally; track uses tiled underground.png; sand pit at SAND_PIT_AT.
        """
        # 1. Sky (world-scrolling, depth -11)
        self._draw_sky(game)

        # 2. Track (underground.png, depth -10)
        self._draw_track(game)

        # 3. Sand pit (depth -2/-1, when in view)
        self._draw_sand_pit(game)

    def _draw_sky(self, game):
        """Draw sky.png tiled horizontally, world-scrolling at (-620, -600)."""
        if self._sky_texture is None:
            return
        sky_w, sky_h = self._sky_texture.get_size()
        # JS position: (-31*worldScale, -30*worldScale) = (-620, -600)
        base_screen_x = -620 - game.camera_x
        base_screen_y = -600 - game.camera_y
        # Step left until we cover the viewport's left edge
        x = base_screen_x
        while x + sky_w > 0 and x > -50000:
            x -= sky_w
        # Tile horizontally and vertically to cover viewport
        while x < SCREEN_WIDTH:
            y = base_screen_y
            while y + sky_h > 0 and y > -50000:
                y -= sky_h
            while y < SCREEN_HEIGHT:
                self.screen.blit(self._sky_texture, (int(x), int(y)))
                y += sky_h
            x += sky_w

    def _draw_track(self, game):
        """Draw underground.png as tiled track at bottom of screen."""
        track_width_meters = (SCREEN_WIDTH / WORLD_SCALE) + 200
        track_height_px = 80
        track_width_px = int(track_width_meters * WORLD_SCALE)
        track_world_x = game.camera_x / WORLD_SCALE - 100
        screen_x = (track_world_x * WORLD_SCALE) - game.camera_x
        screen_y = SCREEN_HEIGHT - track_height_px

        pygame.draw.rect(
            self.screen,
            self.colors['track'],
            (screen_x, screen_y, track_width_px, track_height_px)
        )
        tex_w, tex_h = self.track_texture.get_size()
        if tex_h != track_height_px:
            scaled_tex = pygame.transform.smoothscale(
                self.track_texture, (int(tex_w * track_height_px / tex_h), track_height_px)
            )
        else:
            scaled_tex = self.track_texture
        scaled_tex_w = scaled_tex.get_width()
        phase = int((track_world_x * WORLD_SCALE) % scaled_tex_w)
        start_x = screen_x - phase
        x = start_x
        while x < screen_x + track_width_px:
            self.screen.blit(scaled_tex, (x, screen_y))
            x += scaled_tex_w

    def _draw_sand_pit(self, game):
        """Draw sand pit elements at SAND_PIT_AT when in view."""
        if not (SAND_PIT_AT - 500 < game.camera_x < SAND_PIT_AT + 2100):
            return
        # Transform: screen = world - camera (all in pixels)
        def to_screen(wx, wy):
            return (wx - game.camera_x, wy - game.camera_y)

        # 1. sandpitTape (sandtape.png): pos (19916, 160), size 2000 x 14
        if self._sandtape_texture is not None:
            tw, th = self._sandtape_texture.get_size()
            tape_w, tape_h = 2000, 14
            scaled = pygame.transform.smoothscale(self._sandtape_texture, (tape_w, tape_h))
            sx, sy = to_screen(SAND_PIT_AT - 84, 160)
            self.screen.blit(scaled, (int(sx), int(sy)))

        # 2. sandpitSandBody (sand.png): pos (19994, 176), size 2000 x 25
        if self._sand_texture is not None:
            sw, sh = self._sand_texture.get_size()
            body_w, body_h = 2000, 25
            scaled = pygame.transform.smoothscale(self._sand_texture, (body_w, body_h))
            sx, sy = to_screen(SAND_PIT_AT - 6, 176)
            self.screen.blit(scaled, (int(sx), int(sy)))

        # 3. sandpitSandHead (UISprites frame 24, 72x25): pos (20000, 188.5)
        if self._ui_atlas is not None and self._ui_frames is not None and len(self._ui_frames) > 24:
            fd = self._ui_frames[24]
            fr = fd['frame']
            rect = pygame.Rect(fr['x'], fr['y'], fr['w'], fr['h'])
            surf = self._ui_atlas.subsurface(rect).copy()
            sx, sy = to_screen(SAND_PIT_AT, 188.5)
            self.screen.blit(surf, (int(sx), int(sy)))

        # 4. SandBoard (UISprites frame 16, 366x110): pos (19817, 155)
        if self._ui_atlas is not None and self._ui_frames is not None and len(self._ui_frames) > 16:
            fd = self._ui_frames[16]
            fr = fd['frame']
            rect = pygame.Rect(fr['x'], fr['y'], fr['w'], fr['h'])
            surf = self._ui_atlas.subsurface(rect).copy()
            sx, sy = to_screen(SAND_PIT_AT - 183, 155)
            self.screen.blit(surf, (int(sx), int(sy)))

    def _draw_hurdle(self, game):
        """
        Draw hurdle obstacle (base and top) as rotated rectangles.
        
        Args:
            game: QWOPGame instance
        """
        # Only draw if hurdles are enabled
        if not HURDLES_ENABLED:
            return
        
        # Draw hurdle base
        if game.physics.hurdle_base is not None:
            base_body = game.physics.hurdle_base
            base_width_px = HURDLE_BASE_SIZE[0]
            base_height_px = HURDLE_BASE_SIZE[1]
            
            self._draw_hurdle_part(
                base_body, 
                base_width_px, 
                base_height_px, 
                self.colors['hurdle_base'],
                game
            )
        
        # Draw hurdle top
        if game.physics.hurdle_top is not None:
            top_body = game.physics.hurdle_top
            top_width_px = HURDLE_TOP_SIZE[0]
            top_height_px = HURDLE_TOP_SIZE[1]
            
            self._draw_hurdle_part(
                top_body,
                top_width_px,
                top_height_px,
                self.colors['hurdle_top'],
                game
            )
    
    def _draw_hurdle_part(self, body, width_px, height_px, color, game):
        """
        Draw a single hurdle part as a rotated rectangle.
        
        Args:
            body: Box2D body (b2Body)
            width_px: Width in pixels
            height_px: Height in pixels
            color: RGB tuple
            game: QWOPGame instance
        """
        # Create surface for this hurdle part
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
    
    def _draw_body_parts(self, game):
        """
        Draw all 12 body parts in depth order.
        Uses playercolor.png sprites when available; falls back to colored rectangles.
        
        Args:
            game: QWOPGame instance
        """
        use_sprites = self._player_atlas is not None and self._player_frames is not None
        # Draw in depth order (back to front)
        for body_name in self.render_order:
            body = game.physics.get_body(body_name)
            if body is None:
                continue

            config = BODY_PARTS[body_name]
            if use_sprites:
                self._draw_body_sprite(body, config, body_name, game)
            else:
                color = self.body_colors.get(body_name, (128, 128, 128))
                self._draw_body_rect(body, config, color, game)
    
    def _draw_body_sprite(self, body, config, body_name, game):
        """
        Draw a single body part using a sprite from the playercolor atlas.

        Args:
            body: Box2D body (b2Body)
            config: Body part config dict from BODY_PARTS
            body_name: Body part name (e.g. 'torso', 'leftFoot')
            game: QWOPGame instance
        """
        frame_idx = BODY_PART_TO_FRAME_INDEX.get(body_name)
        if frame_idx is None or frame_idx >= len(self._player_frames):
            return
        frame_data = self._player_frames[frame_idx]
        fr = frame_data['frame']
        rect = pygame.Rect(fr['x'], fr['y'], fr['w'], fr['h'])
        surf = self._player_atlas.subsurface(rect).copy()

        # Scale to physics dimensions (same as colored rect path)
        width_px = config['half_width'] * 2 * WORLD_SCALE
        height_px = config['half_height'] * 2 * WORLD_SCALE
        if surf.get_width() != width_px or surf.get_height() != height_px:
            surf = pygame.transform.smoothscale(surf, (int(width_px), int(height_px)))

        # Rotate (pygame CCW, Box2D radians)
        angle_degrees = -math.degrees(body.angle)
        rotated = pygame.transform.rotate(surf, angle_degrees)

        world_x, world_y = body.position
        screen_x, screen_y = self._world_to_screen(world_x, world_y, game)
        rotated_rect = rotated.get_rect(center=(screen_x, screen_y))
        self.screen.blit(rotated, rotated_rect)

    def _draw_body_rect(self, body, config, color, game):
        """
        Draw a single body part as a rotated rectangle (fallback when sprites unavailable).
        
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
        
        # High score (top left, above thighs UI)
        high_score_text = f"Best: {game.game_state.high_score:.1f}m"
        self._draw_text_with_shadow(
            high_score_text,
            self.small_font,
            16,
            10,
            self.colors['text'],
            right_align=False
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
        Draw Q/W/O/P key state indicators matching original QWOP layout.
        Q and W (THIGHS) on left; O and P (CALVES) on right.
        
        Args:
            game: QWOPGame instance
        """
        btn_size = 44
        btn_gap = 8
        label_offset = 4
        margin = 16

        # Left group: Q and W with THIGHS label (below best score)
        left_x = margin
        key_y = 42
        thighs_keys = [
            ('Q', game.controls.q_down, left_x),
            ('W', game.controls.w_down, left_x + btn_size + btn_gap),
        ]
        for key_char, is_pressed, x in thighs_keys:
            self._draw_key_button(key_char, is_pressed, x, key_y, btn_size)

        thighs_center_x = left_x + btn_size + btn_gap // 2
        thighs_center_y = key_y + btn_size + label_offset + 7
        self._draw_text_with_shadow(
            "THIGHS",
            self.tiny_font,
            thighs_center_x,
            thighs_center_y,
            self.colors['text'],
            center=True
        )

        # Right group: O and P with CALVES label
        right_start = SCREEN_WIDTH - margin - (btn_size * 2 + btn_gap)
        calves_keys = [
            ('O', game.controls.o_down, right_start),
            ('P', game.controls.p_down, right_start + btn_size + btn_gap),
        ]
        for key_char, is_pressed, x in calves_keys:
            self._draw_key_button(key_char, is_pressed, x, key_y, btn_size)

        calves_center_x = right_start + btn_size + btn_gap // 2
        calves_center_y = key_y + btn_size + label_offset + 7
        self._draw_text_with_shadow(
            "CALVES",
            self.tiny_font,
            calves_center_x,
            calves_center_y,
            self.colors['text'],
            center=True
        )

    def _draw_key_button(self, key_char, is_pressed, x, y, size):
        """Draw a single key button with embossed/physical look."""
        key_rect = pygame.Rect(x, y, size, size)

        if is_pressed:
            bg_color = (140, 140, 140)   # Depressed
            text_color = (60, 60, 60)
        else:
            bg_color = (180, 180, 180)   # Light gray, raised
            text_color = (80, 80, 80)

        # Main fill
        pygame.draw.rect(self.screen, bg_color, key_rect)
        # Border for physical button look
        border_color = (220, 220, 220) if not is_pressed else (120, 120, 120)
        pygame.draw.rect(self.screen, border_color, key_rect, 1)
        # Top-left highlight for embossed look
        if not is_pressed:
            pygame.draw.line(self.screen, (230, 230, 230), (x, y), (x + size, y), 1)
            pygame.draw.line(self.screen, (230, 230, 230), (x, y), (x, y + size), 1)

        # Key letter
        text_surf = self.font.render(key_char, True, text_color)
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
