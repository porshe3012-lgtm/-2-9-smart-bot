import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
from pymongo import MongoClient
import datetime
import random

app = Flask(__name__)

# --- [1] CONFIG ---
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
MONGO_URI = os.environ.get("MONGO_URI")

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# --- [2] DATABASE SYSTEM (MongoDB Atlas) ---
client = MongoClient(MONGO_URI)
db = client['m29_smart_classroom']
homework_col = db['homework']
user_col = db['user_state']

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
                {"type": "button", "style": "primary", "color": "#E67E22", "action": {"type": "message", "label": "📢 แจ้งสอบ", "text": "แจ้งสอบ"}},
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
            "body": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "📖 ตารางเรียนวันนี้", "text": "ตารางเรียน"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "📅 ตารางสอบ", "text": "เช็คตารางสอบ"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "🎲 สุ่มเลขที่", "text": "สุ่มเลขที่"}},
                {"type": "button", "style": "primary", "color": "#E67E22", "action": {"type": "message", "label": "📚 เวนยกหนังสือ", "text": "เวนยกหนังสือ"}},
                {"type": "button", "style": "primary", "color": "#F39C12", "action": {"type": "message", "label": "👥 สุ่มจัดกลุ่ม", "text": "สุ่มจัดกลุ่ม"}},
                {"type": "button", "style": "secondary", "action": {"type": "message", "label": "⬅️ หน้า 1", "text": "หน้า 1"}}
            ]}
        }
        line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Menu 2", contents=menu2))
        return

    # --- [4] ระบบวิธีใช้, เวนยกหนังสือ, ติดต่อแอดมิน ---
    elif text == "วิธีใช้":
        how_to = (
            "📖 สรุปวิธีใช้งานบอท ม.2/9\n"
            "--------------------------\n"
            "📝 แจ้งการบ้าน: กดแล้วพิมพ์ 'วิชา/งาน/กำหนดส่ง' และระบุชื่อครู\n"
            "📋 เช็คงาน: ดูสรุปงานสัปดาห์นี้ (แยกรายวัน จ-ศ)\n"
            "🎲 สุ่มเลขที่: สุ่มเพื่อน 1 คนจากเลขที่ 1-40\n"
            "📚 เวนยกหนังสือ: สุ่มเพื่อน 2 คนมาช่วยงาน\n"
            "👥 สุ่มจัดกลุ่ม: ระบุจำนวนกลุ่มที่ต้องการ แล้วบอทจะแบ่งเลขที่ให้\n"
            "📅 ตารางเรียน: ดูวิชาเรียนตามวันจริงของวันนี้\n"
            "--------------------------\n"
            "⚠️ หากบอทค้างหรือพิมพ์ผิด ให้พิมพ์ 'ยกเลิก' เพื่อเริ่มใหม่"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=how_to))

    elif text == "เวนยกหนังสือ":
        lucky_ones = random.sample(range(1, 41), 2)
        res = f"📚 เวนยกหนังสือวันนี้\nได้แก่เลขที่: {lucky_ones[0]} และ {lucky_ones[1]}\nสู้ๆ นะเพื่อน! 💪"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    elif text == "ติดต่อแอดมิน":
        res = "📱 ติดต่อแอดมิน (พชรภัทร)\n📞 เบอร์โทร: 0954672577\n🆔 LINE ID: porshe3012\n\nสามารถพิมพ์ข้อความทิ้งไว้ได้เลยครับ!"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

    # --- [5] HOMEWORK SYSTEM (บันทึกและเช็คงานแยกวัน) ---
    elif text == "แจ้งการบ้าน":
        user_col.update_one({"user_id": uid}, {"$set": {"state": "HW", "step": 1, "temp": ""}}, upsert=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 [1/2] พิมพ์ วิชา / งาน / วันส่ง\n(อย่าลืมพิมพ์ชื่อวัน เช่น วันจันทร์ เพื่อให้ระบบแยกตารางให้ครับ)"))

    elif state == "HW":
        if step == 1:
            user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👨‍🏫 [2/2] ครูท่านไหนสั่งครับ?"))
        elif step == 2:
            time_now = now.strftime("%Y-%m-%d %H:%M")
            homework_col.insert_one({"info": temp, "teacher": text, "created_at": time_now})
            user_col.delete_one({"user_id": uid})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกเรียบร้อย! เช็คได้ที่เมนู 'เช็คงาน'"))

    # --- [5.1] EXAM SYSTEM (ระบบแจ้งสอบ) ---
    elif text == "แจ้งสอบ":
        user_col.update_one({"user_id": uid}, {"$set": {"state": "EXAM", "step": 1, "temp": ""}}, upsert=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📢 [1/2] พิมพ์ วิชา และ เรื่องที่สอบ\n(เช่น คณิต - เลขยกกำลัง)"))
        return

    elif state == "EXAM":
        if step == 1:
            # เก็บข้อมูลวิชาไว้ใน temp แล้วขยับไป step 2
            user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📅 [2/2] สอบวันไหนและคาบไหนครับ?\n(เช่น วันศุกร์ที่ 20 คาบ 3-4)"))
        
        elif step == 2:
            # บันทึกลง Database
            exam_col = db['exams'] # สร้าง collection ใหม่ชื่อ exams
            exam_col.insert_one({
                "subject_info": temp,
                "date_time": text,
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            # ลบ State ของผู้ใช้ทิ้งเพื่อให้กลับสู่สภาวะปกติ
            user_col.delete_one({"user_id": uid})
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกตารางสอบเรียบร้อยแล้ว! สู้ๆ นะทุกคน ✌️"))
        return

    elif text == "เช็คงาน":
        all_hw = list(homework_col.find())
        days = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์"]
        report = "📋 สรุปการบ้านสัปดาห์นี้\n"
        hw_by_day = {day: [] for day in days}
        
        for hw in all_hw:
            info = hw['info']
            found_day = False
            for day in days:
                if day in info:
                    hw_by_day[day].append(f"📌 {info} (ครู{hw['teacher']})")
                    found_day = True
                    break
            if not found_day:
                hw_by_day["วันจันทร์"].append(f"📌 {info} (ครู{hw['teacher']})")          
    elif text == "เช็คตารางสอบ":
         exam_col = db['exams']
        # ดึงข้อมูลสอบทั้งหมด เรียงจากใหม่ไปเก่า (ลิมิตไว้ 10 รายการล่าสุด)
        all_exams = list(exam_col.find().sort("_id", -1).limit(10))
        
        if not all_exams:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🎉 เย้! ยังไม่มีนัดหมายสอบในตอนนี้ครับ"))
        else:
            report = "📅 ตารางสอบ ม.2/9\n"
            report += "--------------------------\n"
            for ex in all_exams:
                report += f"📝 {ex['subject_info']}\n⏰ {ex['date_time']}\n"
                report += "--------------------------\n"
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))
            
        for day in days:
            report += f"\n📍 {day}\n"
            if hw_by_day[day]:
                report += "\n".join(hw_by_day[day]) + "\n"
            else:
                report += "ยังไม่มีข้อมูล/ยังไม่ได้แจ้ง\n"
        
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))

    # --- [6] RANDOM & OTHERS ---
    elif text == "สุ่มจัดกลุ่ม":
        user_col.update_one({"user_id": uid}, {"$set": {"state": "GROUP", "step": 1}}, upsert=True)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👥 แบ่งกี่กลุ่มครับ? (พิมพ์ตัวเลข)"))

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
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ พิมพ์เป็นตัวเลขนะครับ"))
        user_col.delete_one({"user_id": uid})

    elif text == "สุ่มเลขที่":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🎲 เลขที่ {random.randint(1, 40)}"))

    elif text == "ตารางเรียน":
        sch = {"Monday": "ไทย, วิทย์, คณิต", "Tuesday": "สังคม, คณิต, ประวัติ", "Wednesday": "คณิต, ไทย, อังกฤษ", "Thursday": "วิทย์, สังคม, ไทย", "Friday": "พละ, คณิต, ไทย"}
        res = f"📅 ตารางเรียนวันนี้ ({today_en}):\n{sch.get(today_en, 'วันหยุดครับ')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
