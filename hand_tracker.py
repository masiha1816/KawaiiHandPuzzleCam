"""
hand_tracker.py

MediaPipe hand tracking helper.
"""

import math
import cv2

import config


class HandTracker:
    def __init__(
        self,
        max_num_hands=1,
        detection_confidence=0.65,
        tracking_confidence=0.65,
    ):
        self.available = False
        self.mp_hands = None
        self.mp_draw = None
        self.hands = None

        self.landmarks = None
        self.frame_width = 0
        self.frame_height = 0

        self.smoothed_cursor = None

        self.raw_pinch = False
        self.pinching = False
        self.pinch_counter = 0
        self.release_counter = 0

        try:
            import mediapipe as mp

            self.mp_hands = mp.solutions.hands
            self.mp_draw = mp.solutions.drawing_utils

            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=max_num_hands,
                min_detection_confidence=detection_confidence,
                min_tracking_confidence=tracking_confidence,
            )

            self.available = True
            print("HandTracker: MediaPipe Hands ready.")

        except Exception as e:
            print(f"HandTracker warning: MediaPipe unavailable. Reason: {e}")
            print("The app will still open, but hand gestures will not work.")

    def reset_cursor_smoothing(self):
        self.smoothed_cursor = None

    def process(self, frame_bgr):
        self.landmarks = None
        self.frame_height, self.frame_width = frame_bgr.shape[:2]

        if not self.available:
            return frame_bgr

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        if results.multi_hand_landmarks:
            self.landmarks = results.multi_hand_landmarks[0]

        self._update_pinch_state()

        return frame_bgr

    def _landmark_point(self, landmark_id):
        if self.landmarks is None:
            return None

        lm = self.landmarks.landmark[landmark_id]
        x = int(lm.x * self.frame_width)
        y = int(lm.y * self.frame_height)
        return (x, y)

    def get_thumb_tip(self):
        return self._landmark_point(4)

    def get_index_tip(self):
        return self._landmark_point(8)

    def get_middle_tip(self):
        return self._landmark_point(12)

    def get_ring_tip(self):
        return self._landmark_point(16)

    def get_pinky_tip(self):
        return self._landmark_point(20)

    def get_wrist(self):
        return self._landmark_point(0)

    def get_palm_center(self):
        points = [
            self._landmark_point(0),
            self._landmark_point(5),
            self._landmark_point(17),
        ]

        if any(p is None for p in points):
            return None

        x = int(sum(p[0] for p in points) / len(points))
        y = int(sum(p[1] for p in points) / len(points))
        return (x, y)

    def get_pinch_distance(self):
        thumb = self.get_thumb_tip()
        index = self.get_index_tip()

        if thumb is None or index is None:
            return None

        return math.dist(thumb, index)

    def _update_pinch_state(self):
        distance = self.get_pinch_distance()

        if distance is None:
            self.raw_pinch = False
            self.pinching = False
            self.pinch_counter = 0
            self.release_counter = 0
            return

        self.raw_pinch = distance < config.PINCH_THRESHOLD

        if distance < config.PINCH_THRESHOLD:
            self.pinch_counter += 1
            self.release_counter = 0

            if self.pinch_counter >= config.PINCH_DEBOUNCE_FRAMES:
                self.pinching = True

        elif distance > config.PINCH_RELEASE_THRESHOLD:
            self.release_counter += 1
            self.pinch_counter = 0

            if self.release_counter >= config.PINCH_DEBOUNCE_FRAMES:
                self.pinching = False

    def is_pinching(self):
        return self.pinching

    def is_finger_extended(self, tip_id, pip_id):
        if self.landmarks is None:
            return False

        tip = self.landmarks.landmark[tip_id]
        pip = self.landmarks.landmark[pip_id]

        return tip.y < pip.y

    def is_peace_sign(self):
        if self.landmarks is None:
            return False

        index_extended = self.is_finger_extended(8, 6)
        middle_extended = self.is_finger_extended(12, 10)
        ring_extended = self.is_finger_extended(16, 14)
        pinky_extended = self.is_finger_extended(20, 18)

        return index_extended and middle_extended and not ring_extended and not pinky_extended

    def get_hand_cursor(self):
        index = self.get_index_tip()

        if index is None:
            return None

        if self.smoothed_cursor is None:
            self.smoothed_cursor = index
            return index

        old_x, old_y = self.smoothed_cursor
        new_x, new_y = index

        smoothed_x = int(old_x * config.CURSOR_SMOOTHING_OLD + new_x * config.CURSOR_SMOOTHING_NEW)
        smoothed_y = int(old_y * config.CURSOR_SMOOTHING_OLD + new_y * config.CURSOR_SMOOTHING_NEW)

        self.smoothed_cursor = (smoothed_x, smoothed_y)
        return self.smoothed_cursor

    def draw_landmarks(self, frame):
        if not self.available or self.landmarks is None:
            return frame

        self.mp_draw.draw_landmarks(
            frame,
            self.landmarks,
            self.mp_hands.HAND_CONNECTIONS,
        )
        return frame