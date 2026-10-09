"""All settings of the project are kept here, so they are easy to change."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")                 # SQLite database file
KEY_PATH = os.path.join(DATA_DIR, "secret.key")            # face-data encryption key
FLASK_KEY_PATH = os.path.join(DATA_DIR, "flask_secret.key")  # login-cookie signing key

# --- Web server ---
HOST = "127.0.0.1"         # only this computer. Use "0.0.0.0" to allow the LAN (needs HTTPS for camera)
PORT = 5000
MAX_REQUEST_BYTES = 2 * 1024 * 1024   # reject uploads bigger than 2 MB

# --- Accounts ---
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "Admin@123"   # must be changed at first login
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_FAILS = 5        # wrong passwords allowed ...
LOGIN_LOCK_SECONDS = 60    # ... before the account is locked for this long

# --- Face recognition ---
TOLERANCE = 0.5            # lower = stricter matching (0.6 is the library default)
FRAME_SCALE = 0.5          # shrink frames to half size so processing is faster
SAMPLES_FOR_REGISTRATION = 5   # face samples taken while registering a user
SAMPLE_GAP_SECONDS = 0.6   # wait between two samples

# --- Hand geometry (second step, only for users who registered a hand) ---
SAMPLES_FOR_HAND = 5       # hand samples taken while registering
HAND_TOLERANCE = 0.06      # max average ratio difference to accept (lower = stricter)
HAND_MIN_FLATNESS = 0.8    # palm must face the camera (1.0 = perfectly flat)
HAND_TIMEOUT_SECONDS = 20  # time allowed for the hand step after the face step
HAND_MATCHES_NEEDED = 3    # good frames in a row needed to accept the hand

# --- Liveness (blink detection) ---
EAR_THRESHOLD = 0.21       # eye aspect ratio below this = eye is closed
CLOSED_FRAMES_NEEDED = 1   # browser sends ~8 frames/second, so 1 closed frame is enough
BLINKS_REQUIRED = 2        # blinks needed when "blink" is one of the random challenges
TIMEOUT_SECONDS = 30       # give up if no result within this time
CHALLENGES_REQUIRED = 2    # random actions asked per attempt (blink, turn left/right, smile, open mouth)
HOLD_FRAMES = 2            # frames in a row the action must be seen
FRONTAL_TOLERANCE = 0.08   # how straight the head must be (0.5 = looking straight)
TURN_DELTA = 0.15          # how far the head must turn to count as left / right
SMILE_RATIO = 1.15         # mouth must become this much wider than the neutral mouth
MOUTH_OPEN_GAP = 0.06      # extra lip gap (fraction of face height) that counts as open mouth
ATTEMPT_LIFETIME = 120     # forget unfinished attempts after this many seconds
