"""Hand geometry: finds a hand, measures finger lengths / knuckle widths, compares two hands.

MediaPipe gives 21 points per hand (wrist, then 4 points on each finger).
We turn those points into a small list of scale-free ratios, so it does not
matter how far the hand is from the camera.
"""
import cv2
import mediapipe as mp
import numpy as np

import config

WRIST, THUMB_CMC = 0, 1
FINGERS = {"index": (5, 6, 7, 8), "middle": (9, 10, 11, 12),
           "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}
THUMB = (1, 2, 3, 4)

_hands = None


def _detector():
    global _hands
    if _hands is None:
        _hands = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1,
                                          min_detection_confidence=0.6)
    return _hands


def _dist(p, a, b):
    return float(np.linalg.norm(p[a] - p[b]))


def _chain(p, ids):
    """Length of a finger = sum of its 3 bone lengths."""
    return sum(_dist(p, ids[i], ids[i + 1]) for i in range(3))


def find_hand(frame_bgr):
    """Returns (points, box) or (None, None). points = 21x3 array in real-world units."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = _detector().process(rgb)
    if not result.multi_hand_landmarks:
        return None, None
    image_points = result.multi_hand_landmarks[0].landmark
    xs, ys = [q.x for q in image_points], [q.y for q in image_points]
    box = {"x": max(min(xs), 0), "y": max(min(ys), 0),
           "w": min(max(xs), 1) - max(min(xs), 0), "h": min(max(ys), 1) - max(min(ys), 0)}
    world = result.multi_hand_world_landmarks[0].landmark
    points = np.array([[q.x, q.y, q.z] for q in world])
    return points, box


def pose_problem(p):
    """None if the hand is an open palm facing the camera, otherwise a message for the user."""
    for name, ids in FINGERS.items():
        if _dist(p, WRIST, ids[3]) < _dist(p, WRIST, ids[1]) * 1.15:
            return "Open your hand and spread the fingers"
    normal = np.cross(p[5] - p[WRIST], p[17] - p[WRIST])
    if abs(normal[2]) / (np.linalg.norm(normal) + 1e-9) < config.HAND_MIN_FLATNESS:
        return "Face your palm towards the camera"
    return None


def measure(p):
    """21 points -> list of ratios that describe the hand shape."""
    palm = _dist(p, WRIST, 9)                                  # wrist to middle knuckle
    features = []
    for ids in FINGERS.values():
        total = _chain(p, ids)
        features.append(total / palm)                          # finger length
        features.append(_dist(p, ids[0], ids[1]) / total)      # share of the first bone
    features.append((_chain(p, THUMB) + _dist(p, WRIST, THUMB_CMC)) / palm)   # thumb length
    features.append(_dist(p, 5, 9) / palm)                     # knuckle widths
    features.append(_dist(p, 9, 13) / palm)
    features.append(_dist(p, 13, 17) / palm)
    features.append(_dist(p, 5, 17) / palm)                    # palm width
    features.append(_dist(p, WRIST, 5) / palm)                 # wrist to knuckles
    features.append(_dist(p, WRIST, 13) / palm)
    features.append(_dist(p, WRIST, 17) / palm)
    return np.array(features, dtype=np.float64)


def difference(a, b):
    """How different two hands are (0 = identical). Average relative error of the ratios."""
    return float(np.mean(np.abs(a - b) / np.abs(b)))


def same_hand(a, b):
    return difference(a, b) <= config.HAND_TOLERANCE
