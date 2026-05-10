import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
from pymongo import MongoClient  # ใช้ MongoDB แทน psycopg2
import datetime
import random

app = Flask(__name__)

# [1] CONFIG ดึงค่าจาก Environment Variables บน Render
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
MONGO_URI = os.environ.get("MONGO_URI") # ต้องตั้งค่าใน Render ก่อน

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# [2] DATABASE SYSTEM (MongoDB Atlas)
client = MongoClient(MONGO_URI)
db = client['m29_smart_classroom']
homework_col = db['homework']       # เก็บข้อมูลการบ้าน
user_col = db['user_state']         # เก็บสถานะผู้ใช้ (state, step, temp)

def check_and_reset_weekly():
    """ ระบบล้างข้อมูลการบ้านทุกสัปดาห์ (วันอาทิตย์) """
    current_week = datetime.datetime.now().isocalendar()[1]
    last_entry = homework_col.find_one(sort=[("_id", -1)])
    if last_entry:
        try:
            last_date_str = last_entry['created_at'].split(" ")[0]
            last_week = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").isocalendar()[1]
            if current_week != last_week:
                homework_col.delete_many({}) # ลบทั้งหมดถ้าข้ามสัปดาห์
                return True
        except: pass
    return False

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
    
    # ตรวจสอบการรีเซ็ตรายสัปดาห์
    check_and_reset_weekly()

    # ดึงสถานะผู้ใช้จาก MongoDB
    user_data = user_col.find_one({"user_id": uid})
    state = user_data.get('state') if user_data else None
    step = user_data.get('step', 0) if user_data else 0
    temp = user_data.get('temp', "") if user_data else ""

    # --- [3] MENU SYSTEM ---
    if text in ["เมนู", "หน้า 1", "ยกเลิก"]:
        user_col.delete_one({"user_id": uid})
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
                   {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "📚 เวนยกหนังสือ", "text": "เวนยกหนังสือ"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "👥 สุ่มจัดกลุ่ม", "text": "สุ่มจัดกลุ่ม"}},
                {"type": "button", "style": "secondary", "action": {"type": "message", "label": "⬅️ หน้า 1", "text": "หน้า 1"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Menu 2", contents=menu2))
        return

    # --- [4] HOMEWORK SYSTEM (ย้ายมาใช้ MongoDB) ---
    if text == "แจ้งการบ้าน":
        user_col.update_one({"user_id": uid}, {"$set": {"state": "HW", "step": 1, "temp": ""}}, upsert=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 [1/2] พิมพ์ วิชา / งาน / วันส่ง"))

    elif state == "HW":
        if step == 1:
            user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👨‍🏫 [2/2] ครูท่านไหนสั่งครับ?"))
        elif step == 2:
            time_now = now.strftime("%Y-%m-%d %H:%M")
            homework_col.insert_one({"info": temp, "teacher": text, "created_at": time_now})
            user_col.delete_one({"user_id": uid})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกข้อมูลเรียบร้อยแล้ว (เช็คได้ที่เมนู 'เช็คงาน')"))

    elif text == "เช็คงาน":
        days_map = {"Monday": "วันจันทร์", "Tuesday": "วันอังคาร", "Wednesday": "วันพุธ", "Thursday": "วันพฤหัสบดี", "Friday": "วันศุกร์"}
        all_hw = list(homework_col.find())
        report = "📊 สรุปการบ้านสัปดาห์นี้\n"
        found = False
        for en, th in days_map.items():
            header = f"\n📌 {th}" + (" (วันนี้)" if en == today_en else "")
            day_content = ""
            for hw in all_hw:
                db_day = datetime.datetime.strptime(hw['created_at'], "%Y-%m-%d %H:%M").strftime("%A")
                if db_day == en:
                    day_content += f"- {hw['info']} (ครู{hw['teacher']})\n"
                    found = True
            if day_content: report += header + "\n" + day_content
        if not found: report += "\n✨ ยังไม่มีข้อมูล/ยังไม่ได้สั่งจ้า"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))

    # --- [5] RANDOM & OTHERS ---
    elif text == "สุ่มจัดกลุ่ม":
        user_col.update_one({"user_id": uid}, {"$set": {"state": "GROUP", "step": 1}}, upsert=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👥 อยากแบ่งเป็นกี่กลุ่มครับ? (พิมพ์ตัวเลขกลุ่ม)"))

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
        user_col.delete_one({"user_id": uid})

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

    elif text == "ติดต่อแอดมิน":
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="📱 หากมีปัญหาการใช้งานหรือต้องการสอบถามเพิ่มเติม\nสามารถติดต่อแอดมินได้ที่: [ใส่ชื่อหรือไอดีของคุณตรงนี้porshe3012] ครับ"))
    

if __name__ == "__main__":
    # รันบนพอร์ต 5000 ตามที่ Render ต้องการ
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
