import json
import base64
import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ============ تنظیمات (این سه‌تا رو پر کن) ============
BOT_TOKEN = "8824974778:AAGLwgVzGv4JH3EtuZPw8ox8cNs_N7LOsYw"
ADMIN_CHAT_ID = "7195511082"

GITHUB_TOKEN = "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"
GITHUB_USERNAME = "MAXO-121"
GITHUB_REPO = "User-data"
JSON_FILE_PATH = "User.json"
GITHUB_BRANCH = "main"
# ===================================================

GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_USERNAME}/{GITHUB_REPO}/contents/{JSON_FILE_PATH}"


def get_file():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    resp = requests.get(GITHUB_API_URL, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    users = json.loads(content) if content.strip() else []
    return users, data["sha"]


def update_file(new_users, sha, commit_message):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    new_content = json.dumps(new_users, indent=4, ensure_ascii=False)
    encoded_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": commit_message,
        "content": encoded_content,
        "sha": sha,
        "branch": GITHUB_BRANCH,
    }
    resp = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": ADMIN_CHAT_ID, "text": text}, timeout=10)
    except Exception:
        pass


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    entered_key = str(data.get("key", "")).strip()
    device_id = str(data.get("device_id", "")).strip()
    device_model = str(data.get("device_model", "")).strip()

    if not entered_key or not device_id:
        return jsonify({"status": "error", "message": "missing key or device_id"}), 400

    client_ip = get_client_ip()

    try:
        users, sha = get_file()
    except Exception as e:
        return jsonify({"status": "error", "message": f"github_error: {e}"}), 500

    target_user = None
    for u in users:
        if u.get("key") == entered_key:
            target_user = u
            break

    if target_user is None:
        return jsonify({"status": "wrong_key"})

    if target_user.get("device_id") != device_id:
        return jsonify({"status": "wrong_device"})

    try:
        expiry_date = datetime.datetime.strptime(target_user.get("expirydate", ""), "%d-%m-%Y")
    except Exception:
        return jsonify({"status": "error", "message": "invalid expirydate in database"}), 500

    now = datetime.datetime.now()
    if now > expiry_date:
        return jsonify({"status": "expired"})

    days_left = (expiry_date - now).days
    allow_offline = bool(target_user.get("Allowoffline", False))

    try:
        target_user["last_ip"] = client_ip
        target_user["device_model"] = device_model
        update_file(users, sha, f"Update login info for {entered_key}")
    except Exception:
        pass

    send_telegram_message(
        "New login\n"
        f"Key: {entered_key}\n"
        f"Device ID: {device_id}\n"
        f"IP: {client_ip}\n"
        f"Model: {device_model}"
    )

    return jsonify({
        "status": "ok",
        "expirydate": target_user.get("expirydate"),
        "days_left": days_left,
        "allow_offline": allow_offline,
    })


@app.route("/", methods=["GET"])
def health_check():
    return "Login relay service is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
