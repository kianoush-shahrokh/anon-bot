import math
from telebot import types

# بانک کامل ۳۱ استان و شهرهای ایران
IRAN_PROVINCES = {
    "آذربایجان شرقی": [
        "تبریز",
        "مراغه",
        "مرند",
        "اهر",
        "میانه",
        "بناب",
        "سراب",
        "آذرشهر",
        "هادیشهر",
        "عجب‌شیر",
        "سردرود",
        "ملکان",
        "شبستر",
        "بستان‌آباد",
        "هشترود",
        "اسکو",
        "ایلخچی",
        "خسروشاه",
        "باسمنج",
        "سهند",
    ],
    "آذربایجان غربی": [
        "ارومیه",
        "خوی",
        "بوکان",
        "مهاباد",
        "میاندوآب",
        "سلماس",
        "پیرانشهر",
        "نقده",
        "تکاب",
        "ماکو",
        "سردشت",
        "شاهین‌دژ",
        "اشنویه",
        "قره‌ضیاءالدین",
        "شوط",
        "سیه‌چشمه",
        "ربط",
        "پلدشت",
        "بازرگان",
        "چایپاره",
    ],
    "اردبیل": [
        "اردبیل",
        "پارس‌آباد",
        "مشگین‌شهر",
        "خلخال",
        "گرمی",
        "بیله‌سوار",
        "نمین",
        "جعفرآباد",
        "گیوی",
        "عنبران",
        "نیر",
        "سرعین",
        "اصلاندوز",
    ],
    "اصفهان": [
        "اصفهان",
        "کاشان",
        "خمینی‌شهر",
        "نجف‌آباد",
        "شاهین‌شهر",
        "شهرضا",
        "فولادشهر",
        "بهارستان",
        "مبارکه",
        "آران و بیدگل",
        "گلپایگان",
        "زرین‌شهر",
        "درچه",
        "فلاورجان",
        "لنجان",
        "نائین",
        "سمیرم",
        "خوانسار",
        "فریدن",
        "نطنز",
    ],
    "البرز": [
        "کرج",
        "فردیس",
        "کمال‌شهر",
        "نظرآباد",
        "محمدشهر",
        "ماهدشت",
        "مشکین‌دشت",
        "هشتگرد",
        "چهارباغ",
        "گرم‌دره",
        "اشتهارد",
        "طالقان",
        "کوهسار",
    ],
    "ایلام": [
        "ایلام",
        "دهلران",
        "ایوان",
        "آبدانان",
        "دره‌شهر",
        "مهران",
        "سرابله",
        "ارکواز",
        "آسمان‌آباد",
        "چوار",
        "بدره",
        "شباب",
    ],
    "بوشهر": [
        "بوشهر",
        "برازجان",
        "بندر گناوه",
        "بندر کنگان",
        "خورموج",
        "عسلویه",
        "جم",
        "بندر دیلم",
        "بندر دیر",
        "عالی‌شهر",
        "آب‌پخش",
        "نخل تقی",
        "اهرم",
    ],
    "تهران": [
        "تهران",
        "اسلام‌شهر",
        "شهریار",
        "قدس",
        "ملارد",
        "پاکدشت",
        "ورامین",
        "قرچک",
        "ری",
        "نسیم‌شهر",
        "پرند",
        "پردیس",
        "دماوند",
        "رباط‌کریم",
        "بومهن",
        "باقرشهر",
        "پیشوا",
        "لواسان",
        "فیروزکوه",
        "شمیرانات",
    ],
    "چهارمحال و بختیاری": [
        "شهرکرد",
        "بروجن",
        "لردگان",
        "فرخ‌شهر",
        "فارسان",
        "هفشجان",
        "جونقان",
        "سامان",
        "فرادنبه",
        "بن",
        "کیان",
        "سورشجان",
        "اردل",
        "کوهرنگ",
    ],
    "خراسان جنوبی": [
        "بیرجند",
        "قائن",
        "طبس",
        "فردوس",
        "نهبندان",
        "بشرویه",
        "سرایان",
        "سربیشه",
        "اسلامیه",
        "حاجی‌آباد",
        "خوسف",
    ],
    "خراسان رضوی": [
        "مشهد",
        "نیشابور",
        "سبزوار",
        "تربت حیدریه",
        "کاشمر",
        "قوچان",
        "تربت جام",
        "تایباد",
        "چناران",
        "سرخس",
        "گناباد",
        "فریمان",
        "گلبهار",
        "درگز",
        "خواف",
        "بردسکن",
        "طرقبه",
        "شاندیز",
    ],
    "خراسان شمالی": [
        "بجنورد",
        "شیروان",
        "اسفراین",
        "آشخانه",
        "جاجرم",
        "فاروج",
        "گرمه",
        "راز",
    ],
    "خوزستان": [
        "اهواز",
        "دزفول",
        "آبادان",
        "بندر ماهشهر",
        "اندیمشک",
        "خرمشهر",
        "بهبهان",
        "ایذه",
        "شوشتر",
        "مسجدسلیمان",
        "بندر امام خمینی",
        "شوش",
        "رامهرمز",
        "امیدیه",
        "شادگان",
        "سوسنگرد",
        "باغ‌ملک",
        "چمران",
        "هندیجان",
    ],
    "زنجان": [
        "زنجان",
        "ابهر",
        "خرمدره",
        "قیدار",
        "هیدج",
        "صائین‌قلعه",
        "آب‌بر",
        "سلطانیه",
        "سجاس",
        "ماه‌نشان",
    ],
    "سمنان": [
        "سمنان",
        "شاهرود",
        "دامغان",
        "گرمسار",
        "مهدی‌شهر",
        "ایوانکی",
        "شهمیرزاد",
        "سرخه",
        "بسطام",
        "آرادان",
    ],
    "سیستان و بلوچستان": [
        "زاهدان",
        "زابل",
        "ایرانشهر",
        "چابهار",
        "سراوان",
        "خاش",
        "کنارک",
        "جالق",
        "نیک‌شهر",
        "پیشین",
        "سوران",
        "زهک",
        "فنوج",
        "سرباز",
    ],
    "فارس": [
        "شیراز",
        "مرودشت",
        "جهرم",
        "فسا",
        "کازرون",
        "صدرا",
        "داراب",
        "فیروزآباد",
        "لار",
        "آباده",
        "نورآباد",
        "نی‌ریز",
        "اقلید",
        "استهبان",
        "گراش",
        "زرقان",
        "کوار",
        "لامرد",
        "صفاشهر",
    ],
    "قزوین": [
        "قزوین",
        "الوند",
        "تاکستان",
        "بوئین‌زهرا",
        "اقبالیه",
        "محمدیه",
        "آبیک",
        "شال",
        "اسفرورین",
        "بیدستان",
    ],
    "قم": ["قم", "قنوات", "جعفریه", "کهک", "دستجرد", "سلفچگان"],
    "کردستان": [
        "سنندج",
        "سقز",
        "مریوان",
        "بانه",
        "قروه",
        "کامیاران",
        "بیجار",
        "دیواندره",
        "دهگلان",
        "سروآباد",
        "سریش‌آباد",
        "دلبران",
    ],
    "کرمان": [
        "کرمان",
        "سیرجان",
        "رفسنجان",
        "جیرفت",
        "بم",
        "زرند",
        "کهنوج",
        "شهربابک",
        "بافت",
        "بردسیر",
        "بروات",
        "راور",
        "ماهان",
        "عنبرآباد",
    ],
    "کرمانشاه": [
        "کرمانشاه",
        "اسلام‌آباد غرب",
        "جوانرود",
        "کنگاور",
        "سرپل ذهاب",
        "سنقر",
        "هرسین",
        "صحنه",
        "پاوه",
        "روانسر",
        "گیلانغرب",
        "قصر شیرین",
        "تازه‌آباد",
        "کرند غرب",
    ],
    "کهگیلویه و بویراحمد": [
        "یاسوج",
        "دوگنبدان",
        "دهدشت",
        "لیکک",
        "چرام",
        "لنده",
        "سی‌سخت",
        "باشت",
        "پاتاوه",
    ],
    "گلستان": [
        "گرگان",
        "گنبد کاووس",
        "بندر ترکمن",
        "علی‌آباد کتول",
        "آزادشهر",
        "کردکوی",
        "کلاله",
        "آق‌قلا",
        "مینودشت",
        "گالیکش",
        "بندر گز",
        "فاضل‌آباد",
        "گمیشان",
    ],
    "گیلان": [
        "رشت",
        "بندر انزلی",
        "لاهیجان",
        "لنگرود",
        "هشتپر (تالش)",
        "آستارا",
        "صومعه‌سرا",
        "آستانه اشرفیه",
        "رودسر",
        "فومن",
        "خمام",
        "سیاهکل",
        "رضوانشهر",
        "ماسال",
        "منجیل",
        "املش",
        "رودبار",
    ],
    "لرستان": [
        "خرم‌آباد",
        "بروجرد",
        "دورود",
        "کوهدشت",
        "الیگودرز",
        "نورآباد",
        "ازنا",
        "الشتر",
        "پلدختر",
        "اشترینان",
    ],
    "مازندران": [
        "ساری",
        "بابل",
        "آمل",
        "قائم‌شهر",
        "بهشهر",
        "چالوس",
        "نکا",
        "بابلسر",
        "تنکابن",
        "نوشهر",
        "فریدونکنار",
        "رامسر",
        "جویبار",
        "محمودآباد",
        "امیرکلا",
        "نور",
        "گلوگاه",
        "عباس‌آباد",
    ],
    "مرکزی": [
        "اراک",
        "ساوه",
        "خمین",
        "محلات",
        "دلیجان",
        "شازند",
        "مأمونیه",
        "مهاجران",
        "تفرش",
        "آشتیان",
        "خنداب",
    ],
    "هرمزگان": [
        "بندرعباس",
        "میناب",
        "قشم",
        "بندر لنگه",
        "کیش",
        "حاجی‌آباد",
        "بندر کنگ",
        "پارسیان",
        "بندر جاسک",
        "بستک",
        "درگهان",
        "رودان",
    ],
    "همدان": [
        "همدان",
        "ملایر",
        "نهاوند",
        "اسدآباد",
        "تویسرکان",
        "بهار",
        "کبودرآهنگ",
        "لالجین",
        "رزن",
        "فامنین",
    ],
    "یزد": [
        "یزد",
        "میبد",
        "اردکان",
        "بافق",
        "مهریز",
        "ابرکوه",
        "اشکذر",
        "تفت",
        "حمیدیا",
        "زارچ",
        "هرات",
    ],
}


# ۱. منوی اصلی پایین صفحه
def main_menu_keyboard(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("⚡ به یه ناشناس وصلم کن!"))
    markup.row(
        types.KeyboardButton("🔍 جستجوی کاربران"),
        types.KeyboardButton("👤 پروفایل من"),
    )
    markup.row(types.KeyboardButton("👥 دعوت از دوستان"))
    if is_admin:
        markup.row(types.KeyboardButton("🎛 پنل مدیریت ادمین"))
    return markup


# ۲. منوی انتخاب نوع اتصال ناشناس (پایین صفحه)
def connect_filter_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🎲 جستجوی شانسی"))
    markup.row(
        types.KeyboardButton("👧 جستجوی دختر"),
        types.KeyboardButton("👦 جستجوی پسر"),
    )
    markup.row(
        types.KeyboardButton("📍 جستجوی هم‌استانی"),
        types.KeyboardButton("🎂 جستجوی هم‌سن"),
    )
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۳. منوی جستجوی لیست کاربران آنلاین
def search_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("👥 هم‌سن‌ها"),
        types.KeyboardButton("📍 هم‌استانی‌ها"),
    )
    markup.row(
        types.KeyboardButton("🔥 محبوب‌ترین‌ها"),
        types.KeyboardButton("🆕 کاربران جدید"),
    )
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۴. کیبورد حین چت فعال
def chatting_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("⏭ هم‌صحبت بعدی"),
        types.KeyboardButton("❌ پایان مکالمه"),
    )
    markup.row(
        types.KeyboardButton("👤 مشاهده پروفایل"),
        types.KeyboardButton("❤️ لایک هم‌صحبت"),
    )
    markup.row(
        types.KeyboardButton("💣 ارسال عکس تایم‌دار"),
        types.KeyboardButton("🔗 اشتراک‌گذاری آیدی"),
    )
    markup.row(types.KeyboardButton("⚠️ گزارش تخلف"))
    return markup


# ۵. کیبورد صف انتظار
def waiting_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("⛔ انصراف از جستجو"))
    return markup


# ۶. کیبورد مدیریت پروفایل من
def profile_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("✏️ تغییر نام"),
        types.KeyboardButton("📝 ثبت بیوگرافی"),
    )
    markup.row(
        types.KeyboardButton("✏️ تغییر سن"),
        types.KeyboardButton("✏️ تغییر جنسیت"),
    )
    markup.row(
        types.KeyboardButton("✏️ تغییر شهر/استان"),
        types.KeyboardButton("📸 تغییر عکس"),
    )
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۷. کیبورد جنسیت
def gender_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("پسر 👦"), types.KeyboardButton("دختر 👧"))
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۸. کیبورد تک‌دکمه بازگشت
def back_only_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۹. بازه‌های سنی (۹ تا ۶۰ سال)
def age_ranges_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("۹ تا ۱۳"), types.KeyboardButton("۱۴ تا ۱۷")
    )
    markup.row(
        types.KeyboardButton("۱۸ تا ۲۲"), types.KeyboardButton("۲۳ تا ۲۸")
    )
    markup.row(
        types.KeyboardButton("۲۹ تا ۳۵"), types.KeyboardButton("۳۶ تا ۵۰")
    )
    markup.row(types.KeyboardButton("۵۱ تا ۶۰"))
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


def specific_ages_keyboard(start_age, end_age):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for a in range(start_age, end_age + 1):
        row.append(types.KeyboardButton(f"سن {a}"))
        if len(row) == 4:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۱۰. کیبورد کامل ۳۱ استان ایران (۳ ستونی بدون کلمه اضافه استان)
def provinces_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    provs = sorted(list(IRAN_PROVINCES.keys()))
    row = []
    for p in provs:
        row.append(types.KeyboardButton(p))
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۱۱. کیبورد تمام شهرهای استان انتخاب‌شده (۳ ستونی)
def cities_keyboard(province_name):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cities = IRAN_PROVINCES.get(province_name, ["مرکز استان"])
    row = []
    for c in cities:
        row.append(types.KeyboardButton(f"شهر {c}"))
        if len(row) == 3:
            markup.row(*row)
            row = []
    if row:
        markup.row(*row)
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ۱۲. کیبورد انتخاب وضعیت عکس پروفایل
def photo_choice_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("📸 استفاده از عکس تلگرامم"))
    markup.row(types.KeyboardButton("🖼 ارسال یک عکس جدید"))
    markup.row(types.KeyboardButton("🚫 بدون عکس (آواتار پیش‌فرض)"))
    markup.row(types.KeyboardButton("🔙 بازگشت"))
    return markup


# ==================== ۱۳. کیبوردهای پنل مدیریت ادمین ====================

def admin_reply_keyboard():
    """کیبورد پایین صفحه مخصوص ادمین"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("👥 لیست تمام کاربران"),
        types.KeyboardButton("🟢 چت‌های زنده الان"),
    )
    markup.row(
        types.KeyboardButton("📊 آمار زنده ربات"),
        types.KeyboardButton("🔍 جستجوی کاربر"),
    )
    markup.row(
        types.KeyboardButton("📢 پیام همگانی"),
        types.KeyboardButton("🚫 لیست مسدودها"),
    )
    markup.row(types.KeyboardButton("🏠 خروج از پنل مدیریت"))
    return markup


def admin_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ انصراف"))
    return markup


def admin_home_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("👥 لیست تمام کاربران (چت‌ها و مدیا)", callback_data="adm_users:0"))
    kb.add(
        types.InlineKeyboardButton("🟢 چت‌های زنده الان", callback_data="adm_live"),
        types.InlineKeyboardButton("📊 آمار زنده ربات", callback_data="adm_stats"),
    )
    kb.add(
        types.InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="adm_search"),
        types.InlineKeyboardButton("🚫 لیست مسدودها", callback_data="adm_banned"),
    )
    kb.add(types.InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="adm_broadcast"))
    return kb


def admin_users_list_inline(users, total, page, per_page=10):
    kb = types.InlineKeyboardMarkup(row_width=1)
    total_pages = max(1, math.ceil(total / per_page))

    for u in users:
        g_icon = "👦" if u.get("gender") == "پسر" else ("👧" if u.get("gender") == "دختر" else "👤")
        st_icon = "🟢" if u.get("status") == "chatting" else ("🔎" if u.get("status") == "waiting" else "⚪️")
        ban_icon = "🚫" if u.get("is_banned") else ""
        name = (u.get("name") or "ناشناس")[:14]
        p_cnt = u.get("partners_count", 0)
        m_cnt = u.get("msg_count", 0)

        btn_text = f"{st_icon}{ban_icon} {g_icon} {name} | 👥 {p_cnt} مخاطب | 💬 {m_cnt} پیام"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"adm_u:{u['user_id']}:{page}"))

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ قبلی", callback_data=f"adm_users:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * per_page < total:
        nav.append(types.InlineKeyboardButton("بعدی ➡️", callback_data=f"adm_users:{page + 1}"))

    kb.row(*nav)
    kb.add(types.InlineKeyboardButton("🔙 منوی اصلی پنل", callback_data="adm_home"))
    return kb


def admin_user_detail_inline(user, partners, back_page=0):
    kb = types.InlineKeyboardMarkup(row_width=2)
    uid = user["user_id"]

    kb.add(
        types.InlineKeyboardButton("🖼 عکس پروفایل", callback_data=f"adm_uphoto:{uid}"),
        types.InlineKeyboardButton("📂 کل عکس و فیلم‌هایش", callback_data=f"adm_umedia:{uid}"),
    )

    ban_btn = types.InlineKeyboardButton(
        "🔓 رفع مسدودی" if user.get("is_banned") else "🚫 مسدود کردن",
        callback_data=f"adm_toggle_ban:{uid}:{back_page}",
    )
    kb.add(ban_btn)

    if user.get("status") == "chatting" and user.get("partner_id"):
        pid = user["partner_id"]
        kb.add(
            types.InlineKeyboardButton("🟢 مشاهده چت الان", callback_data=f"adm_chat:{uid}:{pid}:0"),
            types.InlineKeyboardButton("✂️ قطع چت الان", callback_data=f"adm_kick:{uid}:{back_page}"),
        )

    if partners:
        kb.add(types.InlineKeyboardButton("👇 با این افراد چت کرده (بزن روش تا چت و مدیا بیاد) 👇", callback_data="noop"))
        for p in partners[:20]:
            p_id = p["partner_id"]
            p_name = (p.get("name") or "ناشناس")[:14]
            p_cid = p.get("custom_id") or p_id
            total_m = p.get("total_messages", 0)
            media_m = p.get("media_count", 0)

            label = f"💬 با {p_name} ({p_cid}) ⬅️ {total_m} پیام | 🎬 {media_m} مدیا"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"adm_chat:{uid}:{p_id}:0"))
    else:
        kb.add(types.InlineKeyboardButton("📭 هنوز با هیچ‌کس چت نکرده است", callback_data="noop"))

    kb.add(types.InlineKeyboardButton("🔙 بازگشت به لیست کاربران", callback_data=f"adm_users:{back_page}"))
    return kb


def admin_conversation_inline(u1, u2, page, total, per_page=15):
    kb = types.InlineKeyboardMarkup(row_width=2)
    total_pages = max(1, math.ceil(total / per_page))

    kb.add(
        types.InlineKeyboardButton("🎬 ارسال تمام عکس‌ها، فیلم‌ها و ویس‌های این چت", callback_data=f"adm_media:{u1}:{u2}")
    )

    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ پیام‌های جدیدتر", callback_data=f"adm_chat:{u1}:{u2}:{page - 1}"))
    nav.append(types.InlineKeyboardButton(f"📄 صفحه {page + 1}/{total_pages}", callback_data="noop"))
    if (page + 1) * per_page < total:
        nav.append(types.InlineKeyboardButton("پیام‌های قدیمی‌تر ➡️", callback_data=f"adm_chat:{u1}:{u2}:{page + 1}"))
    kb.row(*nav)

    kb.add(
        types.InlineKeyboardButton("🔙 پروفایل نفر اول", callback_data=f"adm_u:{u1}:0"),
        types.InlineKeyboardButton("🔙 پروفایل نفر دوم", callback_data=f"adm_u:{u2}:0"),
    )
    kb.add(types.InlineKeyboardButton("🔄 رفرش چت", callback_data=f"adm_chat:{u1}:{u2}:{page}"))
    kb.add(types.InlineKeyboardButton("👥 لیست کل کاربران", callback_data="adm_users:0"))
    return kb