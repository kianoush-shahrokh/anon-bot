import os
import secrets
import string
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# ایجاد استخر اتصال (Connection Pool) برای سرعت بالا و حذف تاخیر
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
                name VARCHAR(64) DEFAULT 'ناشناس',
                gender VARCHAR(10) DEFAULT NULL,
                age INT DEFAULT NULL,
                province VARCHAR(50) DEFAULT NULL,
                city VARCHAR(50) DEFAULT NULL,
                bio VARCHAR(200) DEFAULT 'بدون بیوگرافی',
                photo_file_id TEXT DEFAULT NULL,
                likes_count INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'idle',
                search_filter VARCHAR(30) DEFAULT 'any',
                partner_id BIGINT DEFAULT NULL,
                state VARCHAR(50) DEFAULT 'main_menu',
                prev_state VARCHAR(50) DEFAULT 'main_menu',
                is_banned BOOLEAN DEFAULT FALSE,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # اضافه کردن خودکار ستون‌های جدید اگر جدول از قبل وجود داشته باشد
        alter_queries = [
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS bio VARCHAR(200) DEFAULT 'بدون بیوگرافی';",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS search_filter VARCHAR(30) DEFAULT 'any';",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS prev_state VARCHAR(50) DEFAULT 'main_menu';",
            "ALTER TABLE anon_users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        ]
        for q in alter_queries:
            cur.execute(q)

        # جدول لایک‌ها (برای جلوگیری از لایک تکراری)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_likes (
                liker_id BIGINT,
                liked_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (liker_id, liked_id)
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
        print("🚀 دیتابیس نئون با سیستم پرسرعت Pool آماده به کار است!")
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
        cur.execute(
            "SELECT * FROM anon_users WHERE custom_id = %s OR user_id::text = %s;", 
            (custom_id, custom_id.strip())
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


def like_user(liker_id, liked_id):
    if liker_id == liked_id:
        return False
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM user_likes WHERE liker_id = %s AND liked_id = %s;",
            (liker_id, liked_id),
        )
        if cur.fetchone():
            cur.close()
            return False

        cur.execute(
            "INSERT INTO user_likes (liker_id, liked_id) VALUES (%s, %s);",
            (liker_id, liked_id),
        )
        cur.execute(
            "UPDATE anon_users SET likes_count = likes_count + 1 WHERE user_id = %s;",
            (liked_id,),
        )
        conn.commit()
        cur.close()
        return True
    finally:
        put_conn(conn)


def find_match(user_id, filter_type="any"):
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
        elif filter_type == "same_prov" and user.get("province"):
            query += " AND province = %s"
            params.append(user["province"])
        elif filter_type == "same_age" and user.get("age"):
            query += " AND ABS(age - %s) <= 2"
            params.append(user["age"])

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


def search_users_list(mode, user):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        uid = user["user_id"]

        if mode == "same_age":
            cur.execute(
                """
                SELECT *, (last_seen >= NOW() - INTERVAL '15 minutes') AS is_online
                FROM anon_users
                WHERE ABS(age - %s) <= 1 AND user_id != %s AND is_banned = FALSE
                ORDER BY last_seen DESC LIMIT 12;
            """,
                (user.get("age") or 20, uid),
            )
        elif mode == "same_prov":
            cur.execute(
                """
                SELECT *, (last_seen >= NOW() - INTERVAL '15 minutes') AS is_online
                FROM anon_users
                WHERE province = %s AND user_id != %s AND is_banned = FALSE
                ORDER BY last_seen DESC LIMIT 12;
            """,
                (user.get("province") or "تهران", uid),
            )
        elif mode == "top_likes":
            cur.execute(
                """
                SELECT *, (last_seen >= NOW() - INTERVAL '15 minutes') AS is_online
                FROM anon_users
                WHERE user_id != %s AND is_banned = FALSE
                ORDER BY likes_count DESC, last_seen DESC LIMIT 12;
            """,
                (uid,),
            )
        else:
            cur.execute(
                """
                SELECT *, (last_seen >= NOW() - INTERVAL '15 minutes') AS is_online
                FROM anon_users
                WHERE user_id != %s AND is_banned = FALSE
                ORDER BY last_seen DESC LIMIT 12;
            """,
                (uid,),
            )

        rows = cur.fetchall()
        cur.close()
        return rows
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


# ==================== توابع پیشرفته پنل مدیریت ====================

def get_bot_stats():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS total FROM anon_users;")
        total_users = cur.fetchone()["total"]

        cur.execute("SELECT COUNT(*) AS chatting FROM anon_users WHERE status = 'chatting';")
        chatting_users = cur.fetchone()["chatting"]

        cur.execute("SELECT COUNT(*) AS waiting FROM anon_users WHERE status = 'waiting';")
        waiting_users = cur.fetchone()["waiting"]

        cur.execute("SELECT COUNT(*) AS banned FROM anon_users WHERE is_banned = TRUE;")
        banned_users = cur.fetchone()["banned"]

        cur.execute("SELECT COUNT(*) AS total_msgs FROM chat_logs;")
        total_msgs = cur.fetchone()["total_msgs"]

        cur.execute("SELECT COUNT(*) AS total_media FROM chat_logs WHERE content_type != 'text';")
        total_media = cur.fetchone()["total_media"]

        cur.close()
        return {
            "total_users": total_users,
            "chatting_users": chatting_users,
            "waiting_users": waiting_users,
            "banned_users": banned_users,
            "total_msgs": total_msgs,
            "total_media": total_media
        }
    finally:
        put_conn(conn)


def get_paginated_users(limit=10, offset=0):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS cnt FROM anon_users;")
        total = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT u.*,
                   (SELECT COUNT(DISTINCT CASE WHEN m.sender_id = u.user_id THEN m.receiver_id ELSE m.sender_id END)
                    FROM chat_logs m WHERE m.sender_id = u.user_id OR m.receiver_id = u.user_id) AS partners_count,
                   (SELECT COUNT(*) FROM chat_logs m WHERE m.sender_id = u.user_id OR m.receiver_id = u.user_id) AS msg_count
            FROM anon_users u
            ORDER BY u.last_seen DESC NULLS LAST
            LIMIT %s OFFSET %s;
        """, (limit, offset))
        rows = cur.fetchall()
        cur.close()
        return rows, total
    finally:
        put_conn(conn)


def get_user_chat_partners(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                m.other_id AS partner_id,
                COALESCE(u.name, 'کاربر ناشناس') AS name,
                COALESCE(u.custom_id, CAST(m.other_id AS TEXT)) AS custom_id,
                u.gender,
                COUNT(m.id) AS total_messages,
                COUNT(CASE WHEN m.content_type != 'text' THEN 1 END) AS media_count,
                MAX(m.created_at) AS last_chat_time
            FROM (
                SELECT 
                    id,
                    CASE WHEN sender_id = %s THEN receiver_id ELSE sender_id END AS other_id,
                    content_type,
                    created_at
                FROM chat_logs
                WHERE sender_id = %s OR receiver_id = %s
            ) m
            LEFT JOIN anon_users u ON u.user_id = m.other_id
            GROUP BY m.other_id, u.name, u.custom_id, u.gender
            ORDER BY last_chat_time DESC;
        """, (user_id, user_id, user_id))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_conversation_between(u1, u2, limit=15, offset=0):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM chat_logs
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s);
        """, (u1, u2, u2, u1))
        total = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT * FROM chat_logs
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s;
        """, (u1, u2, u2, u1, limit, offset))
        rows = cur.fetchall()
        rows.reverse()
        cur.close()
        return rows, total
    finally:
        put_conn(conn)


def get_media_between(u1, u2, limit=50):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM chat_logs
            WHERE ((sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s))
              AND content_type != 'text'
              AND content IS NOT NULL
            ORDER BY created_at ASC
            LIMIT %s;
        """, (u1, u2, u2, u1, limit))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_user_all_media(user_id, limit=30):
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM chat_logs
            WHERE (sender_id = %s OR receiver_id = %s)
              AND content_type != 'text'
              AND content IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s;
        """, (user_id, user_id, limit))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_active_chats():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT u1.user_id AS u1_id, u1.name AS u1_name, u1.custom_id AS u1_pub,
                   u2.user_id AS u2_id, u2.name AS u2_name, u2.custom_id AS u2_pub
            FROM anon_users u1
            JOIN anon_users u2 ON u1.partner_id = u2.user_id
            WHERE u1.status = 'chatting' AND u1.user_id < u2.user_id;
        """)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


def get_banned_users():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM anon_users WHERE is_banned = TRUE ORDER BY last_seen DESC LIMIT 30;")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        put_conn(conn)


if __name__ == "__main__":
    init_db()