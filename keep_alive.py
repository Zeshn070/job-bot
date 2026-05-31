"""Tiny web server so Replit keeps the bot awake.

Free Replit repls sleep when idle. This serves a page on a port; point a free
UptimeRobot (uptimerobot.com) monitor at your repl's URL every 5 minutes and it
stays awake. If you run on Railway/your own PC, you can ignore this file.
"""
from threading import Thread
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Job bot is alive."


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    Thread(target=run, daemon=True).start()
