"""
generate_cute_sounds.py

Creates cute WAV sound effects and a soft background music loop.

Run:
python generate_cute_sounds.py
"""

import math
import os
import wave
import struct


SOUND_FOLDER = "assets/sounds"
SAMPLE_RATE = 44100


def ensure_folder():
    os.makedirs(SOUND_FOLDER, exist_ok=True)


def write_wav(path, samples):
    with wave.open(path, "w") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)

        for sample in samples:
            sample = max(-1.0, min(1.0, sample))
            value = int(sample * 32767)
            packed = struct.pack("<hh", value, value)
            wav_file.writeframes(packed)


def sine(freq, t):
    return math.sin(2 * math.pi * freq * t)


def sine_wave(freq, duration, volume=0.25):
    total_samples = int(SAMPLE_RATE * duration)
    samples = []

    for i in range(total_samples):
        t = i / SAMPLE_RATE

        fade_in = min(1.0, t / 0.015)
        fade_out = min(1.0, (duration - t) / 0.04)
        envelope = max(0.0, min(fade_in, fade_out))

        value = sine(freq, t) * volume * envelope
        samples.append(value)

    return samples


def chirp(start_freq, end_freq, duration, volume=0.25):
    total_samples = int(SAMPLE_RATE * duration)
    samples = []

    for i in range(total_samples):
        t = i / SAMPLE_RATE
        progress = t / duration
        freq = start_freq + (end_freq - start_freq) * progress

        fade_in = min(1.0, t / 0.015)
        fade_out = min(1.0, (duration - t) / 0.045)
        envelope = max(0.0, min(fade_in, fade_out))

        value = sine(freq, t) * volume * envelope
        samples.append(value)

    return samples


def combine(parts, gap=0.025):
    output = []
    gap_samples = [0.0] * int(SAMPLE_RATE * gap)

    for part in parts:
        output.extend(part)
        output.extend(gap_samples)

    return output


def make_capture():
    samples = combine(
        [
            chirp(900, 1500, 0.08, 0.18),
            sine_wave(1800, 0.05, 0.13),
        ],
        gap=0.012,
    )
    write_wav(os.path.join(SOUND_FOLDER, "capture.wav"), samples)


def make_pickup():
    samples = chirp(500, 950, 0.10, 0.18)
    write_wav(os.path.join(SOUND_FOLDER, "pickup.wav"), samples)


def make_place():
    samples = chirp(420, 260, 0.12, 0.16)
    write_wav(os.path.join(SOUND_FOLDER, "place.wav"), samples)


def make_success():
    samples = combine(
        [
            sine_wave(660, 0.09, 0.18),
            sine_wave(880, 0.09, 0.18),
            sine_wave(1320, 0.14, 0.20),
        ],
        gap=0.025,
    )
    write_wav(os.path.join(SOUND_FOLDER, "success.wav"), samples)


def make_sparkle():
    samples = combine(
        [
            chirp(1200, 1800, 0.07, 0.13),
            chirp(1700, 2400, 0.07, 0.12),
            sine_wave(2600, 0.05, 0.10),
        ],
        gap=0.010,
    )
    write_wav(os.path.join(SOUND_FOLDER, "sparkle.wav"), samples)


def note(freq, duration, volume=0.10):
    return sine_wave(freq, duration, volume)


def make_background_music():
    """
    Soft cute looping background music.
    Simple, low-volume, music-box style.
    """
    melody = [
        (659.25, 0.28),  # E5
        (783.99, 0.28),  # G5
        (880.00, 0.36),  # A5
        (783.99, 0.28),  # G5
        (659.25, 0.28),  # E5
        (587.33, 0.36),  # D5
        (523.25, 0.42),  # C5
        (587.33, 0.28),  # D5

        (659.25, 0.28),
        (783.99, 0.28),
        (987.77, 0.36),  # B5
        (880.00, 0.28),
        (783.99, 0.28),
        (659.25, 0.36),
        (587.33, 0.42),
        (523.25, 0.42),
    ]

    samples = []

    for freq, duration in melody:
        tone = note(freq, duration, volume=0.075)

        # Add a very soft harmony underneath
        harmony = note(freq / 2, duration, volume=0.035)

        mixed = []
        max_len = max(len(tone), len(harmony))

        for i in range(max_len):
            a = tone[i] if i < len(tone) else 0.0
            b = harmony[i] if i < len(harmony) else 0.0
            mixed.append(a + b)

        samples.extend(mixed)

        # tiny pause between notes
        samples.extend([0.0] * int(SAMPLE_RATE * 0.035))

    # Repeat pattern to make the loop longer
    final_samples = samples * 4

    write_wav(os.path.join(SOUND_FOLDER, "background_music.wav"), final_samples)


def main():
    ensure_folder()

    make_capture()
    make_pickup()
    make_place()
    make_success()
    make_sparkle()
    make_background_music()

    print("Cute sounds created in assets/sounds:")
    print("- capture.wav")
    print("- pickup.wav")
    print("- place.wav")
    print("- success.wav")
    print("- sparkle.wav")
    print("- background_music.wav")


if __name__ == "__main__":
    main()
