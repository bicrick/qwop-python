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

# Track dimensions (matches JS floor segment: screenWidth x underground.height)
TRACK_HEIGHT_PX = 64
TRACK_TILE_WIDTH_PX = 640

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
        
        # Fonts (sizes match JS mundo36/18; Verdana approximates mundo from Athletics.html)
        pygame.font.init()
        self.font = pygame.font.SysFont('verdana', 36, bold=True)
        self.small_font = pygame.font.SysFont('verdana', 18)
        self.tiny_font = pygame.font.SysFont('verdana', 14)
        self.hud_secondary_font = pygame.font.SysFont('verdana', 18, bold=False)  # Best + Timer (match mundo18)
        
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
        """Load sprintbg, sky, sand, sandtape.
        sprintbg.jpg is 1px wide (vertical gradient); scale sideways to 640x400 to match JS."""
        try:
            sprintbg_path = os.path.join(self._assets_dir, 'sprintbg.jpg')
            if os.path.exists(sprintbg_path):
                tex = pygame.image.load(sprintbg_path).convert()
                # JS uses size (640, 400), uv (0,0,640,400) - stretch 1px width across full screen
                self._sprintbg_texture = pygame.transform.scale(tex, (SCREEN_WIDTH, SCREEN_HEIGHT))
        except pygame.error:
            self._sprintbg_texture = None
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
        self._prepare_tiled_textures()

    def _tile_texture(self, tex, target_w, target_h):
        """Tile texture to fill target size (matches JS GL_REPEAT). Returns a Surface."""
        tw, th = tex.get_size()
        surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        for y in range(0, target_h, th):
            for x in range(0, target_w, tw):
                surf.blit(tex, (x, y))
        return surf

    def _prepare_tiled_textures(self):
        """Create cached tiled surfaces (matches JS set_clamp_s GL_REPEAT)."""
        self._track_tiled = None
        self._sand_tiled = None
        self._sandtape_tiled = None
        if self.track_texture is not None:
            seg_h = self.track_texture.get_height()
            self._track_tiled = self._tile_texture(self.track_texture, TRACK_TILE_WIDTH_PX, seg_h)
        if self._sand_texture is not None:
            self._sand_tiled = self._tile_texture(self._sand_texture, 2000, 25)
        if self._sandtape_texture is not None:
            self._sandtape_tiled = self._tile_texture(self._sandtape_texture, 2000, 14)

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
        # sprintbg: 1px-wide vertical gradient, stretched to 640x400 (matches JS pos 0,-16)
        if self._sprintbg_texture is not None:
            self.screen.blit(self._sprintbg_texture, (0, -16))
        else:
            self.screen.fill(self.colors['sky'])

        # Draw layers: track, sand pit (sprintbg provides gradient background)
        self._draw_background(game)
        self._draw_hurdle(game)
        self._draw_body_parts(game)
        self._draw_hud(game)
        self._draw_key_indicators(game)
    
    def _draw_background(self, game):
        """
        Draw background elements in JS order: track, sand pit.
        sprintbg gradient (drawn first in render()) provides the sky/field atmosphere.
        Sky.png is skipped - it uses skyShader in JS for blending; without that shader
        it draws opaque and obscures the sprintbg gradient.
        """
        # 1. Track (underground.png, depth -10)
        self._draw_track(game)

        # 2. Sand pit (depth -2/-1, when in view)
        self._draw_sand_pit(game)

    def _draw_track(self, game):
        """
        Draw track using underground.png segments (matches JS world_batcher floor sprites).
        3 segments, each 640x(underground.height), positioned dynamically to stay under viewport.
        JS formula: world_x = (floor(camera_x/640) + i) * 640, centered: true.
        """
        # Track center Y in world pixels: 10.74275 * WORLD_SCALE
        track_center_y_px = 10.74275 * WORLD_SCALE
        segment_w = TRACK_TILE_WIDTH_PX
        segment_h = TRACK_HEIGHT_PX if self.track_texture is None else self.track_texture.get_height()

        for i in range(3):
            # JS floor position formula (line 863)
            world_x_px = (math.floor(game.camera_x / SCREEN_WIDTH) + i) * SCREEN_WIDTH
            screen_x = world_x_px - game.camera_x
            screen_y = track_center_y_px - game.camera_y

            # Centered: true - blit with center at (screen_x, screen_y)
            blit_left = int(screen_x - segment_w / 2)
            blit_top = int(screen_y - segment_h / 2)

            if self._track_tiled is not None:
                # Tiled texture (matches JS GL_REPEAT) - no stretching
                self.screen.blit(self._track_tiled, (blit_left, blit_top))
            else:
                pygame.draw.rect(
                    self.screen,
                    self.colors['track'],
                    (blit_left, blit_top, segment_w, segment_h)
                )

        # Lane markers (Starting_Line from UISprites frame 17)
        track_top_y = track_center_y_px - segment_h / 2 - game.camera_y
        self._draw_lane_markers(game, int(track_top_y))

    def _draw_lane_markers(self, game, track_y):
        """Draw Starting_Line sprites at intervals along the track (UISprites frame 17)."""
        if self._ui_atlas is None or self._ui_frames is None or len(self._ui_frames) <= 17:
            return
        fd = self._ui_frames[17]
        fr = fd['frame']
        rect = pygame.Rect(fr['x'], fr['y'], fr['w'], fr['h'])
        surf = self._ui_atlas.subsurface(rect).copy()
        # Scale to (37, 77) to match JS startingLine size
        marker_w, marker_h = 37, 77
        surf = pygame.transform.smoothscale(surf, (marker_w, marker_h))
        spacing = 320  # World pixels between markers
        # Draw markers at regular intervals; transform world x to screen
        world_x = (game.camera_x // spacing) * spacing - spacing
        while world_x < game.camera_x + SCREEN_WIDTH + spacing:
            screen_x = world_x - game.camera_x
            # track_y is track top (running surface); markers sit ON the track
            marker_bottom = track_y
            blit_y = marker_bottom - marker_h
            if screen_x + marker_w > 0 and screen_x < SCREEN_WIDTH:
                self.screen.blit(surf, (int(screen_x), int(blit_y)))
            world_x += spacing

    def _draw_sand_pit(self, game):
        """Draw sand pit elements at SAND_PIT_AT when in view."""
        if not (SAND_PIT_AT - 500 < game.camera_x < SAND_PIT_AT + 2100):
            return
        # Transform: screen = world - camera (all in pixels)
        def to_screen(wx, wy):
            return (wx - game.camera_x, wy - game.camera_y)

        # 1. sandpitTape (sandtape.png): pos (19916, 160), size 2000 x 14 (JS GL_REPEAT)
        if self._sandtape_tiled is not None:
            sx, sy = to_screen(SAND_PIT_AT - 84, 160)
            self.screen.blit(self._sandtape_tiled, (int(sx), int(sy)))

        # 2. sandpitSandBody (sand.png): pos (19994, 176), size 2000 x 25 (JS GL_REPEAT)
        if self._sand_tiled is not None:
            sx, sy = to_screen(SAND_PIT_AT - 6, 176)
            self.screen.blit(self._sand_tiled, (int(sx), int(sy)))

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

    def _blit_ui_frame(self, frame_idx, screen_x, screen_y, centered=True):
        """
        Blit a UI atlas frame at screen position.
        Fallback: no-op if atlas/frames missing.

        Args:
            frame_idx: Index into _ui_frames array
            screen_x: X position in pixels
            screen_y: Y position in pixels
            centered: If True, center the sprite at (screen_x, screen_y)
        """
        if self._ui_atlas is None or self._ui_frames is None or frame_idx >= len(self._ui_frames):
            return
        fd = self._ui_frames[frame_idx]
        fr = fd['frame']
        rect = pygame.Rect(fr['x'], fr['y'], fr['w'], fr['h'])
        surf = self._ui_atlas.subsurface(rect).copy()
        if centered:
            blit_rect = surf.get_rect(center=(screen_x, screen_y))
        else:
            blit_rect = surf.get_rect(topleft=(screen_x, screen_y))
        self.screen.blit(surf, blit_rect)

    def _draw_black_overlay(self):
        """Draw semi-transparent black overlay (0.6 alpha) over full screen."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 153))  # 0.6 * 255 ≈ 153
        self.screen.blit(overlay, (0, 0))
    
    def _draw_hud(self, game):
        """
        Draw HUD overlay: score, time, high score, game-over/intro panels.
        
        Args:
            game: QWOPGame instance
        """
        # Game over (FallenEnding or JumpEnding sprites + overlay)
        if game.game_state.game_ended:
            self._draw_black_overlay()
            center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            if game.game_state.jump_landed and not game.game_state.fallen:
                self._blit_ui_frame(7, center_x, center_y, centered=True)  # JumpEnding
                score_str = f"{game.game_state.score:.1f} metres in {int(game.score_time * 10) / 10:.1f} seconds"
                self._draw_text_with_shadow(
                    score_str, self.small_font, center_x, center_y + 22,
                    self.colors['text'], center=True
                )
            else:
                self._blit_ui_frame(3, center_x, center_y, centered=True)  # FallenEnding
                score_str = f"{game.game_state.score:.1f} metres"
                self._draw_text_with_shadow(
                    score_str, self.font, center_x, center_y,
                    self.colors['text'], center=True
                )
            # Fallback text when atlas missing
            if self._ui_atlas is None:
                msg = "SUCCESS!" if (game.game_state.jump_landed and not game.game_state.fallen) else "GAME OVER"
                self._draw_text_with_shadow(msg, self.font, center_x, center_y - 40, self.colors['game_over'], center=True)
            return

        # Intro screen (before first click)
        if not game.first_click:
            self._draw_black_overlay()
            self._blit_ui_frame(6, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, centered=True)  # Intro_clip
            if self._ui_atlas is None:
                self._draw_text_with_shadow(
                    "Press any key to start", self.small_font,
                    SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100, self.colors['text'], center=True
                )
            return

        # Normal HUD: Best (left), Score (center), Timer (right) - matches JS layout
        high_score_text = f"Best: {game.game_state.high_score:.1f}m"
        self._draw_text_with_shadow(
            high_score_text, self.hud_secondary_font, 34, 2,
            self.colors['text'], center=False, right_align=False
        )

        score_text = f"{game.game_state.score:.1f} metres"
        self._draw_text_with_shadow(
            score_text, self.font, SCREEN_WIDTH // 2, 18,
            self.colors['text'], center=True
        )

        time_text = f"{game.score_time:.1f}s"
        self._draw_text_with_shadow(
            time_text, self.hud_secondary_font, SCREEN_WIDTH - 22, 2,
            self.colors['text'], center=False, right_align=True
        )


    def _draw_key_indicators(self, game):
        """
        Draw Q/W/O/P key state indicators matching original QWOP layout.
        Q and W (THIGHS) on left; O and P (CALVES) on right.
        Uses UISprites when atlas available; falls back to rect buttons.
        """
        # JS positions: screenWidth/2=320, key_y=46.5
        # Q: (320-274+0.5, 46.5)=(46.5, 46.5), W: +52 -> (98.5, 46.5)
        # O: (320+274-52.5, 46.5)=(541.5, 46.5), P: (594.5, 46.5)
        # Calves: (568, 85), Thighs: (72, 85)
        if self._ui_atlas is not None and self._ui_frames is not None:
            cx = SCREEN_WIDTH // 2
            key_y = 46.5
            self._blit_ui_frame(14 if not game.controls.q_down else 15, cx - 274 + 0.5, key_y, centered=True)  # Q
            self._blit_ui_frame(19 if not game.controls.w_down else 20, cx - 274 + 52.5, key_y, centered=True)  # W
            self._blit_ui_frame(10 if not game.controls.o_down else 11, cx + 274 - 52.5, key_y, centered=True)  # O
            self._blit_ui_frame(12 if not game.controls.p_down else 13, cx + 274 + 0.5, key_y, centered=True)  # P
            self._blit_ui_frame(18, cx - 248, 85, centered=True)   # Thighs label
            self._blit_ui_frame(1, cx + 248, 85, centered=True)   # Calves label
            return
        # Fallback: programmatic buttons
        btn_size = 44
        btn_gap = 8
        margin = 16
        left_x = margin
        key_y = 42
        for key_char, is_pressed, x in [
            ('Q', game.controls.q_down, left_x),
            ('W', game.controls.w_down, left_x + btn_size + btn_gap),
        ]:
            self._draw_key_button(key_char, is_pressed, x, key_y, btn_size)
        self._draw_text_with_shadow(
            "THIGHS", self.tiny_font,
            left_x + btn_size + btn_gap // 2, key_y + btn_size + 11,
            self.colors['text'], center=True
        )
        right_start = SCREEN_WIDTH - margin - (btn_size * 2 + btn_gap)
        for key_char, is_pressed, x in [
            ('O', game.controls.o_down, right_start),
            ('P', game.controls.p_down, right_start + btn_size + btn_gap),
        ]:
            self._draw_key_button(key_char, is_pressed, x, key_y, btn_size)
        self._draw_text_with_shadow(
            "CALVES", self.tiny_font,
            right_start + btn_size + btn_gap // 2, key_y + btn_size + 11,
            self.colors['text'], center=True
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
        # Draw shadow (1px offset - subtle outline matching JS)
        shadow_surf = font.render(text, True, self.colors['text_shadow'])
        shadow_rect = shadow_surf.get_rect()
        
        if center:
            shadow_rect.center = (x + 1, y + 1)
        elif right_align:
            shadow_rect.topright = (x + 1, y + 1)
        else:
            shadow_rect.topleft = (x + 1, y + 1)
        
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
