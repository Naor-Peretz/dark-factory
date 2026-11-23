"""Minimal auth service. Intentionally has NO rate limiting -- that is the factory's job.

The window and budget are constructor parameters so the behavior can be tested without
waiting 60 real seconds. Any implementation must preserve that.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

# Toy credential store. Not the point of the exercise.
USERS = {"alice": "correct-horse", "bob": "battery-staple"}


def create_app(*, window_seconds: int = 60, max_requests: int = 10) -> Flask:
    app = Flask(__name__)
    app.config["WINDOW_SECONDS"] = window_seconds
    app.config["MAX_REQUESTS"] = max_requests

    @app.post("/login")
    def login():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username")
        password = payload.get("password")
        if username in USERS and USERS[username] == password:
            return jsonify({"status": "ok", "user": username}), 200
        return jsonify({"status": "invalid_credentials"}), 401

    @app.get("/health")
    def health():
        return jsonify({"status": "up"}), 200

    return app


if __name__ == "__main__":
    create_app().run(port=5000)
