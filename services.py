"""The face-check logic: access attempts and face registration.

The browser sends one picture at a time. This file remembers the progress
of each attempt (blinks counted so far, samples collected so far).
"""
import secrets
import threading
import time

import numpy as np

import config
import database
import face_engine
import hand_engine
from liveness import ChallengeRunner

_lock = threading.Lock()
_attempts = {}   # attempt id -> progress of one access check
_enrolls = {}    # user id    -> progress of one face registration


def _cleanup():
    """Forget old unfinished attempts so memory does not grow."""
    limit = time.time() - config.ATTEMPT_LIFETIME
    for key in [k for k, a in _attempts.items() if a["start"] < limit]:
        del _attempts[key]
    for key in [k for k, e in _enrolls.items() if e["start"] < limit]:
        del _enrolls[key]


def _waiting(message, box=None, **extra):
    return {"state": "waiting", "message": message, "box": box, **extra}


# ---------------------------------------------------------------- access check
def start_access(purpose="door"):
    """Begin a new access check. Returns its id. purpose: 'door' (kiosk) or 'login' (website sign-in)."""
    users = database.get_face_users()
    if not users:
        raise ValueError("No approved users are registered yet.")
    with _lock:
        _cleanup()
        attempt_id = secrets.token_urlsafe(16)
        _attempts[attempt_id] = {"users": users, "challenge": ChallengeRunner(), "start": time.time(),
                                 "first": None, "result": None, "stage": "face", "hand_start": 0.0,
                                 "hand_ok": 0, "who": None, "purpose": purpose, "user_id": None}
    return attempt_id


def claim_login(attempt_id):
    """If this finished attempt was a successful sign-in, return the user id (only once), else None."""
    with _lock:
        attempt = _attempts.get(attempt_id)
        if attempt is None or attempt["purpose"] != "login" or attempt["user_id"] is None:
            return None
        del _attempts[attempt_id]
        return attempt["user_id"]


def _finish_access(attempt, granted, name, reason, user_id=None):
    database.log_attempt(name, "GRANTED" if granted else "DENIED", reason, user_id)
    message = f"Welcome {name}" if granted else reason
    attempt["result"] = {"state": "granted" if granted else "denied", "message": message}
    if granted:
        attempt["user_id"] = user_id
    return attempt["result"]


def process_access_frame(attempt_id, jpeg_bytes):
    """Handle one camera picture of an access check."""
    attempt = _attempts.get(attempt_id)
    if attempt is None:
        return {"state": "error", "message": "Session expired. Please start again."}
    if attempt["result"]:                                    # already finished
        return attempt["result"]
    if attempt["stage"] == "face" and time.time() - attempt["start"] > config.TIMEOUT_SECONDS:
        return _finish_access(attempt, False, "Unknown", "Liveness failed (challenges not completed)")

    frame = face_engine.decode_image(jpeg_bytes)
    if frame is None:
        return {"state": "error", "message": "Bad image received."}
    if attempt["stage"] == "hand":
        return _process_hand_step(attempt, frame)

    rgb, locations = face_engine.find_faces(frame)
    if len(locations) == 0:
        return _waiting("No face found")
    if len(locations) > 1:
        return _waiting("Only ONE person please")

    box = face_engine.relative_box(locations[0], rgb.shape)
    challenge = attempt["challenge"]
    landmarks = face_engine.get_landmarks(rgb, locations)
    frontal = challenge.is_frontal(landmarks)
    if attempt["first"] is None:                             # remember the first (straight) face we saw
        if not frontal:
            return _waiting("Look straight at the camera", box)
        attempt["first"] = face_engine.get_encoding(rgb, locations)
    challenge.update(landmarks)

    if not challenge.done:
        return _waiting(challenge.prompt, box)
    if not frontal:                                          # identity is checked on a straight face
        return _waiting("Look straight at the camera", box)

    # Liveness passed: now check who it is.
    encoding = face_engine.get_encoding(rgb, locations)
    if not face_engine.same_person(encoding, attempt["first"]):
        return _finish_access(attempt, False, "Unknown", "Face changed during the check")
    match = face_engine.identify(encoding, attempt["users"])
    if match is None:
        return _finish_access(attempt, False, "Unknown", "Face not recognised")
    if database.get_hand(match[0]) is not None:             # this user also registered a hand
        attempt.update(stage="hand", who=match, hand_start=time.time(), hand_ok=0)
        return _waiting(f"Face OK, {match[1]}. Now show your open palm", None, step="hand")
    return _finish_access(attempt, True, match[1], f"Face matched, challenges passed ({', '.join(challenge.steps)})", match[0])


def _process_hand_step(attempt, frame):
    """Second step: the person who passed the face check must also show the right hand."""
    user_id, name = attempt["who"][0], attempt["who"][1]
    if time.time() - attempt["hand_start"] > config.HAND_TIMEOUT_SECONDS:
        return _finish_access(attempt, False, name, "Hand not verified (time over)", user_id)
    points, box = hand_engine.find_hand(frame)
    if points is None:
        attempt["hand_ok"] = 0
        return _waiting("Show your open palm to the camera", None, step="hand")
    problem = hand_engine.pose_problem(points)
    if problem:
        attempt["hand_ok"] = 0
        return _waiting(problem, box, step="hand")
    if not hand_engine.same_hand(hand_engine.measure(points), database.get_hand(user_id)):
        attempt["hand_ok"] = 0
        return _waiting("Hand does not match, hold still", box, step="hand")
    attempt["hand_ok"] += 1
    if attempt["hand_ok"] < config.HAND_MATCHES_NEEDED:
        return _waiting("Hold still...", box, step="hand")
    return _finish_access(attempt, True, name, "Face matched, challenges passed, hand matched", user_id)


# ---------------------------------------------------------------- face registration
def start_enroll(user_id):
    with _lock:
        _cleanup()
        _enrolls[user_id] = {"encodings": [], "last": 0.0, "start": time.time()}


def process_enroll_frame(user_id, jpeg_bytes):
    """Handle one camera picture of a registration.

    When finished the result contains the key 'encoding' (the averaged face).
    """
    enroll = _enrolls.get(user_id)
    if enroll is None:
        return {"state": "error", "message": "Session expired. Please start again."}

    frame = face_engine.decode_image(jpeg_bytes)
    if frame is None:
        return {"state": "error", "message": "Bad image received."}
    rgb, locations = face_engine.find_faces(frame)
    if len(locations) != 1:
        return _waiting("Show exactly ONE face", count=len(enroll["encodings"]))

    box = face_engine.relative_box(locations[0], rgb.shape)
    needed = config.SAMPLES_FOR_REGISTRATION
    if time.time() - enroll["last"] >= config.SAMPLE_GAP_SECONDS:
        encoding = face_engine.get_encoding(rgb, locations)
        samples = enroll["encodings"]
        if samples and not face_engine.same_person(encoding, samples[0]):
            samples.clear()                                  # a different face appeared: restart
            return _waiting("Face changed, starting again", box, count=0)
        samples.append(encoding)
        enroll["last"] = time.time()

    count = len(enroll["encodings"])
    if count < needed:
        return _waiting(f"Capturing {count}/{needed}", box, count=count)

    average = np.mean(enroll["encodings"], axis=0)
    del _enrolls[user_id]
    owner = face_engine.identify(average, database.get_face_users(), skip_id=user_id)
    if owner:
        return {"state": "error", "message": "This face is already registered to another user."}
    return {"state": "done", "message": "Face captured", "encoding": average, "count": needed}


# ---------------------------------------------------------------- hand registration
def start_hand_enroll(user_id):
    with _lock:
        _cleanup()
        _enrolls[("hand", user_id)] = {"samples": [], "last": 0.0, "start": time.time()}


def process_hand_enroll_frame(user_id, jpeg_bytes):
    """Handle one camera picture of a hand registration.

    When finished the result contains the key 'features' (the averaged hand shape).
    """
    enroll = _enrolls.get(("hand", user_id))
    if enroll is None:
        return {"state": "error", "message": "Session expired. Please start again."}
    frame = face_engine.decode_image(jpeg_bytes)
    if frame is None:
        return {"state": "error", "message": "Bad image received."}

    samples = enroll["samples"]
    points, box = hand_engine.find_hand(frame)
    if points is None:
        return _waiting("Show your open palm to the camera", count=len(samples))
    problem = hand_engine.pose_problem(points)
    if problem:
        return _waiting(problem, box, count=len(samples))

    if time.time() - enroll["last"] >= config.SAMPLE_GAP_SECONDS:
        features = hand_engine.measure(points)
        if samples and not hand_engine.same_hand(features, samples[0]):
            samples.clear()                                  # hand moved too much / another hand: restart
            return _waiting("Hold your hand steady, starting again", box, count=0)
        samples.append(features)
        enroll["last"] = time.time()

    count = len(samples)
    needed = config.SAMPLES_FOR_HAND
    if count < needed:
        return _waiting(f"Capturing {count}/{needed}", box, count=count)
    average = np.mean(samples, axis=0)
    del _enrolls[("hand", user_id)]
    return {"state": "done", "message": "Hand captured", "features": average, "count": needed}
