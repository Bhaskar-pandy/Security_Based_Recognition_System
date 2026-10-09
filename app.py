"""Main file - the Flask web application (pages + API).

Run with:  python app.py   then open http://127.0.0.1:5000
"""
import base64
import csv
import io
import os
import re
import secrets
import time
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)

import config
import database
import services

USERNAME_RULE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,29}$")


def _load_flask_key():
    """Key used to sign the login cookie. Created on first run."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.FLASK_KEY_PATH):
        with open(config.FLASK_KEY_PATH, "w") as f:
            f.write(secrets.token_hex(32))
        os.chmod(config.FLASK_KEY_PATH, 0o600)
    with open(config.FLASK_KEY_PATH) as f:
        return f.read()


app = Flask(__name__)
app.config.update(SECRET_KEY=_load_flask_key(),
                  SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax",
                  MAX_CONTENT_LENGTH=config.MAX_REQUEST_BYTES)
database.init_db()

_login_fails = {}   # username -> (number of fails, time of last fail)


# =============================================================== helpers
@app.before_request
def load_user_and_check_csrf():
    """Runs before every request: find who is logged in, block forged POST requests."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    user_id = session.get("user_id")
    g.user = database.get_user(user_id) if user_id else None
    if request.method == "POST":
        token = request.form.get("csrf") or request.headers.get("X-CSRF-Token") or ""
        if not secrets.compare_digest(token, session["csrf"]):
            abort(400, "Invalid CSRF token")


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(self)"
    return response


@app.context_processor
def inject_globals():
    return {"current_user": g.user, "csrf": session.get("csrf", "")}


def login_required(role=None):
    """Page needs a logged-in user (and optionally a specific role)."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login", next=request.path))
            if role and g.user["role"] != role:
                abort(403)
            if g.user["must_change_password"] and request.endpoint != "change_password":
                return redirect(url_for("change_password"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def home_for(user):
    return url_for("admin_dashboard") if user["role"] == "admin" else url_for("my_account")


def safe_next(url):
    """Only allow redirects inside our own site."""
    return url if url and url.startswith("/") and not url.startswith("//") else None


def image_from_request():
    """Read the picture sent by the browser (a base64 'data URL')."""
    data = request.get_json(silent=True) or {}
    try:
        return base64.b64decode(data.get("image", "").split(",", 1)[1])
    except (IndexError, ValueError):
        return b""


def password_problem(password, confirm):
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return "Passwords do not match."
    return None


# =============================================================== public pages
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/access")
def access():
    return render_template("access.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        problem = None
        if not USERNAME_RULE.match(username):
            problem = "Username: 3-30 letters, numbers, dot, dash or underscore."
        elif not full_name:
            problem = "Please enter your full name."
        else:
            problem = password_problem(password, request.form.get("confirm", ""))
        if not problem:
            try:
                user_id = database.create_user(username, full_name, password)
            except ValueError as error:
                problem = str(error)
        if problem:
            flash(problem, "error")
        else:
            session.clear()
            session["user_id"] = user_id
            flash("Account created. Now register your face. An admin will approve you after that.", "ok")
            return redirect(url_for("enroll", user_id=user_id))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(home_for(g.user))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        fails, last = _login_fails.get(username, (0, 0))
        if fails >= config.MAX_LOGIN_FAILS and time.time() - last < config.LOGIN_LOCK_SECONDS:
            flash("Too many wrong attempts. Wait a minute and try again.", "error")
        else:
            user = database.check_login(username, request.form.get("password", ""))
            if user:
                _login_fails.pop(username, None)
                session.clear()
                session["user_id"] = user["id"]
                return redirect(safe_next(request.args.get("next")) or home_for(user))
            _login_fails[username] = (fails + 1 if time.time() - last < config.LOGIN_LOCK_SECONDS else 1,
                                      time.time())
            flash("Wrong username or password.", "error")
    return render_template("login.html", next_url=safe_next(request.args.get("next")) or "")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/account/password", methods=["GET", "POST"])
@login_required()
def change_password():
    if request.method == "POST":
        if not database.check_login(g.user["username"], request.form.get("current", "")):
            flash("Current password is wrong.", "error")
        else:
            problem = password_problem(request.form.get("password", ""), request.form.get("confirm", ""))
            if problem:
                flash(problem, "error")
            elif request.form.get("password") == request.form.get("current"):
                flash("Choose a different password.", "error")
            else:
                database.set_password(g.user["id"], request.form["password"])
                flash("Password changed.", "ok")
                return redirect(url_for("account"))
    return render_template("change_password.html")


@app.route("/account")
@login_required()
def account():
    return render_template("account.html", has_face=g.user["face_data"] is not None,
                           has_hand=g.user["hand_data"] is not None)


# =============================================================== user area
@app.route("/me")
@login_required("user")
def my_account():
    return render_template("me.html", logs=database.get_user_logs(g.user["id"]),
                           has_face=g.user["face_data"] is not None,
                           has_hand=g.user["hand_data"] is not None)


def enroll_target(user_id):
    """Admin may register any user (and themselves); a user may only register their own face."""
    target = database.get_user(user_id)
    if target is None or (target["role"] != "user" and target["id"] != g.user["id"]):
        abort(404)
    if g.user["role"] != "admin" and g.user["id"] != user_id:
        abort(403)
    return target


@app.route("/enroll/<int:user_id>")
@login_required()
def enroll(user_id):
    return render_template("enroll.html", target=enroll_target(user_id), SELF=user_id == g.user["id"],
                           needed=config.SAMPLES_FOR_REGISTRATION)


@app.route("/enroll-hand/<int:user_id>")
@login_required()
def enroll_hand(user_id):
    target = enroll_target(user_id)
    if target["face_data"] is None:
        flash("Register the face first, then the hand.", "error")
        return redirect(url_for("enroll", user_id=user_id))
    return render_template("enroll_hand.html", target=target, SELF=user_id == g.user["id"],
                           needed=config.SAMPLES_FOR_HAND)


# =============================================================== admin area
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    pending = [u for u in database.list_users() if u["status"] == "pending"]
    return render_template("admin_dashboard.html", stats=database.get_stats(), pending=pending,
                           logs=database.get_logs(limit=8))


@app.route("/admin/users")
@login_required("admin")
def admin_users():
    return render_template("admin_users.html", users=database.list_users())


@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required("admin")
def admin_new_user():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        problem = None
        if not USERNAME_RULE.match(username):
            problem = "Username: 3-30 letters, numbers, dot, dash or underscore."
        elif not full_name:
            problem = "Please enter the full name."
        else:
            problem = password_problem(password, password)
        if not problem:
            try:
                user_id = database.create_user(username, full_name, password,
                                               status="approved", must_change=True)
                flash("User created. Now capture the face.", "ok")
                return redirect(url_for("enroll", user_id=user_id))
            except ValueError as error:
                problem = str(error)
        flash(problem, "error")
    return render_template("admin_new_user.html")


@app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_user_action(user_id, action):
    target = database.get_user(user_id)
    if target is None or target["role"] != "user":
        abort(404)
    if action == "approve":
        if target["face_data"] is None:
            flash("This user has not registered a face yet.", "error")
        else:
            database.set_status(user_id, "approved")
            flash(f"{target['username']} approved.", "ok")
    elif action == "reject":
        database.set_status(user_id, "rejected")
        flash(f"{target['username']} rejected.", "ok")
    elif action == "delete":
        database.delete_user(user_id)
        flash(f"{target['username']} deleted.", "ok")
    elif action == "reset-password":
        new_password = request.form.get("password", "")
        problem = password_problem(new_password, new_password)
        if problem:
            flash(problem, "error")
        else:
            database.set_password(user_id, new_password, must_change=True)
            flash(f"Temporary password set for {target['username']}.", "ok")
    else:
        abort(404)
    return redirect(request.referrer or url_for("admin_users"))


@app.route("/admin/logs")
@login_required("admin")
def admin_logs():
    result = request.args.get("result", "")
    search = request.args.get("search", "").strip()
    return render_template("admin_logs.html", logs=database.get_logs(result, search),
                           result=result, search=search)


@app.route("/admin/logs.csv")
@login_required("admin")
def admin_logs_csv():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["time", "name", "result", "reason"])
    for row in database.get_logs(request.args.get("result"), request.args.get("search"), limit=100000):
        writer.writerow([row["time"], row["name"], row["result"], row["reason"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=access_logs.csv"})


# =============================================================== camera API (used by JavaScript)
@app.route("/api/access/start", methods=["POST"])
def api_access_start():
    purpose = "login" if (request.get_json(silent=True) or {}).get("purpose") == "login" else "door"
    try:
        return jsonify(attempt=services.start_access(purpose))
    except ValueError as error:
        return jsonify(state="error", message=str(error)), 400


@app.route("/api/access/frame", methods=["POST"])
def api_access_frame():
    data = request.get_json(silent=True) or {}
    attempt_id = data.get("attempt", "")
    result = services.process_access_frame(attempt_id, image_from_request())
    if result.get("state") == "granted":
        user_id = services.claim_login(attempt_id)          # only set for face sign-in attempts
        user = database.get_user(user_id) if user_id else None
        if user:
            session.clear()
            session["user_id"] = user["id"]
            result = {**result, "redirect": safe_next(data.get("next")) or home_for(user), "role": user["role"]}
    return jsonify(result)


@app.route("/api/enroll/<int:user_id>/start", methods=["POST"])
@login_required()
def api_enroll_start(user_id):
    enroll_target(user_id)
    services.start_enroll(user_id)
    return jsonify(ok=True)


@app.route("/api/enroll/<int:user_id>/frame", methods=["POST"])
@login_required()
def api_enroll_frame(user_id):
    enroll_target(user_id)
    result = services.process_enroll_frame(user_id, image_from_request())
    if result["state"] == "done":
        database.set_face(user_id, result.pop("encoding"))
        # Admin-registered faces are trusted at once; a user's own face waits for approval.
        database.set_status(user_id, "approved" if g.user["role"] == "admin" else "pending")
    return jsonify(result)


@app.route("/api/hand-enroll/<int:user_id>/start", methods=["POST"])
@login_required()
def api_hand_enroll_start(user_id):
    enroll_target(user_id)
    services.start_hand_enroll(user_id)
    return jsonify(ok=True)


@app.route("/api/hand-enroll/<int:user_id>/frame", methods=["POST"])
@login_required()
def api_hand_enroll_frame(user_id):
    enroll_target(user_id)
    result = services.process_hand_enroll_frame(user_id, image_from_request())
    if result["state"] == "done":
        database.set_hand(user_id, result.pop("features"))
    return jsonify(result)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, text="You are not allowed to open this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, text="Page not found."), 404


if __name__ == "__main__":
    print(f"Open http://{config.HOST}:{config.PORT} in your browser")
    app.run(host=config.HOST, port=config.PORT, debug=False)
