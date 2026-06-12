"""
sounds.py

Safe cute sound manager for Kawaii Puzzle Cam.

Features:
- Cute sound effects
- Cute background music loop
- SFX can be toggled on/off
- Music can be toggled on/off
- No background music if disabled
- No app packaging needed

Emergency mute:
Change SOUND_ENABLED_DEFAULT = True to False.
Change MUSIC_ENABLED_DEFAULT = True to False.
"""

import os


SOUND_ENABLED_DEFAULT = True
MUSIC_ENABLED_DEFAULT = True

SFX_VOLUME = 0.35
MUSIC_VOLUME = 0.12


class SoundManager:
    def __init__(self):
        self.enabled = SOUND_ENABLED_DEFAULT
        self.music_enabled = MUSIC_ENABLED_DEFAULT
        self.available = False
        self.sounds = {}
        self.music_path = "assets/sounds/background_music.wav"
        self.music_playing = False

        try:
            import pygame

            self.pygame = pygame
            self.pygame.mixer.pre_init(
                frequency=44100,
                size=-16,
                channels=2,
                buffer=1024,
            )
            self.pygame.mixer.init()

            self.available = True
            print("SoundManager: sound system is ready.")

        except Exception as e:
            self.pygame = None
            self.available = False
            self.enabled = False
            self.music_enabled = False
            print(f"SoundManager: sound disabled. Reason: {e}")

    def load_sound(self, name, path):
        if not self.available:
            return

        if not os.path.exists(path):
            print(f"SoundManager: missing sound file: {path}")
            return

        try:
            sound = self.pygame.mixer.Sound(path)
            sound.set_volume(SFX_VOLUME)
            self.sounds[name] = sound
            print(f"SoundManager: loaded {name} from {path}")

        except Exception as e:
            print(f"SoundManager: could not load {name}. Reason: {e}")

    def load_default_sounds(self, config):
        self.load_sound("capture", config.SOUND_CAPTURE)
        self.load_sound("pickup", config.SOUND_PICKUP)
        self.load_sound("place", config.SOUND_PLACE)
        self.load_sound("success", config.SOUND_SUCCESS)
        self.load_sound("sparkle", config.SOUND_SPARKLE)

        self.start_music()

    def play(self, name):
        if not self.available or not self.enabled:
            return

        sound = self.sounds.get(name)

        if sound is None:
            return

        try:
            sound.stop()
            sound.play()

        except Exception as e:
            print(f"SoundManager: could not play {name}. Reason: {e}")

    def start_music(self):
        if not self.available or not self.music_enabled:
            return

        if self.music_playing:
            return

        if not os.path.exists(self.music_path):
            print(f"SoundManager: missing music file: {self.music_path}")
            return

        try:
            self.pygame.mixer.music.load(self.music_path)
            self.pygame.mixer.music.set_volume(MUSIC_VOLUME)
            self.pygame.mixer.music.play(-1)
            self.music_playing = True
            print("SoundManager: background music started.")

        except Exception as e:
            self.music_playing = False
            print(f"SoundManager: could not start music. Reason: {e}")

    def stop_music(self):
        if not self.available or self.pygame is None:
            return

        try:
            self.pygame.mixer.music.stop()
            self.music_playing = False
            print("SoundManager: background music stopped.")

        except Exception:
            pass

    def set_sfx_enabled(self, value):
        self.enabled = bool(value)

        if not self.enabled:
            self.stop_sfx_only()

        print(f"SoundManager: sound effects enabled = {self.enabled}")

    def set_music_enabled(self, value):
        self.music_enabled = bool(value)

        if self.music_enabled:
            self.start_music()
        else:
            self.stop_music()

        print(f"SoundManager: background music enabled = {self.music_enabled}")

    def toggle_sfx(self):
        self.set_sfx_enabled(not self.enabled)

    def toggle_music(self):
        self.set_music_enabled(not self.music_enabled)

    def toggle_all_audio(self):
        any_audio_on = self.enabled or self.music_enabled

        if any_audio_on:
            self.set_sfx_enabled(False)
            self.set_music_enabled(False)
        else:
            self.set_sfx_enabled(True)
            self.set_music_enabled(True)

    def stop_sfx_only(self):
        if not self.available or self.pygame is None:
            return

        try:
            self.pygame.mixer.stop()

        except Exception:
            pass

    def stop_all(self):
        if not self.available or self.pygame is None:
            return

        try:
            self.pygame.mixer.stop()
            self.pygame.mixer.music.stop()
            self.music_playing = False

        except Exception:
            pass

    def cleanup(self):
        self.stop_all()

        if not self.available or self.pygame is None:
            return

        try:
            self.pygame.mixer.quit()
            print("SoundManager: cleaned up.")

        except Exception:
            pass
