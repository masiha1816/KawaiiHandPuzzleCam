"""
puzzle.py

Puzzle piece and puzzle game logic.

Includes:
- timer
- wrong drop counter
- score calculation
- easier grabbing: grabs nearest piece within a radius
"""

import random
import math
import time
import cv2

import config


# Bigger number = easier to grab nearby pieces.
# If grabbing feels too easy/wrong, lower this to 60.
# If it still feels too hard, raise this to 110.
GRAB_RADIUS = 90


class PuzzlePiece:
    def __init__(self, image_crop, target_position, current_position, width, height, row, col):
        self.image_crop = image_crop

        self.target_x, self.target_y = target_position
        self.x, self.y = current_position

        self.width = width
        self.height = height
        self.row = row
        self.col = col

        self.is_placed = False
        self.z_index = 0

    def contains_point(self, point):
        if point is None:
            return False

        px, py = point
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height

    def center(self):
        return (self.x + self.width / 2, self.y + self.height / 2)

    def target_center(self):
        return (
            self.target_x + self.width / 2,
            self.target_y + self.height / 2,
        )

    def distance_to_target(self):
        return math.dist(self.center(), self.target_center())

    def distance_to_cursor(self, cursor):
        if cursor is None:
            return 999999

        px, py = cursor

        # If cursor is inside the piece, distance is 0.
        if self.contains_point(cursor):
            return 0

        # Otherwise, measure distance to nearest edge/corner.
        nearest_x = max(self.x, min(px, self.x + self.width))
        nearest_y = max(self.y, min(py, self.y + self.height))

        return math.dist((px, py), (nearest_x, nearest_y))

    def snap_to_target(self):
        self.x = self.target_x
        self.y = self.target_y
        self.is_placed = True

    def update_position_smooth(self, desired_x, desired_y):
        self.x = int(self.x * (1 - config.PIECE_SMOOTHING) + desired_x * config.PIECE_SMOOTHING)
        self.y = int(self.y * (1 - config.PIECE_SMOOTHING) + desired_y * config.PIECE_SMOOTHING)

    def draw(self, frame, selected=False):
        x = int(self.x)
        y = int(self.y)

        h, w = frame.shape[:2]

        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + self.width)
        y2 = min(h, y + self.height)

        if x1 >= x2 or y1 >= y2:
            return

        crop_x1 = x1 - x
        crop_y1 = y1 - y
        crop_x2 = crop_x1 + (x2 - x1)
        crop_y2 = crop_y1 + (y2 - y1)

        piece_crop = self.image_crop[crop_y1:crop_y2, crop_x1:crop_x2]

        frame[y1:y2, x1:x2] = piece_crop

        if self.is_placed:
            border_color = config.SOFT_MINT
        elif selected:
            border_color = config.DARK_PINK
        else:
            border_color = config.BROWN

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            border_color,
            config.PIECE_BORDER_THICKNESS,
        )


class PuzzleGame:
    def __init__(self):
        self.pieces = []
        self.selected_piece = None
        self.grab_offset = (0, 0)
        self.was_pinching = False
        self.last_z_index = 0

        self.target_x = 0
        self.target_y = 0
        self.target_width = 0
        self.target_height = 0

        self.completed_image = None
        self.total_pieces = 0

        self.rows = config.PUZZLE_ROWS
        self.cols = config.PUZZLE_COLS

        self.start_time = None
        self.end_time = None
        self.wrong_drops = 0
        self.completion_sound_played = False

    def start_new_puzzle(self, captured_frame, frame_width, frame_height, rows=None, cols=None):
        self.pieces = []
        self.selected_piece = None
        self.grab_offset = (0, 0)
        self.was_pinching = False
        self.last_z_index = 0
        self.wrong_drops = 0
        self.completion_sound_played = False

        self.start_time = time.time()
        self.end_time = None

        self.rows = rows if rows is not None else config.PUZZLE_ROWS
        self.cols = cols if cols is not None else config.PUZZLE_COLS

        self._create_puzzle(captured_frame, frame_width, frame_height)

    def _create_puzzle(self, captured_frame, frame_width, frame_height):
        rows = self.rows
        cols = self.cols

        desired_width = int(frame_width * config.TARGET_PUZZLE_WIDTH_RATIO)
        desired_height = int(frame_height * config.TARGET_PUZZLE_HEIGHT_RATIO)

        image_h, image_w = captured_frame.shape[:2]
        image_ratio = image_w / image_h
        target_ratio = desired_width / desired_height

        if target_ratio > image_ratio:
            self.target_height = desired_height
            self.target_width = int(desired_height * image_ratio)
        else:
            self.target_width = desired_width
            self.target_height = int(desired_width / image_ratio)

        self.target_x = int((frame_width - self.target_width) / 2)
        self.target_y = int((frame_height - self.target_height) / 2) + 28

        self.completed_image = cv2.resize(
            captured_frame,
            (self.target_width, self.target_height),
            interpolation=cv2.INTER_AREA,
        )

        piece_w = self.target_width // cols
        piece_h = self.target_height // rows

        self.total_pieces = rows * cols
        occupied_positions = []

        for row in range(rows):
            for col in range(cols):
                x1 = col * piece_w
                y1 = row * piece_h

                x2 = self.target_width if col == cols - 1 else x1 + piece_w
                y2 = self.target_height if row == rows - 1 else y1 + piece_h

                crop = self.completed_image[y1:y2, x1:x2].copy()

                actual_w = x2 - x1
                actual_h = y2 - y1

                target_position = (
                    self.target_x + x1,
                    self.target_y + y1,
                )

                current_position = self._random_scatter_position(
                    frame_width,
                    frame_height,
                    actual_w,
                    actual_h,
                    occupied_positions,
                )

                occupied_positions.append(current_position)

                piece = PuzzlePiece(
                    crop,
                    target_position,
                    current_position,
                    actual_w,
                    actual_h,
                    row,
                    col,
                )

                piece.z_index = self.last_z_index
                self.last_z_index += 1

                self.pieces.append(piece)

        random.shuffle(self.pieces)

    def _random_scatter_position(self, frame_width, frame_height, piece_w, piece_h, occupied_positions):
        margin = 24
        top_safe = config.TITLE_BAR_HEIGHT + 10
        bottom_safe = config.BOTTOM_CARD_HEIGHT + 10

        for _ in range(100):
            x = random.randint(margin, max(margin, frame_width - piece_w - margin))
            y = random.randint(top_safe, max(top_safe, frame_height - piece_h - bottom_safe))

            too_close = False

            for ox, oy in occupied_positions:
                if math.dist((x, y), (ox, oy)) < min(piece_w, piece_h) * 0.65:
                    too_close = True
                    break

            if not too_close:
                return (x, y)

        return (
            random.randint(margin, max(margin, frame_width - piece_w - margin)),
            random.randint(top_safe, max(top_safe, frame_height - piece_h - bottom_safe)),
        )

    def placed_count(self):
        return sum(1 for piece in self.pieces if piece.is_placed)

    def is_complete(self):
        complete = self.placed_count() == self.total_pieces and self.total_pieces > 0

        if complete and self.end_time is None:
            self.end_time = time.time()

        return complete

    def get_elapsed_time(self):
        if self.start_time is None:
            return 0

        if self.end_time is not None:
            return int(self.end_time - self.start_time)

        return int(time.time() - self.start_time)

    def get_difficulty_multiplier(self):
        piece_count = self.rows * self.cols

        if piece_count <= 9:
            return 1.0

        if piece_count <= 16:
            return 1.35

        return 1.75

    def get_score(self):
        base_score = 1000
        time_penalty = self.get_elapsed_time() * 3
        mistake_penalty = self.wrong_drops * 35

        raw_score = base_score - time_penalty - mistake_penalty
        raw_score = max(100, raw_score)

        final_score = int(raw_score * self.get_difficulty_multiplier())
        return final_score

    def get_rank(self):
        score = self.get_score()

        if score >= 1500:
            return "S+ Kawaii Master"

        if score >= 1200:
            return "S Sweet Star"

        if score >= 900:
            return "A Cozy Cutie"

        if score >= 650:
            return "B Bakery Buddy"

        return "C Soft Beginner"

    def update(self, cursor, is_pinching, sound_manager=None):
        pinch_started = is_pinching and not self.was_pinching
        pinch_released = not is_pinching and self.was_pinching

        if pinch_started and cursor is not None:
            piece = self._find_best_piece_to_grab(cursor)

            if piece is not None:
                self.selected_piece = piece

                cursor_x, cursor_y = cursor
                self.grab_offset = (
                    cursor_x - piece.x,
                    cursor_y - piece.y,
                )

                self.last_z_index += 1
                piece.z_index = self.last_z_index

                if sound_manager:
                    sound_manager.play("pickup")

        if is_pinching and self.selected_piece is not None and cursor is not None:
            cursor_x, cursor_y = cursor
            offset_x, offset_y = self.grab_offset

            desired_x = cursor_x - offset_x
            desired_y = cursor_y - offset_y

            self.selected_piece.update_position_smooth(desired_x, desired_y)

        if pinch_released and self.selected_piece is not None:
            piece = self.selected_piece

            if piece.distance_to_target() <= config.SNAP_THRESHOLD:
                piece.snap_to_target()

                if sound_manager:
                    sound_manager.play("success")
            else:
                self.wrong_drops += 1

                if sound_manager:
                    sound_manager.play("place")

            self.selected_piece = None

        self.was_pinching = is_pinching

    def _find_best_piece_to_grab(self, cursor):
        """
        Easier grabbing:
        1. Prefer topmost piece directly under the cursor.
        2. If no piece is directly under cursor, grab nearest piece within GRAB_RADIUS.
        """
        unplaced_pieces = [piece for piece in self.pieces if not piece.is_placed]

        # First: exact hit. If overlapping, choose topmost.
        exact_hits = [piece for piece in unplaced_pieces if piece.contains_point(cursor)]

        if exact_hits:
            exact_hits.sort(key=lambda p: p.z_index, reverse=True)
            return exact_hits[0]

        # Second: nearest within grab radius.
        nearby = []

        for piece in unplaced_pieces:
            distance = piece.distance_to_cursor(cursor)

            if distance <= GRAB_RADIUS:
                nearby.append((distance, piece.z_index, piece))

        if not nearby:
            return None

        # Sort by nearest first. If tied, choose topmost.
        nearby.sort(key=lambda item: (item[0], -item[1]))

        return nearby[0][2]

    def draw_ghost_targets(self, frame):
        overlay = frame.copy()

        for piece in self.pieces:
            x = int(piece.target_x)
            y = int(piece.target_y)
            w = int(piece.width)
            h = int(piece.height)

            cv2.rectangle(overlay, (x, y), (x + w, y + h), config.WHITE, -1)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), config.PASTEL_PINK, 2)

        cv2.addWeighted(
            overlay,
            config.GHOST_ALPHA,
            frame,
            1 - config.GHOST_ALPHA,
            0,
            frame,
        )

    def draw_pieces(self, frame):
        sorted_pieces = sorted(self.pieces, key=lambda p: p.z_index)

        for piece in sorted_pieces:
            selected = piece is self.selected_piece
            piece.draw(frame, selected=selected)

    def draw_completed_photo(self, frame):
        if self.completed_image is None:
            return

        x = self.target_x
        y = self.target_y
        h, w = self.completed_image.shape[:2]

        cv2.rectangle(
            frame,
            (x - 12, y - 12),
            (x + w + 12, y + h + 12),
            config.PASTEL_PINK,
            -1,
        )

        cv2.rectangle(
            frame,
            (x - 6, y - 6),
            (x + w + 6, y + h + 6),
            config.CREAM,
            -1,
        )

        frame[y:y + h, x:x + w] = self.completed_image