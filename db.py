import os
import secrets
import string
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ایجاد استخر اتصال (Connection Pool) برای سرعت فوق‌العاده بالا و حذف تاخیر
db_pool = psycopg2.pool.ThreadedConnectionPool(1, 20, DATABASE_URL)


def get_conn():
    return db_pool.getconn()


def put_conn(conn):
    db_pool.putconn(conn)


def generate_custom_id():
    chars = string.ascii_letters + string.digits
    return "user_" + "".join(secrets.choice(chars) for _ in range(8))


def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        # جدول اصلی کاربران
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anon_users (
                user_id BIGINT PRIMARY KEY,
                custom_id VARCHAR(32) UNIQUE,
                name VARCHAR(64) DEFAULT NULL,
                gender VARCHAR(10) DEFAULT NULL,
                age INT DEFAULT NULL,
                province VARCHAR(50) DEFAULT NULL,
                city VARCHAR(50) DEFAULT NULL,
                photo_file_id TEXT DEFAULT NULL,
                status VARCHAR(20) DEFAULT 'idle',
                search_filter VARCHAR(30) DEFAULT 'any',
                partner_id BIGINT DEFAULT NULL,
                state VARCHAR(50) DEFAULT 'main_menu',
                prev_state VARCHAR(50) DEFAULT 'main_menu',
                is_banned BOOLEAN DEFAULT FALSE,
                girl_search_count INT DEFAULT 0,
                girl_search_reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        alter_queries = [
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS search_filter VARCHAR(30) DEFAULT 'any';",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS prev_state VARCHAR(50) DEFAULT 'main_menu';",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS girl_search_count INT DEFAULT 0;",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS girl_search_reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        ]
        for q in alter_queries:
            cur.execute(q)

        # جدول گزارش تخلف کاربران (برای شمارش ۴ گزارش یکتا)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_reports (
                reporter_id BIGINT,
                reported_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (reporter_id, reported_id)
            );
        """)

        # جدول لاگ تمام چت‌ها و عکس‌ها برای ادمین
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id SERIAL PRIMARY KEY,
                sender_id BIGINT,
                receiver_id BIGINT,
                content_type VARCHAR(20),
                content TEXT,
                caption TEXT,
                is_timed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cur.close()
        print("🚀 دیتابیس با سیستم پرسرعت Pool آماده به کار است!")
    finally:
        put_conn(conn)


def get_user(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM anon_users WHERE user_id = %s;", (user_id,))
        user = cur.fetchone()
        cur.close()
        return user
    finally:
        put_conn(conn)


def get_user_by_custom_id(custom_id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        clean_id = str(custom_id).replace("/", "").strip()
        if clean_id.isdigit():
            cur.execute(
                "SELECT * FROM anon_users WHERE custom_id = %s OR user_id = %s;",
                (clean_id, int(clean_id)),
            )
        else:
            cur.execute(
                "SELECT * FROM anon_users WHERE custom_id = %s;", (clean_id,)
            )
        user = cur.fetchone()
        cur.close()
        return user
    finally:
        put_conn(conn)


def add_or_update_user(user_id, **kwargs):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id FROM anon_users WHERE user_id = %s;", (user_id,)
        )
        exists = cur.fetchone()

        if not exists:
            cid = generate_custom_id()
            cur.execute(
                """
                INSERT INTO anon_users (user_id, custom_id, last_seen)
                VALUES (%s, %s, CURRENT_TIMESTAMP);
            """,
                (user_id, cid),
            )

        if kwargs:
            set_clauses = [f"{k} = %s" for k in kwargs.keys()]
            values = list(kwargs.values()) + [user_id]
            query = f"UPDATE anon_users SET {', '.join(set_clauses)}, last_seen = CURRENT_TIMESTAMP WHERE user_id = %s;"
            cur.execute(query, tuple(values))
        else:
            cur.execute(
                "UPDATE anon_users SET last_seen = CURRENT_TIMESTAMP WHERE user_id = %s;",
                (user_id,),
            )

        conn.commit()
        cur.close()
    finally:
        put_conn(conn)


def set_user_state(user_id, new_state):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE anon_users 
            SET prev_state = state, state = %s, last_seen = CURRENT_TIMESTAMP 
            WHERE user_id = %s;
        """,
            (new_state, user_id),
        )
        conn.commit()
        cur.close()
    finally:
        put_conn(conn)


def add_user_report(reporter_id, reported_id):
    """
    ثبت گزارش جدید از یک کاربر علیه کاربر دیگر.
    برمی‌گرداند: (آیا_جدید_بود: bool, تعداد_کل_گزارش‌های_یکتا: int)
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM user_reports WHERE reporter_id = %s AND reported_id = %s;",
            (reporter_id, reported_id),
        )
        already = cur.fetchone() is not None

        if not already:
            cur.execute(
                "INSERT INTO user_reports (reporter_id, reported_id) VALUES (%s, %s);",
                (reporter_id, reported_id),
            )
            conn.commit()

        cur.execute(
            "SELECT COUNT(*) FROM user_reports WHERE reported_id = %s;",
            (reported_id,),
        )
        total_count = cur.fetchone()[0]
        cur.close()
        return (not already), total_count
    finally:
        put_conn(conn)


def check_and_use_girl_search(user_id, max_per_hour=5):
    """
    بررسی سهمیه ساعتی جستجوی دختر (۵ بار در هر ساعت):
    - اگر ۱ ساعت از اولین جستجوی دوره گذشته باشد، سهمیه ریست می‌شود.
    - برمی‌گرداند: (مجاز_است: bool, تعداد_باقی‌مانده: int, دقیقه_تا_تمدید: int)
    """
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT 
                COALESCE(girl_search_count, 0) AS cnt,
                girl_search_reset_at,
                EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - COALESCE(girl_search_reset_at, CURRENT_TIMESTAMP - INTERVAL '2 hours'))) AS elapsed_sec
            FROM anon_users
            WHERE user_id = %s;
        """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            return False, 0, 60

        elapsed = float(row["elapsed_sec"] or 0)
        cnt = int(row["cnt"] or 0)

        if elapsed >= 3600 or row["girl_search_reset_at"] is None:
            cur.execute(
                """
                UPDATE anon_users
                SET girl_search_count = 1, girl_search_reset_at = CURRENT_TIMESTAMP
                WHERE user_id = %s;
            """,
                (user_id,),
            )
            conn.commit()
            cur.close()
            return True, max_per_hour - 1, 60

        if cnt >= max_per_hour:
            rem_minutes = max(1, int((3600 - elapsed) // 60) + 1)
            cur.close()
            return False, 0, rem_minutes

        new_cnt = cnt + 1
        cur.execute(
            """
            UPDATE anon_users
            SET girl_search_count = %s
            WHERE user_id = %s;
        """,
            (new_cnt, user_id),
        )
        conn.commit()
        rem_minutes = max(1, int((3600 - elapsed) // 60) + 1)
        cur.close()
        return True, max_per_hour - new_cnt, rem_minutes
    finally:
        put_conn(conn)


def find_match(user_id, filter_type="any"):
    """پیدا کردن هم‌صحبت بر اساس فیلتر انتخابی (شانسی، دختر، پسر)"""
    user = get_user(user_id)
    if not user:
        return None

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT * FROM anon_users 
            WHERE status = 'waiting' AND user_id != %s AND is_banned = FALSE
        """
        params = [user_id]

        if filter_type == "girl":
            query += " AND gender = 'دختر'"
        elif filter_type == "boy":
            query += " AND gender = 'پسر'"

        query += " ORDER BY last_seen DESC LIMIT 1;"
        cur.execute(query, tuple(params))
        partner = cur.fetchone()

        if partner:
            partner_id = partner["user_id"]
            cur.execute(
                "UPDATE anon_users SET status = 'chatting', partner_id = %s WHERE user_id = %s;",
                (partner_id, user_id),
            )
            cur.execute(
                "UPDATE anon_users SET status = 'chatting', partner_id = %s WHERE user_id = %s;",
                (user_id, partner_id),
            )
            conn.commit()
            cur.close()
            return partner_id
        else:
            cur.execute(
                "UPDATE anon_users SET status = 'waiting', search_filter = %s, partner_id = NULL WHERE user_id = %s;",
                (filter_type, user_id),
            )
            conn.commit()
            cur.close()
            return None
    finally:
        put_conn(conn)


def connect_two_users_directly(user1_id, user2_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE anon_users SET status = 'chatting', partner_id = %s WHERE user_id = %s;",
            (user2_id, user1_id),
        )
        cur.execute(
            "UPDATE anon_users SET status = 'chatting', partner_id = %s WHERE user_id = %s;",
            (user1_id, user2_id),
        )
        conn.commit()
        cur.close()
    finally:
        put_conn(conn)


def disconnect_user(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT partner_id FROM anon_users WHERE user_id = %s;", (user_id,)
        )
        row = cur.fetchone()
        partner_id = row[0] if row else None

        cur.execute(
            "UPDATE anon_users SET status = 'idle', partner_id = NULL WHERE user_id = %s;",
            (user_id,),
        )
        if partner_id:
            cur.execute(
                "UPDATE anon_users SET status = 'idle', partner_id = NULL WHERE user_id = %s;",
                (partner_id,),
            )

        conn.commit()
        cur.close()
        return partner_id
    finally:
        put_conn(conn)


def log_chat_message(
    sender_id, receiver_id, content_type, content, caption=None, is_timed=False
):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO chat_logs (sender_id, receiver_id, content_type, content, caption, is_timed)
            VALUES (%s, %s, %s, %s, %s, %s);
        """,
            (sender_id, receiver_id, content_type, content, caption, is_timed),
        )
        conn.commit()
        cur.close()
    finally:
        put_conn(conn)


def get_all_user_ids():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM anon_users WHERE is_banned = FALSE;")
        ids = [r[0] for r in cur.fetchall()]
        cur.close()
        return ids
    finally:
        put_conn(conn)


# ==================== توابع خواندنی پنل مدیریت ادمین ====================

def get_bot_stats():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM anon_users;")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM anon_users WHERE status = 'chatting';")
        chatting_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM anon_users WHERE status = 'waiting';")
        waiting_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM anon_users WHERE is_banned = TRUE;")
        banned_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chat_logs;")
        total_msgs = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM chat_logs WHERE content_type != 'text';"
        )
        total_media = cur.fetchone()[0]
        cur.close()
        return {
            "total_users": total_users,
            "chatting_users": chatting_users,
            "waiting_users": waiting_users,
            "banned_users": banned_users,
            "total_msgs": total_msgs,
            "total_media": total_media,
        }
    finally:
        put_conn(conn)


def get_all_users_for_admin(limit=100):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT user_id, custom_id, name, gender, age, province, city, is_banned
            FROM anon_users
            ORDER BY last_seen DESC
            LIMIT %s;
        """,
            (limit,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_users_by_gender_for_admin(gender, limit=100):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT user_id, custom_id, name, gender, age, province, city, is_banned
            FROM anon_users
            WHERE gender = %s
            ORDER BY last_seen DESC
            LIMIT %s;
        """,
            (gender, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_user_chat_partners(target_user_id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT DISTINCT
                CASE WHEN sender_id = %s THEN receiver_id ELSE sender_id END AS partner_uid
            FROM chat_logs
            WHERE sender_id = %s OR receiver_id = %s;
        """,
            (target_user_id, target_user_id, target_user_id),
        )
        partner_rows = cur.fetchall()
        partners = []
        for r in partner_rows:
            pid = r["partner_uid"]
            if not pid:
                continue
            cur.execute(
                "SELECT user_id, custom_id, name FROM anon_users WHERE user_id = %s;",
                (pid,),
            )
            u = cur.fetchone()
            if u:
                partners.append(u)
            else:
                partners.append(
                    {"user_id": pid, "custom_id": str(pid), "name": f"کاربر {pid}"}
                )
        cur.close()
        return partners
    finally:
        put_conn(conn)


def get_full_conversation(user1_id, user2_id, limit=80):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT * FROM (
                SELECT * FROM chat_logs
                WHERE (sender_id = %s AND receiver_id = %s)
                   OR (sender_id = %s AND receiver_id = %s)
                ORDER BY created_at DESC, id DESC
                LIMIT %s
            ) sub
            ORDER BY created_at ASC, id ASC;
        """,
            (user1_id, user2_id, user2_id, user1_id, limit),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_chat_log_by_id(log_id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM chat_logs WHERE id = %s;", (log_id,))
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        put_conn(conn)


if __name__ == "__main__":
    init_db()