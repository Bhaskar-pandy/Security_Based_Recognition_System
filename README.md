# Security Based Recognition System

A web-based **face-recognition access-control system** with liveness detection, encrypted face storage, role-based accounts and a complete access log.

Built with **Python, Flask, OpenCV and dlib**.

Full technical documentation (architecture, tech stack, configuration, troubleshooting, design FAQ): **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## Features

- **Face recognition** via the browser webcam with a clear **Access Granted / Access Denied** result
- **Anti-spoofing:** random challenge-response (two random actions per attempt: blink, turn head left/right, smile, open mouth), so photos and pre-recorded videos cannot bypass the system
- **Optional second factor:** hand-geometry verification
- **Admin portal:** dashboard, user management, approvals, access-log viewer with filters and CSV export
- **User portal:** self sign-up, face registration, personal access history
- **Approval workflow:** self-registered users stay pending until an admin approves them
- **Secure by design:** encrypted face data, hashed passwords, CSRF protection, login lockout, full audit log

## How it works

```
Browser camera → frame → Flask server → face detection → liveness challenges → identity match → Granted / Denied → audit log
```

All recognition and liveness checks run on the **server**, so they cannot be skipped by modifying the page.

## Anti-spoofing

| # | Method | Mitigates |
|---|---|---|
| 1 | Random challenge-response (2 random actions per attempt) | Photos, pre-recorded videos |
| 2 | Blink detection (eye aspect ratio) | Printed photos |
| 3 | Landmark pose checks against a neutral baseline | Static or flat images |
| 4 | "Not already doing it" rule: an action counts only if it was not already in progress | Looping videos |
| 5 | Same-face check between start and end of the attempt | Swapping people mid-check |
| 6 | Identity match on a frontal face after the challenges | Matching on a distorted pose |
| 7 | Exactly one face in frame | Photo + real person tricks |
| 8 | Hand-geometry second factor (optional) | Face-only attacks |
| 9 | Server-side decisions with a 30 s time limit per attempt | Client-side tampering |
| 10 | Duplicate-face check at registration | One face under two accounts |

Not covered: 3D masks and live deepfakes / virtual cameras. Planned defences: screen-flash reflection test, rPPG pulse check, texture anti-spoof model, depth/IR camera and signed camera frames.

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript (`getUserMedia`, `fetch`) |
| Backend | Python 3.10–3.12, Flask |
| Face AI | `face_recognition` (dlib), OpenCV, NumPy, MediaPipe |
| Storage | SQLite, Fernet encryption (`cryptography`) |

## Project structure

```
├── app.py            # Web app: routes, login, roles, camera API
├── services.py       # Access-check and face-registration logic
├── face_engine.py    # Face detection, encoding, matching
├── liveness.py       # Liveness: blink + random challenges
├── hand_engine.py    # Hand geometry (optional second factor)
├── database.py       # Users and access logs (SQLite)
├── security.py       # Face-data encryption
├── config.py         # Settings
├── templates/        # HTML pages
├── static/           # CSS and JavaScript
└── data/             # Database and keys (auto-created, never commit)
```

## Installation

**Prerequisites:** Python 3.10–3.12 and CMake (required to build dlib).

**macOS / Linux**
```bash
git clone <repository-url>
cd Security_Based_Recognition_System
brew install cmake                 # macOS only
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt    # building dlib can take several minutes
python app.py
```

**Windows**
```bat
git clone <repository-url>
cd Security_Based_Recognition_System
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** and allow camera access.

## Usage

1. Log in at `/login` with the default admin account (`admin` / `Admin@123`). A password change is required at first login.
2. **Users → Add user**, then capture the face (5 samples).
3. Open **Face Access**, click *Start* and complete the liveness challenges → **Access Granted**.
4. Try a photo or an unregistered face → **Access Denied**.
5. Sign up as a new user, register a face, then approve the account from the admin panel.
6. **Logs** → filter, search and download CSV.

> Change the default admin password immediately and do not expose the app without HTTPS.

## Deployment (Hugging Face Spaces)

The repository includes a `Dockerfile` (gunicorn, single worker, port 7860) for a Docker Space.

1. Create a new Space at huggingface.co/new-space, SDK **Docker**, blank template.
2. Add the Space as a remote and push, replacing the Space README with the template that carries the required metadata:
   ```bash
   git remote add space https://huggingface.co/spaces/<username>/<space-name>
   git checkout -b space-deploy
   cp deploy/huggingface_README.md README.md
   git commit -am "Space metadata"
   git push space space-deploy:main --force
   git checkout main
   ```
   Use a Hugging Face access token (write scope) as the password.
3. Open `https://<username>-<space-name>.hf.space` (HTTPS is required for camera access), log in as the default admin and change the password.

Free Spaces have an ephemeral disk: users, faces and logs reset on restart. Use test data only.

## Roles

| Role | Permissions |
|---|---|
| Visitor | Use Face Access, log in, sign up |
| User | View own status and history, register own face, change password |
| Admin | Manage users, approve/reject, reset passwords, view and export logs |

## Configuration

All settings live in `config.py` (match strictness, liveness sensitivity, timeouts, port, password rules). See [ARCHITECTURE.md](ARCHITECTURE.md#12-configuration-knobs-configpy).

## Troubleshooting

| Problem | Fix |
|---|---|
| `dlib` fails to build | Install CMake and use Python 3.10–3.12 |
| Camera does not start | Open exactly `http://127.0.0.1:5000` and allow camera access in the browser |
| Port 5000 in use (macOS AirPlay) | Set `PORT = 5001` in `config.py` |
| Real user denied / stranger accepted | Adjust `TOLERANCE` in `config.py` |

More in [ARCHITECTURE.md](ARCHITECTURE.md#13-common-errors-and-fixes).

## Limitations

A 3D mask or a real-time deepfake / virtual camera may still defeat the software-only challenges. For any real deployment, use HTTPS and a production WSGI server (not the Flask development server). See [ARCHITECTURE.md](ARCHITECTURE.md#14-limitations-future-work-alternatives) for future work.
