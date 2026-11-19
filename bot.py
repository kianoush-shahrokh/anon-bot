import os
import re
import threading
import time
from dotenv import load_dotenv
import telebot
from telebot import types
import db
import keyboards as kb

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

bot = telebot.TeleBot(BOT_TOKEN)
db.init_db()

try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = ""

USER_CONTEXT = {}

# تنظیمات کانال جوین اجباری
REQUIRED_CHANNEL_USERNAME = "@KR_to_infinity"
REQUIRED_CHANNEL_LINK = "https://t.me/KR_to_infinity"

DEFAULT_BOY_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
DEFAULT_GIRL_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"


def get_admin_ids():
    raw = os.getenv("ADMIN_ID", "")
    ids = []
    for part in str(raw).split(","):
        digits = re.sub(r"\D", "", part)
        if digits and int(digits) != 0:
            ids.append(int(digits))
    return ids


def is_admin(user_id):
    return int(user_id) in get_admin_ids()


def is_private_enabled(user_id):
    u = db.get_user(user_id)
    return bool(u.get("private_chat")) if u else False


def is_chat_protected(user1_id, user2_id):
    return is_private_enabled(user1_id) or is_private_enabled(user2_id)


def get_main_kb(user_id):
    return kb.main_menu_keyboard(
        is_admin=is_admin(user_id),
        private_mode=is_private_enabled(user_id),
    )


def get_chat_kb(user_id):
    return kb.chatting_keyboard(private_mode=is_private_enabled(user_id))


def send_main_menu_with_link(user_id, custom_intro=None):
    user = db.get_user(user_id)
    name = (user.get("name") if user else "") or "رفیق"
    priv_status = (
        "روشن 🔒 (ضداسکرین‌شات و ضدذخیره فعال)"
        if (user and user.get("private_chat"))
        else "خاموش 🔓"
    )
    intro = custom_intro or (
        f"سلام {name} جان! خوش اومدی به منوی اصلی 🌟\n"
        f"برای شروع یک گفتگوی ناشناس جذاب، از دکمه‌های پایین انتخاب کن 👇"
    )
    inline_link = types.InlineKeyboardMarkup()
    inline_link.add(
        types.InlineKeyboardButton(
            "📢 کانال رسمی و اطلاعیه‌ها", url=REQUIRED_CHANNEL_LINK
        )
    )
    bot.send_message(
        user_id,
        f"{intro}\n\n"
        f"🛡 وضعیت چت خصوصی شما: {priv_status}\n"
        f"🔗 کانال رسمی ما: {REQUIRED_CHANNEL_LINK}",
        reply_markup=get_main_kb(user_id),
        disable_web_page_preview=True,
    )
    bot.send_message(
        user_id,
        "✨ عضویت و اخبار ربات در کانال زیر:",
        reply_markup=inline_link,
    )


def is_user_member_of_channel(user_id):
    if is_admin(user_id):
        return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL_USERNAME, user_id)
        return member.status in ["creator", "administrator", "member", "restricted"]
    except Exception:
        return False


def enforce_channel_membership(user_id):
    if is_user_member_of_channel(user_id):
        return False

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "📢 عضویت در کانال", url=REQUIRED_CHANNEL_LINK
        ),
        types.InlineKeyboardButton(
            "✅ عضو شدم / بررسی مجدد", callback_data="check_channel_join"
        ),
    )
    bot.send_message(
        user_id,
        "سلام رفیق! 👋✨\n"
        "برای استفاده از ربات چت ناشناس، ابتدا باید در کانال رسمی ما عضو بشی:\n\n"
        f"🔗 {REQUIRED_CHANNEL_LINK}\n\n"
        "بعد از عضویت، روی دکمه «✅ عضو شدم / بررسی مجدد» پایین بزن تا ربات برات فعال بشه 👇",
        reply_markup=markup,
        disable_web_page_preview=True,
    )
    return True


def is_profile_complete(u):
    if not u:
        return False
    return bool(
        u.get("name")
        and u.get("gender")
        and u.get("age")
        and u.get("province")
        and u.get("city")
    )


def enforce_registration_step(user_id, u):
    if not u or not u.get("name"):
        db.set_user_state(user_id, "reg_name")
        USER_CONTEXT[user_id] = "reg_waiting_name"
        bot.send_message(
            user_id,
            "برای شروع و آشنایی بیشتر، اول **نام** قشنگت رو برام بنویس (اجباری):",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return True

    if not u.get("gender"):
        db.set_user_state(user_id, "reg_gender")
        bot.send_message(
            user_id,
            "حالا **جنسیت** خودت رو از دکمه‌های پایین انتخاب کن (اجباری):",
            parse_mode="Markdown",
            reply_markup=kb.gender_keyboard(allow_back=False),
        )
        return True

    if not u.get("age"):
        db.set_user_state(user_id, "reg_age_range")
        bot.send_message(
            user_id,
            "بازه **سنی** خودت رو انتخاب کن (اجباری):",
            parse_mode="Markdown",
            reply_markup=kb.age_ranges_keyboard(allow_back=False),
        )
        return True

    if not u.get("province"):
        db.set_user_state(user_id, "reg_province")
        bot.send_message(
            user_id,
            "**استان** محل سکونتت رو انتخاب کن (اجباری):",
            parse_mode="Markdown",
            reply_markup=kb.provinces_keyboard(allow_back=False),
        )
        return True

    if not u.get("city"):
        db.set_user_state(user_id, f"reg_city_{u['province']}")
        bot.send_message(
            user_id,
            f"**شهر** خودت در {u['province']} رو انتخاب کن (اجباری):",
            parse_mode="Markdown",
            reply_markup=kb.cities_keyboard(u["province"], allow_back=False),
        )
        return True

    return False


def contains_links_or_usernames(text):
    if not text:
        return False
    pattern = (
        r"(@[a-zA-Z0-9_]{4,}|t\.me/[a-zA-Z0-9_]+|https?://[^\s]+|www\.[^\s]+)"
    )
    return bool(re.search(pattern, text))


def send_profile_card_with_photo(
    receiver_id, target_user, caption, reply_markup=None, protect=False
):
    fid = target_user.get("photo_file_id")

    if not fid:
        try:
            photos = bot.get_user_profile_photos(
                target_user["user_id"], limit=1
            )
            if photos.total_count > 0:
                fid = photos.photos[0][-1].file_id
                db.add_or_update_user(
                    target_user["user_id"], photo_file_id=fid
                )
        except Exception:
            pass

    if fid and fid != "NO_PHOTO":
        try:
            bot.send_photo(
                receiver_id,
                fid,
                caption=caption,
                reply_markup=reply_markup,
                protect_content=protect,
            )
            return
        except Exception:
            pass

    avatar_url = (
        DEFAULT_GIRL_AVATAR
        if target_user.get("gender") == "دختر"
        else DEFAULT_BOY_AVATAR
    )
    try:
        bot.send_photo(
            receiver_id,
            avatar_url,
            caption=caption,
            reply_markup=reply_markup,
            protect_content=protect,
        )
    except Exception:
        bot.send_message(
            receiver_id,
            caption,
            reply_markup=reply_markup,
            protect_content=protect,
        )


def format_profile_caption(u, title="👤 مشخصات حساب شما:"):
    icon = "👦" if u.get("gender") == "پسر" else "👧"
    status_str = "👀 آنلاین"
    if u.get("status") == "chatting":
        status_str = "🗣 در حال چت"
    return (
        f"{title}\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"🏷 نام: {u.get('name') or 'ثبت نشده'}\n"
        f"{icon} جنسیت: {u.get('gender') or 'ثبت نشده'}\n"
        f"🎂 سن: {u.get('age') or 'ثبت نشده'}\n"
        f"📍 موقعیت: {u.get('province') or '-'} ({u.get('city') or '-'})\n"
        f"📡 وضعیت: {status_str}\n"
        f"🆔 شناسه: /{u.get('custom_id')}"
    )


def send_single_logged_media_to_admin(admin_id, log_row):
    ctype = log_row["content_type"]
    fid = log_row["content"]
    cap = log_row.get("caption") or ""
    timed_txt = " (عکس تایم دار)" if log_row.get("is_timed") else ""
    info_caption = f"📎 فایل درخواستی{timed_txt}\n{cap}".strip()

    try:
        if ctype == "photo":
            bot.send_photo(admin_id, fid, caption=info_caption)
        elif ctype == "video":
            bot.send_video(admin_id, fid, caption=info_caption)
        elif ctype == "voice":
            bot.send_voice(admin_id, fid, caption=info_caption)
        elif ctype == "audio":
            bot.send_audio(admin_id, fid, caption=info_caption)
        elif ctype == "document":
            bot.send_document(admin_id, fid, caption=info_caption)
    except Exception as e:
        bot.send_message(admin_id, f"⚠️ خطا در باز کردن فایل: {e}")


def launch_user_session(user_id):
    """شروع خودکار ربات بعد از استارت یا تایید کانال بدون نیاز به استارت مجدد"""
    USER_CONTEXT.pop(user_id, None)
    user = db.get_user(user_id)

    if user and user.get("is_banned"):
        bot.send_message(user_id, "🚫 حساب کاربری شما توسط مدیریت مسدود شده است.")
        return

    initial_photo = None
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            initial_photo = photos.photos[0][-1].file_id
    except Exception:
        pass

    if not user:
        db.add_or_update_user(
            user_id,
            photo_file_id=initial_photo,
            state="reg_name",
        )
        USER_CONTEXT[user_id] = "reg_waiting_name"
        welcome_markup = types.InlineKeyboardMarkup()
        welcome_markup.add(
            types.InlineKeyboardButton(
                "📢 کانال رسمی ربات", url=REQUIRED_CHANNEL_LINK
            )
        )
        bot.send_message(
            user_id,
            "سلام رفیق! خیلی خوش اومدی به جمع صمیمی ما 🎭✨\n"
            "اینجا می‌تونی با کلی آدم جدید و باحال به‌صورت کاملاً ناشناس گپ بزنی و دوستای جدید پیدا کنی.\n\n"
            f"🔗 کانال رسمی و اطلاعیه‌های ما:\n{REQUIRED_CHANNEL_LINK}",
            reply_markup=welcome_markup,
            disable_web_page_preview=True,
        )
        bot.send_message(
            user_id,
            "🚀 ربات برات فعال شد! برای شروع، همین الان **نام** قشنگت رو برام بنویس (تکمیل نام، جنسیت و موقعیت اجباریه):",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    if not user.get("photo_file_id") and initial_photo:
        db.add_or_update_user(user_id, photo_file_id=initial_photo)

    if enforce_registration_step(user_id, user):
        return

    db.set_user_state(user_id, "main_menu")
    send_main_menu_with_link(
        user_id,
        f"سلام {user.get('name')} جان! خیلی خوش اومدی 🌟\n"
        "ربات آماده‌ست، از منوی پایین انتخاب کن 👇",
    )


# --- تایید عضویت در کانال از طریق دکمه شیشه‌ای ---
@bot.callback_query_handler(func=lambda call: call.data == "check_channel_join")
def callback_check_channel_join(call):
    uid = call.from_user.id
    if not is_user_member_of_channel(uid):
        bot.answer_callback_query(
            call.id,
            "❌ هنوز عضو کانال نشدی! اول عضو شو و بعد دوباره دکمه بررسی رو بزن.",
            show_alert=True,
        )
        return

    bot.answer_callback_query(call.id, "✅ عضویتت تایید شد! ربات فعال شد 🌟")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

    launch_user_session(uid)


# --- دکمه تنظیمات چت خصوصی (روشن / خاموش کردن قفل ضداسکرین‌شات و ضدذخیره) ---
@bot.message_handler(
    func=lambda msg: msg.text
    in ["🔒 چت خصوصی: روشن ✅", "🔓 چت خصوصی: خاموش ❌"]
)
def toggle_private_chat_setting(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if enforce_registration_step(user_id, user):
        return

    new_state = db.toggle_private_mode(user_id)
    user = db.get_user(user_id)

    if new_state:
        info_txt = (
            "🔒 **حالت چت خصوصی روشن شد!**\n"
            "✅ از این لحظه به بعد، تمام پیام‌ها، عکس‌ها، ویدیوها و ویس‌های چت شما محافظت می‌شوند و امکان **اسکرین‌شات، فوروارد و ذخیره** غیرفعال خواهد بود."
        )
    else:
        info_txt = (
            "🔓 **حالت چت خصوصی خاموش شد.**\n"
            "پیام‌ها به صورت عادی ارسال می‌شوند (مگر اینکه طرف مقابل چت خصوصی را روشن کرده باشد)."
        )

    if user and user.get("status") == "chatting":
        bot.send_message(
            user_id,
            info_txt,
            parse_mode="Markdown",
            reply_markup=get_chat_kb(user_id),
        )
        partner_id = user.get("partner_id")
        if partner_id:
            try:
                status_notif = (
                    "🔒 هم‌صحبت شما **چت خصوصی** را روشن کرد (امکان اسکرین‌شات و فوروارد غیرفعال شد)."
                    if new_state
                    else "🔓 هم‌صحبت شما **چت خصوصی** را خاموش کرد."
                )
                bot.send_message(
                    partner_id, status_notif, parse_mode="Markdown"
                )
            except Exception:
                pass
    else:
        bot.send_message(
            user_id,
            info_txt,
            parse_mode="Markdown",
            reply_markup=get_main_kb(user_id),
        )


# --- دکمه‌های شیشه‌ای دعوت‌نامه مدیر به کاربر و مسدودسازی گزارش‌ها ---
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("admin_invite_custom_")
    or call.data.startswith("admin_invite_default_")
)
def handle_admin_send_invite(call):
    uid = call.from_user.id
    if not is_admin(uid):
        return

    if call.data.startswith("admin_invite_custom_"):
        target_id = int(call.data.replace("admin_invite_custom_", ""))
        USER_CONTEXT[uid] = f"admin_writing_invite_msg_{target_id}"
        bot.answer_callback_query(call.id)
        bot.send_message(
            uid,
            "✍️ متن پیام اختصاصی خودت رو بنویس تا همراه با درخواست چت رسمی مدیریت برای کاربر ارسال بشه:",
            reply_markup=kb.back_only_keyboard(),
        )
        return

    if call.data.startswith("admin_invite_default_"):
        target_id = int(call.data.replace("admin_invite_default_", ""))
        bot.answer_callback_query(call.id, "✅ درخواست چت لوکس ارسال شد!")
        dispatch_luxury_admin_invite(uid, target_id, custom_note=None)


def dispatch_luxury_admin_invite(admin_id, target_id, custom_note=None):
    target = db.get_user(target_id)
    if not target:
        bot.send_message(admin_id, "❌ کاربر یافت نشد.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "✅ پذیرش دعوت و شروع گفتگو",
            callback_data=f"accept_admin_chat_{admin_id}",
        ),
        types.InlineKeyboardButton(
            "❌ رد درخواست",
            callback_data=f"reject_admin_chat_{admin_id}",
        ),
    )

    if custom_note:
        luxury_text = (
            "✨ <b>دعوت‌نامه ویژه از طرف مدیریت ربات</b> ✨\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "کاربر گرامی، یک درخواست گفتگوی اختصاصی از سوی <b>مدیریت</b> برای شما ثبت شده است.\n\n"
            f"💌 <b>پیام مدیر:</b>\n«{custom_note}»\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "در صورت تمایل به گفتگو، گزینه پذیرش را انتخاب نمایید 👇"
        )
    else:
        luxury_text = (
            "✨ <b>دعوت‌نامه ویژه از طرف مدیریت ربات</b> ✨\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "کاربر گرامی، <b>مدیریت</b> درخواست گفتگوی مستقیم با شما را دارند.\n"
            "این گفتگو در فضایی اختصاصی و محرمانه برقرار خواهد شد.\n"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "لطفاً وضعیت درخواست را از دکمه‌های زیر مشخص کنید 👇"
        )

    try:
        bot.send_message(
            target_id,
            luxury_text,
            parse_mode="HTML",
            reply_markup=markup,
            protect_content=True,
        )
        bot.send_message(
            admin_id,
            f"✅ دعوت‌نامه رسمی با موفقیت برای «{target.get('name')}» (/{target.get('custom_id')}) ارسال شد. منتظر پاسخ کاربر بمانید.",
            reply_markup=kb.admin_main_reply_kb(),
        )
    except Exception as e:
        bot.send_message(
            admin_id,
            f"⚠️ امکان ارسال پیام به این کاربر وجود نداشت (احتمالاً ربات را بلاک کرده است): {e}",
            reply_markup=kb.admin_main_reply_kb(),
        )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("accept_admin_chat_")
    or call.data.startswith("reject_admin_chat_")
)
def handle_user_admin_invite_response(call):
    uid = call.from_user.id
    user = db.get_user(uid)

    if call.data.startswith("reject_admin_chat_"):
        admin_id = int(call.data.replace("reject_admin_chat_", ""))
        try:
            bot.edit_message_text(
                "❌ درخواست گفتگوی مدیریت توسط شما رد شد.",
                call.message.chat.id,
                call.message.message_id,
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id, "درخواست رد شد.")
        try:
            bot.send_message(
                admin_id,
                f"❌ کاربر «{user.get('name') if user else uid}» (/{user.get('custom_id') if user else uid}) درخواست گفتگوی شما را رد کرد.",
            )
        except Exception:
            pass
        return

    if call.data.startswith("accept_admin_chat_"):
        admin_id = int(call.data.replace("accept_admin_chat_", ""))

        u_curr = db.get_user(uid)
        if u_curr and u_curr.get("status") == "chatting":
            old_p = db.disconnect_user(uid)
            if old_p:
                db.set_user_state(old_p, "main_menu")
                bot.send_message(
                    old_p,
                    "طرف مقابل مکالمه را پایان داد! 🚪",
                    reply_markup=get_main_kb(old_p),
                )

        a_curr = db.get_user(admin_id)
        if a_curr and a_curr.get("status") == "chatting":
            old_ap = db.disconnect_user(admin_id)
            if old_ap:
                db.set_user_state(old_ap, "main_menu")
                bot.send_message(
                    old_ap,
                    "طرف مقابل مکالمه را پایان داد! 🚪",
                    reply_markup=get_main_kb(old_ap),
                )

        db.connect_two_users_directly(uid, admin_id)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        bot.send_message(
            uid,
            "✨ گفتگو با مدیریت برقرار شد! می‌توانید پیام خود را ارسال کنید 👇",
            reply_markup=get_chat_kb(uid),
        )
        bot.send_message(
            admin_id,
            f"🎉 کاربر «{user.get('name') if user else uid}» (/{user.get('custom_id') if user else uid}) دعوت شما را پذیرفت و چت مستقیم برقرار شد! 👇",
            reply_markup=get_chat_kb(admin_id),
        )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("repban_")
    or call.data == "repdismiss"
)
def handle_report_admin_decision(call):
    uid = call.from_user.id
    if not is_admin(uid):
        return

    if call.data == "repdismiss":
        bot.answer_callback_query(call.id, "گزارش نادیده گرفته شد.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    if call.data.startswith("repban_"):
        target_id = int(call.data.replace("repban_", ""))
        db.add_or_update_user(target_id, is_banned=True)
        old_p = db.disconnect_user(target_id)
        if old_p:
            db.set_user_state(old_p, "main_menu")
            bot.send_message(
                old_p,
                "طرف مقابل به دلیل تخلف از چت خارج شد.",
                reply_markup=get_main_kb(old_p),
            )
        bot.answer_callback_query(call.id, "🚫 کاربر مسدود شد!")
        try:
            bot.edit_message_text(
                f"🚫 کاربر {target_id} توسط مدیریت مسدود شد.",
                call.message.chat.id,
                call.message.message_id,
            )
        except Exception:
            pass


# --- استارت، ورود و باز کردن لینک‌های عکس و ویدیو ---
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = message.chat.id
    parts = (message.text or "").split()

    if len(parts) > 1 and parts[1].startswith("media_") and is_admin(user_id):
        try:
            log_id = int(parts[1].replace("media_", ""))
            log_row = db.get_chat_log_by_id(log_id)
            if log_row:
                send_single_logged_media_to_admin(user_id, log_row)
            else:
                bot.send_message(user_id, "❌ فایل پیدا نشد.")
        except Exception:
            pass
        return

    if enforce_channel_membership(user_id):
        return

    launch_user_session(user_id)


# ==================== پنل مدیریت ۱۰۰٪ کیبوردی (/admin) ====================

@bot.message_handler(regexp=r"^/admin(@[a-zA-Z0-9_]+)?$")
@bot.message_handler(
    func=lambda msg: msg.text in ["🎛 پنل مدیریت", "🔙 بازگشت به پنل مدیریت"]
)
def open_admin_panel(message):
    uid = message.chat.id
    if not is_admin(uid):
        bot.send_message(uid, "متوجه نشدم")
        return
    USER_CONTEXT.pop(uid, None)
    bot.send_message(
        uid,
        "🎛 پنل مدیریت ربات (از دکمه‌های کیبورد پایین انتخاب کنید):",
        reply_markup=kb.admin_main_reply_kb(),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id) and msg.text == "🏠 خروج از پنل مدیریت"
)
def exit_admin_panel(message):
    uid = message.chat.id
    USER_CONTEXT.pop(uid, None)
    db.set_user_state(uid, "main_menu")
    send_main_menu_with_link(uid)


# --- بخش جدید: چت با کاربران ---
@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text in ["💬 چت با کاربران", "🔙 بازگشت به انتخاب جنسیت"]
)
def admin_chat_select_gender(message):
    uid = message.chat.id
    USER_CONTEXT[uid] = "admin_chat_choosing_gender"
    bot.send_message(
        uid,
        "💬 می‌خواهید لیست کدام کاربران را ببینید؟\nدختر یا پسر را انتخاب کنید:",
        reply_markup=kb.admin_chat_gender_kb(),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text in ["👧 کاربران دختر", "👦 کاربران پسر"]
)
def admin_chat_list_by_gender(message):
    uid = message.chat.id
    gender = "دختر" if "دختر" in message.text else "پسر"
    users = db.get_users_by_gender_for_admin(gender, limit=100)

    if not users:
        bot.send_message(
            uid,
            f"فعلاً هیچ کاربر «{gender}» ثبت‌نام نکرده است.",
            reply_markup=kb.admin_chat_gender_kb(),
        )
        return

    bot.send_message(
        uid,
        f"📋 لیست کاربران {gender} ({len(users)} نفر):\nروی آیدی هر کاربر در کیبورد پایین بزنید تا پروفایلش باز شود:",
        reply_markup=kb.admin_gender_users_kb(users),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text
    and msg.text.startswith("🆔 ")
    and "|" in msg.text
)
def admin_view_user_profile_to_chat(message):
    uid = message.chat.id
    cid = message.text.split("|")[-1].strip()
    target = db.get_user_by_custom_id(cid)
    if not target:
        bot.send_message(uid, "❌ کاربر پیدا نشد!")
        return

    t_uid = target["user_id"]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            "✍️ ارسال درخواست چت با پیام دلخواه مدیر",
            callback_data=f"admin_invite_custom_{t_uid}",
        ),
        types.InlineKeyboardButton(
            "✨ ارسال درخواست چت با پیام پیش‌فرض لوکس",
            callback_data=f"admin_invite_default_{t_uid}",
        ),
    )

    caption = format_profile_caption(target, "👤 پروفایل کامل کاربر:")
    send_profile_card_with_photo(uid, target, caption, reply_markup=markup)


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and str(USER_CONTEXT.get(msg.chat.id, "")).startswith(
        "admin_writing_invite_msg_"
    )
    and msg.text != "🔙 بازگشت"
)
def admin_receive_custom_invite_message(message):
    uid = message.chat.id
    ctx = USER_CONTEXT.pop(uid, "")
    target_id = int(ctx.replace("admin_writing_invite_msg_", ""))
    custom_note = (message.text or "").strip()
    dispatch_luxury_admin_invite(uid, target_id, custom_note=custom_note)


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id) and msg.text == "📊 آمار زنده ربات"
)
def admin_stats_button(message):
    uid = message.chat.id
    st = db.get_bot_stats()
    text = (
        f"📊 آمار لحظه‌ای ربات:\n\n"
        f"👥 کل کاربران: {st['total_users']} نفر\n"
        f"🟢 مشغول چت الان: {st['chatting_users']} نفر\n"
        f"⏳ در صف انتظار: {st['waiting_users']} نفر\n"
        f"🚫 مسدود شده‌ها: {st['banned_users']} نفر\n"
        f"💬 کل پیام‌ها: {st['total_msgs']}\n"
        f"🎬 کل عکس و ویدیوها: {st['total_media']}"
    )
    bot.send_message(uid, text, reply_markup=kb.admin_main_reply_kb())


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text in ["👥 لیست تمام کاربران", "🔙 بازگشت به لیست کاربران"]
)
def admin_show_all_users(message):
    uid = message.chat.id
    users = db.get_all_users_for_admin(limit=100)
    USER_CONTEXT[uid] = "admin_selecting_user"
    bot.send_message(
        uid,
        f"👥 لیست تمام کاربران ({len(users)} نفر):\nروی هر کاربر در کیبورد پایین بزنید تا ببینید با چه کسانی چت کرده است:",
        reply_markup=kb.admin_users_reply_kb(users),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text
    and msg.text.startswith("👤 ")
    and "|" in msg.text
)
def admin_select_user_from_kb(message):
    uid = message.chat.id
    cid = message.text.split("|")[-1].strip()
    target = db.get_user_by_custom_id(cid)
    if not target:
        bot.send_message(uid, "❌ کاربر پیدا نشد!")
        return

    USER_CONTEXT[f"admin_selected_u1_{uid}"] = target["user_id"]
    partners = db.get_user_chat_partners(target["user_id"])

    if not partners:
        bot.send_message(
            uid,
            f"👤 کاربر «{target.get('name')}» (/{target.get('custom_id')}) تا به حال با هیچ‌کس چت نکرده است.",
        )
        return

    bot.send_message(
        uid,
        f"👤 کاربر: {target.get('name')} (/{target.get('custom_id')})\n"
        f"👇 با این {len(partners)} نفر چت کرده است (روی هر نفر در کیبورد پایین بزنید تا چت و عکس‌هایشان باز شود):",
        reply_markup=kb.admin_partners_reply_kb(partners),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text
    and msg.text.startswith("💬 ")
    and "|" in msg.text
)
def admin_select_partner_from_kb(message):
    uid = message.chat.id
    u1_id = USER_CONTEXT.get(f"admin_selected_u1_{uid}")
    if not u1_id:
        bot.send_message(
            uid,
            "ابتدا از لیست کاربران یک نفر را انتخاب کنید.",
            reply_markup=kb.admin_main_reply_kb(),
        )
        return

    cid2 = message.text.split("|")[-1].strip()
    u2 = db.get_user_by_custom_id(cid2)
    u2_id = u2["user_id"] if u2 else int(cid2)

    u1_info = db.get_user(u1_id) or {"user_id": u1_id, "name": str(u1_id)}
    u2_info = db.get_user(u2_id) or {"user_id": u2_id, "name": str(u2_id)}

    msgs = db.get_full_conversation(u1_id, u2_id, limit=80)
    if not msgs:
        bot.send_message(uid, "هیچ پیامی بین این دو نفر یافت نشد.")
        return

    u1_name = u1_info.get("name") or "کاربر ۱"
    u2_name = u2_info.get("name") or "کاربر ۲"

    first_dt = msgs[-1].get("created_at")
    date_str = first_dt.strftime("%m/%d") if first_dt else "-"
    time_str = first_dt.strftime("%H:%M") if first_dt else "-"

    lines = [
        "تاریخچه چت",
        f"{u1_name}->🔴 و {u2_name}->🔵",
        f"تاریخ : {date_str}",
        f"ساعت : {time_str}",
    ]

    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            BOT_USERNAME = bot.get_me().username
        except Exception:
            BOT_USERNAME = ""

    for m in msgs:
        dot = "🔴" if m["sender_id"] == u1_id else "🔵"
        ctype = m.get("content_type", "text")
        log_id = m["id"]
        deep_link = f"https://t.me/{BOT_USERNAME}?start=media_{log_id}"

        if ctype == "text":
            safe_txt = (
                (m.get("content") or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            lines.append(f"{dot}: {safe_txt}")
        elif ctype == "photo":
            if m.get("is_timed"):
                lines.append(f'{dot}: <a href="{deep_link}">(عکس تایم دار)</a>')
            else:
                lines.append(f'{dot}: <a href="{deep_link}">(عکس)</a>')
        elif ctype == "video":
            lines.append(f'{dot}: <a href="{deep_link}">(ویدیو)</a>')
        elif ctype == "voice":
            lines.append(f'{dot}: <a href="{deep_link}">(ویس)</a>')
        elif ctype == "audio":
            lines.append(f'{dot}: <a href="{deep_link}">(موزیک)</a>')
        elif ctype == "document":
            lines.append(f'{dot}: <a href="{deep_link}">(فایل)</a>')

    final_text = "\n\n".join(lines)
    for i in range(0, len(final_text), 3800):
        bot.send_message(
            uid,
            final_text[i : i + 3800],
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text in ["📢 پیام همگانی", "🚫 مسدود کردن کاربر", "🔓 رفع مسدودی کاربر"]
)
def admin_action_prompts(message):
    uid = message.chat.id
    if message.text == "📢 پیام همگانی":
        USER_CONTEXT[uid] = "admin_waiting_broadcast"
        bot.send_message(
            uid, "متن پیام همگانی را بفرستید:", reply_markup=kb.back_only_keyboard()
        )
    elif message.text == "🚫 مسدود کردن کاربر":
        USER_CONTEXT[uid] = "admin_waiting_ban"
        bot.send_message(
            uid,
            "آیدی اختصاصی (مثلاً user_xxxx) یا آیدی عددی کاربر را برای مسدود کردن بفرستید:",
            reply_markup=kb.back_only_keyboard(),
        )
    elif message.text == "🔓 رفع مسدودی کاربر":
        USER_CONTEXT[uid] = "admin_waiting_unban"
        bot.send_message(
            uid,
            "آیدی اختصاصی (مثلاً user_xxxx) یا آیدی عددی کاربر را برای رفع مسدودی بفرستید:",
            reply_markup=kb.back_only_keyboard(),
        )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and USER_CONTEXT.get(msg.chat.id)
    in ["admin_waiting_broadcast", "admin_waiting_ban", "admin_waiting_unban"]
    and msg.text != "🔙 بازگشت"
)
def handle_admin_text_actions(message):
    uid = message.chat.id
    mode = USER_CONTEXT.pop(uid, None)
    txt = (message.text or "").strip()

    if mode == "admin_waiting_ban":
        target = db.get_user_by_custom_id(txt)
        if not target:
            bot.send_message(
                uid, "❌ کاربر یافت نشد.", reply_markup=kb.admin_main_reply_kb()
            )
            return
        db.add_or_update_user(target["user_id"], is_banned=True)
        db.disconnect_user(target["user_id"])
        bot.send_message(
            uid,
            f"🚫 کاربر {target.get('name')} مسدود شد.",
            reply_markup=kb.admin_main_reply_kb(),
        )

    elif mode == "admin_waiting_unban":
        target = db.get_user_by_custom_id(txt)
        if not target:
            bot.send_message(
                uid, "❌ کاربر یافت نشد.", reply_markup=kb.admin_main_reply_kb()
            )
            return
        db.add_or_update_user(target["user_id"], is_banned=False)
        bot.send_message(
            uid,
            f"🔓 کاربر {target.get('name')} رفع مسدودی شد.",
            reply_markup=kb.admin_main_reply_kb(),
        )

    elif mode == "admin_waiting_broadcast":
        uids = db.get_all_user_ids()
        sent = 0
        for u in uids:
            try:
                bot.send_message(u, f"📢 پیام مدیریت:\n\n{txt}")
                sent += 1
            except Exception:
                pass
        bot.send_message(
            uid,
            f"✅ پیام همگانی برای {sent} نفر ارسال شد.",
            reply_markup=kb.admin_main_reply_kb(),
        )


# --- دکمه بازگشت پله‌به‌پله ---
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت")
def handle_back_button(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    ctx = str(USER_CONTEXT.pop(user_id, "") or "")

    if is_admin(user_id) and (
        ctx
        in [
            "admin_waiting_broadcast",
            "admin_waiting_ban",
            "admin_waiting_unban",
        ]
        or ctx.startswith("admin_writing_invite_msg_")
    ):
        bot.send_message(
            user_id, "🎛 پنل مدیریت:", reply_markup=kb.admin_main_reply_kb()
        )
        return

    user = db.get_user(user_id)
    if not user:
        return

    if enforce_registration_step(user_id, user):
        return

    curr = user.get("state", "main_menu")

    if curr in ["profile_menu", "connect_filter"]:
        db.set_user_state(user_id, "main_menu")
        send_main_menu_with_link(user_id)

    elif curr == "select_specific_age":
        db.set_user_state(user_id, "select_age_range")
        bot.send_message(
            user_id,
            "بازه سنی خودت رو انتخاب کن:",
            reply_markup=kb.age_ranges_keyboard(),
        )

    elif curr in [
        "select_age_range",
        "select_province",
        "select_photo_type",
        "edit_gender",
    ]:
        db.set_user_state(user_id, "profile_menu")
        bot.send_message(
            user_id, "منوی پروفایل:", reply_markup=kb.profile_menu_keyboard()
        )

    elif curr.startswith("select_city_"):
        db.set_user_state(user_id, "select_province")
        bot.send_message(
            user_id,
            "استان خود را انتخاب کنید:",
            reply_markup=kb.provinces_keyboard(),
        )

    else:
        db.set_user_state(user_id, "main_menu")
        send_main_menu_with_link(user_id)


# --- ثبت نام اجباری (مرحله ۱: وارد کردن نام) ---
@bot.message_handler(
    func=lambda msg: USER_CONTEXT.get(msg.chat.id) == "reg_waiting_name"
    and msg.text
    and not msg.text.startswith("/")
)
def handle_registration_name(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    raw_name = message.text.strip()
    if contains_links_or_usernames(raw_name) or len(raw_name) < 2:
        bot.send_message(
            user_id,
            "⚠️ لطفاً یک نام معتبر (بدون آیدی و لینک و حداقل ۲ حرف) وارد کن:",
        )
        return

    db.add_or_update_user(user_id, name=raw_name[:30])
    USER_CONTEXT.pop(user_id, None)
    user = db.get_user(user_id)
    enforce_registration_step(user_id, user)


# --- ثبت‌نام و ویرایش مشخصات ---
@bot.message_handler(func=lambda msg: msg.text in ["پسر 👦", "دختر 👧"])
def set_gender(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    g = "پسر" if "پسر" in message.text else "دختر"
    db.add_or_update_user(user_id, gender=g)
    user = db.get_user(user_id)

    if is_profile_complete(user):
        db.set_user_state(user_id, "profile_menu")
        bot.send_message(
            user_id,
            f"✅ جنسیت شما به «{g}» تغییر یافت.",
            reply_markup=kb.profile_menu_keyboard(),
        )
    else:
        enforce_registration_step(user_id, user)


@bot.message_handler(
    func=lambda msg: msg.text
    in [
        "۹ تا ۱۳",
        "۱۴ تا ۱۷",
        "۱۸ تا ۲۲",
        "۲۳ تا ۲۸",
        "۲۹ تا ۳۵",
        "۳۶ تا ۵۰",
        "۵۱ تا ۶۰",
    ]
)
def set_age_range(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    mapping = {
        "۹ تا ۱۳": (9, 13),
        "۱۴ تا ۱۷": (14, 17),
        "۱۸ تا ۲۲": (18, 22),
        "۲۳ تا ۲۸": (23, 28),
        "۲۹ تا ۳۵": (29, 35),
        "۳۶ تا ۵۰": (36, 50),
        "۵۱ تا ۶۰": (51, 60),
    }
    s, e = mapping[message.text]
    allow_b = is_profile_complete(user)
    db.set_user_state(user_id, "select_specific_age")
    bot.send_message(
        user_id,
        "سن دقیق خودت رو انتخاب کن:",
        reply_markup=kb.specific_ages_keyboard(s, e, allow_back=allow_b),
    )


@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith("سن "))
def set_exact_age(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    try:
        val = int(message.text.replace("سن ", "").strip())
        db.add_or_update_user(user_id, age=val)
        user = db.get_user(user_id)
        if is_profile_complete(user):
            db.set_user_state(user_id, "profile_menu")
            bot.send_message(
                user_id,
                f"✅ سن شما به {val} سال تغییر کرد.",
                reply_markup=kb.profile_menu_keyboard(),
            )
        else:
            enforce_registration_step(user_id, user)
    except ValueError:
        pass


@bot.message_handler(
    func=lambda msg: msg.text and msg.text.strip() in kb.IRAN_PROVINCES
)
def set_province(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    prov = message.text.strip()
    db.add_or_update_user(user_id, province=prov)
    user = db.get_user(user_id)
    allow_b = is_profile_complete(user)
    db.set_user_state(user_id, f"select_city_{prov}")
    bot.send_message(
        user_id,
        f"شهر خودت در {prov} رو انتخاب کن:",
        reply_markup=kb.cities_keyboard(prov, allow_back=allow_b),
    )


@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith("شهر "))
def set_city(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    city_name = message.text.replace("شهر ", "").strip()
    db.add_or_update_user(user_id, city=city_name)
    user = db.get_user(user_id)

    if user and user.get("state") == "profile_menu":
        db.set_user_state(user_id, "profile_menu")
        bot.send_message(
            user_id,
            f"✅ موقعیت مکانی شما به {user.get('province')} ({city_name}) تغییر یافت.",
            reply_markup=kb.profile_menu_keyboard(),
        )
        return

    db.set_user_state(user_id, "select_photo_type")
    bot.send_message(
        user_id,
        f"✅ موقعیت مکانی ثبت شد ({city_name}).\nحالا وضعیت عکس پروفایلت رو انتخاب کن:",
        reply_markup=kb.photo_choice_keyboard(allow_back=False),
    )


@bot.message_handler(
    func=lambda msg: msg.text
    in [
        "📸 استفاده از عکس تلگرامم",
        "🚫 بدون عکس (آواتار پیش‌فرض)",
        "🖼 ارسال یک عکس جدید",
    ]
)
def set_photo_preference(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    t = message.text

    if t == "📸 استفاده از عکس تلگرامم":
        try:
            photos = bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                fid = photos.photos[0][-1].file_id
                db.add_or_update_user(user_id, photo_file_id=fid)
                bot.send_message(user_id, "✅ عکس پروفایل تلگرامت تنظیم شد!")
            else:
                bot.send_message(
                    user_id,
                    "⚠️ عکس تلگرام شما مخفی است یا عکسی ندارید؛ آواتار پیش‌فرض فعال شد.",
                )
        except Exception:
            bot.send_message(user_id, "آواتار پیش‌فرض فعال شد.")

    elif t == "🚫 بدون عکس (آواتار پیش‌فرض)":
        db.add_or_update_user(user_id, photo_file_id="NO_PHOTO")
        bot.send_message(
            user_id, "✅ آواتار پیش‌فرض برای پروفایل شما تنظیم شد."
        )

    elif t == "🖼 ارسال یک عکس جدید":
        USER_CONTEXT[user_id] = "waiting_for_avatar"
        user = db.get_user(user_id)
        kb_back = (
            kb.back_only_keyboard()
            if is_profile_complete(user)
            else types.ReplyKeyboardRemove()
        )
        bot.send_message(
            user_id,
            "📸 لطفاً عکس دلخواهت رو همین‌جا بفرست:",
            reply_markup=kb_back,
        )
        return

    db.set_user_state(user_id, "main_menu")
    user = db.get_user(user_id)
    send_profile_card_with_photo(
        user_id,
        user,
        format_profile_caption(user, "🎉 پروفایل شما آماده شد:"),
        reply_markup=get_main_kb(user_id),
    )
    send_main_menu_with_link(user_id)


@bot.message_handler(
    content_types=["photo"],
    func=lambda msg: USER_CONTEXT.get(msg.chat.id) == "waiting_for_avatar",
)
def receive_custom_avatar(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    fid = message.photo[-1].file_id
    db.add_or_update_user(user_id, photo_file_id=fid)
    USER_CONTEXT.pop(user_id, None)
    db.set_user_state(user_id, "main_menu")
    user = db.get_user(user_id)
    send_profile_card_with_photo(
        user_id,
        user,
        format_profile_caption(user, "✅ عکس پروفایل شما ذخیره شد:"),
        reply_markup=get_main_kb(user_id),
    )
    send_main_menu_with_link(user_id)


# --- بخش پروفایل من ---
@bot.message_handler(func=lambda msg: msg.text == "👤 پروفایل من")
def show_my_profile(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if enforce_registration_step(user_id, user):
        return

    db.set_user_state(user_id, "profile_menu")
    caption = format_profile_caption(user, "👤 مشخصات حساب شما:")
    send_profile_card_with_photo(
        user_id, user, caption, reply_markup=kb.profile_menu_keyboard()
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر نام")
def edit_name_prompt(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    USER_CONTEXT[user_id] = "waiting_for_name"
    bot.send_message(
        user_id,
        "نام یا لقب جدیدت رو بنویس:",
        reply_markup=kb.back_only_keyboard(),
    )


@bot.message_handler(
    func=lambda msg: USER_CONTEXT.get(msg.chat.id) == "waiting_for_name"
    and msg.text != "🔙 بازگشت"
)
def save_text_profile_fields(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    if contains_links_or_usernames(message.text) or len(message.text.strip()) < 2:
        bot.send_message(
            user_id, "⚠️ نام نامعتبر است (قرار دادن آیدی و لینک مجاز نیست)!"
        )
        return

    USER_CONTEXT.pop(user_id, None)
    db.add_or_update_user(user_id, name=message.text.strip()[:30])
    show_my_profile(message)


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر جنسیت")
def edit_gender_prompt(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    db.set_user_state(user_id, "edit_gender")
    bot.send_message(
        user_id, "جنسیت خود را انتخاب کنید:", reply_markup=kb.gender_keyboard()
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر سن")
def edit_age_prompt(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    db.set_user_state(user_id, "select_age_range")
    bot.send_message(
        user_id,
        "بازه سنی خودت رو انتخاب کن:",
        reply_markup=kb.age_ranges_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر شهر/استان")
def edit_province_prompt(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    db.set_user_state(user_id, "select_province")
    bot.send_message(
        user_id,
        "استان خودت رو انتخاب کن:",
        reply_markup=kb.provinces_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "📸 تغییر عکس")
def edit_photo_prompt(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return
    db.set_user_state(user_id, "select_photo_type")
    bot.send_message(
        user_id,
        "وضعیت عکس پروفایل رو انتخاب کن:",
        reply_markup=kb.photo_choice_keyboard(),
    )


# --- اتصال به ناشناس (با محدودیت ۵ جستجوی دختر در هر ساعت) ---
@bot.message_handler(func=lambda msg: msg.text == "⚡ به یه ناشناس وصلم کن!")
def open_connect_filters(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if enforce_registration_step(user_id, user):
        return

    db.set_user_state(user_id, "connect_filter")
    bot.send_message(
        user_id,
        "⚡ کیو پیدا کنم برات؟ از کیبورد پایین انتخاب کن:",
        reply_markup=kb.connect_filter_keyboard(),
    )


@bot.message_handler(
    func=lambda msg: msg.text
    in [
        "🎲 جستجوی شانسی",
        "👧 جستجوی دختر",
        "👦 جستجوی پسر",
        "⏭ هم‌صحبت بعدی",
    ]
)
def start_filtered_search(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if enforce_registration_step(user_id, user):
        return

    f_map = {
        "🎲 جستجوی شانسی": "any",
        "👧 جستجوی دختر": "girl",
        "👦 جستجوی پسر": "boy",
        "⏭ هم‌صحبت بعدی": user.get("search_filter", "any"),
    }
    chosen_filter = f_map.get(message.text, "any")

    quota_note = ""
    if chosen_filter == "girl":
        allowed, rem_left, rem_mins = db.check_and_use_girl_search(
            user_id, max_per_hour=5
        )
        if not allowed:
            bot.send_message(
                user_id,
                f"⏳ سهمیه ۵ بار جستجوی دختر در این ساعت تمام شده است!\n"
                f"🔄 حدود **{rem_mins} دقیقه** دیگر سهمیه شما دوباره تمدید می‌شود.\n"
                f"فعلاً می‌تونی از «🎲 جستجوی شانسی» استفاده کنی.",
                parse_mode="Markdown",
                reply_markup=kb.connect_filter_keyboard(),
            )
            return
        quota_note = f"\n(سهمیه باقی‌مانده جستجوی دختر در این ساعت: {rem_left} از ۵)"

    if user["status"] == "chatting":
        old_partner = db.disconnect_user(user_id)
        if old_partner:
            db.set_user_state(old_partner, "main_menu")
            send_main_menu_with_link(
                old_partner, "طرف مقابل مکالمه رو قطع کرد و رفت نفر بعدی! 🚪"
            )

    partner_id = db.find_match(user_id, chosen_filter)

    if partner_id:
        protected = is_chat_protected(user_id, partner_id)
        priv_banner = (
            "\n🔒 (چت خصوصی فعال است: اسکرین‌شات و فوروارد قفل شد)"
            if protected
            else "\n🔓 (چت عادی است؛ برای قفل اسکرین‌شات دکمه چت خصوصی را بزنید)"
        )
        msg_text = "🎉 هم‌صحبت پیدا شد و وصل شدید! سلام کن 👋" + priv_banner
        bot.send_message(
            user_id,
            msg_text + quota_note,
            reply_markup=get_chat_kb(user_id),
        )
        bot.send_message(
            partner_id,
            msg_text,
            reply_markup=get_chat_kb(partner_id),
        )
    else:
        bot.send_message(
            user_id,
            "🔍 در حال جستجوی هم‌صحبت... منتظر بمونید." + quota_note,
            reply_markup=kb.waiting_keyboard(),
        )


# --- پایان مکالمه با تایید دومرحله‌ای («بله، مطمئنم») ---
@bot.message_handler(func=lambda msg: msg.text == "❌ پایان مکالمه")
def ask_confirm_stop_chat(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting":
        db.set_user_state(user_id, "main_menu")
        send_main_menu_with_link(user_id)
        return

    bot.send_message(
        user_id,
        "⚠️ مطمئنی که می‌خوای مکالمه رو تموم کنی؟",
        reply_markup=kb.confirm_end_chat_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "🔙 انصراف و ادامه چت")
def cancel_stop_chat(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if user and user.get("status") == "chatting":
        bot.send_message(
            user_id,
            "✅ عالیه! به مکالمه ادامه بده 👇",
            reply_markup=get_chat_kb(user_id),
        )
    else:
        db.set_user_state(user_id, "main_menu")
        send_main_menu_with_link(user_id)


@bot.message_handler(
    func=lambda msg: msg.text in ["✅ بله، مطمئنم", "⛔ انصراف از جستجو"]
)
def stop_chat_confirmed(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    USER_CONTEXT.pop(user_id, None)
    partner_id = db.disconnect_user(user_id)
    db.set_user_state(user_id, "main_menu")
    send_main_menu_with_link(user_id, "مکالمه پایان یافت. 👋")
    if partner_id:
        USER_CONTEXT.pop(partner_id, None)
        db.set_user_state(partner_id, "main_menu")
        send_main_menu_with_link(
            partner_id, "طرف مقابل مکالمه رو ترک کرد! 🚪"
        )


# --- امکانات داخل چت: مشاهده پروفایل، اشتراک آیدی، عکس تایم‌دار با زمان دلخواه ---
@bot.message_handler(func=lambda msg: msg.text == "👤 مشاهده پروفایل")
def view_partner_profile(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner = db.get_user(user["partner_id"])
    if not partner:
        return

    try:
        bot.send_message(
            partner["user_id"], "🔔 هم‌صحبت شما همین الان پروفایل شما را مشاهده کرد!"
        )
    except Exception:
        pass

    protected = is_chat_protected(user_id, partner["user_id"])
    caption = format_profile_caption(partner, "👤 پروفایل هم‌صحبت شما:")
    send_profile_card_with_photo(user_id, partner, caption, protect=protected)


@bot.message_handler(func=lambda msg: msg.text == "🔗 اشتراک‌گذاری آیدی")
def request_share_id(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner_id = user["partner_id"]
    USER_CONTEXT[f"share_{user_id}_{partner_id}"] = True

    if USER_CONTEXT.get(f"share_{partner_id}_{user_id}"):
        u1_username = message.from_user.username
        try:
            p_chat = bot.get_chat(partner_id)
            u2_username = p_chat.username
        except Exception:
            u2_username = None

        if u1_username and u2_username:
            bot.send_message(
                user_id, f"🎉 آیدی هم‌صحبت شما:\n@{u2_username}"
            )
            bot.send_message(
                partner_id, f"🎉 آیدی هم‌صحبت شما:\n@{u1_username}"
            )
        elif u1_username and not u2_username:
            bot.send_message(
                user_id,
                "طرف مقابل آیدی تلگرام ندارد، اما آیدی شما برایش ارسال شد تا پیام دهد.",
            )
            bot.send_message(
                partner_id,
                f"🎉 شما آیدی ندارید، اما آیدی طرف مقابل دریافت شد:\n@{u1_username}",
            )
        elif not u1_username and u2_username:
            bot.send_message(
                user_id,
                f"🎉 شما آیدی ندارید، اما آیدی طرف مقابل دریافت شد:\n@{u2_username}",
            )
            bot.send_message(
                partner_id,
                "طرف مقابل آیدی تلگرام ندارد، اما آیدی شما برایش ارسال شد تا پیام دهد.",
            )
        else:
            bot.send_message(
                user_id,
                f"🔗 لینک مستقیم اکانت طرف مقابل:\ntg://user?id={partner_id}",
            )
            bot.send_message(
                partner_id,
                f"🔗 لینک مستقیم اکانت طرف مقابل:\ntg://user?id={user_id}",
            )
    else:
        bot.send_message(
            user_id, "⏳ درخواست اشتراک آیدی ارسال شد. منتظر تایید طرف مقابل باشید."
        )
        bot.send_message(
            partner_id,
            "🔔 هم‌صحبت شما درخواست تبادل آیدی تلگرام داده است. در صورت موافقت روی دکمه «🔗 اشتراک‌گذاری آیدی» بزنید.",
        )


@bot.message_handler(func=lambda msg: msg.text == "💣 ارسال عکس تایم‌دار")
def prompt_timed_photo_duration(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting":
        return
    USER_CONTEXT[user_id] = "choosing_timed_photo_seconds"
    bot.send_message(
        user_id,
        "⏱ مدت زمان نمایش عکس تایم‌دار را انتخاب کن (بعد از اتمام زمان از صفحه هر دو نفر پاک می‌شود):",
        reply_markup=kb.timed_photo_duration_keyboard(),
    )


@bot.message_handler(
    func=lambda msg: msg.text
    in ["⏱ ۵ ثانیه", "⏱ ۱۰ ثانیه", "⏱ ۱۵ ثانیه", "⏱ ۳۰ ثانیه", "⏱ ۶۰ ثانیه"]
)
def set_timed_photo_duration(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    sec_map = {
        "⏱ ۵ ثانیه": 5,
        "⏱ ۱۰ ثانیه": 10,
        "⏱ ۱۵ ثانیه": 15,
        "⏱ ۳۰ ثانیه": 30,
        "⏱ ۶۰ ثانیه": 60,
    }
    chosen_sec = sec_map.get(message.text, 10)
    USER_CONTEXT[user_id] = f"waiting_for_timed_photo_{chosen_sec}"
    bot.send_message(
        user_id,
        f"💣 عالی! حالا عکس خودت رو بفرست تا به مدت **{chosen_sec} ثانیه** (ضداسکرین‌شات و محوشونده) ارسال بشه:",
        parse_mode="Markdown",
        reply_markup=get_chat_kb(user_id),
    )


@bot.message_handler(func=lambda msg: msg.text == "🔙 انصراف از عکس تایم‌دار")
def cancel_timed_photo(message):
    user_id = message.chat.id
    USER_CONTEXT.pop(user_id, None)
    bot.send_message(
        user_id,
        "ارسال عکس تایم‌دار لغو شد.",
        reply_markup=get_chat_kb(user_id),
    )


def delete_timed_messages_both_sides(
    sender_chat_id,
    sender_msg_id,
    receiver_chat_id,
    receiver_msg_id,
    notice_msg_id=None,
    delay=10,
):
    time.sleep(delay)
    for cid, mid in [
        (receiver_chat_id, receiver_msg_id),
        (sender_chat_id, sender_msg_id),
        (sender_chat_id, notice_msg_id),
    ]:
        if cid and mid:
            try:
                bot.delete_message(cid, mid)
            except Exception:
                pass


# --- گزارش تخلف (ارسال هشدار مسدودسازی به همه مدیران پس از رسیدن به ۴ گزارش) ---
@bot.message_handler(func=lambda msg: msg.text == "⚠️ گزارش تخلف")
def report_partner(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner_id = user["partner_id"]
    partner = db.get_user(partner_id)

    is_new, total_reports = db.add_user_report(user_id, partner_id)
    if not is_new:
        bot.send_message(
            user_id, "⚠️ شما قبلاً این کاربر را گزارش داده‌اید."
        )
        return

    bot.send_message(
        user_id, "✅ گزارش تخلف شما ثبت شد و در سیستم بررسی می‌شود."
    )

    admin_list = get_admin_ids()
    if admin_list and total_reports >= 4:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "🚫 مسدودسازی کاربر", callback_data=f"repban_{partner_id}"
            ),
            types.InlineKeyboardButton(
                "❌ نادیده گرفتن", callback_data="repdismiss"
            ),
        )
        report_text = (
            f"🚨 <b>هشدار حدنصاب گزارش تخلف!</b>\n"
            f"کاربر «{partner.get('name') if partner else '-'}» (/{partner.get('custom_id') if partner else partner_id}) "
            f"تاکنون توسط <b>{total_reports} نفر</b> گزارش شده است!\n\n"
            f"آیا مایل به مسدودسازی این کاربر هستید؟"
        )
        for aid in admin_list:
            try:
                bot.send_message(
                    aid, report_text, parse_mode="HTML", reply_markup=markup
                )
            except Exception:
                pass


# --- موتور هدایت پیام‌های چت (با اعمال قفل اسکرین‌شات بر اساس وضعیت چت خصوصی) ---
@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "voice",
        "video",
        "audio",
        "document",
        "sticker",
    ]
)
def relay_all_chat_messages(message):
    user_id = message.chat.id
    if enforce_channel_membership(user_id):
        return

    user = db.get_user(user_id)
    if enforce_registration_step(user_id, user):
        return

    if user.get("status") != "chatting" or not user.get("partner_id"):
        bot.send_message(user_id, "متوجه نشدم")
        return

    partner_id = user["partner_id"]
    protected = is_chat_protected(user_id, partner_id)

    if message.content_type == "sticker":
        bot.send_message(
            user_id, "⚠️ ارسال استیکر در محیط چت ناشناس ممنوع است!"
        )
        return

    if message.content_type == "text":
        if contains_links_or_usernames(message.text):
            bot.send_message(
                user_id,
                "⚠️ ارسال آیدی و لینک مجاز نیست! از دکمه «🔗 اشتراک‌گذاری آیدی» استفاده کنید.",
            )
            return
        db.log_chat_message(user_id, partner_id, "text", message.text)
        bot.send_message(partner_id, message.text, protect_content=protected)
        return

    if message.content_type == "photo":
        fid = message.photo[-1].file_id
        cap = message.caption or ""
        if contains_links_or_usernames(cap):
            bot.send_message(user_id, "⚠️ ارسال آیدی و لینک در کپشن مجاز نیست!")
            return

        ctx_str = str(USER_CONTEXT.get(user_id, ""))
        if ctx_str.startswith("waiting_for_timed_photo_"):
            USER_CONTEXT.pop(user_id, None)
            try:
                delay_sec = int(ctx_str.replace("waiting_for_timed_photo_", ""))
            except ValueError:
                delay_sec = 10

            db.log_chat_message(
                user_id, partner_id, "photo", fid, caption=cap, is_timed=True
            )
            sent_msg = bot.send_photo(
                partner_id,
                fid,
                caption=f"💣 عکس تایم‌دار محافظت‌شده ({delay_sec} ثانیه دیگر خودکار حذف می‌شود)\n"
                + cap,
                has_spoiler=True,
                protect_content=True,
            )
            notice = bot.send_message(
                user_id,
                f"✅ عکس تایم‌دار ارسال شد ({delay_sec} ثانیه بعد از صفحه هر دو نفر پاک می‌شود).",
            )
            threading.Thread(
                target=delete_timed_messages_both_sides,
                args=(
                    user_id,
                    message.message_id,
                    partner_id,
                    sent_msg.message_id,
                    notice.message_id,
                    delay_sec,
                ),
                daemon=True,
            ).start()
            return

        db.log_chat_message(
            user_id, partner_id, "photo", fid, caption=cap, is_timed=False
        )
        bot.send_photo(partner_id, fid, caption=cap, protect_content=protected)
        return

    if message.content_type == "voice":
        db.log_chat_message(user_id, partner_id, "voice", message.voice.file_id)
        bot.send_voice(
            partner_id, message.voice.file_id, protect_content=protected
        )
    elif message.content_type == "video":
        db.log_chat_message(
            user_id,
            partner_id,
            "video",
            message.video.file_id,
            caption=message.caption,
        )
        bot.send_video(
            partner_id,
            message.video.file_id,
            caption=message.caption or "",
            protect_content=protected,
        )
    elif message.content_type == "audio":
        db.log_chat_message(
            user_id,
            partner_id,
            "audio",
            message.audio.file_id,
            caption=message.caption,
        )
        bot.send_audio(
            partner_id,
            message.audio.file_id,
            caption=message.caption or "",
            protect_content=protected,
        )
    elif message.content_type == "document":
        db.log_chat_message(
            user_id,
            partner_id,
            "document",
            message.document.file_id,
            caption=message.caption,
        )
        bot.send_document(
            partner_id,
            message.document.file_id,
            caption=message.caption or "",
            protect_content=protected,
        )


if __name__ == "__main__":
    print("🔥 ربات نسخه PRO با سرعت بالا روشن شد...")
    bot.infinity_polling()