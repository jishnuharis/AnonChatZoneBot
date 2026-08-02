# Imports responsible for running the bot in cloud
from flask import Flask
from threading import Thread

from message import BOT_RUNNING_STATUS_TEXT

web_app = Flask('')  # Creates a web app object


# Runs the bot in a said host and port
def run():
    web_app.run(host='0.0.0.0', port=8080)


# Acts as a entry point and ensures the bot is active
@web_app.route('/')
def home():
    return BOT_RUNNING_STATUS_TEXT


# Function which keeps the bot alive
def keep_alive():
    Thread(target=run).start()
