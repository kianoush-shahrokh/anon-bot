import os
import threading
from flask import Flask
import bot

app = Flask(__name__)


@app.route("/")
def home():
    return "🤖 Anonymous Chat Bot is Running 24/7!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    # اجرای وب‌سرور در یک رشته (Thread) جداگانه
    threading.Thread(target=run_flask, daemon=True).start()
    print("🚀 Web server started. Launching Telegram Bot...")
    # اجرای ربات تلگرام
    bot.bot.infinity_polling(skip_pending=True)