from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime
import random

app = Flask(__name__)

# [1] CONFIG
# ดึงค่าจาก Environment Variables บน Render
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
DATABASE_URL = os.environ.get("DATABASE_URL")

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# [2] DATABASE SYSTEM (PostgreSQL)
def Init_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    c = conn.cursor()
    # สร้างตารางสถานะผู้ใช้
    c.execute("""CREATE TABLE IF NOT EXISTS user_state (
        user_id TEXT PRIMARY KEY, 
        state TEXT, 
        step INTEGER, 
        temp TEXT)""")
    # สร้างตารางการบ้าน
    c.execute("""CREATE TABLE IF NOT EXISTS homework (
        id SERIAL PRIMARY KEY, 
        info TEXT, 
        teacher TEXT, 
        created_at TEXT)""")
    conn.commit()
    c.close()
    conn.close()

def check_and_reset_weekly(c):
    current_week = datetime.datetime.now().isocalendar()[1]
    c.execute("SELECT created_at FROM homework ORDER BY id DESC LIMIT 1")
    last_entry = c.fetchone()
    if last_entry:
        try:
            last_date_str = last_entry[0].split(" ")[0]
            last_week = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").isocalendar()[1]
            if current_week != last_week:
                c.execute("DELETE FROM homework")
                return True
        except:
            pass
    return False

# เรียกใช้งาน Database ครั้งแรก
Init_db()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    uid = event.source.user_id
    text = event.message.text
    now = datetime.datetime.now()
    today_en = now.strftime("%A")
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    c = conn.cursor()
    
    check_and_reset_weekly(c)
    conn.commit()

    c.execute("SELECT state, step, temp FROM user_state WHERE user_id = %s", (uid,))
    row = c.fetchone()
    state, step, temp = (row[0], row[1], row[2]) if row else (None, 0, "")

    # --- [3] MENU SYSTEM ---
    if text in ["เมนู", "หน้า 1", "ยกเลิก"]:
        c.execute("DELETE FROM user_state WHERE user_id = %s", (uid,))
        conn.commit()
        menu1 = {
            "type": "bubble",
            "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "🌸 ม.2/9 Menu (1/2)", "weight": "bold", "size": "xl", "color": "#1DB446"}]},
            "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📝 แจ้งการบ้าน", "text": "แจ้งการบ้าน"}},
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📋 เช็คงานสัปดาห์นี้", "text": "เช็คงาน"}},
                {"type": "button", "style": "secondary", "color": "#555555", "action": {"type": "message", "label": "💡 วิธีใช้", "text": "วิธีใช้"}},
                {"type": "button", "style": "secondary", "action": {"type": "message", "label": "➡️ หน้า 2", "text": "หน้า 2"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Menu", contents=menu1))
        return

    elif text == "หน้า 2":
        menu2 = {
            "type": "bubble",
            "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "🎯 ระบบสุ่ม & ตาราง (2/2)", "weight": "bold", "size": "xl", "color": "#E67E22"}]},
            "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "📖 ตารางเรียนวันนี้", "text": "ตารางเรียน"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "🎲 สุ่มเลขที่", "text": "สุ่มเลขที่"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "👥 สุ่มจัดกลุ่ม", "text": "สุ่มจัดกลุ่ม"}},
                {"type": "button", "style": "secondary", "action": {"type": "message", "label": "⬅️ หน้า 1", "text": "หน้า 1"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Menu 2", contents=menu2))
        return

    # --- [4] HOMEWORK SYSTEM ---
    if text == "แจ้งการบ้าน":
        c.execute("INSERT INTO user_state (user_id, state, step, temp) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET state='HW', step=1", (uid, 'HW', 1, ""))
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 [1/2] พิมพ์ วิชา / งาน / วันส่ง"))
        conn.commit()

    elif state == "HW":
        if step == 1:
            c.execute("UPDATE user_state SET step = 2, temp = %s WHERE user_id = %s", (text, uid))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👨‍🏫 [2/2] ครูท่านไหนสั่งครับ?"))
        elif step == 2:
            time_now = now.strftime("%Y-%m-%d %H:%M")
            c.execute("INSERT INTO homework (info, teacher, created_at) VALUES (%s, %s, %s)", (temp, text, time_now))
            c.execute("DELETE FROM user_state WHERE user_id = %s", (uid,))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกข้อมูลเรียบร้อยแล้ว (เช็คได้ที่เมนู 'เช็คงาน')"))
        conn.commit()

    elif text == "เช็คงาน":
        days_map = {"Monday": "วันจันทร์", "Tuesday": "วันอังคาร", "Wednesday": "วันพุธ", "Thursday": "วันพฤหัสบดี", "Friday": "วันศุกร์"}
        c.execute("SELECT info, created_at FROM homework")
        all_hw = c.fetchall()
        report = "📊 สรุปการบ้านสัปดาห์นี้\n"
        found = False
        for en, th in days_map.items():
            header = f"\n📌 {th}" + (" (วันนี้)" if en == today_en else "")
            day_content = ""
            for hw_info, created_at in all_hw:
                db_day = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M").strftime("%A")
                if db_day == en:
                    day_content += f"- {hw_info}\n"
                    found = True
            if day_content: report += header + "\n" + day_content
        if not found: report += "\n✨ ยังไม่มีข้อมูล/ยังไม่ได้สั่งจ้า"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))

    # --- [5] RANDOM & OTHERS ---
    elif text == "สุ่มจัดกลุ่ม":
        c.execute("INSERT INTO user_state (user_id, state, step, temp) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET state='GROUP', step=1", (uid, 'GROUP', 1, ""))
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👥 อยากแบ่งเป็นกี่กลุ่มครับ? (พิมพ์ตัวเลขกลุ่ม)"))
        conn.commit()

    elif state == "GROUP":
        try:
            num_groups = int(text)
            students = list(range(1, 41))
            random.shuffle(students)
            res = "🎲 ผลการสุ่มจัดกลุ่ม ม.2/9\n"
            for i in range(num_groups):
                group_members = students[i::num_groups]
                res += f"\nกลุ่มที่ {i+1}: " + ", ".join(map(str, sorted(group_members)))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
        except:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ กรุณาพิมพ์เป็นตัวเลขครับ"))
        c.execute("DELETE FROM user_state WHERE user_id = %s", (uid,))
        conn.commit()

    elif text == "สุ่มเลขที่":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🎲 เลขที่ {random.randint(1, 40)}"))

    elif text == "ตารางเรียน":
        sch = {
            "Monday": "1-2: ไทย, 3-4: วิทย์, 5: คณิต, 7: คณิต, 8: เลือก",
            "Tuesday": "1-2: สังคม, 3: คณิต, 4: ประวัติ, 5: ประวัติ, 7: วิทย์, 8: ชุมนุม",
            "Wednesday": "1-2: คณิต, 3: ไทย, 4: อังกฤษ, 5: สังคม, 7-8: ศิลปะ",
            "Thursday": "1-2: วิทย์, 3: สังคม, 4: ไทย, 5: คณิต, 7-8: การงาน",
            "Friday": "1-2: พละ, 3: คณิต, 4: ไทย, 5: สุขศึกษา, 7: แนะแนว"
        }
        res = f"📅 ตารางเรียนวันนี้ ({today_en}):\n{sch.get(today_en, 'วันหยุดพักผ่อนครับ')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    elif text == "วิธีใช้":
        help_text = "📖 สรุปวิธีใช้งานบอท ม.2/9\n\n📝 แจ้งการบ้าน: กดแล้วพิมพ์ 'วิชา/งาน/วันส่ง' และระบุชื่อครู\n📋 เช็คงาน: ดูสรุปงานสัปดาห์นี้ (ล้างทุกวันอาทิตย์อัตโนมัติ)\n🎲 สุ่มเลขที่: สุ่มเพื่อน 1 คนจากเลขที่ 1-40\n👥 สุ่มจัดกลุ่ม: ระบุจำนวนกลุ่มที่ต้องการ แล้วบอทจะแบ่งเลขที่ให้\n📅 ตารางเรียน: ดูวิชาเรียนหลักของวันนี้\n\n⚠️ หากบอทค้างหรือพิมพ์ผิด ให้พิมพ์ 'ยกเลิก' เพื่อเริ่มใหม่"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))

    c.close()
    conn.close()

if __name__ == "__main__":
    app.run(port=5000)

