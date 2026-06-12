"""
main.py

Kawaii Hand Puzzle Cam

Controls:
1         Easy 3x3 puzzle
2         Medium 4x4 puzzle
3         Hard 5x5 puzzle
4         Photo Booth mode
V         Gallery
T         Settings
I         Instructions / Help
H         Toggle puzzle help overlay
Q         Quit
ESC       Quit
R         Reset / refresh
SPACE     Capture puzzle / start photo booth countdown
+ or =    Zoom in
-         Zoom out
D         Toggle debug
C         Switch camera
M         Return to menu
S         Save screenshot on complete screen
P         Pause / unpause
F         Switch photo frame theme
K         Toggle face stickers on/off
G         Cycle face sticker style
X         Ask to delete current gallery photo
Y         Confirm delete
N         Cancel delete
[ or A    Gallery previous
] or E    Gallery next
"""

import json
import os
import random
import time
from datetime import datetime

import cv2
import numpy as np

import config
from hand_tracker import HandTracker
from puzzle import PuzzleGame
from sounds import SoundManager
from ui import KawaiiUI


def apply_zoom(frame, zoom_level):
    if zoom_level <= 1.0:
        return frame.copy()

    h, w = frame.shape[:2]
    crop_w = int(w / zoom_level)
    crop_h = int(h / zoom_level)

    x1 = int((w - crop_w) / 2)
    y1 = int((h - crop_h) / 2)

    cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


class KawaiiHandPuzzleCamApp:
    def __init__(self):
        self.state = config.STATE_MENU
        self.previous_state_before_pause = config.STATE_MENU

        self.current_camera_index = config.CAMERA_INDEX
        self.cap = None
        self.webcam_ready = False

        self.hand_tracker = HandTracker()
        self.puzzle_game = PuzzleGame()
        self.ui = KawaiiUI()

        self.sound_manager = SoundManager()
        self.sound_manager.load_default_sounds(config)

        self.debug_mode = False
        self.particles_enabled = True
        self.show_puzzle_help = True

        self.zoom_level = 1.0
        self.target_zoom_level = 1.0
        self.previous_pinch_distance_for_zoom = None

        self.peace_start_time = None
        self.peace_stable_frames = 0
        self.countdown_start_time = None
        self.photobooth_countdown_start_time = None

        self.last_camera_frame = None
        self.last_output_frame = None
        self.last_saved_path = None
        self.last_photobooth_frame = None
        self.photobooth_flash_start_time = None
        self.photobooth_saved_message_start_time = None
        self.photobooth_tips = [
            "Smile big for bunny!",
            "Press G to change stickers!",
            "Press F for a new frame!",
            "Try Cat or Bunny stickers!",
            "Press B for quiet mode!",
            "SPACE starts the cute countdown!",
            "Saved photos go to Gallery!",
        ]
        self.photobooth_tip_index = random.randint(0, len(self.photobooth_tips) - 1)
        self.photobooth_last_tip_change_time = time.time()

        self.complete_start_time = None
        self.last_completion_was_new_best = False

        self.difficulty_name = "Easy"
        self.puzzle_rows = 3
        self.puzzle_cols = 3

        self.frame_themes = ["Pink", "Peach", "Bakery", "Heart"]
        self.frame_theme_index = 0

        self.stickers_enabled = True
        self.sticker_styles = [
            "Bow",
            "Heart",
            "Cafe",
            "Cat",
            "Bunny",
            "Star",
            "Angel",
            "Devil",
            "Crown",
            "Sleepy",
            "Kawaii Mix",
        ]
        self.sticker_style_index = 0

        self.face_detector_ready = False
        self.face_cascade = None
        self.last_face_box = None

        self.best_scores = self.load_best_scores()

        self.gallery_images = []
        self.gallery_index = 0
        self.gallery_loaded_image = None
        self.gallery_loaded_path = None
        self.delete_confirm_pending = False

        self.particles = []
        self.last_particle_spawn_time = time.time()

        self.mascot_tips = [
            "Pinch gently to grab puzzle pieces!",
            "Press H during puzzles for help!",
            "Press B anytime for quiet mode!",
            "Photo Booth loves cute stickers!",
            "Try Hard mode for a bigger score!",
            "Press G to change your sticker style!",
            "Press F to change the photo frame!",
            "Small moves make puzzle pieces easier to place!",
        ]
        self.mascot_tip_index = random.randint(0, len(self.mascot_tips) - 1)
        self.mascot_last_tip_change_time = time.time()
        self.mascot_tip_change_seconds = 6.0
        self.mascot_blink_cycle_seconds = 3.8
        self.mascot_blink_length_seconds = 0.16
        self.mascot_celebration_lines = [
            "You did it! So cute!",
            "Puzzle magic complete!",
            "That was adorable!",
            "Amazing puzzle energy!",
            "Bunny is proud of you!",
            "Sparkly win unlocked!",
        ]

        self.load_user_settings()
        self._setup_face_detector()
        self._setup_camera(self.current_camera_index)

    # -------------------------------------------------
    # Settings save/load
    # -------------------------------------------------

    def load_user_settings(self):
        if not os.path.exists(config.SETTINGS_FILE):
            return

        try:
            with open(config.SETTINGS_FILE, "r", encoding="utf-8") as file:
                data = json.load(file)

            self.frame_theme_index = int(data.get("frame_theme_index", self.frame_theme_index))
            self.sticker_style_index = int(data.get("sticker_style_index", self.sticker_style_index))
            self.stickers_enabled = bool(data.get("stickers_enabled", self.stickers_enabled))
            self.particles_enabled = bool(data.get("particles_enabled", self.particles_enabled))
            self.debug_mode = bool(data.get("debug_mode", self.debug_mode))

            if self.sound_manager is not None:
                self.sound_manager.set_sfx_enabled(data.get("sound_enabled", self.sound_manager.enabled))
                self.sound_manager.set_music_enabled(data.get("music_enabled", self.sound_manager.music_enabled))

            self.frame_theme_index = max(0, min(self.frame_theme_index, len(self.frame_themes) - 1))
            self.sticker_style_index = max(0, min(self.sticker_style_index, len(self.sticker_styles) - 1))

            print("Settings loaded.")

        except Exception as e:
            print(f"Could not load settings. Reason: {e}")

    def save_user_settings(self):
        data = {
            "frame_theme_index": self.frame_theme_index,
            "sticker_style_index": self.sticker_style_index,
            "stickers_enabled": self.stickers_enabled,
            "particles_enabled": self.particles_enabled,
            "debug_mode": self.debug_mode,
            "sound_enabled": self.sound_manager.enabled if self.sound_manager is not None else True,
            "music_enabled": self.sound_manager.music_enabled if self.sound_manager is not None else True,
        }

        try:
            with open(config.SETTINGS_FILE, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)

            print("Settings saved.")

        except Exception as e:
            print(f"Could not save settings. Reason: {e}")

    # -------------------------------------------------
    # Basic getters / switches
    # -------------------------------------------------

    def current_frame_theme(self):
        return self.frame_themes[self.frame_theme_index]

    def current_sticker_style(self):
        return self.sticker_styles[self.sticker_style_index]

    def difficulty_key(self):
        return f"{self.difficulty_name}_{self.puzzle_rows}x{self.puzzle_cols}"

    def switch_frame_theme(self):
        self.frame_theme_index = (self.frame_theme_index + 1) % len(self.frame_themes)
        print(f"Frame theme: {self.current_frame_theme()}")
        self.save_user_settings()

    def switch_sticker_style(self):
        self.sticker_style_index = (self.sticker_style_index + 1) % len(self.sticker_styles)
        print(f"Sticker style: {self.current_sticker_style()}")
        self.save_user_settings()

    def toggle_stickers(self):
        self.stickers_enabled = not self.stickers_enabled
        print(f"Face stickers enabled: {self.stickers_enabled}")
        self.save_user_settings()

    def toggle_particles(self):
        self.particles_enabled = not self.particles_enabled

        if not self.particles_enabled:
            self.particles = []

        print(f"Particles enabled: {self.particles_enabled}")
        self.save_user_settings()

    def toggle_debug(self):
        self.debug_mode = not self.debug_mode
        print(f"Debug mode: {self.debug_mode}")
        self.save_user_settings()

    def toggle_sound_effects(self):
        if self.sound_manager is None:
            return

        self.sound_manager.toggle_sfx()
        self.save_user_settings()

    def toggle_background_music(self):
        if self.sound_manager is None:
            return

        self.sound_manager.toggle_music()
        self.save_user_settings()

    def toggle_all_audio(self):
        if self.sound_manager is None:
            return

        self.sound_manager.toggle_all_audio()
        self.save_user_settings()

    def toggle_puzzle_help(self):
        self.show_puzzle_help = not self.show_puzzle_help
        print(f"Puzzle help overlay: {self.show_puzzle_help}")

    # -------------------------------------------------
    # Best scores
    # -------------------------------------------------

    def load_best_scores(self):
        if not os.path.exists(config.BEST_SCORE_FILE):
            return {}

        try:
            with open(config.BEST_SCORE_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:
            return {}

    def save_best_scores(self):
        try:
            with open(config.BEST_SCORE_FILE, "w", encoding="utf-8") as file:
                json.dump(self.best_scores, file, indent=2)
        except Exception as e:
            print(f"Could not save best scores. Reason: {e}")

    def update_best_score_if_needed(self):
        key = self.difficulty_key()

        current_score = self.puzzle_game.get_score()
        current_time = self.puzzle_game.get_elapsed_time()
        current_wrong_drops = self.puzzle_game.wrong_drops
        current_rank = self.puzzle_game.get_rank()

        old = self.best_scores.get(key)
        is_new_best = False

        if old is None:
            is_new_best = True
        elif current_score > old.get("score", 0):
            is_new_best = True
        elif current_score == old.get("score", 0) and current_time < old.get("time", 999999):
            is_new_best = True

        if is_new_best:
            self.best_scores[key] = {
                "difficulty": self.difficulty_name,
                "rows": self.puzzle_rows,
                "cols": self.puzzle_cols,
                "score": current_score,
                "time": current_time,
                "wrong_drops": current_wrong_drops,
                "rank": current_rank,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            self.save_best_scores()
            print(f"New best score for {key}: {current_score}")

        return is_new_best

    def get_best_score_text(self):
        key = self.difficulty_key()
        best = self.best_scores.get(key)

        if best is None:
            return "Best: none yet"

        return f"Best: {best['score']} pts | {best['time']}s | {best['rank']}"

    # -------------------------------------------------
    # Setup
    # -------------------------------------------------

    def _setup_face_detector(self):
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)

            if cascade.empty():
                print("Friendly warning: Could not load face detector cascade.")
                self.face_detector_ready = False
                self.face_cascade = None
                return

            self.face_cascade = cascade
            self.face_detector_ready = True
            print("Face detector ready.")

        except Exception as e:
            print(f"Friendly warning: Face detector unavailable. Reason: {e}")
            self.face_detector_ready = False
            self.face_cascade = None

    def _setup_camera(self, camera_index):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        print(f"Trying camera index: {camera_index}")

        self.cap = cv2.VideoCapture(camera_index)

        if not self.cap.isOpened():
            print(f"Friendly warning: Camera index {camera_index} is unavailable.")
            self.webcam_ready = False
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.FPS_TARGET)

        ok, frame = self.cap.read()

        if not ok or frame is None:
            print(f"Friendly warning: Camera index {camera_index} opened but did not return frames.")
            self.webcam_ready = False
            return

        self.current_camera_index = camera_index
        self.webcam_ready = True
        self.hand_tracker.reset_cursor_smoothing()

        print(f"Camera ready on index {camera_index}.")

    # -------------------------------------------------
    # App flow
    # -------------------------------------------------

    def switch_camera(self):
        next_index = self.current_camera_index + 1

        if next_index > config.MAX_CAMERA_INDEX_TO_TRY:
            next_index = 0

        self._setup_camera(next_index)

    def set_difficulty(self, name, rows, cols):
        self.difficulty_name = name
        self.puzzle_rows = rows
        self.puzzle_cols = cols
        self.reset_to_camera()

    def enter_photobooth(self):
        self.state = config.STATE_PHOTOBOOTH
        self.previous_state_before_pause = config.STATE_PHOTOBOOTH

        self.zoom_level = 1.0
        self.target_zoom_level = 1.0
        self.previous_pinch_distance_for_zoom = None
        self.last_saved_path = None
        self.photobooth_countdown_start_time = None
        self.hand_tracker.reset_cursor_smoothing()

        print("Photo Booth mode started.")

    def start_photobooth_countdown(self):
        self.state = config.STATE_PHOTOBOOTH_COUNTDOWN
        self.previous_state_before_pause = config.STATE_PHOTOBOOTH_COUNTDOWN
        self.photobooth_countdown_start_time = time.time()
        print("Photo Booth countdown started.")

    def enter_gallery(self):
        self.refresh_gallery()
        self.delete_confirm_pending = False

        self.state = config.STATE_GALLERY
        self.previous_state_before_pause = config.STATE_GALLERY

        print("Gallery opened.")

    def enter_settings(self):
        self.state = config.STATE_SETTINGS
        self.previous_state_before_pause = config.STATE_SETTINGS
        print("Settings opened.")

    def toggle_pause(self):
        if self.state == config.STATE_PAUSED:
            self.state = self.previous_state_before_pause
            print("Unpaused.")
            return

        if self.state in [
            config.STATE_CAMERA,
            config.STATE_PUZZLE,
            config.STATE_COMPLETE,
            config.STATE_PHOTOBOOTH,
            config.STATE_PHOTOBOOTH_COUNTDOWN,
            config.STATE_GALLERY,
            config.STATE_SETTINGS,
        ]:
            self.previous_state_before_pause = self.state
            self.state = config.STATE_PAUSED
            print("Paused.")

    def return_to_menu(self):
        self.state = config.STATE_MENU
        self.previous_state_before_pause = config.STATE_MENU

        self.zoom_level = 1.0
        self.target_zoom_level = 1.0
        self.previous_pinch_distance_for_zoom = None

        self.peace_start_time = None
        self.peace_stable_frames = 0
        self.countdown_start_time = None
        self.photobooth_countdown_start_time = None

        self.last_saved_path = None
        self.last_photobooth_frame = None
        self.photobooth_flash_start_time = None
        self.photobooth_saved_message_start_time = None
        self.photobooth_tips = [
            "Smile big for bunny!",
            "Press G to change stickers!",
            "Press F for a new frame!",
            "Try Cat or Bunny stickers!",
            "Press B for quiet mode!",
            "SPACE starts the cute countdown!",
            "Saved photos go to Gallery!",
        ]
        self.photobooth_tip_index = random.randint(0, len(self.photobooth_tips) - 1)
        self.photobooth_last_tip_change_time = time.time()
        self.delete_confirm_pending = False

        self.puzzle_game = PuzzleGame()
        self.ui.reset_particles()
        self.hand_tracker.reset_cursor_smoothing()

    def reset_to_camera(self):
        self.state = config.STATE_CAMERA
        self.previous_state_before_pause = config.STATE_CAMERA

        self.zoom_level = 1.0
        self.target_zoom_level = 1.0
        self.previous_pinch_distance_for_zoom = None

        self.peace_start_time = None
        self.peace_stable_frames = 0
        self.countdown_start_time = None
        self.photobooth_countdown_start_time = None
        self.complete_start_time = None
        self.last_completion_was_new_best = False
        self.last_saved_path = None

        self.puzzle_game = PuzzleGame()
        self.ui.reset_particles()
        self.hand_tracker.reset_cursor_smoothing()

        print(f"Starting {self.difficulty_name} mode: {self.puzzle_rows}x{self.puzzle_cols}")

    # -------------------------------------------------
    # Save / gallery
    # -------------------------------------------------

    def make_save_path(self, mode):
        os.makedirs(config.SCREENSHOT_FOLDER, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_mode = mode.lower().replace(" ", "_")
        safe_difficulty = self.difficulty_name.lower().replace(" ", "_")
        safe_frame = self.current_frame_theme().lower().replace(" ", "_")
        safe_sticker = self.current_sticker_style().lower().replace(" ", "_")

        filename = (
            f"kawaii_{safe_mode}_{safe_difficulty}_"
            f"{self.puzzle_rows}x{self.puzzle_cols}_"
            f"{safe_frame}_{safe_sticker}_{timestamp}.png"
        )

        return os.path.join(config.SCREENSHOT_FOLDER, filename)

    def save_image(self, image, mode):
        if image is None:
            print("No image available to save.")
            return

        path = self.make_save_path(mode)
        ok = cv2.imwrite(path, image)

        if ok:
            self.last_saved_path = path
            print(f"Saved: {path}")
            self.sound_manager.play("sparkle")
            self.refresh_gallery()
        else:
            print("Could not save image.")

    def save_screenshot(self):
        self.save_image(self.last_output_frame, "puzzle")

    def save_photobooth_photo(self):
        self.save_image(self.last_photobooth_frame, "photobooth")
        self.photobooth_flash_start_time = time.time()
        self.photobooth_saved_message_start_time = time.time()


    def refresh_gallery(self):
        os.makedirs(config.SCREENSHOT_FOLDER, exist_ok=True)

        valid_extensions = [".png", ".jpg", ".jpeg"]
        paths = []

        for name in os.listdir(config.SCREENSHOT_FOLDER):
            lower = name.lower()

            if any(lower.endswith(ext) for ext in valid_extensions):
                paths.append(os.path.join(config.SCREENSHOT_FOLDER, name))

        paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        self.gallery_images = paths

        if self.gallery_index >= len(self.gallery_images):
            self.gallery_index = 0

        self.gallery_loaded_image = None
        self.gallery_loaded_path = None

    def gallery_next(self):
        self.delete_confirm_pending = False

        if not self.gallery_images:
            return

        self.gallery_index += 1

        if self.gallery_index >= len(self.gallery_images):
            self.gallery_index = 0

        self.gallery_loaded_image = None
        self.gallery_loaded_path = None

    def gallery_previous(self):
        self.delete_confirm_pending = False

        if not self.gallery_images:
            return

        self.gallery_index -= 1

        if self.gallery_index < 0:
            self.gallery_index = len(self.gallery_images) - 1

        self.gallery_loaded_image = None
        self.gallery_loaded_path = None

    def ask_delete_current_gallery_image(self):
        if not self.gallery_images:
            print("No gallery image to delete.")
            return

        self.delete_confirm_pending = True
        print("Delete confirmation pending. Press Y to delete or N to cancel.")

    def cancel_delete_gallery_image(self):
        self.delete_confirm_pending = False
        print("Delete cancelled.")

    def confirm_delete_current_gallery_image(self):
        if not self.delete_confirm_pending:
            return

        if not self.gallery_images:
            self.delete_confirm_pending = False
            return

        path = self.gallery_images[self.gallery_index]

        try:
            os.remove(path)
            print(f"Deleted: {path}")
        except Exception as e:
            print(f"Could not delete image. Reason: {e}")
            self.delete_confirm_pending = False
            return

        self.delete_confirm_pending = False
        self.refresh_gallery()

        if self.gallery_index >= len(self.gallery_images):
            self.gallery_index = max(0, len(self.gallery_images) - 1)

        self.gallery_loaded_image = None
        self.gallery_loaded_path = None

    def get_current_gallery_image(self):
        if not self.gallery_images:
            return None, None

        path = self.gallery_images[self.gallery_index]

        if self.gallery_loaded_path == path and self.gallery_loaded_image is not None:
            return self.gallery_loaded_image, path

        image = cv2.imread(path)

        if image is None:
            return None, path

        self.gallery_loaded_image = image
        self.gallery_loaded_path = path

        return image, path

    # -------------------------------------------------
    # Capture / countdown
    # -------------------------------------------------

    def manual_capture(self):
        if self.last_camera_frame is None:
            print("Cannot capture yet. No camera frame available.")
            return

        self.sound_manager.play("capture")

        h, w = self.last_camera_frame.shape[:2]

        self.puzzle_game.start_new_puzzle(
            self.last_camera_frame.copy(),
            w,
            h,
            rows=self.puzzle_rows,
            cols=self.puzzle_cols,
        )

        self.state = config.STATE_PUZZLE
        self.previous_state_before_pause = config.STATE_PUZZLE
        print("Manual photo captured. Puzzle mode started.")

    def start_countdown(self):
        self.state = config.STATE_COUNTDOWN
        self.countdown_start_time = time.time()
        print("Countdown started.")

    def finish_countdown_capture(self):
        if self.last_camera_frame is None:
            self.state = config.STATE_CAMERA
            return

        self.sound_manager.play("capture")

        h, w = self.last_camera_frame.shape[:2]

        self.puzzle_game.start_new_puzzle(
            self.last_camera_frame.copy(),
            w,
            h,
            rows=self.puzzle_rows,
            cols=self.puzzle_cols,
        )

        self.state = config.STATE_PUZZLE
        self.previous_state_before_pause = config.STATE_PUZZLE
        self.countdown_start_time = None

        print("Photo captured. Puzzle mode started.")

    # -------------------------------------------------
    # Reading input
    # -------------------------------------------------

    def _read_frame(self):
        if not self.webcam_ready or self.cap is None:
            frame = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
            self.ui.draw_webcam_unavailable(frame, self.current_camera_index)
            return frame, False

        ok, frame = self.cap.read()

        if not ok or frame is None:
            frame = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
            self.ui.draw_webcam_unavailable(frame, self.current_camera_index)
            return frame, False

        frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
        frame = cv2.flip(frame, 1)

        return frame, True

    def _handle_keyboard(self, key):
        if key == 255:
            return True

        if key == 27 or key in [ord("q"), ord("Q")]:
            self.save_user_settings()
            return False

        if key in [ord("p"), ord("P")]:
            self.toggle_pause()
            return True

        if key in [ord("m"), ord("M")]:
            self.return_to_menu()
            return True

        if key in [ord("v"), ord("V")]:
            self.enter_gallery()
            return True

        if key in [ord("t"), ord("T")]:
            self.enter_settings()
            return True

        if key in [ord("h"), ord("H")]:
            if self.state == config.STATE_PUZZLE:
                self.toggle_puzzle_help()
            else:
                self.enter_instructions()
            return True

        if key in [ord("i"), ord("I")]:
            self.enter_instructions()
            return True

        if key in [ord("r"), ord("R")]:
            if self.state == config.STATE_GALLERY:
                self.refresh_gallery()
                self.delete_confirm_pending = False
            elif self.state in [config.STATE_PHOTOBOOTH, config.STATE_PHOTOBOOTH_COUNTDOWN]:
                self.enter_photobooth()
            elif self.state == config.STATE_SETTINGS:
                self.enter_settings()
            else:
                self.reset_to_camera()
            return True

        if key in [ord("f"), ord("F")]:
            self.switch_frame_theme()
            return True

        if key in [ord("k"), ord("K")]:
            self.toggle_stickers()
            return True

        if key in [ord("g"), ord("G")]:
            self.switch_sticker_style()
            return True

        if key in [ord("d"), ord("D")]:
            self.toggle_debug()
            return True

        if key in [ord("b"), ord("B")]:
            self.toggle_all_audio()
            return True

        if self.state == config.STATE_SETTINGS:
            if key == ord("1"):
                self.toggle_stickers()
            elif key == ord("2"):
                self.switch_sticker_style()
            elif key == ord("3"):
                self.switch_frame_theme()
            elif key == ord("4"):
                self.toggle_particles()
            elif key == ord("5"):
                self.toggle_debug()
            elif key == ord("6"):
                self.toggle_sound_effects()
            elif key == ord("7"):
                self.toggle_background_music()

            return True

        if self.state == config.STATE_GALLERY:
            if key in [ord("y"), ord("Y")]:
                self.confirm_delete_current_gallery_image()
            elif key in [ord("n"), ord("N")]:
                self.cancel_delete_gallery_image()
            elif key in [ord("x"), ord("X")]:
                self.ask_delete_current_gallery_image()
            elif key in [ord("["), ord("a"), ord("A"), 81]:
                self.gallery_previous()
            elif key in [ord("]"), ord("e"), ord("E"), 83]:
                self.gallery_next()

            return True

        if self.state == config.STATE_PAUSED:
            return True

        if key == ord("1"):
            self.set_difficulty("Easy", 3, 3)

        elif key == ord("2"):
            self.set_difficulty("Medium", 4, 4)

        elif key == ord("3"):
            self.set_difficulty("Hard", 5, 5)

        elif key == ord("4"):
            self.enter_photobooth()

        elif key in [ord("s"), ord("S")]:
            if self.state == config.STATE_COMPLETE:
                self.save_screenshot()
            elif self.state == config.STATE_PHOTOBOOTH:
                self.start_photobooth_countdown()
            else:
                print("Save is available on complete screen or photo booth.")

        elif key == ord(" "):
            if self.state == config.STATE_CAMERA:
                self.manual_capture()
            elif self.state == config.STATE_PHOTOBOOTH:
                self.start_photobooth_countdown()

        elif key in [ord("+"), ord("=")]:
            self.target_zoom_level = min(config.MAX_ZOOM, self.target_zoom_level + 0.1)

        elif key in [ord("-"), ord("_")]:
            self.target_zoom_level = max(config.MIN_ZOOM, self.target_zoom_level - 0.1)

        elif key in [ord("c"), ord("C")]:
            print("Switching camera...")
            self.switch_camera()

        return True

    # -------------------------------------------------
    # Zoom / gestures
    # -------------------------------------------------

    def _update_zoom_from_pinch(self, pinch_distance):
        if pinch_distance is None:
            self.previous_pinch_distance_for_zoom = None
            return

        if pinch_distance > config.ZOOM_PINCH_ACTIVE_DISTANCE:
            self.previous_pinch_distance_for_zoom = None
            return

        if self.previous_pinch_distance_for_zoom is None:
            self.previous_pinch_distance_for_zoom = pinch_distance
            return

        delta = pinch_distance - self.previous_pinch_distance_for_zoom

        self.target_zoom_level += delta * config.ZOOM_SENSITIVITY
        self.target_zoom_level = max(config.MIN_ZOOM, min(config.MAX_ZOOM, self.target_zoom_level))

        self.previous_pinch_distance_for_zoom = pinch_distance

    def _smooth_zoom(self):
        self.zoom_level = (
            self.zoom_level * (1 - config.ZOOM_SMOOTHING)
            + self.target_zoom_level * config.ZOOM_SMOOTHING
        )

        self.zoom_level = max(config.MIN_ZOOM, min(config.MAX_ZOOM, self.zoom_level))

    def _update_peace_capture_detection(self, is_peace):
        if is_peace:
            self.peace_stable_frames += 1

            if self.peace_start_time is None:
                self.peace_start_time = time.time()

            stable_time = time.time() - self.peace_start_time

            if (
                stable_time >= config.PEACE_HOLD_SECONDS
                and self.peace_stable_frames >= config.PEACE_DEBOUNCE_FRAMES
            ):
                self.start_countdown()
                self.peace_start_time = None
                self.peace_stable_frames = 0
        else:
            self.peace_start_time = None
            self.peace_stable_frames = 0

    # -------------------------------------------------
    # Particles
    # -------------------------------------------------

    def spawn_particle(self, frame_width, frame_height):
        kind = random.choice(["heart", "sparkle"])
        x = random.randint(30, frame_width - 30)
        y = frame_height + random.randint(5, 80)

        particle = {
            "kind": kind,
            "x": float(x),
            "y": float(y),
            "speed": random.uniform(0.7, 1.8),
            "size": random.randint(10, 22),
            "life": random.uniform(2.5, 5.0),
            "born": time.time(),
        }

        self.particles.append(particle)

    def update_and_draw_particles(self, canvas, amount="normal"):
        if not self.particles_enabled:
            return

        h, w = canvas.shape[:2]
        now = time.time()

        spawn_delay = 0.20 if amount == "many" else 0.45

        if now - self.last_particle_spawn_time >= spawn_delay:
            self.spawn_particle(w, h)
            self.last_particle_spawn_time = now

        alive = []

        for p in self.particles:
            age = now - p["born"]

            if age > p["life"]:
                continue

            p["y"] -= p["speed"]
            p["x"] += np.sin(age * 3.0) * 0.4

            x = int(p["x"])
            y = int(p["y"])
            size = int(p["size"])

            if p["kind"] == "heart":
                self._draw_simple_heart(canvas, (x, y), size, config.DARK_PINK)
            else:
                self._draw_simple_sparkle(canvas, (x, y), max(6, size // 2), config.WHITE)

            alive.append(p)

        self.particles = alive[-80:]

    # -------------------------------------------------
    # Shape helpers
    # -------------------------------------------------

    def _draw_soft_blush(self, canvas, center, radius, color=(220, 180, 255)):
        overlay = canvas.copy()
        cv2.circle(overlay, center, radius, color, -1)
        cv2.addWeighted(overlay, 0.28, canvas, 0.72, 0, canvas)

    def _draw_simple_heart(self, canvas, center, size, color):
        cx, cy = center
        r = max(2, size // 3)

        cv2.circle(canvas, (cx - r, cy - r // 2), r, color, -1)
        cv2.circle(canvas, (cx + r, cy - r // 2), r, color, -1)

        points = np.array(
            [
                [cx - size, cy - r // 3],
                [cx + size, cy - r // 3],
                [cx, cy + size],
            ],
            np.int32,
        )

        cv2.fillConvexPoly(canvas, points, color)

    def _draw_simple_sparkle(self, canvas, center, size, color):
        cx, cy = center

        cv2.line(canvas, (cx - size, cy), (cx + size, cy), color, 2)
        cv2.line(canvas, (cx, cy - size), (cx, cy + size), color, 2)
        cv2.line(canvas, (cx - size // 2, cy - size // 2), (cx + size // 2, cy + size // 2), color, 1)
        cv2.line(canvas, (cx - size // 2, cy + size // 2), (cx + size // 2, cy - size // 2), color, 1)

    def _draw_bow(self, canvas, center, width, height):
        cx, cy = center

        left_center = (int(cx - width * 0.32), cy)
        right_center = (int(cx + width * 0.32), cy)

        cv2.ellipse(canvas, left_center, (int(width * 0.28), int(height * 0.22)), 25, 0, 360, config.DARK_PINK, -1)
        cv2.ellipse(canvas, right_center, (int(width * 0.28), int(height * 0.22)), -25, 0, 360, config.DARK_PINK, -1)

        cv2.ellipse(canvas, left_center, (int(width * 0.18), int(height * 0.12)), 25, 0, 360, config.SOFT_PINK, -1)
        cv2.ellipse(canvas, right_center, (int(width * 0.18), int(height * 0.12)), -25, 0, 360, config.SOFT_PINK, -1)

        cv2.circle(canvas, (cx, cy), int(height * 0.18), config.BROWN, -1)
        cv2.circle(canvas, (cx, cy), int(height * 0.10), config.PEACH, -1)

    def _draw_cookie(self, canvas, center, radius):
        cx, cy = center

        cv2.circle(canvas, (cx, cy), radius, config.PEACH, -1)
        cv2.circle(canvas, (cx, cy), radius, config.BROWN, 2)

        chip_positions = [
            (cx - radius // 3, cy - radius // 4),
            (cx + radius // 4, cy - radius // 6),
            (cx - radius // 6, cy + radius // 4),
            (cx + radius // 5, cy + radius // 5),
        ]

        for px, py in chip_positions:
            cv2.circle(canvas, (px, py), max(2, radius // 6), config.BROWN, -1)

    def _draw_triangle(self, canvas, points, color, border_color=None):
        points_np = np.array(points, np.int32)
        cv2.fillConvexPoly(canvas, points_np, color)

        if border_color is not None:
            cv2.polylines(canvas, [points_np], True, border_color, 3)

    def _draw_cat_ear(self, canvas, base_center, size):
        cx, cy = base_center

        points = [
            (cx - size, cy + size),
            (cx, cy - size),
            (cx + size, cy + size),
        ]

        self._draw_triangle(canvas, points, config.BROWN, config.WHITE)

        inner_points = [
            (cx - size // 2, cy + size // 2),
            (cx, cy - size // 3),
            (cx + size // 2, cy + size // 2),
        ]

        self._draw_triangle(canvas, inner_points, config.SOFT_PINK, None)

    def _draw_bunny_ear(self, canvas, center, width, height, angle):
        cx, cy = center

        cv2.ellipse(canvas, (cx, cy), (width, height), angle, 0, 360, config.WHITE, -1)
        cv2.ellipse(canvas, (cx, cy), (width, height), angle, 0, 360, config.BROWN, 3)

        cv2.ellipse(
            canvas,
            (cx, cy),
            (max(2, width // 2), max(4, int(height * 0.65))),
            angle,
            0,
            360,
            config.SOFT_PINK,
            -1,
        )

    def _draw_halo(self, canvas, center, width, height):
        cx, cy = center
        cv2.ellipse(canvas, (cx, cy), (width, height), 0, 0, 360, config.SOFT_YELLOW, 5)
        cv2.ellipse(canvas, (cx, cy), (width, height), 0, 0, 360, config.WHITE, 2)

    def _draw_devil_horn(self, canvas, base_center, size):
        cx, cy = base_center

        points = [
            (cx - size, cy + size),
            (cx, cy - size),
            (cx + size, cy + size),
        ]

        self._draw_triangle(canvas, points, config.DARK_PINK, config.BROWN)

    def _draw_crown(self, canvas, center, width, height):
        cx, cy = center

        x1 = cx - width // 2
        x2 = cx + width // 2
        y_bottom = cy + height // 2
        y_top = cy - height // 2

        points = [
            (x1, y_bottom),
            (x1 + width // 5, y_top + height // 3),
            (cx - width // 6, y_bottom - height // 4),
            (cx, y_top),
            (cx + width // 6, y_bottom - height // 4),
            (x2 - width // 5, y_top + height // 3),
            (x2, y_bottom),
        ]

        self._draw_triangle(canvas, points, config.SOFT_YELLOW, config.BROWN)
        cv2.rectangle(canvas, (x1, y_bottom - 8), (x2, y_bottom + 8), config.SOFT_YELLOW, -1)
        cv2.rectangle(canvas, (x1, y_bottom - 8), (x2, y_bottom + 8), config.BROWN, 2)

        gem_positions = [
            (x1 + width // 5, y_top + height // 3),
            (cx, y_top + 4),
            (x2 - width // 5, y_top + height // 3),
        ]

        for pos in gem_positions:
            cv2.circle(canvas, pos, max(3, height // 10), config.DARK_PINK, -1)

    def _draw_moon(self, canvas, center, radius):
        cx, cy = center

        cv2.circle(canvas, (cx, cy), radius, config.SOFT_YELLOW, -1)
        cv2.circle(canvas, (cx + radius // 2, cy - radius // 4), radius, config.CREAM, -1)

    def _draw_whiskers(self, canvas, left_cheek, right_cheek, width):
        lx, ly = left_cheek
        rx, ry = right_cheek

        line_len = max(20, int(width * 0.18))

        for offset in [-12, 0, 12]:
            cv2.line(canvas, (lx - 5, ly + offset), (lx - line_len, ly + offset - 5), config.BROWN, 2)
            cv2.line(canvas, (rx + 5, ry + offset), (rx + line_len, ry + offset - 5), config.BROWN, 2)


    # -------------------------------------------------
    # Cute mascot helper
    # -------------------------------------------------

    def current_mascot_tip(self):
        if not hasattr(self, "mascot_tips") or not self.mascot_tips:
            return "Have a cozy puzzle day!"

        now = time.time()

        if not hasattr(self, "mascot_last_tip_change_time"):
            self.mascot_last_tip_change_time = now

        if not hasattr(self, "mascot_tip_change_seconds"):
            self.mascot_tip_change_seconds = 6.0

        if now - self.mascot_last_tip_change_time >= self.mascot_tip_change_seconds:
            self.next_mascot_tip()
            self.mascot_last_tip_change_time = now

        return self.mascot_tips[self.mascot_tip_index % len(self.mascot_tips)]

    def next_mascot_tip(self):
        if not hasattr(self, "mascot_tips") or not self.mascot_tips:
            return

        self.mascot_tip_index = (self.mascot_tip_index + 1) % len(self.mascot_tips)

    def current_mascot_celebration(self):
        if not hasattr(self, "mascot_celebration_lines") or not self.mascot_celebration_lines:
            return "You did it! So cute!"

        elapsed = self.puzzle_game.get_elapsed_time() if self.puzzle_game is not None else 0
        score = self.puzzle_game.get_score() if self.puzzle_game is not None else 0

        index = int((elapsed + score + time.time()) % len(self.mascot_celebration_lines))
        return self.mascot_celebration_lines[index]

    def _mascot_animation_values(self):
        now = time.time()

        bounce = int(np.sin(now * 4.0) * 5)

        blink_cycle = getattr(self, "mascot_blink_cycle_seconds", 3.8)
        blink_length = getattr(self, "mascot_blink_length_seconds", 0.16)

        blink_time = now % blink_cycle
        is_blinking = blink_time < blink_length

        ear_wiggle = int(np.sin(now * 3.2) * 3)

        return bounce, is_blinking, ear_wiggle

    def _draw_bunny_mascot(self, canvas, center, size=70):
        bounce, is_blinking, ear_wiggle = self._mascot_animation_values()

        cx, cy = center
        cy = cy + bounce

        # Shadow
        cv2.ellipse(
            canvas,
            (cx, cy + int(size * 0.76) - bounce // 2),
            (int(size * 0.58), int(size * 0.16)),
            0,
            0,
            360,
            (210, 210, 220),
            -1,
        )

        # Ears
        left_ear_center = (cx - int(size * 0.28) - ear_wiggle, cy - int(size * 0.62))
        right_ear_center = (cx + int(size * 0.28) + ear_wiggle, cy - int(size * 0.62))

        cv2.ellipse(
            canvas,
            left_ear_center,
            (int(size * 0.18), int(size * 0.46)),
            -12 - ear_wiggle,
            0,
            360,
            config.WHITE,
            -1,
        )
        cv2.ellipse(
            canvas,
            right_ear_center,
            (int(size * 0.18), int(size * 0.46)),
            12 + ear_wiggle,
            0,
            360,
            config.WHITE,
            -1,
        )

        cv2.ellipse(
            canvas,
            left_ear_center,
            (int(size * 0.09), int(size * 0.32)),
            -12 - ear_wiggle,
            0,
            360,
            config.SOFT_PINK,
            -1,
        )
        cv2.ellipse(
            canvas,
            right_ear_center,
            (int(size * 0.09), int(size * 0.32)),
            12 + ear_wiggle,
            0,
            360,
            config.SOFT_PINK,
            -1,
        )

        cv2.ellipse(
            canvas,
            left_ear_center,
            (int(size * 0.18), int(size * 0.46)),
            -12 - ear_wiggle,
            0,
            360,
            config.BROWN,
            2,
        )
        cv2.ellipse(
            canvas,
            right_ear_center,
            (int(size * 0.18), int(size * 0.46)),
            12 + ear_wiggle,
            0,
            360,
            config.BROWN,
            2,
        )

        # Body
        cv2.ellipse(
            canvas,
            (cx, cy + int(size * 0.62)),
            (int(size * 0.44), int(size * 0.36)),
            0,
            0,
            360,
            config.CREAM,
            -1,
        )
        cv2.ellipse(
            canvas,
            (cx, cy + int(size * 0.62)),
            (int(size * 0.44), int(size * 0.36)),
            0,
            0,
            360,
            config.BROWN,
            3,
        )

        # Head
        cv2.circle(canvas, (cx, cy), int(size * 0.48), config.WHITE, -1)
        cv2.circle(canvas, (cx, cy), int(size * 0.48), config.BROWN, 3)

        # Eyes
        eye_y = cy - int(size * 0.08)
        left_eye = (cx - int(size * 0.17), eye_y)
        right_eye = (cx + int(size * 0.17), eye_y)

        if is_blinking:
            cv2.line(
                canvas,
                (left_eye[0] - int(size * 0.055), left_eye[1]),
                (left_eye[0] + int(size * 0.055), left_eye[1]),
                config.BROWN,
                3,
            )
            cv2.line(
                canvas,
                (right_eye[0] - int(size * 0.055), right_eye[1]),
                (right_eye[0] + int(size * 0.055), right_eye[1]),
                config.BROWN,
                3,
            )
        else:
            cv2.circle(canvas, left_eye, max(3, int(size * 0.045)), config.BROWN, -1)
            cv2.circle(canvas, right_eye, max(3, int(size * 0.045)), config.BROWN, -1)
            cv2.circle(canvas, (left_eye[0] - 1, left_eye[1] - 1), max(1, int(size * 0.015)), config.WHITE, -1)
            cv2.circle(canvas, (right_eye[0] - 1, right_eye[1] - 1), max(1, int(size * 0.015)), config.WHITE, -1)

        # Blush
        self._draw_soft_blush(canvas, (cx - int(size * 0.27), cy + int(size * 0.08)), max(6, int(size * 0.10)), config.SOFT_PINK)
        self._draw_soft_blush(canvas, (cx + int(size * 0.27), cy + int(size * 0.08)), max(6, int(size * 0.10)), config.SOFT_PINK)

        # Nose
        cv2.circle(canvas, (cx, cy + int(size * 0.06)), max(3, int(size * 0.045)), config.DARK_PINK, -1)

        # Smile
        cv2.ellipse(
            canvas,
            (cx - int(size * 0.08), cy + int(size * 0.14)),
            (int(size * 0.08), int(size * 0.07)),
            0,
            0,
            180,
            config.BROWN,
            2,
        )
        cv2.ellipse(
            canvas,
            (cx + int(size * 0.08), cy + int(size * 0.14)),
            (int(size * 0.08), int(size * 0.07)),
            0,
            0,
            180,
            config.BROWN,
            2,
        )

        # Tiny paws
        cv2.circle(
            canvas,
            (cx - int(size * 0.28), cy + int(size * 0.52)),
            max(5, int(size * 0.09)),
            config.WHITE,
            -1,
        )
        cv2.circle(
            canvas,
            (cx + int(size * 0.28), cy + int(size * 0.52)),
            max(5, int(size * 0.09)),
            config.WHITE,
            -1,
        )
        cv2.circle(
            canvas,
            (cx - int(size * 0.28), cy + int(size * 0.52)),
            max(5, int(size * 0.09)),
            config.BROWN,
            2,
        )
        cv2.circle(
            canvas,
            (cx + int(size * 0.28), cy + int(size * 0.52)),
            max(5, int(size * 0.09)),
            config.BROWN,
            2,
        )

        # Tiny bow
        self._draw_bow(
            canvas,
            (cx + int(size * 0.34), cy - int(size * 0.28)),
            int(size * 0.45),
            int(size * 0.28),
        )

        # Tiny heart
        self._draw_simple_heart(
            canvas,
            (cx - int(size * 0.38), cy + int(size * 0.55)),
            max(8, int(size * 0.12)),
            config.DARK_PINK,
        )

    def _draw_mascot_speech(self, canvas, text, x, y, width=390, height=82):
        self.ui.rounded_rect(canvas, x, y, x + width, y + height, config.WHITE, radius=24)
        self.ui.rounded_rect(canvas, x, y, x + width, y + height, config.PASTEL_PINK, radius=24, thickness=3)

        # Speech tail
        points = np.array(
            [
                [x + 38, y + height - 4],
                [x + 75, y + height - 4],
                [x + 46, y + height + 28],
            ],
            np.int32,
        )
        cv2.fillConvexPoly(canvas, points, config.WHITE)
        cv2.polylines(canvas, [points], True, config.PASTEL_PINK, 3)

        self.ui.put_text(
            canvas,
            text,
            (x + 24, y + 37),
            scale=0.55,
            color=config.BROWN,
            thickness=2,
        )

        self.ui.put_text(
            canvas,
            "Bunny helper",
            (x + 24, y + 66),
            scale=0.48,
            color=config.DARK_PINK,
            thickness=2,
        )

    # -------------------------------------------------
    # Face detection + stickers
    # -------------------------------------------------

    def _detect_primary_face(self, frame):
        if not self.face_detector_ready or self.face_cascade is None:
            self.last_face_box = None
            return None

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, None, fx=0.5, fy=0.5)

            faces = self.face_cascade.detectMultiScale(
                small,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60),
            )

            if len(faces) == 0:
                self.last_face_box = None
                return None

            largest = max(faces, key=lambda f: f[2] * f[3])
            x, y, w, h = largest

            x *= 2
            y *= 2
            w *= 2
            h *= 2

            self.last_face_box = (x, y, w, h)
            return self.last_face_box

        except Exception:
            self.last_face_box = None
            return None

    def _apply_face_stickers(self, frame):
        if not self.stickers_enabled:
            return None

        face = self._detect_primary_face(frame)

        if face is None:
            return None

        x, y, w, h = face

        face_center_x = x + w // 2

        left_cheek = (x + int(w * 0.28), y + int(h * 0.68))
        right_cheek = (x + int(w * 0.72), y + int(h * 0.68))

        forehead_center = (x + w // 2, y + int(h * 0.10))

        upper_left = (x + int(w * 0.10), y + int(h * 0.10))
        upper_right = (x + int(w * 0.90), y + int(h * 0.10))

        side_left = (x - int(w * 0.08), y + int(h * 0.38))
        side_right = (x + w + int(w * 0.08), y + int(h * 0.38))

        above_head = (x + w // 2, y - int(h * 0.13))

        blush_radius = max(10, int(w * 0.12))
        small_heart_size = max(10, int(w * 0.08))
        sparkle_size = max(8, int(w * 0.06))

        self._draw_soft_blush(frame, left_cheek, blush_radius, color=(220, 180, 255))
        self._draw_soft_blush(frame, right_cheek, blush_radius, color=(220, 180, 255))

        style = self.current_sticker_style()

        if style == "Bow":
            self._draw_bow(frame, (forehead_center[0], forehead_center[1] - int(h * 0.15)), int(w * 0.60), int(h * 0.28))
            self._draw_simple_heart(frame, upper_left, small_heart_size, config.DARK_PINK)
            self._draw_simple_heart(frame, upper_right, small_heart_size, config.DARK_PINK)
            self._draw_simple_sparkle(frame, side_left, sparkle_size, config.WHITE)
            self._draw_simple_sparkle(frame, side_right, sparkle_size, config.WHITE)

        elif style == "Heart":
            self._draw_simple_heart(frame, upper_left, small_heart_size + 4, config.DARK_PINK)
            self._draw_simple_heart(frame, upper_right, small_heart_size + 4, config.DARK_PINK)
            self._draw_simple_heart(frame, side_left, small_heart_size, config.PASTEL_PINK)
            self._draw_simple_heart(frame, side_right, small_heart_size, config.PASTEL_PINK)
            self._draw_simple_sparkle(frame, (face_center_x, y - int(h * 0.10)), sparkle_size + 2, config.WHITE)

        elif style == "Cafe":
            self._draw_bow(frame, (forehead_center[0], forehead_center[1] - int(h * 0.13)), int(w * 0.50), int(h * 0.22))
            self._draw_cookie(frame, side_left, max(10, int(w * 0.07)))
            self._draw_cookie(frame, side_right, max(10, int(w * 0.07)))
            self._draw_simple_sparkle(frame, upper_left, sparkle_size, config.WHITE)
            self._draw_simple_sparkle(frame, upper_right, sparkle_size, config.WHITE)

        elif style == "Cat":
            ear_size = max(24, int(w * 0.16))
            self._draw_cat_ear(frame, (x + int(w * 0.25), y - int(h * 0.04)), ear_size)
            self._draw_cat_ear(frame, (x + int(w * 0.75), y - int(h * 0.04)), ear_size)
            self._draw_whiskers(frame, left_cheek, right_cheek, w)
            self._draw_simple_heart(frame, (face_center_x, y + int(h * 0.58)), max(8, int(w * 0.05)), config.SOFT_PINK)

        elif style == "Bunny":
            ear_w = max(14, int(w * 0.08))
            ear_h = max(45, int(h * 0.28))
            self._draw_bunny_ear(frame, (x + int(w * 0.35), y - int(h * 0.10)), ear_w, ear_h, -12)
            self._draw_bunny_ear(frame, (x + int(w * 0.65), y - int(h * 0.10)), ear_w, ear_h, 12)
            self._draw_simple_heart(frame, (face_center_x, y + int(h * 0.62)), max(8, int(w * 0.05)), config.SOFT_PINK)
            self._draw_simple_sparkle(frame, side_left, sparkle_size, config.WHITE)
            self._draw_simple_sparkle(frame, side_right, sparkle_size, config.WHITE)

        elif style == "Star":
            self._draw_simple_sparkle(frame, upper_left, sparkle_size + 5, config.SOFT_YELLOW)
            self._draw_simple_sparkle(frame, upper_right, sparkle_size + 5, config.SOFT_YELLOW)
            self._draw_simple_sparkle(frame, side_left, sparkle_size + 3, config.WHITE)
            self._draw_simple_sparkle(frame, side_right, sparkle_size + 3, config.WHITE)

            for offset_x in [-35, -18, 18, 35]:
                self._draw_simple_sparkle(
                    frame,
                    (face_center_x + offset_x, y + int(h * 0.78)),
                    max(4, int(w * 0.025)),
                    config.SOFT_YELLOW,
                )

        elif style == "Angel":
            self._draw_halo(frame, above_head, max(30, int(w * 0.24)), max(8, int(h * 0.04)))
            self._draw_simple_sparkle(frame, upper_left, sparkle_size + 4, config.WHITE)
            self._draw_simple_sparkle(frame, upper_right, sparkle_size + 4, config.WHITE)
            self._draw_simple_sparkle(frame, side_left, sparkle_size, config.SOFT_YELLOW)
            self._draw_simple_sparkle(frame, side_right, sparkle_size, config.SOFT_YELLOW)

        elif style == "Devil":
            horn_size = max(18, int(w * 0.11))
            self._draw_devil_horn(frame, (x + int(w * 0.28), y + int(h * 0.03)), horn_size)
            self._draw_devil_horn(frame, (x + int(w * 0.72), y + int(h * 0.03)), horn_size)
            self._draw_simple_heart(frame, side_left, small_heart_size, config.DARK_PINK)
            self._draw_simple_heart(frame, side_right, small_heart_size, config.DARK_PINK)

        elif style == "Crown":
            self._draw_crown(frame, (forehead_center[0], forehead_center[1] - int(h * 0.18)), int(w * 0.50), int(h * 0.25))
            self._draw_simple_sparkle(frame, side_left, sparkle_size, config.WHITE)
            self._draw_simple_sparkle(frame, side_right, sparkle_size, config.WHITE)
            self._draw_simple_heart(frame, right_cheek, small_heart_size, config.DARK_PINK)

        elif style == "Sleepy":
            self._draw_moon(frame, (x + int(w * 0.18), y - int(h * 0.08)), max(15, int(w * 0.08)))
            self._draw_simple_sparkle(frame, (x + int(w * 0.35), y - int(h * 0.10)), sparkle_size, config.SOFT_YELLOW)
            self._draw_simple_sparkle(frame, (x + int(w * 0.72), y - int(h * 0.07)), sparkle_size, config.WHITE)
            self.ui.put_text(frame, "Z", (x + w + 8, y + int(h * 0.30)), scale=0.9, color=config.BROWN, thickness=3)
            self.ui.put_text(frame, "z", (x + w + 35, y + int(h * 0.20)), scale=0.7, color=config.BROWN, thickness=2)

        elif style == "Kawaii Mix":
            self._draw_bow(frame, (forehead_center[0], forehead_center[1] - int(h * 0.15)), int(w * 0.52), int(h * 0.23))
            self._draw_simple_heart(frame, upper_left, small_heart_size, config.DARK_PINK)
            self._draw_simple_heart(frame, upper_right, small_heart_size, config.DARK_PINK)
            self._draw_simple_sparkle(frame, side_left, sparkle_size + 2, config.WHITE)
            self._draw_simple_sparkle(frame, side_right, sparkle_size + 2, config.WHITE)
            self._draw_cookie(frame, (x + int(w * 0.10), y + int(h * 0.85)), max(8, int(w * 0.045)))
            self._draw_cookie(frame, (x + int(w * 0.90), y + int(h * 0.85)), max(8, int(w * 0.045)))

        return face

    # -------------------------------------------------
    # Frame themes
    # -------------------------------------------------

    def _draw_frame_theme_around_photo(self, canvas):
        if self.puzzle_game.completed_image is None:
            return

        self._draw_frame_around_image(
            canvas,
            self.puzzle_game.completed_image,
            self.puzzle_game.target_x,
            self.puzzle_game.target_y,
        )

    def _draw_frame_around_image(self, canvas, image, x, y):
        theme = self.current_frame_theme()

        h, w = image.shape[:2]

        outer_x1 = x - 36
        outer_y1 = y - 36
        outer_x2 = x + w + 36
        outer_y2 = y + h + 36

        inner_x1 = x - 14
        inner_y1 = y - 14
        inner_x2 = x + w + 14
        inner_y2 = y + h + 14

        if theme == "Pink":
            outer_color = config.PASTEL_PINK
            inner_color = config.SOFT_PINK
            accent_color = config.DARK_PINK

        elif theme == "Peach":
            outer_color = config.PEACH
            inner_color = config.CREAM
            accent_color = config.BROWN

        elif theme == "Bakery":
            outer_color = config.BROWN
            inner_color = config.CREAM
            accent_color = config.PEACH

        else:
            outer_color = config.PASTEL_PINK
            inner_color = config.WHITE
            accent_color = config.DARK_PINK

        self.ui.rounded_rect(canvas, outer_x1, outer_y1, outer_x2, outer_y2, outer_color, radius=34)
        self.ui.rounded_rect(canvas, inner_x1, inner_y1, inner_x2, inner_y2, inner_color, radius=24)

        canvas[y:y + h, x:x + w] = image

        cv2.rectangle(canvas, (x, y), (x + w, y + h), accent_color, 4)

        if theme == "Pink":
            self._draw_simple_sparkle(canvas, (outer_x1 + 26, outer_y1 + 28), 12, config.WHITE)
            self._draw_simple_sparkle(canvas, (outer_x2 - 26, outer_y2 - 28), 12, config.WHITE)
            self._draw_simple_heart(canvas, (outer_x2 - 30, outer_y1 + 30), 15, config.DARK_PINK)
            self._draw_simple_heart(canvas, (outer_x1 + 30, outer_y2 - 30), 15, config.DARK_PINK)

        elif theme == "Peach":
            self._draw_simple_sparkle(canvas, (outer_x1 + 28, outer_y1 + 30), 14, config.WHITE)
            self._draw_simple_sparkle(canvas, (outer_x2 - 28, outer_y1 + 30), 14, config.WHITE)
            self._draw_simple_sparkle(canvas, (outer_x1 + 28, outer_y2 - 30), 14, config.WHITE)
            self._draw_simple_sparkle(canvas, (outer_x2 - 28, outer_y2 - 30), 14, config.WHITE)

        elif theme == "Bakery":
            dot_positions = [
                (outer_x1 + 35, outer_y1 + 35),
                (outer_x2 - 35, outer_y1 + 35),
                (outer_x1 + 35, outer_y2 - 35),
                (outer_x2 - 35, outer_y2 - 35),
                (outer_x1 + 35, (outer_y1 + outer_y2) // 2),
                (outer_x2 - 35, (outer_y1 + outer_y2) // 2),
            ]

            for px, py in dot_positions:
                self._draw_cookie(canvas, (px, py), 11)

        elif theme == "Heart":
            heart_positions = [
                (outer_x1 + 30, outer_y1 + 28),
                (outer_x2 - 30, outer_y1 + 28),
                (outer_x1 + 30, outer_y2 - 28),
                (outer_x2 - 30, outer_y2 - 28),
                ((outer_x1 + outer_x2) // 2, outer_y1 + 22),
                ((outer_x1 + outer_x2) // 2, outer_y2 - 22),
            ]

            for pos in heart_positions:
                self._draw_simple_heart(canvas, pos, 14, config.DARK_PINK)

    # -------------------------------------------------
    # Draw states
    # -------------------------------------------------

    def _draw_menu_state(self, frame):
        canvas = frame.copy()

        overlay = canvas.copy()
        overlay[:] = config.CREAM
        cv2.addWeighted(overlay, 0.86, canvas, 0.14, 0, canvas)

        self.ui.draw_base_frame(canvas)
        self.update_and_draw_particles(canvas, amount="normal")

        h, w = canvas.shape[:2]

        # Main title card
        self.ui.rounded_rect(canvas, w // 2 - 430, 34, w // 2 + 430, 155, config.SOFT_PINK, radius=38)
        self.ui.rounded_rect(canvas, w // 2 - 430, 34, w // 2 + 430, 155, config.PASTEL_PINK, radius=38, thickness=4)

        self.ui.put_text(
            canvas,
            "Kawaii Puzzle Cam",
            (w // 2 - 260, 92),
            scale=1.55,
            color=config.DARK_PINK,
            thickness=4,
        )

        self.ui.put_text(
            canvas,
            "webcam puzzle + photo booth",
            (w // 2 - 170, 128),
            scale=0.62,
            color=config.BROWN,
            thickness=2,
        )

        self._draw_simple_heart(canvas, (w // 2 - 355, 92), 18, config.DARK_PINK)
        self._draw_simple_heart(canvas, (w // 2 + 355, 92), 18, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (w // 2 - 392, 68), 11, config.WHITE)
        self._draw_simple_sparkle(canvas, (w // 2 + 392, 122), 11, config.WHITE)

        # Left mode card
        left_x1 = 105
        left_x2 = w // 2 - 20
        right_x1 = w // 2 + 20
        right_x2 = w - 105
        top_y = 190
        bottom_y = 610

        self.ui.rounded_rect(canvas, left_x1, top_y, left_x2, bottom_y, config.WHITE, radius=35)
        self.ui.rounded_rect(canvas, left_x1, top_y, left_x2, bottom_y, config.PASTEL_PINK, radius=35, thickness=5)

        self.ui.put_text(canvas, "Start Playing", (left_x1 + 150, top_y + 55), scale=1.05, color=config.DARK_PINK, thickness=3)

        menu_items = [
            ("1", "Easy Puzzle", "3 x 3 - quick and cozy"),
            ("2", "Medium Puzzle", "4 x 4 - better challenge"),
            ("3", "Hard Puzzle", "5 x 5 - serious puzzle mode"),
            ("4", "Photo Booth", "stickers, frames, cute photos"),
        ]

        y = top_y + 88
        for key_text, title, desc in menu_items:
            self.ui.rounded_rect(canvas, left_x1 + 45, y, left_x2 - 45, y + 62, config.CREAM, radius=24)
            cv2.circle(canvas, (left_x1 + 82, y + 31), 20, config.SOFT_PINK, -1)
            cv2.circle(canvas, (left_x1 + 82, y + 31), 20, config.BROWN, 2)
            self.ui.put_text(canvas, key_text, (left_x1 + 74, y + 40), scale=0.68, color=config.BROWN, thickness=2)
            self.ui.put_text(canvas, title, (left_x1 + 120, y + 28), scale=0.66, color=config.BROWN, thickness=2)
            self.ui.put_text(canvas, desc, (left_x1 + 120, y + 52), scale=0.48, color=config.DARK_PINK, thickness=1)
            y += 77

        # Right help card
        self.ui.rounded_rect(canvas, right_x1, top_y, right_x2, bottom_y, config.WHITE, radius=35)
        self.ui.rounded_rect(canvas, right_x1, top_y, right_x2, bottom_y, config.PASTEL_PINK, radius=35, thickness=5)

        self.ui.put_text(canvas, "Menu", (right_x1 + 230, top_y + 55), scale=1.05, color=config.DARK_PINK, thickness=3)

        side_items = [
            ("I", "Instructions", "learn controls and gestures"),
            ("V", "Gallery", "view saved photos"),
            ("T", "Settings", "stickers, frames, debug"),
            ("Q", "Quit", "close the game"),
        ]

        y = top_y + 88
        for key_text, title, desc in side_items:
            self.ui.rounded_rect(canvas, right_x1 + 45, y, right_x2 - 45, y + 62, config.CREAM, radius=24)
            cv2.circle(canvas, (right_x1 + 82, y + 31), 20, config.SOFT_PINK, -1)
            cv2.circle(canvas, (right_x1 + 82, y + 31), 20, config.BROWN, 2)
            self.ui.put_text(canvas, key_text, (right_x1 + 73, y + 40), scale=0.68, color=config.BROWN, thickness=2)
            self.ui.put_text(canvas, title, (right_x1 + 120, y + 28), scale=0.66, color=config.BROWN, thickness=2)
            self.ui.put_text(canvas, desc, (right_x1 + 120, y + 52), scale=0.48, color=config.DARK_PINK, thickness=1)
            y += 77

        # Status strip
        sticker_status = "On" if self.stickers_enabled else "Off"
        particle_status = "On" if self.particles_enabled else "Off"

        self.ui.rounded_rect(canvas, 150, h - 82, w - 150, h - 30, config.WHITE, radius=22)

        self.ui.put_text(
            canvas,
            f"Frame: {self.current_frame_theme()}   |   Stickers: {sticker_status} - {self.current_sticker_style()}   |   Particles: {particle_status}",
            (195, h - 50),
            scale=0.58,
            color=config.BROWN,
            thickness=2,
        )

        self._draw_bunny_mascot(canvas, (118, h - 138), size=68)
        self._draw_mascot_speech(
            canvas,
            self.current_mascot_tip(),
            w // 2 - 235,
            155,
            width=470,
            height=78,
        )

        return canvas

    def enter_instructions(self):
        self.state = "instructions"
        self.previous_state_before_pause = "instructions"
        print("Instructions opened.")

    def _draw_instructions_state(self, frame):
        canvas = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
        canvas[:] = config.CREAM

        self.ui.draw_base_frame(canvas)
        self.update_and_draw_particles(canvas, amount="normal")

        h, w = canvas.shape[:2]

        self.ui.rounded_rect(canvas, w // 2 - 390, 40, w // 2 + 390, 135, config.SOFT_PINK, radius=35)
        self.ui.rounded_rect(canvas, w // 2 - 390, 40, w // 2 + 390, 135, config.PASTEL_PINK, radius=35, thickness=4)

        self.ui.put_text(
            canvas,
            "How To Play",
            (w // 2 - 150, 100),
            scale=1.45,
            color=config.DARK_PINK,
            thickness=4,
        )

        card_y1 = 170
        card_y2 = 610
        self.ui.rounded_rect(canvas, 110, card_y1, w - 110, card_y2, config.WHITE, radius=35)
        self.ui.rounded_rect(canvas, 110, card_y1, w - 110, card_y2, config.PASTEL_PINK, radius=35, thickness=5)

        left_x = 170
        right_x = w // 2 + 40

        self.ui.put_text(canvas, "Puzzle Mode", (left_x, card_y1 + 55), scale=0.95, color=config.DARK_PINK, thickness=3)

        puzzle_lines = [
            "1 / 2 / 3 = choose difficulty",
            "SPACE = capture webcam photo",
            "Pinch fingers = grab a puzzle piece",
            "Move hand = drag the piece",
            "Open fingers = drop the piece",
            "P = pause, R = restart, M = menu",
        ]

        y = card_y1 + 95
        for line in puzzle_lines:
            self._draw_simple_heart(canvas, (left_x + 12, y - 8), 7, config.DARK_PINK)
            self.ui.put_text(canvas, line, (left_x + 35, y), scale=0.58, color=config.BROWN, thickness=2)
            y += 43

        self.ui.put_text(canvas, "Photo Booth + Extras", (right_x, card_y1 + 55), scale=0.95, color=config.DARK_PINK, thickness=3)

        extra_lines = [
            "4 = photo booth mode",
            "SPACE or S = start photo countdown",
            "G = change sticker style",
            "K = stickers on/off",
            "F = change frame theme",
            "V = gallery, X/Y/N = delete confirm",
        ]

        y = card_y1 + 95
        for line in extra_lines:
            self._draw_simple_sparkle(canvas, (right_x + 12, y - 8), 8, config.WHITE)
            self.ui.put_text(canvas, line, (right_x + 35, y), scale=0.58, color=config.BROWN, thickness=2)
            y += 43

        # Tip card
        self.ui.rounded_rect(canvas, 175, card_y2 - 75, w - 175, card_y2 - 25, config.CREAM, radius=22)
        self.ui.put_text(
            canvas,
            "Tip: If grabbing feels hard, use debug mode with D and make sure your hand is clearly visible.",
            (215, card_y2 - 43),
            scale=0.57,
            color=config.DARK_PINK,
            thickness=2,
        )

        self.ui.rounded_rect(canvas, 260, h - 72, w - 260, h - 30, config.WHITE, radius=20)
        self.ui.put_text(canvas, "M = back to menu   |   Q or ESC = quit", (w // 2 - 190, h - 44), scale=0.65, color=config.BROWN, thickness=2)

        self._draw_bunny_mascot(canvas, (155, h - 135), size=72)
        self._draw_mascot_speech(canvas, self.current_mascot_tip(), 235, h - 212, width=460, height=86)

        return canvas

    def _draw_settings_state(self, frame):
        canvas = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
        canvas[:] = config.CREAM

        self.ui.draw_base_frame(canvas)
        self.update_and_draw_particles(canvas, amount="normal")

        h, w = canvas.shape[:2]

        sticker_status = "On" if self.stickers_enabled else "Off"
        particle_status = "On" if self.particles_enabled else "Off"
        debug_status = "On" if self.debug_mode else "Off"

        if self.sound_manager is not None:
            sound_status = "On" if self.sound_manager.enabled else "Off"
            music_status = "On" if self.sound_manager.music_enabled else "Off"
        else:
            sound_status = "Off"
            music_status = "Off"

        self.ui.rounded_rect(canvas, w // 2 - 360, 45, w // 2 + 360, 130, config.SOFT_PINK, radius=35)
        self.ui.put_text(
            canvas,
            "Settings",
            (w // 2 - 105, 102),
            scale=1.45,
            color=config.DARK_PINK,
            thickness=4,
        )

        self.ui.rounded_rect(canvas, w // 2 - 520, 158, w // 2 + 520, 635, config.WHITE, radius=35)
        self.ui.rounded_rect(canvas, w // 2 - 520, 158, w // 2 + 520, 635, config.PASTEL_PINK, radius=35, thickness=5)

        items = [
            f"1  -  Toggle stickers: {sticker_status}",
            f"2  -  Change sticker style: {self.current_sticker_style()}",
            f"3  -  Change frame theme: {self.current_frame_theme()}",
            f"4  -  Toggle particles: {particle_status}",
            f"5  -  Toggle debug mode: {debug_status}",
            f"6  -  Toggle sound effects: {sound_status}",
            f"7  -  Toggle background music: {music_status}",
        ]

        y = 198
        for item in items:
            self.ui.rounded_rect(canvas, w // 2 - 410, y, w // 2 + 410, y + 45, config.CREAM, radius=20)
            self.ui.put_text(canvas, item, (w // 2 - 360, y + 31), scale=0.66, color=config.BROWN, thickness=2)
            y += 56

        self.ui.rounded_rect(canvas, w // 2 - 430, h - 75, w // 2 + 430, h - 30, config.WHITE, radius=18)
        self.ui.put_text(
            canvas,
            "Settings save automatically | B = quick mute/unmute | M = menu | Q = quit",
            (w // 2 - 380, h - 45),
            scale=0.56,
            color=config.BROWN,
            thickness=2,
        )

        return canvas

    def _draw_camera_state(self, frame):
        zoomed_frame = apply_zoom(frame, self.zoom_level)

        self.hand_tracker.process(zoomed_frame)

        pinch_distance = self.hand_tracker.get_pinch_distance()
        is_pinching = self.hand_tracker.is_pinching()
        is_peace = self.hand_tracker.is_peace_sign()

        self._update_zoom_from_pinch(pinch_distance)
        self._smooth_zoom()

        face_box = self._apply_face_stickers(zoomed_frame)

        self.last_camera_frame = zoomed_frame.copy()

        self.ui.draw_camera_ui(zoomed_frame, self.zoom_level, self.current_camera_index)
        self.update_and_draw_particles(zoomed_frame, amount="normal")

        sticker_status = "On" if self.stickers_enabled else "Off"

        self.ui.put_text(
            zoomed_frame,
            f"{self.difficulty_name} {self.puzzle_rows}x{self.puzzle_cols} | {self.get_best_score_text()}",
            (230, 95),
            scale=0.58,
            color=config.BROWN,
            thickness=2,
        )

        self.ui.put_text(
            zoomed_frame,
            f"Frame: {self.current_frame_theme()} | Stickers: {sticker_status} {self.current_sticker_style()} | SPACE = capture",
            (230, 123),
            scale=0.56,
            color=config.DARK_PINK,
            thickness=2,
        )

        cursor = self.hand_tracker.get_hand_cursor()
        self.ui.draw_cursor(zoomed_frame, cursor, is_pinching)

        self._update_peace_capture_detection(is_peace)

        if self.debug_mode:
            if face_box is not None:
                x, y, w, h = face_box
                cv2.rectangle(zoomed_frame, (x, y), (x + w, y + h), config.SOFT_MINT, 2)

            self.hand_tracker.draw_landmarks(zoomed_frame)
            self.ui.draw_debug(
                zoomed_frame,
                self.state,
                self.zoom_level,
                self.current_camera_index,
                pinch_distance,
                is_pinching,
                is_peace,
            )

        return zoomed_frame


    def current_photobooth_tip(self):
        if not hasattr(self, "photobooth_tips") or not self.photobooth_tips:
            return "Smile big for bunny!"

        now = time.time()

        if not hasattr(self, "photobooth_last_tip_change_time"):
            self.photobooth_last_tip_change_time = now

        if now - self.photobooth_last_tip_change_time >= 5.0:
            self.photobooth_tip_index = (self.photobooth_tip_index + 1) % len(self.photobooth_tips)
            self.photobooth_last_tip_change_time = now

        return self.photobooth_tips[self.photobooth_tip_index % len(self.photobooth_tips)]

    def _draw_photobooth_decorations(self, canvas):
        h, w = canvas.shape[:2]

        # Corner hearts and sparkles
        self._draw_simple_heart(canvas, (48, 48), 16, config.DARK_PINK)
        self._draw_simple_heart(canvas, (w - 48, 48), 16, config.DARK_PINK)
        self._draw_simple_heart(canvas, (48, h - 48), 16, config.DARK_PINK)
        self._draw_simple_heart(canvas, (w - 48, h - 48), 16, config.DARK_PINK)

        self._draw_simple_sparkle(canvas, (95, 95), 15, config.WHITE)
        self._draw_simple_sparkle(canvas, (w - 95, 95), 15, config.WHITE)
        self._draw_simple_sparkle(canvas, (95, h - 95), 15, config.WHITE)
        self._draw_simple_sparkle(canvas, (w - 95, h - 95), 15, config.WHITE)

        # Decorative side dots
        for y in range(180, h - 160, 82):
            self._draw_cookie(canvas, (42, y), 8)
            self._draw_cookie(canvas, (w - 42, y), 8)

    def _draw_photobooth_saved_banner(self, canvas):
        if self.photobooth_saved_message_start_time is None:
            return

        elapsed = time.time() - self.photobooth_saved_message_start_time

        if elapsed > 2.7:
            self.photobooth_saved_message_start_time = None
            return

        h, w = canvas.shape[:2]

        y = 165
        if elapsed < 0.25:
            y -= int((0.25 - elapsed) * 120)

        self.ui.rounded_rect(canvas, w // 2 - 250, y, w // 2 + 250, y + 72, config.WHITE, radius=26)
        self.ui.rounded_rect(canvas, w // 2 - 250, y, w // 2 + 250, y + 72, config.PASTEL_PINK, radius=26, thickness=4)

        self._draw_simple_heart(canvas, (w // 2 - 205, y + 36), 14, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (w // 2 + 205, y + 36), 13, config.SOFT_YELLOW)

        self.ui.put_text(
            canvas,
            "Photo saved!",
            (w // 2 - 108, y + 45),
            scale=0.95,
            color=config.DARK_PINK,
            thickness=3,
        )

    def _draw_photobooth_flash(self, canvas):
        if self.photobooth_flash_start_time is None:
            return

        elapsed = time.time() - self.photobooth_flash_start_time

        if elapsed > 0.28:
            self.photobooth_flash_start_time = None
            return

        strength = max(0.0, 1.0 - elapsed / 0.28)

        overlay = canvas.copy()
        overlay[:] = config.WHITE
        cv2.addWeighted(overlay, 0.55 * strength, canvas, 1.0 - 0.55 * strength, 0, canvas)


    def _draw_photobooth_base(self, frame):
        zoomed_frame = apply_zoom(frame, self.zoom_level)

        self.hand_tracker.process(zoomed_frame)

        pinch_distance = self.hand_tracker.get_pinch_distance()
        is_pinching = self.hand_tracker.is_pinching()

        self._update_zoom_from_pinch(pinch_distance)
        self._smooth_zoom()

        face_box = self._apply_face_stickers(zoomed_frame)

        canvas = zoomed_frame.copy()

        self.update_and_draw_particles(canvas, amount="many")
        self.ui.draw_base_frame(canvas)
        self._draw_photobooth_decorations(canvas)

        h, w = canvas.shape[:2]

        # Title card
        self.ui.rounded_rect(canvas, 235, 54, w - 235, 135, config.SOFT_PINK, radius=30)
        self.ui.rounded_rect(canvas, 235, 54, w - 235, 135, config.WHITE, radius=30, thickness=3)

        self.ui.put_text(
            canvas,
            "Photo Booth",
            (w // 2 - 135, 92),
            scale=1.05,
            color=config.DARK_PINK,
            thickness=3,
        )

        sticker_status = "On" if self.stickers_enabled else "Off"

        self.ui.put_text(
            canvas,
            f"Frame: {self.current_frame_theme()} | Stickers: {sticker_status} - {self.current_sticker_style()}",
            (w // 2 - 265, 122),
            scale=0.55,
            color=config.BROWN,
            thickness=2,
        )

        # Bunny helper on lower right
        if hasattr(self, "_draw_bunny_mascot"):
            self._draw_bunny_mascot(canvas, (w - 118, h - 145), size=62)
            self._draw_mascot_speech(
                canvas,
                self.current_photobooth_tip(),
                w - 575,
                h - 226,
                width=385,
                height=82,
            )

        # Bottom controls card
        self.ui.rounded_rect(canvas, 135, h - 92, w - 135, h - 30, config.WHITE, radius=24)
        self.ui.rounded_rect(canvas, 135, h - 92, w - 135, h - 30, config.PASTEL_PINK, radius=24, thickness=3)

        self.ui.put_text(
            canvas,
            "SPACE/S = countdown photo | F = frame | G = sticker | K = stickers | V = gallery | B = mute",
            (170, h - 55),
            scale=0.52,
            color=config.BROWN,
            thickness=2,
        )

        if self.last_saved_path:
            self.ui.put_text(
                canvas,
                f"Last saved: {self.last_saved_path}",
                (175, h - 108),
                scale=0.46,
                color=config.DARK_PINK,
                thickness=2,
            )

        self._draw_photobooth_saved_banner(canvas)
        self._draw_photobooth_flash(canvas)

        if self.debug_mode:
            if face_box is not None:
                x, y, fw, fh = face_box
                cv2.rectangle(canvas, (x, y), (x + fw, y + fh), config.SOFT_MINT, 2)

            self.hand_tracker.draw_landmarks(canvas)
            self.ui.draw_debug(
                canvas,
                self.state,
                self.zoom_level,
                self.current_camera_index,
                pinch_distance,
                is_pinching,
                self.hand_tracker.is_peace_sign(),
            )

        return canvas

    def _draw_photobooth_state(self, frame):
        canvas = self._draw_photobooth_base(frame)
        self.last_photobooth_frame = canvas.copy()
        return canvas

    def _draw_photobooth_countdown_state(self, frame):
        canvas = self._draw_photobooth_base(frame)
        self.last_photobooth_frame = canvas.copy()

        if self.photobooth_countdown_start_time is None:
            self.photobooth_countdown_start_time = time.time()

        elapsed = time.time() - self.photobooth_countdown_start_time

        if elapsed < 1.0:
            text = "3"
        elif elapsed < 2.0:
            text = "2"
        elif elapsed < 3.0:
            text = "1"
        elif elapsed < config.COUNTDOWN_SECONDS:
            text = "Smile!"
        else:
            text = "Snap!"

        h, w = canvas.shape[:2]

        # Soft pink overlay during countdown
        overlay = canvas.copy()
        overlay[:] = config.SOFT_PINK
        cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)

        # Big countdown bubble
        self.ui.rounded_rect(canvas, w // 2 - 250, h // 2 - 120, w // 2 + 250, h // 2 + 120, config.WHITE, radius=44)
        self.ui.rounded_rect(canvas, w // 2 - 250, h // 2 - 120, w // 2 + 250, h // 2 + 120, config.PASTEL_PINK, radius=44, thickness=6)

        if text in ["3", "2", "1"]:
            self.ui.put_text(
                canvas,
                text,
                (w // 2 - 36, h // 2 + 40),
                scale=3.3,
                color=config.DARK_PINK,
                thickness=8,
            )
        else:
            self.ui.put_text(
                canvas,
                text,
                (w // 2 - 128, h // 2 + 25),
                scale=1.55,
                color=config.DARK_PINK,
                thickness=5,
            )

        self._draw_simple_heart(canvas, (w // 2 - 190, h // 2 - 70), 20, config.DARK_PINK)
        self._draw_simple_heart(canvas, (w // 2 + 190, h // 2 - 70), 20, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (w // 2 - 190, h // 2 + 75), 18, config.SOFT_YELLOW)
        self._draw_simple_sparkle(canvas, (w // 2 + 190, h // 2 + 75), 18, config.SOFT_YELLOW)

        if elapsed >= config.COUNTDOWN_SECONDS:
            self.save_photobooth_photo()
            self.photobooth_countdown_start_time = None
            self.state = config.STATE_PHOTOBOOTH
            self.previous_state_before_pause = config.STATE_PHOTOBOOTH

        return canvas

    def _draw_countdown_state(self, frame):
        zoomed_frame = apply_zoom(frame, self.zoom_level)
        self.hand_tracker.process(zoomed_frame)

        face_box = self._apply_face_stickers(zoomed_frame)
        self.last_camera_frame = zoomed_frame.copy()

        elapsed = time.time() - self.countdown_start_time

        if elapsed < 1.0:
            text = "3"
        elif elapsed < 2.0:
            text = "2"
        elif elapsed < 3.0:
            text = "1"
        else:
            text = "Snap!"

        self.ui.draw_camera_ui(zoomed_frame, self.zoom_level, self.current_camera_index)
        self.update_and_draw_particles(zoomed_frame, amount="many")
        self.ui.draw_countdown(zoomed_frame, text)

        if elapsed >= config.COUNTDOWN_SECONDS:
            self.finish_countdown_capture()

        if self.debug_mode:
            if face_box is not None:
                x, y, w, h = face_box
                cv2.rectangle(zoomed_frame, (x, y), (x + w, y + h), config.SOFT_MINT, 2)

            self.hand_tracker.draw_landmarks(zoomed_frame)
            self.ui.draw_debug(
                zoomed_frame,
                self.state,
                self.zoom_level,
                self.current_camera_index,
                self.hand_tracker.get_pinch_distance(),
                self.hand_tracker.is_pinching(),
                self.hand_tracker.is_peace_sign(),
            )

        return zoomed_frame

    def _draw_puzzle_help_overlay(self, canvas):
        if not self.show_puzzle_help:
            return

        h, w = canvas.shape[:2]

        panel_x1 = w - 390
        panel_y1 = 170
        panel_x2 = w - 35
        panel_y2 = 360

        overlay = canvas.copy()
        self.ui.rounded_rect(overlay, panel_x1, panel_y1, panel_x2, panel_y2, config.WHITE, radius=24)
        cv2.addWeighted(overlay, 0.82, canvas, 0.18, 0, canvas)

        self.ui.rounded_rect(canvas, panel_x1, panel_y1, panel_x2, panel_y2, config.PASTEL_PINK, radius=24, thickness=4)

        self.ui.put_text(
            canvas,
            "How to Play",
            (panel_x1 + 78, panel_y1 + 38),
            scale=0.78,
            color=config.DARK_PINK,
            thickness=3,
        )

        help_lines = [
            "Pinch fingers = grab piece",
            "Move hand = drag piece",
            "Open fingers = drop piece",
            "Match the faint ghost spots",
            "H = hide/show this help",
            "P = pause   M = menu",
        ]

        y = panel_y1 + 72
        for line in help_lines:
            self.ui.put_text(
                canvas,
                line,
                (panel_x1 + 28, y),
                scale=0.52,
                color=config.BROWN,
                thickness=2,
            )
            y += 26

        self._draw_simple_heart(canvas, (panel_x1 + 42, panel_y1 + 34), 10, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (panel_x2 - 38, panel_y1 + 34), 10, config.WHITE)

    def _draw_puzzle_state(self, frame):
        tracking_frame = frame.copy()
        self.hand_tracker.process(tracking_frame)

        cursor = self.hand_tracker.get_hand_cursor()
        is_pinching = self.hand_tracker.is_pinching()

        canvas = np.zeros_like(frame)
        canvas[:] = config.CREAM

        self.ui.draw_puzzle_ui(canvas, self.puzzle_game)

        elapsed = self.puzzle_game.get_elapsed_time()
        score = self.puzzle_game.get_score()

        self.ui.put_text(
            canvas,
            f"{self.difficulty_name} {self.puzzle_rows}x{self.puzzle_cols} | Time: {elapsed}s | Wrong drops: {self.puzzle_game.wrong_drops} | Score: {score}",
            (245, 105),
            scale=0.55,
            color=config.BROWN,
            thickness=2,
        )

        self.ui.put_text(
            canvas,
            self.get_best_score_text(),
            (470, 135),
            scale=0.52,
            color=config.DARK_PINK,
            thickness=2,
        )

        self.puzzle_game.draw_ghost_targets(canvas)

        self.puzzle_game.update(
            cursor,
            is_pinching,
            sound_manager=self.sound_manager,
        )

        self.puzzle_game.draw_pieces(canvas)
        self.ui.draw_cursor(canvas, cursor, is_pinching)

        self._draw_puzzle_help_overlay(canvas)

        if self.puzzle_game.is_complete():
            if not self.puzzle_game.completion_sound_played:
                self.sound_manager.play("sparkle")
                self.puzzle_game.completion_sound_played = True
                self.last_completion_was_new_best = self.update_best_score_if_needed()

            self.state = config.STATE_COMPLETE
            self.previous_state_before_pause = config.STATE_COMPLETE
            self.complete_start_time = time.time()

        if self.debug_mode:
            self.hand_tracker.draw_landmarks(canvas)
            self.ui.draw_debug(
                canvas,
                self.state,
                self.zoom_level,
                self.current_camera_index,
                self.hand_tracker.get_pinch_distance(),
                is_pinching,
                self.hand_tracker.is_peace_sign(),
            )

        return canvas

    def _draw_complete_state(self, frame):
        canvas = np.zeros_like(frame)
        canvas[:] = config.CREAM

        self.update_and_draw_particles(canvas, amount="many")

        elapsed = self.puzzle_game.get_elapsed_time()
        score = self.puzzle_game.get_score()
        rank = self.puzzle_game.get_rank()
        wrong_drops = self.puzzle_game.wrong_drops

        self.ui.draw_complete_ui(canvas, self.puzzle_game, elapsed_seconds=elapsed)
        self._draw_frame_theme_around_photo(canvas)

        h, w = canvas.shape[:2]

        # Main result card
        card_x1 = w // 2 - 440
        card_y1 = 70
        card_x2 = w // 2 + 440
        card_y2 = 285

        self.ui.rounded_rect(canvas, card_x1, card_y1, card_x2, card_y2, config.WHITE, radius=34)
        self.ui.rounded_rect(canvas, card_x1, card_y1, card_x2, card_y2, config.PASTEL_PINK, radius=34, thickness=5)

        title_text = "Puzzle Complete!"
        if self.last_completion_was_new_best:
            title_text = "New Best Score!"

        self.ui.put_text(
            canvas,
            title_text,
            (w // 2 - 205, 113),
            scale=1.18,
            color=config.DARK_PINK,
            thickness=4,
        )

        self._draw_simple_heart(canvas, (card_x1 + 55, card_y1 + 45), 17, config.DARK_PINK)
        self._draw_simple_heart(canvas, (card_x2 - 55, card_y1 + 45), 17, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (card_x1 + 70, card_y2 - 45), 13, config.WHITE)
        self._draw_simple_sparkle(canvas, (card_x2 - 70, card_y2 - 45), 13, config.WHITE)

        # Stats rows
        stat_left_x = w // 2 - 350
        stat_right_x = w // 2 + 40
        row_1_y = 158
        row_2_y = 202
        row_3_y = 246

        self.ui.rounded_rect(canvas, stat_left_x - 25, row_1_y - 30, stat_left_x + 300, row_1_y + 10, config.CREAM, radius=18)
        self.ui.rounded_rect(canvas, stat_right_x - 25, row_1_y - 30, stat_right_x + 300, row_1_y + 10, config.CREAM, radius=18)
        self.ui.rounded_rect(canvas, stat_left_x - 25, row_2_y - 30, stat_left_x + 300, row_2_y + 10, config.CREAM, radius=18)
        self.ui.rounded_rect(canvas, stat_right_x - 25, row_2_y - 30, stat_right_x + 300, row_2_y + 10, config.CREAM, radius=18)
        self.ui.rounded_rect(canvas, stat_left_x - 25, row_3_y - 30, stat_left_x + 690, row_3_y + 10, config.CREAM, radius=18)

        self.ui.put_text(canvas, f"Difficulty: {self.difficulty_name} {self.puzzle_rows}x{self.puzzle_cols}", (stat_left_x, row_1_y), scale=0.62, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, f"Time: {elapsed}s", (stat_right_x, row_1_y), scale=0.62, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, f"Wrong drops: {wrong_drops}", (stat_left_x, row_2_y), scale=0.62, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, f"Rank: {rank}", (stat_right_x, row_2_y), scale=0.62, color=config.DARK_PINK, thickness=2)
        self.ui.put_text(canvas, f"Score: {score} points", (stat_left_x, row_3_y), scale=0.68, color=config.DARK_PINK, thickness=2)
        self.ui.put_text(canvas, self.get_best_score_text(), (stat_right_x + 35, row_3_y), scale=0.52, color=config.BROWN, thickness=2)

        # Bottom controls card
        self.ui.rounded_rect(canvas, 155, h - 162, w - 155, h - 72, config.WHITE, radius=26)
        self.ui.rounded_rect(canvas, 155, h - 162, w - 155, h - 72, config.PASTEL_PINK, radius=26, thickness=3)

        self.ui.put_text(
            canvas,
            "R = replay | M = menu | S = save photo | F = frame | V = gallery | P = pause | Q = quit",
            (205, h - 125),
            scale=0.58,
            color=config.BROWN,
            thickness=2,
        )

        if self.last_saved_path:
            self.ui.put_text(
                canvas,
                f"Saved: {self.last_saved_path}",
                (310, h - 90),
                scale=0.52,
                color=config.DARK_PINK,
                thickness=2,
            )
        else:
            self.ui.put_text(
                canvas,
                "Press S to save this result to your gallery.",
                (420, h - 90),
                scale=0.52,
                color=config.DARK_PINK,
                thickness=2,
            )

        self._draw_bunny_mascot(canvas, (w - 120, h - 145), size=62)
        self._draw_mascot_speech(canvas, self.current_mascot_celebration(), w - 555, h - 225, width=360, height=82)

        if self.debug_mode:
            self.ui.draw_debug(
                canvas,
                self.state,
                self.zoom_level,
                self.current_camera_index,
                None,
                False,
                False,
            )

        return canvas

    def _draw_gallery_state(self, frame):
        canvas = np.zeros((config.FRAME_HEIGHT, config.FRAME_WIDTH, 3), dtype=np.uint8)
        canvas[:] = config.CREAM

        self.ui.draw_base_frame(canvas)
        self.update_and_draw_particles(canvas, amount="normal")

        h, w = canvas.shape[:2]

        self.ui.rounded_rect(canvas, w // 2 - 340, 45, w // 2 + 340, 125, config.SOFT_PINK, radius=32)

        self.ui.put_text(
            canvas,
            "Gallery",
            (w // 2 - 80, 98),
            scale=1.45,
            color=config.DARK_PINK,
            thickness=4,
        )

        if not self.gallery_images:
            self.ui.rounded_rect(canvas, w // 2 - 390, 240, w // 2 + 390, 470, config.WHITE, radius=34)
            self.ui.rounded_rect(canvas, w // 2 - 390, 240, w // 2 + 390, 470, config.PASTEL_PINK, radius=34, thickness=4)

            self.ui.put_text(
                canvas,
                "No saved photos yet.",
                (w // 2 - 175, 330),
                scale=1.0,
                color=config.BROWN,
                thickness=3,
            )

            self.ui.put_text(
                canvas,
                "Go to Photo Booth or finish a puzzle, then press S.",
                (w // 2 - 330, 385),
                scale=0.72,
                color=config.DARK_PINK,
                thickness=2,
            )

        else:
            image, path = self.get_current_gallery_image()

            if image is not None:
                image_h, image_w = image.shape[:2]

                max_w = int(w * 0.72)
                max_h = int(h * 0.62)

                scale = min(max_w / image_w, max_h / image_h)
                display_w = int(image_w * scale)
                display_h = int(image_h * scale)

                resized = cv2.resize(image, (display_w, display_h), interpolation=cv2.INTER_AREA)

                x = (w - display_w) // 2
                y = 155

                self._draw_frame_around_image(canvas, resized, x, y)

                base_name = os.path.basename(path)

                self.ui.put_text(
                    canvas,
                    f"{self.gallery_index + 1} / {len(self.gallery_images)}",
                    (w // 2 - 45, h - 158),
                    scale=0.75,
                    color=config.DARK_PINK,
                    thickness=2,
                )

                self.ui.put_text(
                    canvas,
                    base_name[:80],
                    (w // 2 - 335, h - 128),
                    scale=0.52,
                    color=config.BROWN,
                    thickness=2,
                )

                if self.delete_confirm_pending:
                    self.ui.rounded_rect(canvas, w // 2 - 390, h - 112, w // 2 + 390, h - 72, config.SOFT_PINK, radius=18)
                    self.ui.put_text(
                        canvas,
                        "Delete this photo? Press Y to delete or N to cancel.",
                        (w // 2 - 335, h - 84),
                        scale=0.62,
                        color=config.BROWN,
                        thickness=2,
                    )

            else:
                self.ui.put_text(
                    canvas,
                    "Could not load this image.",
                    (w // 2 - 180, h // 2),
                    scale=0.85,
                    color=config.BROWN,
                    thickness=2,
                )

        self.ui.rounded_rect(canvas, 160, h - 65, w - 160, h - 25, config.WHITE, radius=18)

        self.ui.put_text(
            canvas,
            "[/A = prev | ]/E = next | X = ask delete | Y/N = confirm/cancel | M = menu",
            (200, h - 39),
            scale=0.55,
            color=config.BROWN,
            thickness=2,
        )

        return canvas

    def _draw_paused_state(self, frame):
        if self.last_output_frame is not None:
            canvas = self.last_output_frame.copy()
        else:
            canvas = frame.copy()

        h, w = canvas.shape[:2]

        overlay = canvas.copy()
        overlay[:] = config.SOFT_PINK
        cv2.addWeighted(overlay, 0.45, canvas, 0.55, 0, canvas)

        self.ui.rounded_rect(canvas, w // 2 - 330, h // 2 - 160, w // 2 + 330, h // 2 + 160, config.CREAM, radius=40)
        self.ui.rounded_rect(canvas, w // 2 - 330, h // 2 - 160, w // 2 + 330, h // 2 + 160, config.PASTEL_PINK, radius=40, thickness=5)

        self.ui.put_text(canvas, "Paused", (w // 2 - 105, h // 2 - 80), scale=1.65, color=config.DARK_PINK, thickness=5)
        self.ui.put_text(canvas, "Press P to continue", (w // 2 - 160, h // 2 - 15), scale=0.9, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, "Press R to restart", (w // 2 - 145, h // 2 + 30), scale=0.8, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, "Press M for menu", (w // 2 - 135, h // 2 + 70), scale=0.8, color=config.BROWN, thickness=2)
        self.ui.put_text(canvas, "Press Q to quit", (w // 2 - 120, h // 2 + 110), scale=0.8, color=config.BROWN, thickness=2)

        self._draw_simple_heart(canvas, (w // 2 - 250, h // 2 - 95), 16, config.DARK_PINK)
        self._draw_simple_heart(canvas, (w // 2 + 250, h // 2 - 95), 16, config.DARK_PINK)
        self._draw_simple_sparkle(canvas, (w // 2 - 240, h // 2 + 95), 12, config.WHITE)
        self._draw_simple_sparkle(canvas, (w // 2 + 240, h // 2 + 95), 12, config.WHITE)

        return canvas

    # -------------------------------------------------
    # Main loop
    # -------------------------------------------------

    def run(self):
        cv2.namedWindow(config.WINDOW_NAME, cv2.WINDOW_NORMAL)

        running = True

        while running:
            frame, camera_ok = self._read_frame()

            if self.state == config.STATE_MENU:
                output = self._draw_menu_state(frame)

            elif self.state == "instructions":
                output = self._draw_instructions_state(frame)

            elif self.state == config.STATE_CAMERA:
                output = self._draw_camera_state(frame)

            elif self.state == config.STATE_COUNTDOWN:
                output = self._draw_countdown_state(frame)

            elif self.state == config.STATE_PUZZLE:
                output = self._draw_puzzle_state(frame)

            elif self.state == config.STATE_COMPLETE:
                output = self._draw_complete_state(frame)

            elif self.state == config.STATE_PHOTOBOOTH:
                output = self._draw_photobooth_state(frame)

            elif self.state == config.STATE_PHOTOBOOTH_COUNTDOWN:
                output = self._draw_photobooth_countdown_state(frame)

            elif self.state == config.STATE_GALLERY:
                output = self._draw_gallery_state(frame)

            elif self.state == config.STATE_SETTINGS:
                output = self._draw_settings_state(frame)

            elif self.state == config.STATE_PAUSED:
                output = self._draw_paused_state(frame)

            else:
                output = frame

            if self.state != config.STATE_PAUSED:
                self.last_output_frame = output.copy()

            cv2.imshow(config.WINDOW_NAME, output)

            key = cv2.waitKey(1) & 0xFF
            running = self._handle_keyboard(key)

        self.cleanup()

    def cleanup(self):
        self.save_user_settings()

        if self.cap is not None:
            self.cap.release()

        if self.sound_manager is not None:
            self.sound_manager.cleanup()

        cv2.destroyAllWindows()
        print("Goodbye from Kawaii Puzzle Cam.")


if __name__ == "__main__":
    app = KawaiiHandPuzzleCamApp()
    app.run()