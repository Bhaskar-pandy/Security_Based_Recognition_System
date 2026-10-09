"""Liveness checks - anti-spoofing.

Blink detection: a printed photo cannot blink.
Random challenges: a recorded video cannot know what will be asked (turn head, smile, ...).
"""
import math
import secrets

import config


def _distance(p1, p2):
    return math.dist(p1, p2)


def eye_aspect_ratio(eye):
    """eye = 6 (x, y) points around one eye. Small result = closed eye."""
    vertical_1 = _distance(eye[1], eye[5])
    vertical_2 = _distance(eye[2], eye[4])
    horizontal = _distance(eye[0], eye[3])
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


class BlinkDetector:
    def __init__(self):
        self.closed_frames = 0
        self.blinks = 0

    def update(self, landmarks):
        """Call once per video frame with the face landmarks."""
        left = eye_aspect_ratio(landmarks["left_eye"])
        right = eye_aspect_ratio(landmarks["right_eye"])
        ear = (left + right) / 2.0

        if ear < config.EAR_THRESHOLD:
            self.closed_frames += 1          # eye is closed in this frame
        else:
            if self.closed_frames >= config.CLOSED_FRAMES_NEEDED:
                self.blinks += 1             # eye just re-opened = one blink
            self.closed_frames = 0

    def is_live(self):
        return self.blinks >= config.BLINKS_REQUIRED


# ---------------------------------------------------------------- random challenges
# The server picks random actions for every attempt, so a pre-recorded video
# (which cannot know what will be asked) fails.
PROMPTS = {"blink": "Blink twice", "turn_left": "Turn your head to your LEFT",
           "turn_right": "Turn your head to your RIGHT", "smile": "Smile",
           "open_mouth": "Open your mouth"}
_random = secrets.SystemRandom()          # unpredictable choice, not the plain random module


def _xs(points):
    return [p[0] for p in points]


def measure_face(landmarks):
    """Landmarks -> numbers that describe head turn and mouth shape (all relative to face size)."""
    jaw = landmarks["chin"]
    width = (max(_xs(jaw)) - min(_xs(jaw))) or 1
    height = (jaw[8][1] - landmarks["nose_bridge"][0][1]) or 1
    nose_x = sum(_xs(landmarks["nose_tip"])) / len(landmarks["nose_tip"])
    lips = landmarks["top_lip"] + landmarks["bottom_lip"]
    inner_top = sum(p[1] for p in landmarks["top_lip"][-5:]) / 5
    inner_bottom = sum(p[1] for p in landmarks["bottom_lip"][-5:]) / 5
    return {"yaw": (nose_x - min(_xs(jaw))) / width,           # 0.5 = looking straight
            "mouth_width": (max(_xs(lips)) - min(_xs(lips))) / width,
            "mouth_gap": (inner_bottom - inner_top) / height}


class ChallengeRunner:
    """Gives the person a few random actions, one after the other, and checks each one."""

    def __init__(self):
        self.steps = _random.sample(list(PROMPTS), config.CHALLENGES_REQUIRED)
        self.index = 0
        self.blink = BlinkDetector()
        self.baseline = None         # neutral face: {'mouth_width', 'mouth_gap'}
        self._samples = []
        self._armed = False          # the pose must first be "not done" before it can count
        self._hold = 0

    @property
    def done(self):
        return self.index >= len(self.steps)

    @property
    def current(self):
        return None if self.done else self.steps[self.index]

    @property
    def prompt(self):
        if self.done:
            return "Look straight at the camera"
        if self.baseline is None:
            return "Look straight at the camera"
        if self.current == "blink":
            return f"Blink twice ({self.blink.blinks}/{config.BLINKS_REQUIRED})"
        return PROMPTS[self.current]

    def is_frontal(self, landmarks):
        return abs(measure_face(landmarks)["yaw"] - 0.5) <= config.FRONTAL_TOLERANCE

    def _pose_ok(self, step, m):
        if step == "turn_left":                                   # person's left = image right
            return m["yaw"] >= 0.5 + config.TURN_DELTA
        if step == "turn_right":
            return m["yaw"] <= 0.5 - config.TURN_DELTA
        if step == "smile":
            return m["mouth_width"] >= self.baseline["mouth_width"] * config.SMILE_RATIO
        return m["mouth_gap"] - self.baseline["mouth_gap"] >= config.MOUTH_OPEN_GAP

    def _next(self):
        self.index += 1
        self._armed, self._hold = False, 0
        self.blink = BlinkDetector()

    def update(self, landmarks):
        """Call once per video frame."""
        if self.done:
            return
        m = measure_face(landmarks)
        if self.baseline is None:                                 # first learn the neutral face
            if abs(m["yaw"] - 0.5) <= config.FRONTAL_TOLERANCE:
                self._samples.append(m)
            if len(self._samples) >= 3:
                self.baseline = {k: sum(s[k] for s in self._samples) / len(self._samples)
                                 for k in ("mouth_width", "mouth_gap")}
            return
        step = self.current
        if step == "blink":
            self.blink.update(landmarks)
            if self.blink.is_live():
                self._next()
            return
        if not self._pose_ok(step, m):
            self._armed, self._hold = True, 0                     # neutral seen: now the action counts
        elif self._armed:
            self._hold += 1
            if self._hold >= config.HOLD_FRAMES:
                self._next()
