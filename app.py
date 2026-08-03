from flask import Flask
from threading import Thread

from message import BOT_RUNNING_STATUS_TEXT

web_app = Flask('')


def run():
    web_app.run(host='0.0.0.0', port=8080)


@web_app.route('/')
def home():
    return BOT_RUNNING_STATUS_TEXT


def keep_alive():
    Thread(target=run).start()
