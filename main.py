import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher
from bot_handlers import register_handlers
from db import init_db
from db import SessionLocal
from bot_handlers import *
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

# create dispatcher and register handlers once
from telegram.ext import Dispatcher
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)
register_handlers(dispatcher)

@app.route("/health")
def health():
    return "OK"

@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "OK"

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
