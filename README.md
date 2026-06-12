# Kawaii Hand Puzzle Cam

Kawaii Hand Puzzle Cam is a cute real-time webcam puzzle and photo booth application. The app uses a webcam to capture the user, tracks hand gestures with MediaPipe, lets the user create puzzles from live camera photos, and allows puzzle pieces to be moved using pinch gestures.

The project also includes a kawaii photo booth, face stickers, a gallery, music, sound effects, score tracking, and an animated bunny helper.

## Features

* Real-time webcam camera mode
* Hand tracking using MediaPipe
* Pinch-to-grab puzzle interaction
* Easy, Medium, and Hard puzzle modes
* Webcam photo capture
* Photo Booth mode
* Cute face stickers
* Multiple sticker styles
* Multiple photo frame themes
* Gallery for saved photos
* Puzzle scoring system
* Best score tracking
* Puzzle completion result screen
* Background music
* Cute sound effects
* Audio mute/unmute controls
* Animated bunny mascot helper
* Settings screen
* Help and instructions screen

## Controls

| Key     | Action                          |
| ------- | ------------------------------- |
| 1       | Easy puzzle                     |
| 2       | Medium puzzle                   |
| 3       | Hard puzzle                     |
| 4       | Photo Booth mode                |
| V       | Gallery                         |
| T       | Settings                        |
| H / I   | Help / Instructions             |
| Space   | Capture photo / start countdown |
| P       | Pause / unpause                 |
| R       | Restart                         |
| M       | Main menu                       |
| B       | Mute / unmute audio             |
| F       | Change photo frame              |
| G       | Change sticker style            |
| K       | Toggle face stickers            |
| S       | Save photo or result            |
| Q / ESC | Quit                            |

## Tech Stack

* Python
* OpenCV
* MediaPipe
* NumPy
* Pygame

## How It Works

The webcam captures video frames in real time.

MediaPipe detects and tracks the user's hand landmarks.

The app detects pinch gestures and uses them as the main interaction method for grabbing, moving, and dropping puzzle pieces.

The user can capture a webcam image, and the app splits that image into puzzle pieces based on the selected difficulty.

OpenCV is used to display the webcam feed, draw the UI, apply cute decorations, show face stickers, display the puzzle pieces, and render the gallery and result screens.

Pygame is used for sound effects and background music.

## Why I Built This

I built this project to practice real-time computer vision, gesture-based interaction, and playful user interface design.

The goal was to create a fun webcam experience that feels more interactive than a normal camera app. Instead of using the mouse, the player uses hand gestures to control puzzle pieces and interact with the game.

This project helped me better understand:

* Real-time video processing
* Hand landmark detection
* Gesture-based controls
* Pinch interaction logic
* OpenCV UI drawing
* Webcam-based gameplay
* Saving and loading local files
* Adding sound effects and background music
* Building polished AI portfolio projects

## Requirements

Make sure your computer has:

* Python installed
* A working webcam
* Camera permissions enabled
* Required Python packages installed

Install the required packages with:

```bash
pip install -r requirements.txt
```

## How to Run

```bash
cd KawaiiHandPuzzleCam
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Camera Permission Note

This app uses your webcam.

On macOS, you may need to allow Terminal or Python camera access in:

System Settings → Privacy & Security → Camera

## Future Improvements

Some features I would like to add next:

* More sticker styles
* More photo frame themes
* More puzzle difficulties
* Better hand gesture controls
* More animated mascot reactions
* More music options
* Exportable photo booth frames
* Improved gallery layout
* A packaged desktop version
* Better onboarding for first-time users

## Project Status

The project is currently a working Python webcam app with puzzle gameplay, photo booth mode, gallery, sound, music, settings, and a kawaii animated mascot.

## Author

Built by masiha1816

This project demonstrates real-time computer vision, hand gesture recognition, webcam interaction, playful UI design, and basic game mechanics using Python, OpenCV, MediaPipe, NumPy, and Pygame.
