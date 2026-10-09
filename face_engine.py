"""Face detection, face encoding and face matching (uses face_recognition)."""
import cv2
import face_recognition
import numpy as np

import config


def decode_image(jpeg_bytes):
    """JPEG bytes sent by the browser -> OpenCV image (or None if broken)."""
    array = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def find_faces(frame_bgr):
    """Detect faces. Returns (rgb_small_image, list_of_face_locations)."""
    small = cv2.resize(frame_bgr, (0, 0), fx=config.FRAME_SCALE, fy=config.FRAME_SCALE)
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)   # OpenCV uses BGR, the library uses RGB
    locations = face_recognition.face_locations(rgb)
    return rgb, locations


def get_encoding(rgb, locations):
    """Turn the face into 128 numbers that describe it."""
    return face_recognition.face_encodings(rgb, locations)[0]


def get_landmarks(rgb, locations):
    """Points on eyes, nose, lips... Returns a dict like {'left_eye': [...], ...}."""
    return face_recognition.face_landmarks(rgb, locations)[0]


def same_person(encoding_a, encoding_b):
    """True if two encodings are close enough to be the same face."""
    return face_recognition.face_distance([encoding_a], encoding_b)[0] <= config.TOLERANCE


def identify(encoding, users, skip_id=None):
    """Compare with saved users [(id, name, encoding)].

    Returns (id, name) of the best match, or None. skip_id = ignore this user id.
    """
    users = [u for u in users if u[0] != skip_id]
    if not users:
        return None
    distances = face_recognition.face_distance([u[2] for u in users], encoding)
    best = distances.argmin()
    if distances[best] <= config.TOLERANCE:
        return users[best][0], users[best][1]
    return None


def relative_box(location, image_shape):
    """Face box as fractions (0 to 1) of the image, so the browser can draw it at any size."""
    top, right, bottom, left = location
    height, width = image_shape[:2]
    return {"x": left / width, "y": top / height,
            "w": (right - left) / width, "h": (bottom - top) / height}
