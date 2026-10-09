# Architecture & Technical Reference

> **Purpose:** detailed technical reference for the project: design, tech stack, module overview, configuration, troubleshooting and design rationale.
> Keep it in sync with the code: update the relevant section and add an entry to the Change Log (section 19) with every change. Track new requirements in the Requirements Backlog (section 18).

**Contents**
1. Project summary · 2. Tech stack · 3. Folder structure · 4. Modules & API · 5. Roles & rules · 6. Routes · 7. Data flow · 8. Database · 9. Security design · 10. Concepts (what / why / how) · 11. Module overview · 12. Configuration · 13. Common errors · 14. Limitations, future work, alternatives · 15. Extension recipes · 16. Design FAQ · 17. Conventions · 18. Requirements backlog · 19. Change log

---

## 1. Project summary
- **Name:** Security Based Recognition System .
- **What:** Flask **web app** for face-recognition access control. The browser webcam sends pictures → the server detects the face, checks liveness (blinks), matches it → **ACCESS GRANTED / DENIED**. Admin and User roles, encrypted face storage, full access log.
- **Language / UI:** Python 3.10–3.12, Flask + Jinja templates + plain JavaScript (no frontend framework).
- **Design principle:** keep the code simple and readable; avoid unnecessary abstraction and dependencies.
- **History:** v1 was a Tkinter desktop app (`main.py`, removed). v2 (current) is the web app. v1 data (`data/security.db`) is NOT used by v2 (v2 uses `data/app.db`).

---

## 2. Tech stack

### 2.1 Big picture
```
 BROWSER (what the user sees)                 SERVER (the Python program)
┌──────────────────────────────┐            ┌─────────────────────────────────┐
│ HTML + CSS  → pages, design  │            │ Flask (app.py)  → routes, login │
│ JavaScript  → camera, sends  │ ─ JPEG ──► │ services.py     → check logic   │
│   pictures every moment      │            │ OpenCV + NumPy  → read picture  │
│                              │ ◄─ JSON ── │ face_recognition (dlib) → AI    │
│ Shows GRANTED / DENIED       │            │ SQLite + Fernet → store safely  │
└──────────────────────────────┘            └─────────────────────────────────┘
```
The browser captures and displays. The server thinks and decides. Everything security-related happens on the server.

### 2.2 Summary table
| Library / technology | Role |
|---|---|
| `Flask` (+ Werkzeug, Jinja2) | Web server, routing, templates, sessions, password hashing |
| `face_recognition` (dlib) | Face detection, 68 landmarks, 128-number encoding, distance |
| `opencv-python` (`cv2`) | Decode JPEG from browser, resize, colour conversion |
| `numpy` | Arrays, averaging encodings |
| `cryptography` (Fernet) | Encrypt face data at rest |
| `sqlite3` (stdlib) | Database |
| `setuptools<81` | `face_recognition_models` needs `pkg_resources` |
| `cmake`, `dlib` | Build/AI engine required by `face_recognition` |
| Browser `getUserMedia`, `fetch`, Canvas | Camera, sending frames, snapshots (no JS libraries) |

### 2.3 Frontend (runs in the browser)
| Technology | What it is | Role here |
|---|---|---|
| **HTML** (`templates/*.html`) | Structure of a page | Forms, tables, buttons, the video box |
| **CSS** (`static/css/style.css`) | Styling | Colours, cards, layout, dark mode, green/red badges |
| **JavaScript** (`static/js/camera.js` + script blocks) | Code running in the browser | Starts the camera, takes pictures, sends them, draws the face box, shows the result |
| **`getUserMedia`** | Built-in browser feature | Gives JavaScript the webcam (after the user clicks *Allow*) |
| **`fetch`** | Built-in browser feature | Sends data to the server without reloading the page |
| **Canvas** | Drawing area | Takes a snapshot from the video; draws the orange face rectangle |

**How a picture travels:** `grabFrame()` draws the video frame on a hidden canvas (480×360) → `toDataURL("image/jpeg")` turns it into text (base64) → `postJSON()` sends it to `/api/access/frame` → the server replies `{state, message, box}` → JavaScript draws the box, shows the message, sends the next picture → repeats until `granted` or `denied`.

### 2.4 Backend (runs on the server)
- **Python** — main language: readable, has libraries for web, AI and databases.
- **Flask** (`app.py`) — turns Python functions into pages: `@app.route("/login")` = "run this function when /login is opened". Serves pages, handles login/logout, checks roles, receives camera pictures, answers in JSON. Comes with **Jinja2** (fills HTML templates, e.g. `{{ user.name }}`), **Werkzeug** (password hashing) and **sessions** (signed cookie remembering who is logged in).
- **OpenCV (`cv2`)** — computer-vision library. Here: decodes the browser's JPEG, shrinks it to half size (faster), converts BGR→RGB.
- **NumPy** — fast number arrays. Images and encodings are NumPy arrays; used to average the 5 registration samples and convert encodings to bytes for encryption.
- **face_recognition + dlib** (`face_engine.py`) — `face_recognition` is an easy wrapper around **dlib** (C++ machine-learning library with pre-trained models, so nothing is trained by us). It does: **detect** (`face_locations`), **landmarks** (`face_landmarks`, 68 points; we use the 6 points of each eye), **encode** (`face_encodings`, 128 numbers), **compare** (`face_distance`).
- **Liveness** (`liveness.py`) — plain Python (`math`). Eye Aspect Ratio `EAR = eye height / eye width` (open ≈ 0.3, closed ≈ 0.1). EAR < 0.21 then rising again = 1 blink. Two blinks = live person (a photo can't blink).
- **SQLite** (`database.py`) — database in one file (`data/app.db`), built into Python, nothing to install. Tables: `users`, `access_logs`.
- **cryptography / Fernet** (`security.py`) — easy strong encryption (same key locks and unlocks). The 128 face numbers are encrypted before going into the DB; a stolen `app.db` without `secret.key` is unreadable.

### 2.5 Why these choices
- Python + Flask: simple, readable, ideal for a BCA project.
- `face_recognition`: pre-trained, no dataset or model training needed.
- SQLite: zero setup, single file.
- Plain JavaScript (no React/Angular): fewer moving parts, easy to explain line by line.
- Server-side checks: more secure than checking inside the browser.

---

## 3. Folder structure
```
Security_Based_Recognition_System/
├── app.py             # Flask app: all routes, login/roles, CSRF, camera API endpoints
├── services.py        # Face-check logic: access attempts + face registration state
├── face_engine.py     # detect / encode / landmarks / identify / same_person
├── liveness.py        # eye aspect ratio + BlinkDetector
├── database.py        # SQLite: users, access_logs, password hashing, stats
├── security.py        # Fernet key handling, encrypt/decrypt face encodings
├── config.py          # every tunable setting
├── requirements.txt
├── README.md          # clean overview + quick start
├── ARCHITECTURE.md    # this file (full detail)
├── templates/         # Jinja HTML pages (base.html + one per page)
│   ├── base.html index.html login.html signup.html change_password.html error.html
│   ├── access.html enroll.html me.html
│   └── admin_dashboard.html admin_users.html admin_new_user.html admin_logs.html
├── static/
│   ├── css/style.css  # all styling (light + dark mode)
│   └── js/camera.js   # helpers: startCamera, stopCamera, grabFrame, drawBox, postJSON, sleep
└── data/              # created at runtime (never share/commit)
    ├── app.db  secret.key (face-data key)  flask_secret.key (cookie-signing key)
```

---

## 4. Module responsibilities and API
Dependency direction: `app → services → face_engine, liveness, database → security → config`. No circular imports.

| File | Public functions / classes |
|---|---|
| `config.py` | constants only |
| `security.py` | `encrypt_encoding(arr)->bytes`, `decrypt_encoding(bytes)->ndarray` |
| `database.py` | `init_db()` (also creates default admin), `create_user(username, full_name, password, role, status, must_change)->id` (ValueError if duplicate), `get_user(id)`, `get_user_by_username`, `check_login(username, pw)->row\|None`, `list_users()`, `set_status(id, status)`, `set_password(id, pw, must_change)`, `set_face(id, enc)`, `delete_user(id)` (users only, never admins), `get_face_users()->[(id, username, enc)]` (approved + has face), `log_attempt(name, result, reason, user_id)`, `get_logs(result, search, limit)`, `get_user_logs(id)`, `get_stats()` |
| `liveness.py` | `eye_aspect_ratio(eye)`, `BlinkDetector.update(landmarks)`, `.is_live()`, `.blinks` |
| `face_engine.py` | `decode_image(bytes)`, `find_faces(frame)->(rgb, locs)`, `get_encoding`, `get_landmarks`, `same_person(a,b)`, `identify(enc, users, skip_id)->(id,name)\|None`, `relative_box(loc, shape)` |
| `services.py` | `start_access()->attempt_id`, `process_access_frame(id, jpeg)->dict`, `start_enroll(user_id)`, `process_enroll_frame(user_id, jpeg)->dict` (on completion includes key `encoding`) |
| `app.py` | Flask `app`, `load_user_and_check_csrf()` (before every request), `login_required(role=None)`, `home_for`, `safe_next`, `enroll_target`, `admin_user_action`, `api_*` endpoints |

State of in-progress checks lives **in memory** in `services.py` (`_attempts`, `_enrolls`), so run a single server process (the default `python app.py`). For multi-process deployment move this state into the DB/Redis.

---

## 5. Roles and rules
| Role | Can do |
|---|---|
| Anonymous | Home, **/access** (face kiosk), login, sign up |
| User | `/me` (status, own history), register/re-register own face, change password |
| Admin | Dashboard, users (add, capture face, approve, reject, reset password, delete), logs (filter, CSV), change password |

- Default admin: `admin` / `Admin@123`, created on first run with `must_change_password=1` (forced change at first login).
- **User sign-up → status `pending`** → admin approves → `approved`. Only `approved` users with a face can get ACCESS GRANTED. (Reason: otherwise anyone could add themselves to the access list.)
- Admin-created users and admin-captured faces are `approved` immediately; a user registering/re-registering their own face goes (back) to `pending`.
- **Sign in = Face OR Password (one step, never both).** `/login` has a Face/Password switch (last choice remembered). Face sign-in runs the same random-challenge check as the door and, on success, creates the session server-side (`services.claim_login`). Only `approved` accounts with a face can use it; pending users sign in with their password.
- Admins cannot be deleted. Admins may register their own face/hand (Account page) and then sign in by face too; the face check also lets them through the door kiosk.
- A face already registered to another user is rejected at enrollment.

---

## 6. Routes
- **Pages:** `/` · `/access` (door kiosk, does not sign in) · `/account` (sign-in methods) · `/signup` · `/login` · `POST /logout` · `/account/password`
- **User:** `/me` · `/enroll/<uid>`
- **Admin:** `/admin` · `/admin/users` · `/admin/users/new` · `POST /admin/users/<id>/<approve|reject|delete|reset-password>` · `/admin/logs` · `/admin/logs.csv`
- **API (JSON, CSRF header required):** `POST /api/access/start` · `POST /api/access/frame` · `POST /api/enroll/<uid>/start` · `POST /api/enroll/<uid>/frame`

---

## 7. Data flow

**Face access (public `/access`)**
1. JS opens the camera → `POST /api/access/start` (server loads approved users, creates an attempt id).
2. Loop: grab 480×360 JPEG → `POST /api/access/frame`.
3. Server: decode → detect (exactly 1 face) → remember first encoding → `BlinkDetector.update`.
4. When blinks ≥ `BLINKS_REQUIRED`: encode → check same face as first (else "Face changed during the check") → `identify`.
5. Result `granted` / `denied` + `log_attempt`. Timeout → denied "Liveness failed (no blink detected)".
6. Response shape: `{state: waiting|granted|denied|error, message, box, blinks}`.

**Face registration (`/enroll/<uid>`)**
1. `start` → frames → every `SAMPLE_GAP_SECONDS` one encoding; a different face restarts the samples.
2. After `SAMPLES_FOR_REGISTRATION` samples: average → duplicate-face check → `set_face` (encrypted) → set status (`approved` if admin, `pending` if user).

**Why checks are on the server:** if the blink check ran in the browser, a cheater could edit the JavaScript and skip it. On the server it cannot be skipped.

```
Browser camera → JPEG → Flask API → find face → blink check → encode → compare with DB → Granted/Denied → Log
```

---

## 8. Database schema (SQLite `data/app.db`)
```
users(id PK, username UNIQUE, full_name, password_hash, role 'admin'|'user',
      status 'pending'|'approved'|'rejected', face_data BLOB NULL (Fernet float64[128]),
      must_change_password 0|1, created_at)
access_logs(id PK, time, user_id NULL, name, result 'GRANTED'|'DENIED', reason)
```
`name` is stored as text so logs survive user deletion; strangers are logged as `Unknown`.

---

## 9. Security design
| Layer | Technology | Protects against |
|---|---|---|
| Random challenge-response liveness (blink, turn, smile, open mouth) | dlib landmarks + `ChallengeRunner` | Photos, pre-recorded videos (full list in section 10.5) |
| Hand geometry second factor (optional) | MediaPipe Hands + ratios | Face-only attacks |
| Same-face check | encoding distance before/after blinking | Swapping people mid-check |
| Exactly one face | detection count | Crowd / photo + real face tricks |
| Face encryption | Fernet (key file chmod 600) | Database theft |
| Password hashing (min 8 chars, forced change for default/reset) | Werkzeug | Password leaks |
| Sessions + roles | Flask signed cookie (HttpOnly, SameSite=Lax), cleared on login | Unauthorised pages, session fixation |
| CSRF token on every POST | form field `csrf` / header `X-CSRF-Token` | Forged requests from other sites |
| Login lockout (5 fails → 60 s) | in-memory counter per username | Password guessing |
| SQL `?` placeholders | sqlite3 | SQL injection |
| Safe redirects (`safe_next`), headers (nosniff, frame deny, no-store, camera permission), 2 MB request limit | Flask | Open redirect, clickjacking, huge uploads |
| Username regex | `^[A-Za-z0-9][A-Za-z0-9_.-]{2,29}$` | Odd characters, CSV injection |
| Server-side checks | Python | Editing browser JavaScript |
| Logging every attempt | `access_logs` | No accountability |

Face data = 128 numbers; no photos are stored anywhere.

---

## 10. Concepts explained (What / Why / How in this project)

### 10.1 Face detection
- **What:** finding where a face is in a picture.
- **Why:** the face must be located before it can be recognised.
- **How here:** `face_recognition.face_locations()` in `face_engine.find_faces()`; exactly one face is required.

### 10.2 Face encoding (embedding)
- **What:** 128 numbers describing a face; same person → similar numbers.
- **Why:** comparing numbers is easy, and no photos need storing (privacy).
- **How here:** `face_encodings()`; registration averages 5 encodings for stability.

### 10.3 Matching: distance and tolerance
- **What:** distance = how different two encodings are; tolerance = largest distance still accepted.
- **Why:** to decide "same person or not".
- **How here:** `face_distance()`; the best match with distance ≤ `TOLERANCE` (0.5) wins. Lower = stricter.

### 10.4 Facial landmarks
- **What:** key points on a face (eyes, nose, lips, jaw).
- **Why:** eye points are needed to detect blinks.
- **How here:** `face_landmarks()` gives `left_eye` / `right_eye` (6 points each).

### 10.5 Spoofing and liveness detection
- **What:** spoofing = cheating with a photo/video/mask; liveness = proving a real person is present.
- **Why:** otherwise a photo of an authorized person opens the door.
- **How here:** the server asks for `CHALLENGES_REQUIRED` (2) random actions per attempt, then checks the face is the same before and after. All the methods are listed below.

**Anti-spoofing methods used (all run on the server)**
| # | Method | Where | Stops |
|---|---|---|---|
| 1 | Random challenge-response: random actions from blink, turn left, turn right, smile, open mouth, chosen with `secrets.SystemRandom` | `liveness.ChallengeRunner` | Photos, pre-recorded videos (cannot know the challenge) |
| 2 | Blink detection (EAR < `EAR_THRESHOLD`, then eye reopens, `BLINKS_REQUIRED` times) | `liveness.BlinkDetector` | Printed photos |
| 3 | Landmark pose checks: head turn = nose x vs. jaw width (`TURN_DELTA`); smile = mouth width vs. neutral (`SMILE_RATIO`); open mouth = inner-lip gap vs. neutral (`MOUTH_OPEN_GAP`); pose held `HOLD_FRAMES` frames | `liveness.measure_face`, `_pose_ok` | Flat or static images |
| 4 | Neutral baseline learned from the first 3 straight frames; an action counts only after a "not doing it" frame was seen (armed rule) | `ChallengeRunner.update` | Looping videos that start mid-action |
| 5 | Same-face check: encoding of the final face vs. the first straight face (`TOLERANCE`) | `services.process_access_frame` | Swapping people mid-check |
| 6 | Identity matched only on a frontal face (`FRONTAL_TOLERANCE`) after the challenges | `services.process_access_frame` | Matching on a turned or distorted face |
| 7 | Exactly one face in the picture | `services.process_access_frame` | Photo + real person tricks |
| 8 | Hand geometry second factor: open palm, 16 finger/knuckle ratios vs. the stored template (`HAND_TOLERANCE`), `HAND_MATCHES_NEEDED` good frames | `hand_engine.py`, `services._process_hand_step` | Face-only attacks |
| 9 | Server-side decisions, attempt id, `TIMEOUT_SECONDS` limit, `ATTEMPT_LIFETIME` cleanup | `services.py` | Editing the page to skip checks, stale sessions |
| 10 | Duplicate-face check at registration | `services.process_enroll_frame` | One face under two accounts |

**Not covered:** 3D masks and live deepfakes / virtual cameras. **Future defences:** screen-flash reflection test, rPPG pulse check, texture anti-spoof CNN, depth/IR camera, signed camera frames and device attestation, deepfake detector, rate limiting on `/access`.

### 10.6 Eye Aspect Ratio (EAR)
- **What:** `(vertical1 + vertical2) / (2 × horizontal)` of the 6 eye points. Open ≈ 0.3, closed ≈ 0.1.
- **Why:** simple blink detector, no extra model.
- **How here:** `liveness.py`; EAR < 0.21 then the eye opens again = 1 blink.

### 10.7 Flask (web framework)
- **What:** a small Python library for building websites.
- **Why:** lightweight, widely used and sufficient for this application's needs.
- **How here:** `app.py`; each `@app.route` is a URL handled by one function.

### 10.8 Templates (Jinja2)
- **What:** HTML with placeholders `{{ }}` and loops `{% for %}`.
- **Why:** one layout (`base.html`) reused by every page.
- **How here:** files in `templates/`, rendered with `render_template()`.

### 10.9 Browser camera and API (JavaScript `fetch`)
- **What:** browsers can use the webcam (`getUserMedia`); `fetch` sends data without reloading; an *API* is a URL that returns data (JSON) instead of a page.
- **Why:** Python cannot read the visitor's camera; the browser must capture and send it.
- **How here:** `camera.js` grabs a frame, base64-encodes it, `postJSON` sends it to `/api/access/frame`; the server replies with `{state, message, box}`.

### 10.10 Sessions, cookies and login
- **What:** after login the server gives the browser a signed cookie so it remembers you.
- **Why:** HTTP forgets everything between requests.
- **How here:** Flask `session`; `login_required("admin")` protects admin pages; a normal user opening them gets *403*.

### 10.11 Password hashing
- **What:** storing a one-way scrambled version of the password.
- **Why:** if the database leaks, passwords stay safe.
- **How here:** `generate_password_hash()` on save, `check_password_hash()` at login.

### 10.12 CSRF protection
- **What:** an attack where another website makes your logged-in browser send a request (e.g. "delete user").
- **Why:** prevents forged actions.
- **How here:** every form/API call carries a secret token that must match the session's.

### 10.13 Encryption (Fernet)
- **What:** scrambling data so only the key holder can read it.
- **Why:** a stolen database file does not reveal face data.
- **How here:** `security.py`; key in `data/secret.key`; `database.py` encrypts before saving, decrypts when matching.

### 10.14 SQLite and logging
- **What:** a database in one file; logging = recording every event.
- **Why:** reliable storage with no server; security needs accountability.
- **How here:** `users` and `access_logs`; `log_attempt()` after every access check.

### 10.15 Account lockout and roles
- **What:** lock after 5 wrong passwords for 60 s; roles decide what each account may do.
- **Why:** stops password guessing; separates admin from user powers.
- **How here:** `_login_fails` in `app.py`; `role` column (`admin` / `user`).

### 10.16 Virtual environment (`venv`)
- **What:** a private folder of libraries for one project.
- **Why:** avoids version clashes between projects.
- **How here:** `python3 -m venv venv` then `source venv/bin/activate`.

---

## 11. Module overview
- **`config.py`** — notice board of settings.
- **`security.py`** — a locker. Make a key once; lock face data before saving; unlock when needed.
- **`database.py`** — a register book in one file: *users* sheet (who exists, status, locked face) and *access_logs* sheet (who tried, result, reason). The `?` marks keep it safe from SQL injection.
- **`liveness.py`** — eye height ÷ eye width. Blink → ratio drops → rises again → count one blink.
- **`face_engine.py`** — helpers: find the face, describe it in numbers, find the eye points, tell whose face it is.
- **`services.py`** — the supervisor of one check. It remembers how many blinks were seen and decides GRANTED or DENIED.
- **`app.py`** — the receptionist. Each URL is a desk (login, admin, camera). Before serving anyone it checks who they are and whether they are allowed.
- **`camera.js`** — the browser's helper: turn the camera on, take a photo every moment, send it, show the answer.

---

## 12. Configuration knobs (`config.py`)
| Setting | Default | Meaning |
|---|---|---|
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Where the server listens (`0.0.0.0` for LAN needs HTTPS for camera) |
| `MAX_REQUEST_BYTES` | 2 MB | Upload size limit |
| `DEFAULT_ADMIN_USERNAME` / `PASSWORD` | `admin` / `Admin@123` | First-run admin (forced change) |
| `MIN_PASSWORD_LENGTH` | 8 | Password rule |
| `MAX_LOGIN_FAILS` / `LOGIN_LOCK_SECONDS` | 5 / 60 | Lockout |
| `TOLERANCE` | 0.5 | Match strictness (lower = stricter; never above 0.6) |
| `FRAME_SCALE` | 0.5 | Shrink factor for speed |
| `SAMPLES_FOR_REGISTRATION` / `SAMPLE_GAP_SECONDS` | 5 / 0.6 | Registration samples |
| `EAR_THRESHOLD` | 0.21 | Below = eye closed |
| `CLOSED_FRAMES_NEEDED` | 1 | Pictures the eye must stay closed (browser sends ~8 pictures/s) |
| `BLINKS_REQUIRED` | 2 | Blinks needed |
| `TIMEOUT_SECONDS` | 20 | Access check time limit |
| `ATTEMPT_LIFETIME` | 120 | Forget unfinished checks after this many seconds |
| `DB_PATH`, `KEY_PATH`, `FLASK_KEY_PATH` | `data/...` | File locations |

---

## 13. Common errors and fixes
| Problem | Reason | Fix |
|---|---|---|
| `Failed building wheel for dlib` / `CMake must be installed` | Build tools missing | Mac: `brew install cmake`, `xcode-select --install`. Windows: Visual Studio Build Tools (C++) + CMake. Use Python 3.10–3.12 |
| `Please install face_recognition_models` / `No module named 'pkg_resources'` | New setuptools | `pip install "setuptools<81"` then `pip install face_recognition_models` |
| `No module named 'flask'` (or cv2…) | venv not active / not installed | `source venv/bin/activate` then `pip install -r requirements.txt` |
| `Address already in use` (port 5000) | Mac AirPlay uses 5000, or app already running | Set `PORT = 5001` in `config.py` (or turn off AirPlay Receiver) |
| "Camera is not available" / camera does not start | Not on `localhost`/HTTPS, or permission denied | Open exactly `http://127.0.0.1:5000`; click the lock icon → allow Camera; close Zoom/Meet |
| Black video after allowing camera | Another app uses the camera | Close other apps, reload |
| "No face found" always | Poor light, too far | Face a light, 40–80 cm from the camera |
| Blinks not counted | Eyes/glasses/light | Raise `EAR_THRESHOLD` to 0.25; remove glasses; blink slowly; good light |
| Real user denied | Too strict | `TOLERANCE` 0.55; re-register in good light |
| Stranger granted | Too loose | `TOLERANCE` 0.45 |
| "This face is already registered to another user" | Same face on two accounts | Delete the old account first |
| "No approved users are registered yet" | Nobody approved / no face | Admin: add a user or approve a pending one that has a face |
| Locked out after wrong passwords | 5 failures → 60 s lock | Wait one minute |
| Forgot admin password | – | Stop app, delete `data/app.db`, run again (default admin returns; users are lost) |
| `cryptography.fernet.InvalidToken` | `secret.key` changed but old DB kept | Delete `data/app.db`, register users again |
| 400 "Invalid CSRF token" | Page open too long / cookies blocked | Reload, enable cookies |
| Slow recognition | Weak CPU | Lower `FRAME_SCALE` to 0.4 |

---

## 14. Limitations, future work, alternatives

**Known limitations**
- Random challenges (`ChallengeRunner`) stop photos and pre-recorded videos, but a 3D mask or a live deepfake / virtual camera may still fool them.
- No rate limiting on `/access` attempts; login lockout is in memory (resets on restart).
- Browser camera needs `localhost` or HTTPS; other devices on a LAN need HTTPS.
- The Flask development server is for local use only; use waitress/gunicorn + HTTPS for real use (single process, see section 4).
- Keys and DB live on the same machine.
- Tested with a **stubbed** face library (all routes/flows pass); real-camera accuracy must be verified on a real machine.

**Future work:** screen-flash reflection test, rPPG pulse check, texture anti-spoof model, depth/IR camera, door-lock relay, email alerts on denial, intruder snapshot, dashboard charts, HTTPS deployment.

**Alternative designs considered:**
1. *Browser-side detection (face-api.js / MediaPipe)* — faster, no frames uploaded, but the check can be tampered with.
2. *Desktop Tkinter app (v1)* — simplest, but one machine only.
3. *Mobile app / Raspberry Pi door unit* calling the same Flask API.

Server-side checking was chosen because it is more secure and keeps the client thin.

---

## 15. How to extend (recipes)
| Wanted change | Where |
|---|---|
| Stricter / looser matching | `config.TOLERANCE` |
| Blink too sensitive / not detected | `config.EAR_THRESHOLD`, `CLOSED_FRAMES_NEEDED`, `BLINKS_REQUIRED` |
| Random-challenge liveness | `liveness.py` + `services.process_access_frame` |
| Door-lock / relay output | new `actuator.py`, call in `services._finish_access` when granted |
| Email/SMS alert on denial | new `notify.py`, call in `services._finish_access` |
| Save intruder snapshot | store `frame` with `cv2.imwrite` in `services._finish_access` |
| Charts on dashboard | `database.get_stats()` + a Chart.js block in `admin_dashboard.html` |
| Multiple admins | `role` column exists; add an admin-create form in `app.py` |
| HTTPS / deployment | reverse proxy (nginx/Caddy) or `waitress-serve`; set `SESSION_COOKIE_SECURE=True` |

---

## 16. Design FAQ

**Summary:** a web-based access-control system that grants access only to a live, approved person whose face matches a stored record.

**Workflow:** a user signs up and registers their face through the browser camera; the server converts it to a 128-dimension encoding, encrypts it and stores it. An admin approves the account. At the access point, the browser streams camera frames to the server, which issues random liveness challenges, then compares the face encoding with stored records. The result (**Access Granted** / **Access Denied**) is logged and available to admins with filtering and CSV export.

1. **Why a web app?** It works in any browser, supports admin and user roles, and keeps logs centrally.
2. **Why verify on the server?** Client-side code can be modified; server-side decisions cannot be bypassed from the page.
3. **How does recognition work?** A dlib neural network converts a face to 128 numbers; the distance between two encodings determines the match.
4. **What is tolerance?** The maximum distance accepted as a match; 0.5 is strict (see `config.py`).
5. **How does liveness work?** Random challenges (blink, head turn, smile, mouth open) are verified from facial landmarks; blinks use the Eye Aspect Ratio (EAR).
6. **Can it be fooled?** 3D masks and live deepfakes / virtual cameras may succeed; see section 14 for mitigations.
7. **How is data protected?** Fernet-encrypted face data, hashed passwords, CSRF tokens, login lockout, role checks, parameterised SQL and an audit log.
8. **Why admin approval?** It prevents self-registered users from adding themselves to the access list.
9. **False accept vs. false reject?** Admitting the wrong person vs. denying the right one; tolerance balances the two.
10. **Why SQLite?** Bundled with Python, zero setup, adequate for a single-node deployment.
11. **Why store encodings, not photos?** They are smaller and less sensitive, and a photo cannot easily be reconstructed from them.
12. **Why Flask and plain JavaScript?** Minimal dependencies; the application only needs routing, templates, camera access and `fetch`.
13. **What if multiple faces appear?** The server requires exactly one face and does not proceed.

**Suggested demo flow:** admin login → add user and capture face → Face Access with liveness challenges (granted) → photo on a phone (denied) → unregistered face (denied) → sign up as a new user → admin approval → Logs and CSV export.

---

## 17. Conventions
- Readable code: short functions, simple names, one-line docstrings, few comments that explain *why*.
- Settings go in `config.py`, never hard-coded.
- DB access only through `database.py`; encryption only through `security.py`; face-check state only in `services.py`; UI/routes only in `app.py` + `templates/`.
- Every POST must carry the CSRF token (forms: hidden `csrf`; JS: `postJSON` adds the header).
- Camera is opened only while a task runs and released at the end.
- Update this file after every change.

---

## 18. Requirements Backlog  ← ADD NEW REQUIREMENTS HERE
Format: `- [ ] ID — description (priority)`; mark `[x]` when done and note the files touched.

- [x] R1 — Camera capture, face detect + recognise (`face_engine.py`, `services.py`, `access.html`)
- [x] R2 — Access Granted / Denied message (`access.html`)
- [x] R3 — Liveness / anti-spoofing via blink (`liveness.py`, `services.py`)
- [x] R4 — Encrypted storage of face data (`security.py`, `database.py`)
- [x] R5 — Log successful + failed attempts (`database.py`, admin logs page)
- [x] R6 — Simple UI → upgraded to web UI (`templates/`, `static/`)
- [x] R7 — Documentation (`ARCHITECTURE.md`, `README.md`)
- [x] R8 — Web interface with Admin login (monitor, logs, register, delete, approve, CSV) (`app.py`, admin templates)
- [x] R9 — User login + self sign-up with face registration, admin approval (`app.py`, `me.html`, `enroll.html`)
- [x] R10 — Simple sign-in: Face OR Password for users and admins, guided onboarding stepper, Account page, redesigned UI (`app.py`, `services.py`, `login.html`, `account.html`, `me.html`, `style.css`, `camera.js`)
- [ ] R11 — *(add your next requirement here)*

---

## 19. Change Log
| Date | Change | Files |
|---|---|---|
| 2026-10-05 | v1 Tkinter prototype + docs | all |
| 2026-10-05 | v2: converted to Flask web app, roles (admin/user), approval flow, CSRF, lockout, CSV export, same-face check, duplicate-face check; removed Tkinter `main.py`; DB moved to `app.db` | app.py, services.py, database.py, face_engine.py, config.py, templates/, static/, requirements.txt, docs |
| 2026-10-05 | Docs restructure: README = clean overview; ARCHITECTURE = full detail (tech stack, concepts, code explanation, errors, design FAQ) | README.md, ARCHITECTURE.md |
| 2026-10-05 | Hand geometry as optional 2nd step after face+blink (MediaPipe Hands 0.10.21, 16 scale-free finger/knuckle ratios, encrypted `users.hand_data`); UI redesign (style.css, base.html) | hand_engine.py, services.py, database.py, app.py, config.py, templates/enroll_hand.html, me.html, admin_users.html, requirements.txt |
| 2026-10-05 | Random challenge-response liveness: server picks `CHALLENGES_REQUIRED` random actions (blink, turn left/right, smile, open mouth) per attempt, learns a neutral baseline, requires a straight face before identity check | liveness.py, services.py, config.py, templates/access.html, index.html, README.md |
| 2026-10-05 | Docs: listed all anti-spoofing methods used (README + ARCHITECTURE 10.5, section 9 table) | README.md, ARCHITECTURE.md |
| 2026-10-05 | Unified sign-in (Face OR Password, admins included), `/account` page, onboarding stepper, scanner UI, `purpose` (door/login) on access attempts, `runAccessCheck` helper | app.py, services.py, database.py, camera.js, templates/, style.css |
