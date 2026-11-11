import db

conn = db.get_connection()
cur = conn.cursor()

# حذف جدول‌های قبلی جهت نوسازی کامل ساختار
cur.execute("DROP TABLE IF EXISTS anon_users CASCADE;")
cur.execute("DROP TABLE IF EXISTS chat_logs CASCADE;")

conn.commit()
cur.close()
conn.close()

print("🗑 جدول‌های قدیمی پاک شدند. حالا در حال ساخت جدول‌های نو...")
db.init_db()
print("✨ دیتابیس با تمام ستون‌ها نوسازی شد!")