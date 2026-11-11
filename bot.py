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

# آواتارهای پیش‌فرض باکیفیت (برای کسانی که عکس تلگرام ندارند یا مخفی است تا همیشه کارت عکس‌دار بیاید)
DEFAULT_BOY_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
DEFAULT_GIRL_AVATAR = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"


def is_admin(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID


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
    """
    ارسال تضمینی کارت پروفایل به همراه عکس در بالای مشخصات:
    ۱. اگر کاربر عکس ذخیره شده دارد، همان ارسال می‌شود.
    ۲. اگر ندارد، لحظه‌ای عکس پروفایل تلگرامش چک و کش می‌شود.
    ۳. اگر پروفایل تلگرامش خالی یا قفل بود، آواتار پیش‌فرض ارسال می‌شود تا هیچ‌وقت بدون عکس نباشد.
    """
    fid = target_user.get("photo_file_id")

    # تلاش برای گرفتن خودکار عکس پروفایل تلگرام در صورتی که هنوز ذخیره نشده باشد
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

    # اگر عکس نداشت یا قفل بود، ارسال آواتار گرافیکی بالای متن مشخصات
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
    user = db.get_user(user_id)

    if user and user.get("is_banned"):
        bot.send_message(user_id, "🚫 حساب کاربری شما توسط مدیریت مسدود شده است.")
        return

    # تلاش اولیه برای ذخیره عکس تلگرام کاربر در بدو ورود
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
        reply_markup=kb.main_menu_keyboard(),
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
            user_id, "منوی اصلی:", reply_markup=kb.main_menu_keyboard()
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
            user_id, "منوی اصلی:", reply_markup=kb.main_menu_keyboard()
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
    func=lambda msg: msg.text and msg.text.startswith("استان ")
)
def set_province(message):
    user_id = message.chat.id
    prov = message.text.replace("استان ", "").strip()
    if prov not in kb.IRAN_PROVINCES:
        return
    db.add_or_update_user(user_id, province=prov)
    db.set_user_state(user_id, f"select_city_{prov}")
    bot.send_message(
        user_id,
        f"شهر خودت در استان {prov} رو انتخاب کن:",
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
                    "⚠️ عکس تلگرام شما مخفی است یا عکسی ندارید؛ آواتار پیش‌فرض فعال شد (می‌توانید از ارسال عکس جدید استفاده کنید).",
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
        reply_markup=kb.main_menu_keyboard(),
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


# --- بخش پروفایل من (با نمایش حتمی عکس بالای مشخصات) ---
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


# مشاهده پروفایل با کلیک روی /user_xxxxxx به همراه دکمه لایک و درخواست چت
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
                reply_markup=kb.main_menu_keyboard(),
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
        user_id, "مکالمه پایان یافت.", reply_markup=kb.main_menu_keyboard()
    )
    if partner_id:
        db.set_user_state(partner_id, "main_menu")
        bot.send_message(
            partner_id,
            "طرف مقابل مکالمه رو ترک کرد! 🚪",
            reply_markup=kb.main_menu_keyboard(),
        )


# --- امکانات داخل چت: مشاهده پروفایل، لایک، اشتراک آیدی، عکس تایم‌دار ---
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


# --- گزارش تخلف (فقط ارسال به ادمین بدون بن خودکار) ---
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
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "🚫 مسدودسازی کاربر", callback_data=f"ban_{partner_id}"
            ),
            types.InlineKeyboardButton(
                "📋 دیدن چت‌های متهم", callback_data=f"logs_{partner_id}"
            ),
            types.InlineKeyboardButton(
                "❌ رد گزارش", callback_data="dismiss_report"
            ),
        )
        report_text = (
            f"🚨 گزارش تخلف جدید!\n"
            f"شاکی: {user_id}\n"
            f"متهم: {partner_id} ({partner.get('name') if partner else '-'})\n"
            f"شناسه متهم: /{partner.get('custom_id') if partner else '-'}"
        )
        try:
            bot.send_message(ADMIN_ID, report_text, reply_markup=markup)
        except Exception:
            pass


# --- پنل مدیریت ادمین (/admin) ---
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.chat.id):
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 آمار زنده ربات", callback_data="admin_stats"),
        types.InlineKeyboardButton(
            "🔍 مشاهده چت و عکس کاربر", callback_data="admin_view_logs"
        ),
        types.InlineKeyboardButton(
            "📢 پیام همگانی", callback_data="admin_broadcast"
        ),
        types.InlineKeyboardButton(
            "🔓 رفع مسدودی کاربر", callback_data="admin_unban"
        ),
    )
    bot.send_message(
        message.chat.id, "🎛 پنل مدیریت کل ربات چت ناشناس:", reply_markup=markup
    )


# --- مدیریت دکمه‌های شیشه‌ای (لایک، درخواست چت مستقیم و پنل ادمین) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.from_user.id

    # لایک کردن از روی کارت پروفایل
    if call.data.startswith("like_"):
        target_id = int(call.data.replace("like_", ""))
        if db.like_user(uid, target_id):
            bot.answer_callback_query(call.id, "❤️ لایک شما ثبت شد!")
            try:
                bot.send_message(
                    target_id,
                    f"❤️ یک نفر پروفایل شما را لایک کرد!",
                )
            except Exception:
                pass
        else:
            bot.answer_callback_query(
                call.id, "شما قبلاً این پروفایل را لایک کرده‌اید یا متعلق به خودتان است!"
            )
        return

    # درخواست چت مستقیم از لیست جستجو
    if call.data.startswith("reqchat_"):
        target_id = int(call.data.replace("reqchat_", ""))
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

    if call.data.startswith("acceptchat_"):
        requester_id = int(call.data.replace("acceptchat_", ""))
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

    if call.data.startswith("rejectchat_"):
        requester_id = int(call.data.replace("rejectchat_", ""))
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(requester_id, "❌ درخواست چت شما توسط کاربر رد شد.")
        return

    # --- دستورات مخصوص ادمین ---
    if not is_admin(uid):
        return

    if call.data == "admin_stats":
        conn = db.get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM anon_users;")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM anon_users WHERE status = 'chatting';"
            )
            chatting = cur.fetchone()[0] // 2
            cur.execute(
                "SELECT COUNT(*) FROM anon_users WHERE status = 'waiting';"
            )
            waiting = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chat_logs;")
            total_msgs = cur.fetchone()[0]
            cur.close()
        finally:
            db.put_conn(conn)

        bot.answer_callback_query(call.id)
        bot.send_message(
            uid,
            f"📊 آمار لحظه‌ای ربات:\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🗣 چت‌های فعال همزمان: {chatting}\n"
            f"⏳ افراد در صف انتظار: {waiting}\n"
            f"📨 کل پیام‌ها و عکس‌های ثبت‌شده: {total_msgs}",
        )

    elif call.data.startswith("ban_"):
        target_id = int(call.data.replace("ban_", ""))
        db.add_or_update_user(target_id, is_banned=True)
        db.disconnect_user(target_id)
        bot.answer_callback_query(call.id, "کاربر مسدود شد.")
        bot.edit_message_text(
            f"🚫 کاربر {target_id} مسدود شد.",
            call.message.chat.id,
            call.message.message_id,
        )

    elif call.data.startswith("logs_"):
        target_id = int(call.data.replace("logs_", ""))
        bot.answer_callback_query(call.id)
        send_logs_to_admin(uid, target_id)

    elif call.data == "dismiss_report":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "admin_view_logs":
        USER_CONTEXT[uid] = "admin_waiting_log_id"
        bot.answer_callback_query(call.id)
        bot.send_message(
            uid,
            "شناسه عددی (User ID) یا آیدی اختصاصی (مثلاً user_xxxx) کاربر را بفرستید:",
        )

    elif call.data == "admin_broadcast":
        USER_CONTEXT[uid] = "admin_waiting_broadcast"
        bot.answer_callback_query(call.id)
        bot.send_message(
            uid, "متن پیام همگانی را بنویسید تا برای تمام کاربران ارسال شود:"
        )

    elif call.data == "admin_unban":
        USER_CONTEXT[uid] = "admin_waiting_unban"
        bot.answer_callback_query(call.id)
        bot.send_message(uid, "شناسه عددی کاربر را برای رفع مسدودی وارد کنید:")


def send_logs_to_admin(admin_id, target_uid):
    conn = db.get_conn()
    try:
        cur = conn.cursor(cursor_factory=db.RealDictCursor)
        cur.execute(
            """
            SELECT * FROM chat_logs 
            WHERE sender_id = %s OR receiver_id = %s 
            ORDER BY created_at DESC LIMIT 15;
        """,
            (target_uid, target_uid),
        )
        logs = cur.fetchall()
        cur.close()
    finally:
        db.put_conn(conn)

    if not logs:
        bot.send_message(admin_id, "هیچ پیام یا عکسی برای این کاربر ثبت نشده است.")
        return

    bot.send_message(
        admin_id, f"📂 ۱۵ پیام و رسانه اخیر کاربر `{target_uid}`:"
    )
    for l in reversed(logs):
        direction = (
            f"📤 فرستاده به {l['receiver_id']}"
            if l["sender_id"] == target_uid
            else f"📥 دریافتی از {l['sender_id']}"
        )
        if l["content_type"] == "text":
            bot.send_message(admin_id, f"{direction}:\n💬 {l['content']}")
        elif l["content_type"] == "photo":
            t_tag = " [💣 عکس تایم‌دار]" if l.get("is_timed") else ""
            bot.send_photo(
                admin_id,
                l["content"],
                caption=f"{direction}{t_tag}\n{l.get('caption') or ''}",
            )
        elif l["content_type"] == "voice":
            bot.send_voice(admin_id, l["content"], caption=direction)


@bot.message_handler(
    func=lambda msg: is_admin(msg.chat.id)
    and USER_CONTEXT.get(msg.chat.id)
    in [
        "admin_waiting_log_id",
        "admin_waiting_broadcast",
        "admin_waiting_unban",
    ]
)
def handle_admin_inputs(message):
    admin_id = message.chat.id
    mode = USER_CONTEXT.pop(admin_id, None)
    txt = message.text.strip().replace("/", "")

    if mode == "admin_waiting_log_id":
        if txt.startswith("user_"):
            u = db.get_user_by_custom_id(txt)
            if not u:
                bot.send_message(admin_id, "کاربر یافت نشد.")
                return
            target_uid = u["user_id"]
        else:
            try:
                target_uid = int(txt)
            except ValueError:
                bot.send_message(admin_id, "فرمت آیدی نامعتبر است.")
                return
        send_logs_to_admin(admin_id, target_uid)

    elif mode == "admin_waiting_unban":
        try:
            target_uid = int(txt)
            db.add_or_update_user(target_uid, is_banned=False)
            bot.send_message(admin_id, f"✅ کاربر {target_uid} رفع مسدودی شد.")
        except ValueError:
            bot.send_message(admin_id, "آیدی نامعتبر است.")

    elif mode == "admin_waiting_broadcast":
        uids = db.get_all_user_ids()
        sent = 0
        for u in uids:
            try:
                bot.send_message(u, f"📢 پیام مدیریت:\n\n{message.text}")
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

    # ۴. ویس و ویدیو
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


if __name__ == "__main__":
    print("🔥 ربات نسخه PRO با سرعت بالا روشن شد...")
    bot.infinity_polling()