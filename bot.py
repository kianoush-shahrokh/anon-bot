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
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(BOT_TOKEN)
db.init_db()

USER_CONTEXT = {}

# آواتارهای پیش‌فرض باکیفیت
DEFAULT_BOY_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
DEFAULT_GIRL_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"


def is_admin(user_id):
    return ADMIN_ID != 0 and int(user_id) == ADMIN_ID


def get_main_kb(user_id):
    return kb.main_menu_keyboard(is_admin=is_admin(user_id))


def contains_links_or_usernames(text):
    if not text:
        return False
    pattern = (
        r"(@[a-zA-Z0-9_]{4,}|t\.me/[a-zA-Z0-9_]+|https?://[^\s]+|www\.[^\s]+)"
    )
    return bool(re.search(pattern, text))


def send_profile_card_with_photo(
    receiver_id, target_user, caption, reply_markup=None
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
                receiver_id, fid, caption=caption, reply_markup=reply_markup
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
            receiver_id, avatar_url, caption=caption, reply_markup=reply_markup
        )
    except Exception:
        bot.send_message(receiver_id, caption, reply_markup=reply_markup)


def format_profile_caption(u, title="👤 مشخصات حساب شما:"):
    icon = "👦" if u.get("gender") == "پسر" else "👧"
    status_str = "👀 آنلاین"
    if u.get("status") == "chatting":
        status_str = "🗣 در حال چت"
    return (
        f"{title}\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"🏷 نام: {u.get('name')}\n"
        f"{icon} جنسیت: {u.get('gender') or 'ثبت نشده'}\n"
        f"🎂 سن: {u.get('age') or 'ثبت نشده'}\n"
        f"📍 موقعیت: {u.get('province') or '-'} ({u.get('city') or '-'})\n"
        f"📝 بیوگرافی: {u.get('bio') or 'بدون بیوگرافی'}\n"
        f"📡 وضعیت: {status_str}\n"
        f"❤️ لایک‌ها: {u.get('likes_count', 0)}\n"
        f"🆔 شناسه: /{u.get('custom_id')}"
    )


# --- استارت و ورود ---
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = message.chat.id
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
            name=message.from_user.first_name or "کاربر",
            photo_file_id=initial_photo,
            state="ask_gender",
        )
        bot.send_message(
            user_id,
            "سلام! به ربات چت ناشناس خوش اومدی 🎭\nبرای شروع، جنسیت خودت رو از دکمه‌های پایین انتخاب کن:",
            reply_markup=kb.gender_keyboard(),
        )
        return

    if not user.get("photo_file_id") and initial_photo:
        db.add_or_update_user(user_id, photo_file_id=initial_photo)

    db.set_user_state(user_id, "main_menu")
    bot.send_message(
        user_id,
        "منوی اصلی چت ناشناس 👇",
        reply_markup=get_main_kb(user_id),
    )


# --- دکمه بازگشت پله‌به‌پله ---
@bot.message_handler(func=lambda msg: msg.text == "🔙 بازگشت")
def handle_back_button(message):
    user_id = message.chat.id
    USER_CONTEXT.pop(user_id, None)
    user = db.get_user(user_id)
    if not user:
        return

    curr = user.get("state", "main_menu")

    if curr in [
        "search_menu",
        "profile_menu",
        "connect_filter",
        "ask_gender",
    ]:
        db.set_user_state(user_id, "main_menu")
        bot.send_message(
            user_id, "منوی اصلی:", reply_markup=get_main_kb(user_id)
        )

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
        bot.send_message(
            user_id, "منوی اصلی:", reply_markup=get_main_kb(user_id)
        )


# --- ثبت‌نام و ویرایش مشخصات ---
@bot.message_handler(func=lambda msg: msg.text in ["پسر 👦", "دختر 👧"])
def set_gender(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    g = "پسر" if "پسر" in message.text else "دختر"
    db.add_or_update_user(user_id, gender=g)

    if user and user.get("age") and user.get("province"):
        db.set_user_state(user_id, "profile_menu")
        bot.send_message(
            user_id,
            f"✅ جنسیت شما به «{g}» تغییر یافت.",
            reply_markup=kb.profile_menu_keyboard(),
        )
    else:
        db.set_user_state(user_id, "select_age_range")
        bot.send_message(
            user_id,
            "حالا بازه سنی خودت رو انتخاب کن:",
            reply_markup=kb.age_ranges_keyboard(),
        )


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
    db.set_user_state(user_id, "select_specific_age")
    bot.send_message(
        user_id,
        "سن دقیق خودت رو انتخاب کن:",
        reply_markup=kb.specific_ages_keyboard(s, e),
    )


@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith("سن "))
def set_exact_age(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    try:
        val = int(message.text.replace("سن ", "").strip())
        db.add_or_update_user(user_id, age=val)
        if user and user.get("province"):
            db.set_user_state(user_id, "profile_menu")
            bot.send_message(
                user_id,
                f"✅ سن شما به {val} سال تغییر کرد.",
                reply_markup=kb.profile_menu_keyboard(),
            )
        else:
            db.set_user_state(user_id, "select_province")
            bot.send_message(
                user_id,
                "استان محل سکونتت رو انتخاب کن:",
                reply_markup=kb.provinces_keyboard(),
            )
    except ValueError:
        pass


@bot.message_handler(
    func=lambda msg: msg.text and msg.text.strip() in kb.IRAN_PROVINCES
)
def set_province(message):
    user_id = message.chat.id
    prov = message.text.strip()
    db.add_or_update_user(user_id, province=prov)
    db.set_user_state(user_id, f"select_city_{prov}")
    bot.send_message(
        user_id,
        f"شهر خودت در {prov} رو انتخاب کن:",
        reply_markup=kb.cities_keyboard(prov),
    )


@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith("شهر "))
def set_city(message):
    user_id = message.chat.id
    city_name = message.text.replace("شهر ", "").strip()
    db.add_or_update_user(user_id, city=city_name)
    db.set_user_state(user_id, "select_photo_type")
    bot.send_message(
        user_id,
        f"✅ موقعیت مکانی ثبت شد ({city_name}).\nحالا وضعیت عکس پروفایلت رو انتخاب کن:",
        reply_markup=kb.photo_choice_keyboard(),
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
        bot.send_message(
            user_id,
            "📸 لطفاً عکس دلخواهت رو همین‌جا بفرست:",
            reply_markup=kb.back_only_keyboard(),
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


@bot.message_handler(
    content_types=["photo"],
    func=lambda msg: USER_CONTEXT.get(msg.chat.id) == "waiting_for_avatar",
)
def receive_custom_avatar(message):
    user_id = message.chat.id
    fid = message.photo[-1].file_id
    db.add_or_update_user(user_id, photo_file_id=fid)
    USER_CONTEXT.pop(user_id, None)
    db.set_user_state(user_id, "profile_menu")
    user = db.get_user(user_id)
    send_profile_card_with_photo(
        user_id,
        user,
        format_profile_caption(user, "✅ عکس پروفایل جدید شما ذخیره شد:"),
        reply_markup=kb.profile_menu_keyboard(),
    )


# --- بخش پروفایل من ---
@bot.message_handler(func=lambda msg: msg.text == "👤 پروفایل من")
def show_my_profile(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user:
        return

    db.set_user_state(user_id, "profile_menu")
    caption = format_profile_caption(user, "👤 مشخصات حساب شما:")
    send_profile_card_with_photo(
        user_id, user, caption, reply_markup=kb.profile_menu_keyboard()
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر نام")
def edit_name_prompt(message):
    user_id = message.chat.id
    USER_CONTEXT[user_id] = "waiting_for_name"
    bot.send_message(
        user_id,
        "نام یا لقب جدیدت رو بنویس:",
        reply_markup=kb.back_only_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "📝 ثبت بیوگرافی")
def edit_bio_prompt(message):
    user_id = message.chat.id
    USER_CONTEXT[user_id] = "waiting_for_bio"
    bot.send_message(
        user_id,
        "یک متن کوتاه (حداکثر ۱۵۰ کاراکتر) به عنوان بیوگرافی پروفایلت بنویس:",
        reply_markup=kb.back_only_keyboard(),
    )


@bot.message_handler(
    func=lambda msg: USER_CONTEXT.get(msg.chat.id)
    in ["waiting_for_name", "waiting_for_bio"]
    and msg.text != "🔙 بازگشت"
)
def save_text_profile_fields(message):
    user_id = message.chat.id
    mode = USER_CONTEXT.pop(user_id, None)
    if contains_links_or_usernames(message.text):
        bot.send_message(
            user_id, "⚠️ قرار دادن آیدی و لینک در نام یا بیوگرافی مجاز نیست!"
        )
        return

    if mode == "waiting_for_name":
        db.add_or_update_user(user_id, name=message.text.strip()[:30])
    elif mode == "waiting_for_bio":
        db.add_or_update_user(user_id, bio=message.text.strip()[:150])

    show_my_profile(message)


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر جنسیت")
def edit_gender_prompt(message):
    user_id = message.chat.id
    db.set_user_state(user_id, "edit_gender")
    bot.send_message(
        user_id, "جنسیت خود را انتخاب کنید:", reply_markup=kb.gender_keyboard()
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر سن")
def edit_age_prompt(message):
    user_id = message.chat.id
    db.set_user_state(user_id, "select_age_range")
    bot.send_message(
        user_id,
        "بازه سنی خودت رو انتخاب کن:",
        reply_markup=kb.age_ranges_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "✏️ تغییر شهر/استان")
def edit_province_prompt(message):
    user_id = message.chat.id
    db.set_user_state(user_id, "select_province")
    bot.send_message(
        user_id,
        "استان خودت رو انتخاب کن:",
        reply_markup=kb.provinces_keyboard(),
    )


@bot.message_handler(func=lambda msg: msg.text == "📸 تغییر عکس")
def edit_photo_prompt(message):
    user_id = message.chat.id
    db.set_user_state(user_id, "select_photo_type")
    bot.send_message(
        user_id,
        "وضعیت عکس پروفایل رو انتخاب کن:",
        reply_markup=kb.photo_choice_keyboard(),
    )


# --- دعوت از دوستان ---
@bot.message_handler(func=lambda msg: msg.text == "👥 دعوت از دوستان")
def invite_friends(message):
    user_id = message.chat.id
    bot_info = bot.get_me()
    invite_text = (
        f"🔥 بیا توی این ربات چت ناشناس تا با افراد هم‌سن و هم‌استانی خودت ناشناس چت کنی!\n\n"
        f"👇 روی لینک زیر بزن:\n"
        f"https://t.me/{bot_info.username}?start"
    )
    bot.send_message(user_id, invite_text)


# --- جستجوی کاربران و لیست افراد آنلاین ---
@bot.message_handler(func=lambda msg: msg.text == "🔍 جستجوی کاربران")
def open_search_menu(message):
    user_id = message.chat.id
    db.set_user_state(user_id, "search_menu")
    bot.send_message(
        user_id,
        "🔍 کیو برات پیدا کنم؟ از دکمه‌های پایین انتخاب کن:",
        reply_markup=kb.search_menu_keyboard(),
    )


@bot.message_handler(
    func=lambda msg: msg.text
    in ["👥 هم‌سن‌ها", "📍 هم‌استانی‌ها", "🔥 محبوب‌ترین‌ها", "🆕 کاربران جدید"]
)
def handle_user_lists(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user:
        return

    mode_map = {
        "👥 هم‌سن‌ها": (
            "same_age",
            f"📍 لیست افراد هم‌سن شما ({user.get('age') or 20} سال):",
        ),
        "📍 هم‌استانی‌ها": (
            "same_prov",
            f"📍 لیست کاربران استان {user.get('province') or 'شما'}:",
        ),
        "🔥 محبوب‌ترین‌ها": (
            "top_likes",
            "🔥 محبوب‌ترین کاربران (بیشترین لایک):",
        ),
        "🆕 کاربران جدید": ("new_users", "🆕 لیست کاربران آنلاین اخیر:"),
    }
    mode, header = mode_map[message.text]
    users = db.search_users_list(mode, user)

    if not users:
        bot.send_message(user_id, "فعلاً کاربری در این دسته یافت نشد!")
        return

    msg = f"{header}\n\n"
    for u in users:
        icon = "👨" if u.get("gender") == "پسر" else "👩"
        status_text = (
            "هم‌اکنون 👀 آنلایـــن" if u.get("is_online") else "آفلاین"
        )
        if u.get("status") == "chatting":
            status_text += " (درحال چت🗣)"
        msg += (
            f"{icon} نام: {u.get('name')} (سن: {u.get('age') or '-'})\n"
            f"استان: {u.get('province') or '-'} ({u.get('city') or '-'})\n"
            f"{status_text}\n"
            f"❤️ لایک‌ها: {u.get('likes_count', 0)}\n"
            f"🆔 : /{u.get('custom_id')}\n"
            f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        )
    bot.send_message(user_id, msg)


@bot.message_handler(regexp=r"^/user_[a-zA-Z0-9]+$")
def click_custom_id(message):
    user_id = message.chat.id
    cid = message.text.replace("/", "").strip()
    target = db.get_user_by_custom_id(cid)
    if not target:
        bot.send_message(user_id, "❌ کاربر پیدا نشد!")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    if target["user_id"] != user_id:
        markup.add(
            types.InlineKeyboardButton(
                "💬 درخواست چت", callback_data=f"reqchat_{target['user_id']}"
            ),
            types.InlineKeyboardButton(
                f"❤️ لایک ({target.get('likes_count', 0)})",
                callback_data=f"like_{target['user_id']}",
            ),
        )

    caption = format_profile_caption(target, "👤 پروفایل کاربر:")
    send_profile_card_with_photo(
        user_id, target, caption, reply_markup=markup
    )


# --- اتصال به ناشناس با فیلترهای مختلف ---
@bot.message_handler(func=lambda msg: msg.text == "⚡ به یه ناشناس وصلم کن!")
def open_connect_filters(message):
    user_id = message.chat.id
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
        "📍 جستجوی هم‌استانی",
        "🎂 جستجوی هم‌سن",
        "⏭ هم‌صحبت بعدی",
    ]
)
def start_filtered_search(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user:
        return

    if user["status"] == "chatting":
        old_partner = db.disconnect_user(user_id)
        if old_partner:
            db.set_user_state(old_partner, "main_menu")
            bot.send_message(
                old_partner,
                "طرف مقابل مکالمه رو قطع کرد و رفت نفر بعدی! 🚪",
                reply_markup=get_main_kb(old_partner),
            )

    f_map = {
        "🎲 جستجوی شانسی": "any",
        "👧 جستجوی دختر": "girl",
        "👦 جستجوی پسر": "boy",
        "📍 جستجوی هم‌استانی": "same_prov",
        "🎂 جستجوی هم‌سن": "same_age",
        "⏭ هم‌صحبت بعدی": user.get("search_filter", "any"),
    }
    chosen_filter = f_map.get(message.text, "any")
    partner_id = db.find_match(user_id, chosen_filter)

    if partner_id:
        msg_text = "🎉 هم‌صحبت پیدا شد و وصل شدید! سلام کن 👋"
        bot.send_message(user_id, msg_text, reply_markup=kb.chatting_keyboard())
        bot.send_message(
            partner_id, msg_text, reply_markup=kb.chatting_keyboard()
        )
    else:
        bot.send_message(
            user_id,
            "🔍 در حال جستجوی هم‌صحبت... منتظر بمونید.",
            reply_markup=kb.waiting_keyboard(),
        )


@bot.message_handler(
    func=lambda msg: msg.text in ["❌ پایان مکالمه", "⛔ انصراف از جستجو"]
)
def stop_chat(message):
    user_id = message.chat.id
    partner_id = db.disconnect_user(user_id)
    db.set_user_state(user_id, "main_menu")
    bot.send_message(
        user_id, "مکالمه پایان یافت.", reply_markup=get_main_kb(user_id)
    )
    if partner_id:
        db.set_user_state(partner_id, "main_menu")
        bot.send_message(
            partner_id,
            "طرف مقابل مکالمه رو ترک کرد! 🚪",
            reply_markup=get_main_kb(partner_id),
        )


# --- امکانات داخل چت ---
@bot.message_handler(func=lambda msg: msg.text == "👤 مشاهده پروفایل")
def view_partner_profile(message):
    user_id = message.chat.id
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

    caption = format_profile_caption(partner, "👤 پروفایل هم‌صحبت شما:")
    send_profile_card_with_photo(user_id, partner, caption)


@bot.message_handler(func=lambda msg: msg.text == "❤️ لایک هم‌صحبت")
def like_current_partner(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner_id = user["partner_id"]
    if db.like_user(user_id, partner_id):
        bot.send_message(user_id, "❤️ پروفایل هم‌صحبتت رو لایک کردی!")
        bot.send_message(
            partner_id, "❤️ هم‌صحبتت ازت خوشش اومد و پروفایلت رو لایک کرد!"
        )
    else:
        bot.send_message(user_id, "شما قبلاً این کاربر رو لایک کرده‌اید!")


@bot.message_handler(func=lambda msg: msg.text == "🔗 اشتراک‌گذاری آیدی")
def request_share_id(message):
    user_id = message.chat.id
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
def prompt_timed_photo(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting":
        return
    USER_CONTEXT[user_id] = "waiting_for_timed_photo"
    bot.send_message(
        user_id,
        "💣 اکنون عکس خود را بفرستید تا به صورت محوشونده (۱۰ ثانیه‌ای) ارسال شود:",
    )


def delete_timed_message(chat_id, message_id, delay=10):
    time.sleep(delay)
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass


# --- گزارش تخلف ---
@bot.message_handler(func=lambda msg: msg.text == "⚠️ گزارش تخلف")
def report_partner(message):
    user_id = message.chat.id
    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner_id = user["partner_id"]
    partner = db.get_user(partner_id)
    bot.send_message(
        user_id, "✅ گزارش شما ثبت شد و توسط ادمین بررسی خواهد شد."
    )

    if ADMIN_ID != 0:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton(
                "🚫 مسدودسازی کاربر", callback_data=f"adm_toggle_ban:{partner_id}:0"
            ),
            types.InlineKeyboardButton(
                "👁 چت‌های این دو نفر", callback_data=f"adm_chat:{user_id}:{partner_id}:0"
            ),
            types.InlineKeyboardButton(
                "👤 پروفایل و مخاطب‌های متهم", callback_data=f"adm_u:{partner_id}:0"
            ),
            types.InlineKeyboardButton(
                "❌ رد گزارش", callback_data="dismiss_report"
            ),
        )
        report_text = (
            f"🚨 گزارش تخلف جدید!\n"
            f"شاکی: {user_id} ({user.get('name')})\n"
            f"متهم: {partner_id} ({partner.get('name') if partner else '-'})\n"
            f"شناسه متهم: /{partner.get('custom_id') if partner else '-'}"
        )
        try:
            bot.send_message(ADMIN_ID, report_text, reply_markup=markup)
        except Exception:
            pass


# ==================== پنل مدیریت پیشرفته ادمین (/admin) ====================

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.chat.id):
        return
    uid = message.chat.id
    USER_CONTEXT.pop(uid, None)
    bot.send_message(
        uid,
        "🎹 کیبورد مدیریت فعال شد:",
        reply_markup=kb.admin_reply_keyboard(),
    )
    users, total = db.get_paginated_users(limit=10, offset=0)
    bot.send_message(
        uid,
        f"🎛 پنل مدیریت کل ربات چت ناشناس\n"
        f"👥 کل کاربران ثبت‌نامی: {total} نفر\n\n"
        f"👇 روی هر کاربر کلیک کنید تا پروفایل، عکس پروفایل و لیست افرادی که با آن‌ها چت کرده نمایش داده شود:",
        reply_markup=kb.admin_users_list_inline(users, total, page=0, per_page=10),
    )


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and msg.text
    in [
        "🎛 پنل مدیریت ادمین",
        "👥 لیست تمام کاربران",
        "🟢 چت‌های زنده الان",
        "📊 آمار زنده ربات",
        "🔍 جستجوی کاربر",
        "📢 پیام همگانی",
        "🚫 لیست مسدودها",
        "🏠 خروج از پنل مدیریت",
        "❌ انصراف",
    ]
)
def handle_admin_reply_buttons(message):
    uid = message.chat.id
    txt = message.text
    USER_CONTEXT.pop(uid, None)

    if txt in ["🎛 پنل مدیریت ادمین", "👥 لیست تمام کاربران"]:
        admin_panel(message)

    elif txt == "🏠 خروج از پنل مدیریت":
        bot.send_message(
            uid, "🏠 به منوی اصلی کاربری بازگشتید:", reply_markup=get_main_kb(uid)
        )

    elif txt == "❌ انصراف":
        bot.send_message(
            uid, "✅ عملیات لغو شد.", reply_markup=kb.admin_reply_keyboard()
        )
        bot.send_message(
            uid, "🎛 منوی پنل مدیریت:", reply_markup=kb.admin_home_inline()
        )

    elif txt == "📊 آمار زنده ربات":
        send_admin_stats(uid)

    elif txt == "🟢 چت‌های زنده الان":
        send_admin_live_chats(uid)

    elif txt == "🚫 لیست مسدودها":
        send_admin_banned_list(uid)

    elif txt == "🔍 جستجوی کاربر":
        USER_CONTEXT[uid] = "admin_waiting_search"
        bot.send_message(
            uid,
            "🔍 شناسه عددی (User ID) یا آیدی اختصاصی (مثلاً user_xxxx) کاربر را بفرستید:",
            reply_markup=kb.admin_cancel_keyboard(),
        )

    elif txt == "📢 پیام همگانی":
        USER_CONTEXT[uid] = "admin_waiting_broadcast"
        bot.send_message(
            uid,
            "📢 متن یا رسانه پیام همگانی را ارسال کنید تا برای تمام کاربران فرستاده شود:",
            reply_markup=kb.admin_cancel_keyboard(),
        )


def build_admin_user_text(u, partners):
    st_map = {
        "idle": "⚪️ آزاد",
        "waiting": "🔎 در صف انتظار",
        "chatting": "🟢 در حال چت",
    }
    st_str = st_map.get(u.get("status"), "نامشخص")
    ban_str = "🚫 مسدود" if u.get("is_banned") else "✅ فعال"

    return (
        f"👤 اطلاعات کامل کاربر:\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"🏷 نام: {u.get('name') or 'ناشناس'}\n"
        f"🆔 آیدی عددی: {u['user_id']}\n"
        f"🔖 آیدی ربات: /{u.get('custom_id')}\n"
        f"🚻 جنسیت: {u.get('gender') or '-'} | 🎂 سن: {u.get('age') or '-'}\n"
        f"📍 استان/شهر: {u.get('province') or '-'} ({u.get('city') or '-'})\n"
        f"❤️ لایک‌ها: {u.get('likes_count', 0)}\n"
        f"📡 وضعیت: {st_str} | حساب: {ban_str}\n"
        f"👥 تعداد افرادی که با آن‌ها چت کرده: {len(partners)} نفر\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"👇 روی هر مخاطب زیر بزنید تا تمام پیام‌ها و عکس/فیلم‌هایشان نمایش داده شود:"
    )


def format_admin_conversation(u1_info, u2_info, msgs, total):
    u1_name = u1_info.get("name") or str(u1_info["user_id"])
    u2_name = u2_info.get("name") or str(u2_info["user_id"])
    u1_id = u1_info["user_id"]

    header = (
        f"💬 تاریخچه چت بین دو کاربر:\n"
        f"🔵 {u1_name} (/{u1_info.get('custom_id')})\n"
        f"🟣 {u2_name} (/{u2_info.get('custom_id')})\n"
        f"📨 کل پیام‌های رد و بدل شده: {total}\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
    )

    if not msgs:
        return header + "هیچ پیامی بین این دو نفر ثبت نشده است."

    type_labels = {
        "photo": "📸 [عکس فرستاد]",
        "video": "🎥 [ویدیو فرستاد]",
        "voice": "🎤 [ویس فرستاد]",
        "audio": "🎵 [فایل صوتی]",
        "document": "📎 [فایل/سند]",
    }

    lines = []
    for m in msgs:
        t_str = (
            m["created_at"].strftime("%m/%d %H:%M")
            if m.get("created_at")
            else ""
        )
        sender = f"🔵 {u1_name}" if m["sender_id"] == u1_id else f"🟣 {u2_name}"
        ctype = m.get("content_type", "text")
        content = m.get("content") or ""
        cap = m.get("caption") or ""

        if ctype == "text":
            lines.append(f"🕒 {t_str} | {sender}:\n{content}")
        else:
            timed_tag = " 💣[تایم‌دار]" if m.get("is_timed") else ""
            badge = type_labels.get(ctype, f"[{ctype}]")
            cap_str = f" ({cap})" if cap else ""
            lines.append(f"🕒 {t_str} | {sender}: {badge}{timed_tag}{cap_str}")

    body = "\n──────────────\n".join(lines)
    return (header + body)[:4000]


def send_media_list_to_admin(admin_id, media_list):
    for item in media_list:
        s_id = item["sender_id"]
        r_id = item["receiver_id"]
        s_user = db.get_user(s_id) or {"name": str(s_id), "custom_id": str(s_id)}
        r_user = db.get_user(r_id) or {"name": str(r_id), "custom_id": str(r_id)}

        t_str = (
            item["created_at"].strftime("%Y-%m-%d %H:%M")
            if item.get("created_at")
            else ""
        )
        timed_str = " | 💣 عکس تایم‌دار" if item.get("is_timed") else ""
        cap_extra = (
            f"\n📝 کپشن: {item['caption']}" if item.get("caption") else ""
        )

        caption = (
            f"📤 فرستنده: {s_user.get('name')} (/{s_user.get('custom_id')})\n"
            f"📥 گیرنده: {r_user.get('name')} (/{r_user.get('custom_id')})\n"
            f"⏰ زمان: {t_str}{timed_str}"
            f"{cap_extra}"
        )

        ctype = item["content_type"]
        fid = item["content"]
        try:
            if ctype == "photo":
                bot.send_photo(admin_id, fid, caption=caption)
            elif ctype == "video":
                bot.send_video(admin_id, fid, caption=caption)
            elif ctype == "voice":
                bot.send_voice(admin_id, fid, caption=caption)
            elif ctype == "audio":
                bot.send_audio(admin_id, fid, caption=caption)
            elif ctype == "document":
                bot.send_document(admin_id, fid, caption=caption)
        except Exception as e:
            bot.send_message(admin_id, f"⚠️ خطا در ارسال فایل ({ctype}): {e}")


def send_admin_stats(chat_id, msg_id=None):
    st = db.get_bot_stats()
    text = (
        f"📊 آمار لحظه‌ای ربات:\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"👥 کل کاربران: {st['total_users']} نفر\n"
        f"🟢 در حال چت الان: {st['chatting_users']} نفر\n"
        f"⏳ در صف انتظار: {st['waiting_users']} نفر\n"
        f"🚫 مسدود شده‌ها: {st['banned_users']} نفر\n"
        f"📨 کل پیام‌ها: {st['total_msgs']}\n"
        f"🎬 کل عکس، فیلم و ویس‌ها: {st['total_media']}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔄 بروزرسانی", callback_data="adm_stats")
    )
    markup.add(
        types.InlineKeyboardButton(
            "👥 لیست تمام کاربران", callback_data="adm_users:0"
        )
    )
    markup.add(
        types.InlineKeyboardButton("🔙 منوی اصلی پنل", callback_data="adm_home")
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)


def send_admin_live_chats(chat_id, msg_id=None):
    active = db.get_active_chats()
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not active:
        text = "🟢 در حال حاضر هیچ چت زنده‌ای در جریان نیست."
    else:
        text = f"🟢 چت‌های زنده در حال انجام ({len(active)} مکالمه):\nروی هر مکالمه بزنید تا محتوای چت و مدیاها باز شود:"
        for pair in active:
            btn_txt = f"👁 {pair['u1_name']} ({pair['u1_pub']}) ↔️ {pair['u2_name']} ({pair['u2_pub']})"
            markup.add(
                types.InlineKeyboardButton(
                    btn_txt,
                    callback_data=f"adm_chat:{pair['u1_id']}:{pair['u2_id']}:0",
                )
            )
    markup.add(
        types.InlineKeyboardButton("🔄 بروزرسانی", callback_data="adm_live")
    )
    markup.add(
        types.InlineKeyboardButton("🔙 منوی اصلی پنل", callback_data="adm_home")
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)


def send_admin_banned_list(chat_id, msg_id=None):
    banned = db.get_banned_users()
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not banned:
        text = "✅ هیچ کاربر مسدودی در سیستم وجود ندارد."
    else:
        text = "🚫 لیست کاربران مسدود شده (برای مشاهده یا رفع مسدودی کلیک کنید):"
        for u in banned:
            markup.add(
                types.InlineKeyboardButton(
                    f"🔓 {u.get('name')} | {u.get('custom_id')}",
                    callback_data=f"adm_u:{u['user_id']}:0",
                )
            )
    markup.add(
        types.InlineKeyboardButton("🔙 منوی اصلی پنل", callback_data="adm_home")
    )
    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)


# --- مدیریت دکمه‌های شیشه‌ای (لایک، درخواست چت مستقیم و پنل پیشرفته ادمین) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    # لایک کردن از روی کارت پروفایل
    if data.startswith("like_"):
        target_id = int(data.replace("like_", ""))
        if db.like_user(uid, target_id):
            bot.answer_callback_query(call.id, "❤️ لایک شما ثبت شد!")
            try:
                bot.send_message(
                    target_id, "❤️ یک نفر پروفایل شما را لایک کرد!"
                )
            except Exception:
                pass
        else:
            bot.answer_callback_query(
                call.id,
                "شما قبلاً این پروفایل را لایک کرده‌اید یا متعلق به خودتان است!",
            )
        return

    # درخواست چت مستقیم از لیست جستجو
    if data.startswith("reqchat_"):
        target_id = int(data.replace("reqchat_", ""))
        sender = db.get_user(uid)
        target = db.get_user(target_id)
        if not target or target.get("status") == "chatting":
            bot.answer_callback_query(
                call.id, "این کاربر هم‌اکنون مشغول چت دیگری است!", show_alert=True
            )
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✅ قبول درخواست چت", callback_data=f"acceptchat_{uid}"
            ),
            types.InlineKeyboardButton(
                "❌ رد کردن", callback_data=f"rejectchat_{uid}"
            ),
        )
        bot.send_message(
            target_id,
            f"🔔 کاربر «{sender.get('name')}» (/{sender.get('custom_id')}) به شما درخواست چت داده است:",
            reply_markup=markup,
        )
        bot.answer_callback_query(
            call.id, "✅ درخواست چت برای کاربر ارسال شد!", show_alert=True
        )
        return

    if data.startswith("acceptchat_"):
        requester_id = int(data.replace("acceptchat_", ""))
        db.connect_two_users_directly(uid, requester_id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(
            uid,
            "🎉 درخواست چت پذیرفته شد و وصل شدید!",
            reply_markup=kb.chatting_keyboard(),
        )
        bot.send_message(
            requester_id,
            "🎉 درخواست چت شما پذیرفته شد و وصل شدید!",
            reply_markup=kb.chatting_keyboard(),
        )
        return

    if data.startswith("rejectchat_"):
        requester_id = int(data.replace("rejectchat_", ""))
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(requester_id, "❌ درخواست چت شما توسط کاربر رد شد.")
        return

    # ==================== دستورات پنل پیشرفته ادمین ====================
    if not is_admin(uid):
        return

    if data == "dismiss_report":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif data == "adm_home":
        bot.edit_message_text(
            "🎛 پنل مدیریت کل ربات چت ناشناس:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb.admin_home_inline(),
        )

    elif data == "adm_stats":
        send_admin_stats(call.message.chat.id, call.message.message_id)

    elif data == "adm_live":
        send_admin_live_chats(call.message.chat.id, call.message.message_id)

    elif data == "adm_banned":
        send_admin_banned_list(call.message.chat.id, call.message.message_id)

    elif data == "adm_search":
        USER_CONTEXT[uid] = "admin_waiting_search"
        bot.answer_callback_query(call.id)
        bot.send_message(
            uid,
            "🔍 شناسه عددی (User ID) یا آیدی اختصاصی (مثلاً user_xxxx) کاربر را بفرستید:",
            reply_markup=kb.admin_cancel_keyboard(),
        )

    elif data == "adm_broadcast":
        USER_CONTEXT[uid] = "admin_waiting_broadcast"
        bot.answer_callback_query(call.id)
        bot.send_message(
            uid,
            "📢 متن یا رسانه پیام همگانی را ارسال کنید:",
            reply_markup=kb.admin_cancel_keyboard(),
        )

    # ۱. لیست صفحه‌بندی شده تمام کاربران
    elif data.startswith("adm_users:"):
        page = int(data.split(":")[1])
        per_page = 10
        users, total = db.get_paginated_users(limit=per_page, offset=page * per_page)
        bot.edit_message_text(
            f"👥 لیست تمام کاربران ربات (مجموع: {total} نفر)\n"
            f"👇 روی هر کاربر بزنید تا افراد چت‌کرده با او و عکس/فیلم‌هایش را ببینید:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb.admin_users_list_inline(users, total, page, per_page),
        )

    # ۲. پروفایل کاربر + لیست افرادی که با آن‌ها چت کرده
    elif data.startswith("adm_u:"):
        parts = data.split(":")
        target_id = int(parts[1])
        back_page = int(parts[2]) if len(parts) > 2 else 0

        target_user = db.get_user(target_id)
        if not target_user:
            bot.answer_callback_query(call.id, "کاربر یافت نشد!", show_alert=True)
            return

        partners = db.get_user_chat_partners(target_id)
        text = build_admin_user_text(target_user, partners)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb.admin_user_detail_inline(target_user, partners, back_page),
        )

    # ۳. مشاهده متن چت بین دو کاربر
    elif data.startswith("adm_chat:"):
        parts = data.split(":")
        u1 = int(parts[1])
        u2 = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        per_page = 15

        u1_info = db.get_user(u1) or {"user_id": u1, "name": f"کاربر {u1}", "custom_id": str(u1)}
        u2_info = db.get_user(u2) or {"user_id": u2, "name": f"کاربر {u2}", "custom_id": str(u2)}

        msgs, total = db.get_conversation_between(u1, u2, limit=per_page, offset=page * per_page)
        text = format_admin_conversation(u1_info, u2_info, msgs, total)

        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb.admin_conversation_inline(u1, u2, page, total, per_page),
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=kb.admin_conversation_inline(u1, u2, page, total, per_page),
            )
        bot.answer_callback_query(call.id)

    # ۴. ارسال تمام عکس‌ها، فیلم‌ها و ویس‌های بین دو کاربر
    elif data.startswith("adm_media:"):
        parts = data.split(":")
        u1 = int(parts[1])
        u2 = int(parts[2])

        media_list = db.get_media_between(u1, u2, limit=50)
        if not media_list:
            bot.answer_callback_query(
                call.id, "📭 هیچ عکس، فیلم یا ویسی بین این دو نفر ارسال نشده است!", show_alert=True
            )
            return

        bot.answer_callback_query(call.id, f"در حال ارسال {len(media_list)} فایل مدیا...")
        send_media_list_to_admin(uid, media_list)
        bot.send_message(uid, f"✅ تمام {len(media_list)} فایل مدیای بین این دو نفر ارسال شد.")

    # ۵. ارسال تمام عکس‌ها و فیلم‌های یک کاربر خاص
    elif data.startswith("adm_umedia:"):
        target_id = int(data.split(":")[1])
        media_list = db.get_user_all_media(target_id, limit=30)
        if not media_list:
            bot.answer_callback_query(
                call.id, "📭 این کاربر هیچ عکس یا فیلمی ارسال یا دریافت نکرده است!", show_alert=True
            )
            return

        bot.answer_callback_query(call.id, f"در حال ارسال {len(media_list)} فایل مدیا...")
        send_media_list_to_admin(uid, media_list)
        bot.send_message(uid, "✅ تمام فایل‌های مدیای این کاربر ارسال شد.")

    # ۶. ارسال عکس پروفایل کاربر (با همان سیستم هوشمند عکس تلگرام / دیتابیس / آواتار)
    elif data.startswith("adm_uphoto:"):
        target_id = int(data.split(":")[1])
        target_user = db.get_user(target_id)
        if not target_user:
            bot.answer_callback_query(call.id, "کاربر یافت نشد!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        cap = format_profile_caption(target_user, "🖼 کارت پروفایل کاربر:")
        send_profile_card_with_photo(uid, target_user, cap)

    # ۷. مسدود / رفع مسدودی کاربر
    elif data.startswith("adm_toggle_ban:"):
        parts = data.split(":")
        target_id = int(parts[1])
        back_page = int(parts[2])
        target_user = db.get_user(target_id)
        if target_user:
            new_ban = not target_user.get("is_banned", False)
            db.add_or_update_user(target_id, is_banned=new_ban)
            if new_ban:
                db.disconnect_user(target_id)
            bot.answer_callback_query(
                call.id,
                "🚫 کاربر مسدود شد!" if new_ban else "🔓 کاربر رفع مسدودیت شد!",
                show_alert=True,
            )
            target_user = db.get_user(target_id)
            partners = db.get_user_chat_partners(target_id)
            bot.edit_message_text(
                build_admin_user_text(target_user, partners),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb.admin_user_detail_inline(target_user, partners, back_page),
            )

    # ۸. قطع چت فعال کاربر توسط ادمین
    elif data.startswith("adm_kick:"):
        parts = data.split(":")
        target_id = int(parts[1])
        back_page = int(parts[2])
        partner_id = db.disconnect_user(target_id)
        for u in (target_id, partner_id):
            if u:
                db.set_user_state(u, "main_menu")
                try:
                    bot.send_message(
                        u, "🛑 مکالمه توسط مدیریت قطع شد.", reply_markup=get_main_kb(u)
                    )
                except Exception:
                    pass
        bot.answer_callback_query(call.id, "مکالمه قطع شد ✅", show_alert=True)
        target_user = db.get_user(target_id)
        partners = db.get_user_chat_partners(target_id)
        bot.edit_message_text(
            build_admin_user_text(target_user, partners),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb.admin_user_detail_inline(target_user, partners, back_page),
        )


@bot.message_handler(
    content_types=["text", "photo", "video", "voice", "audio", "document"],
    func=lambda msg: is_admin(msg.chat.id)
    and USER_CONTEXT.get(msg.chat.id)
    in [
        "admin_waiting_search",
        "admin_waiting_broadcast",
    ]
    and msg.text != "❌ انصراف",
)
def handle_admin_inputs(message):
    admin_id = message.chat.id
    mode = USER_CONTEXT.pop(admin_id, None)

    if mode == "admin_waiting_search":
        txt = (message.text or "").strip().replace("/", "")
        target = db.get_user_by_custom_id(txt)
        if not target:
            bot.send_message(
                admin_id,
                "❌ کاربری با این شناسه یافت نشد.",
                reply_markup=kb.admin_reply_keyboard(),
            )
            return
        partners = db.get_user_chat_partners(target["user_id"])
        bot.send_message(
            admin_id, "✅ کاربر پیدا شد:", reply_markup=kb.admin_reply_keyboard()
        )
        bot.send_message(
            admin_id,
            build_admin_user_text(target, partners),
            reply_markup=kb.admin_user_detail_inline(target, partners, 0),
        )

    elif mode == "admin_waiting_broadcast":
        uids = db.get_all_user_ids()
        sent = 0
        bot.send_message(
            admin_id,
            f"⏳ در حال ارسال پیام همگانی به {len(uids)} کاربر...",
            reply_markup=kb.admin_reply_keyboard(),
        )
        for u in uids:
            try:
                bot.copy_message(u, admin_id, message.message_id)
                sent += 1
            except Exception:
                pass
        bot.send_message(
            admin_id, f"✅ پیام همگانی با موفقیت برای {sent} کاربر ارسال شد."
        )


# --- موتور هدایت پیام‌های چت (با فیلتر استیکر، لینک و ذخیره لاگ) ---
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
    user = db.get_user(user_id)
    if not user or user.get("status") != "chatting" or not user.get("partner_id"):
        return

    partner_id = user["partner_id"]

    # ۱. ممنوعیت قطعی استیکر
    if message.content_type == "sticker":
        bot.send_message(
            user_id, "⚠️ ارسال استیکر در محیط چت ناشناس ممنوع است!"
        )
        return

    # ۲. پیام متنی و فیلتر لینک/آیدی
    if message.content_type == "text":
        if contains_links_or_usernames(message.text):
            bot.send_message(
                user_id,
                "⚠️ ارسال آیدی و لینک مجاز نیست! از دکمه «🔗 اشتراک‌گذاری آیدی» استفاده کنید.",
            )
            return
        db.log_chat_message(user_id, partner_id, "text", message.text)
        bot.send_message(partner_id, message.text)
        return

    # ۳. عکس (معمولی و تایم‌دار محوشونده)
    if message.content_type == "photo":
        fid = message.photo[-1].file_id
        cap = message.caption or ""
        if contains_links_or_usernames(cap):
            bot.send_message(user_id, "⚠️ ارسال آیدی و لینک در کپشن مجاز نیست!")
            return

        if USER_CONTEXT.get(user_id) == "waiting_for_timed_photo":
            USER_CONTEXT.pop(user_id, None)
            db.log_chat_message(
                user_id, partner_id, "photo", fid, caption=cap, is_timed=True
            )
            sent_msg = bot.send_photo(
                partner_id,
                fid,
                caption="💣 عکس تایم‌دار (۱۰ ثانیه دیگر خودکار حذف می‌شود)\n"
                + cap,
                has_spoiler=True,
            )
            bot.send_message(
                user_id, "✅ عکس تایم‌دار ارسال شد (۱۰ ثانیه بعد پاک می‌شود)."
            )
            threading.Thread(
                target=delete_timed_message,
                args=(partner_id, sent_msg.message_id, 10),
                daemon=True,
            ).start()
            return

        db.log_chat_message(
            user_id, partner_id, "photo", fid, caption=cap, is_timed=False
        )
        bot.send_photo(partner_id, fid, caption=cap)
        return

    # ۴. ویس، ویدیو، فایل صوتی و سند
    if message.content_type == "voice":
        db.log_chat_message(user_id, partner_id, "voice", message.voice.file_id)
        bot.send_voice(partner_id, message.voice.file_id)
    elif message.content_type == "video":
        db.log_chat_message(
            user_id,
            partner_id,
            "video",
            message.video.file_id,
            caption=message.caption,
        )
        bot.send_video(
            partner_id, message.video.file_id, caption=message.caption or ""
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
            partner_id, message.audio.file_id, caption=message.caption or ""
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
            partner_id, message.document.file_id, caption=message.caption or ""
        )


if __name__ == "__main__":
    print("🔥 ربات نسخه PRO با سرعت بالا روشن شد...")
    bot.infinity_polling()