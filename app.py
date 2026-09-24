from flask import Flask, jsonify
from threading import Thread
import logging

from message import BOT_RUNNING_STATUS_TEXT

logger = logging.getLogger(__name__)
web_app = Flask('')


def run():
    # Run lightweight health/keep-alive server
    web_app.run(host='0.0.0.0', port=8080)


@web_app.route('/')
def home():
    return BOT_RUNNING_STATUS_TEXT


@web_app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "AnonChatZoneBot",
        "version": "2.0.0"
    }), 200


def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
