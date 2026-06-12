"""
ui.py

Cute kawaii OpenCV UI drawing.
"""

import math
import random
import cv2
import numpy as np

import config


class KawaiiUI:
    def __init__(self):
        self.sparkles = []
        self._create_completion_particles()

    def _create_completion_particles(self):
        self.sparkles = []

        for _ in range(40):
            self.sparkles.append({
                "x": random.randint(80, config.FRAME_WIDTH - 80),
                "y": random.randint(90, config.FRAME_HEIGHT - 90),
                "speed": random.uniform(0.5, 2.0),
                "phase": random.uniform(0, math.pi * 2),
                "size": random.randint(8, 18),
            })

    def reset_particles(self):
        self._create_completion_particles()

    def rounded_rect(self, frame, x1, y1, x2, y2, color, radius=20, thickness=-1):
        if thickness == -1:
            cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, -1)
            cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, -1)

            cv2.circle(frame, (x1 + radius, y1 + radius), radius, color, -1)
            cv2.circle(frame, (x2 - radius, y1 + radius), radius, color, -1)
            cv2.circle(frame, (x1 + radius, y2 - radius), radius, color, -1)
            cv2.circle(frame, (x2 - radius, y2 - radius), radius, color, -1)
        else:
            cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
            cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, thickness)

            cv2.circle(frame, (x1 + radius, y1 + radius), radius, color, thickness)
            cv2.circle(frame, (x2 - radius, y1 + radius), radius, color, thickness)
            cv2.circle(frame, (x1 + radius, y2 - radius), radius, color, thickness)
            cv2.circle(frame, (x2 - radius, y2 - radius), radius, color, thickness)

    def put_text(self, frame, text, position, scale=0.75, color=None, thickness=2):
        if color is None:
            color = config.BROWN

        cv2.putText(
            frame,
            text,
            position,
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

    def draw_heart(self, frame, center, size=16, color=None):
        if color is None:
            color = config.DARK_PINK

        x, y = center
        r = max(2, size // 4)

        cv2.circle(frame, (x - r, y - r), r, color, -1)
        cv2.circle(frame, (x + r, y - r), r, color, -1)

        pts = np.array([
            [x - size // 2, y - r],
            [x + size // 2, y - r],
            [x, y + size // 2],
        ], dtype=np.int32)

        cv2.fillPoly(frame, [pts], color)

    def draw_sparkle(self, frame, center, size=14, color=None):
        if color is None:
            color = config.PEACH

        x, y = center

        cv2.line(frame, (x, y - size), (x, y + size), color, 2)
        cv2.line(frame, (x - size, y), (x + size, y), color, 2)
        cv2.line(frame, (x - size // 2, y - size // 2), (x + size // 2, y + size // 2), color, 1)
        cv2.line(frame, (x + size // 2, y - size // 2), (x - size // 2, y + size // 2), color, 1)

    def draw_bow(self, frame, center, size=22):
        x, y = center
        color = config.PASTEL_PINK

        left = np.array([
            [x, y],
            [x - size, y - size // 2],
            [x - size, y + size // 2],
        ], dtype=np.int32)

        right = np.array([
            [x, y],
            [x + size, y - size // 2],
            [x + size, y + size // 2],
        ], dtype=np.int32)

        cv2.fillPoly(frame, [left], color)
        cv2.fillPoly(frame, [right], color)
        cv2.circle(frame, (x, y), size // 4, config.BROWN, -1)

    def draw_base_frame(self, frame):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), config.PASTEL_PINK, 18)
        cv2.rectangle(frame, (15, 15), (w - 16, h - 16), config.CREAM, 4)

        self.draw_heart(frame, (45, 45), 22)
        self.draw_heart(frame, (w - 45, 45), 22)
        self.draw_sparkle(frame, (45, h - 45), 16)
        self.draw_sparkle(frame, (w - 45, h - 45), 16)

    def draw_camera_ui(self, frame, zoom_level, camera_index):
        h, w = frame.shape[:2]

        self.draw_base_frame(frame)

        self.rounded_rect(frame, 245, 15, w - 245, 70, config.SOFT_PINK, radius=24)
        self.put_text(
            frame,
            "Kawaii Puzzle Cam",
            (w // 2 - 205, 53),
            scale=1.25,
            color=config.BROWN,
            thickness=3,
        )

        self.draw_bow(frame, (270, 43), 20)
        self.draw_bow(frame, (w - 270, 43), 20)

        card_x1 = 210
        card_y1 = h - 120
        card_x2 = w - 210
        card_y2 = h - 25

        self.rounded_rect(frame, card_x1, card_y1, card_x2, card_y2, config.CREAM, radius=26)
        self.rounded_rect(frame, card_x1, card_y1, card_x2, card_y2, config.PASTEL_PINK, radius=26, thickness=3)

        self.put_text(frame, "Pinch to zoom", (card_x1 + 35, card_y1 + 36), scale=0.72)
        self.put_text(frame, "Peace sign to capture", (card_x1 + 35, card_y1 + 66), scale=0.72)
        self.put_text(frame, "Press C to switch camera", (card_x1 + 360, card_y1 + 52), scale=0.75, color=config.DARK_PINK, thickness=2)

        self.draw_heart(frame, (card_x2 - 50, card_y1 + 40), 20)
        self.draw_sparkle(frame, (card_x2 - 95, card_y1 + 65), 14)

        self.put_text(
            frame,
            f"Zoom: {zoom_level:.2f}x | Camera: {camera_index}",
            (30, h - 25),
            scale=0.6,
            color=config.BROWN,
            thickness=2,
        )

    def draw_countdown(self, frame, countdown_text):
        h, w = frame.shape[:2]

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), config.SOFT_PINK, -1)
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

        self.rounded_rect(
            frame,
            w // 2 - 150,
            h // 2 - 115,
            w // 2 + 150,
            h // 2 + 115,
            config.CREAM,
            radius=35,
        )

        self.rounded_rect(
            frame,
            w // 2 - 150,
            h // 2 - 115,
            w // 2 + 150,
            h // 2 + 115,
            config.PASTEL_PINK,
            radius=35,
            thickness=5,
        )

        self.put_text(
            frame,
            countdown_text,
            (w // 2 - 70, h // 2 + 20),
            scale=2.6,
            color=config.DARK_PINK,
            thickness=6,
        )

        self.draw_heart(frame, (w // 2 - 105, h // 2 - 70), 26)
        self.draw_sparkle(frame, (w // 2 + 105, h // 2 + 70), 22)

    def draw_puzzle_ui(self, frame, puzzle_game):
        h, w = frame.shape[:2]

        self.draw_base_frame(frame)

        self.rounded_rect(frame, 255, 15, w - 255, 70, config.SOFT_PINK, radius=24)
        self.put_text(
            frame,
            "Put the photo back together!",
            (w // 2 - 250, 52),
            scale=1.02,
            color=config.BROWN,
            thickness=3,
        )

        placed = puzzle_game.placed_count()
        total = puzzle_game.total_pieces

        self.rounded_rect(frame, 25, 88, 270, 138, config.CREAM, radius=18)
        self.rounded_rect(frame, 25, 88, 270, 138, config.PASTEL_PINK, radius=18, thickness=3)
        self.put_text(frame, f"Pieces placed: {placed} / {total}", (45, 120), scale=0.68)

    def draw_cursor(self, frame, cursor, is_pinching):
        if cursor is None:
            return

        x, y = cursor

        if is_pinching:
            color = config.DARK_PINK
            radius = 15
        else:
            color = config.PASTEL_PINK
            radius = 11

        cv2.circle(frame, (x, y), radius, color, -1)
        cv2.circle(frame, (x, y), radius + 3, config.WHITE, 2)
        self.draw_heart(frame, (x + 24, y - 20), 13, color=config.DARK_PINK)

    def draw_complete_ui(self, frame, puzzle_game, elapsed_seconds=0):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (0, 0), (w, h), config.CREAM, -1)
        self.draw_base_frame(frame)

        for particle in self.sparkles:
            particle["y"] -= particle["speed"]

            if particle["y"] < 80:
                particle["y"] = h - 70
                particle["x"] = random.randint(80, w - 80)

            wobble = int(math.sin(particle["phase"] + particle["y"] * 0.03) * 8)
            self.draw_sparkle(
                frame,
                (int(particle["x"] + wobble), int(particle["y"])),
                particle["size"],
                color=config.PEACH,
            )

        self.rounded_rect(frame, w // 2 - 260, 25, w // 2 + 260, 100, config.SOFT_PINK, radius=30)

        self.put_text(
            frame,
            "Puzzle Complete!",
            (w // 2 - 225, 75),
            scale=1.35,
            color=config.DARK_PINK,
            thickness=4,
        )

        puzzle_game.draw_completed_photo(frame)

        self.rounded_rect(frame, w // 2 - 250, h - 120, w // 2 + 250, h - 35, config.WHITE, radius=28)
        self.rounded_rect(frame, w // 2 - 250, h - 120, w // 2 + 250, h - 35, config.PASTEL_PINK, radius=28, thickness=3)

        self.put_text(frame, "Sooo cute! You did it!", (w // 2 - 170, h - 82), scale=0.9, color=config.BROWN, thickness=2)
        self.put_text(frame, "Press R to play again", (w // 2 - 150, h - 52), scale=0.72, color=config.DARK_PINK, thickness=2)

        self.draw_heart(frame, (w // 2 - 215, h - 78), 22)
        self.draw_heart(frame, (w // 2 + 215, h - 78), 22)

    def draw_debug(self, frame, mode, zoom_level, camera_index, pinch_distance, is_pinching, is_peace):
        lines = [
            f"Mode: {mode}",
            f"Camera index: {camera_index}",
            f"Zoom: {zoom_level:.2f}",
            f"Pinch distance: {pinch_distance:.1f}" if pinch_distance is not None else "Pinch distance: None",
            f"Pinching: {is_pinching}",
            f"Peace sign: {is_peace}",
            "C: camera | D: debug | R: reset | ESC: quit",
        ]

        x = 20
        y = 170

        self.rounded_rect(frame, x - 10, y - 28, x + 430, y + 28 * len(lines), config.WHITE, radius=14)
        self.rounded_rect(frame, x - 10, y - 28, x + 430, y + 28 * len(lines), config.BROWN, radius=14, thickness=2)

        for i, line in enumerate(lines):
            self.put_text(
                frame,
                line,
                (x, y + i * 27),
                scale=config.DEBUG_FONT_SCALE,
                color=config.BROWN,
                thickness=2,
            )

    def draw_webcam_unavailable(self, frame, camera_index):
        h, w = frame.shape[:2]

        cv2.rectangle(frame, (0, 0), (w, h), config.CREAM, -1)
        self.draw_base_frame(frame)

        self.rounded_rect(frame, w // 2 - 380, h // 2 - 130, w // 2 + 380, h // 2 + 130, config.WHITE, radius=35)
        self.rounded_rect(frame, w // 2 - 380, h // 2 - 130, w // 2 + 380, h // 2 + 130, config.PASTEL_PINK, radius=35, thickness=5)

        self.put_text(frame, "Camera not available", (w // 2 - 230, h // 2 - 45), scale=1.15, color=config.DARK_PINK, thickness=3)
        self.put_text(frame, f"Current camera index: {camera_index}", (w // 2 - 180, h // 2 + 5), scale=0.75, color=config.BROWN, thickness=2)
        self.put_text(frame, "Press C to try another camera", (w // 2 - 225, h // 2 + 45), scale=0.75, color=config.BROWN, thickness=2)
        self.put_text(frame, "Press ESC to quit", (w // 2 - 120, h // 2 + 85), scale=0.7, color=config.BROWN, thickness=2)