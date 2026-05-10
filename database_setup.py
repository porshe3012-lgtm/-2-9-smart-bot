import sqlite3

def init_db():
    conn = sqlite3.connect('classroom.db')
    cursor = conn.cursor()

    # ตารางการบ้าน
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS homework (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT,
        details TEXT,
        status TEXT DEFAULT 'pending'
    )''')

    # ตารางเวรยกหนังสือ (เริ่มที่ 0)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS book_duty (
        id INTEGER PRIMARY KEY,
        last_student_index INTEGER
    )''')
    cursor.execute('INSERT OR IGNORE INTO book_duty (id, last_student_index) VALUES (1, 0)')

    conn.commit()
    conn.close()
    print("✅ สร้างฐานข้อมูล classroom.db เรียบร้อย!")

if __name__ == "__main__":
    init_db()

