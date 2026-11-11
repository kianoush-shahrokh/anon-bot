import os
import threading
from flask import Flask
import bot

app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Anonymous Chat Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def run_bot():
    print("🚀 Launching Telegram Bot Polling...")
    bot.bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # اجرای ربات تلگرام در یک ترد مستقل
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # اجرای فلسک در حلقه اصلی برای زنده نگه داشتن وب‌سرویس
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)