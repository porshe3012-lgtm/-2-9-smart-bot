import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
from pymongo import MongoClient
import datetime
import random
import time

app = Flask(__name__)

# --- [1] CONFIG ---
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
MONGO_URI = os.environ.get("MONGO_URI")

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# --- [2] DATABASE SYSTEM ---
try:
    client = MongoClient(MONGO_URI)
    db = client['m29_smart_classroom']
    homework_col = db['homework']
    user_col = db['user_state']
    exam_col = db['exams']
except Exception as e:
    print(f"DB Error: {e}")

# --- [0] ADVANCED ANTI-SPAM CONFIG ---
# ระบบ Burst Cooldown: ยอมให้กดรัวได้ในช่วงแรก แต่ถ้าเกินขีดจำกัดต้องรอ
user_spam_filter = {} 
BURST_LIMIT = 5        # กดรัวติดต่อกันได้ 5 ครั้งแรก
COOLDOWN_TIME = 0.8    # หลังจากครั้งที่ 5 ต้องรอ 0.8 วินาทีต่อการส่ง 1 ครั้ง
RESET_THRESHOLD = 2.0  # ถ้าหยุดพิมพ์เกิน 2 วินาที จะรีเซ็ตโควตาการกดรัวใหม่

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
    current_time = time.time()
    
    # ดึงข้อมูลประวัติการกดของ User
    user_info = user_spam_filter.get(uid, {"last_time": 0, "count": 0})
    
    # ตรวจสอบว่าเป็นการกดต่อเนื่องหรือไม่
    if current_time - user_info["last_time"] < RESET_THRESHOLD:
        user_info["count"] += 1
    else:
        user_info["count"] = 1 # หยุดเล่นนานพอแล้ว รีเซ็ตให้นับ 1 ใหม่
    
    # --- ตรรกะป้องกันการกดรั่ว ---
    if user_info["count"] > BURST_LIMIT:
        # ถ้ากดเกิน 5 ครั้ง และยังรอไม่ถึง 0.8 วิ ให้บล็อกคำสั่งนี้
        if current_time - user_info["last_time"] < COOLDOWN_TIME:
            # อัปเดตเวลาเพื่อให้ User ต้องเริ่มนับถอยหลังใหม่จากจุดนี้
            user_info["last_time"] = current_time 
            user_spam_filter[uid] = user_info
            return 
    
    # อัปเดตข้อมูลการกดล่าสุด
    user_info["last_time"] = current_time
    user_spam_filter[uid] = user_info

    # ---------------------------------
    
    text = event.message.text.strip()
    
    # [FIX] บังคับเวลาประเทศไทยเสมอ
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    today_en = now.strftime("%A")
    
    try:
        user_data = user_col.find_one({"user_id": uid})
        state = user_data.get('state') if user_data else None
        step = user_data.get('step', 0) if user_data else 0
        temp = user_data.get('temp', "") if user_data else ""
    except:
        state, step, temp = None, 0, ""

    try:
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
                "📝 แจ้งการบ้าน: กดแล้วพิมพ์ 'วิชา/งาน/กำหนดส่ง'\n"
                "📋 เช็คงาน: ดูสรุปงานแยกรายวัน\n"
                "📢 แจ้งสอบ: บันทึกวิชาและวันสอบ\n"
                "🎲 สุ่มเลขที่: สุ่มเพื่อน 1 คน\n"
                "--------------------------\n"
                "⚠️ หากบอทไม่ตอบ แสดงว่ากดรัวเกินไปจ้า (รอ 0.8 วิ)"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=how_to))
            return

        elif text == "เวนยกหนังสือ":
            lucky_ones = random.sample(range(1, 41), 2)
            res = f"📚 เวนยกหนังสือวันนี้\nได้แก่เลขที่: {lucky_ones[0]} และ {lucky_ones[1]}\nสู้ๆ นะเพื่อน! 💪"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
            return

        elif text == "ติดต่อแอดมิน":
            res = "📱 ติดต่อแอดมิน (พชรภัทร)\n📞 เบอร์โทร: 0954672577\n🆔 LINE ID: porshe3012"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
            return

        # --- [5] HOMEWORK SYSTEM ---
        elif text == "แจ้งการบ้าน":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "HW", "step": 1, "temp": ""}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 [1/2] พิมพ์ วิชา / งาน / วันส่ง"))
            return

        elif state == "HW":
            if step == 1:
                user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👨‍🏫 [2/2] ครูท่านไหนสั่งครับ?"))
            elif step == 2:
                homework_col.insert_one({"info": temp, "teacher": text, "created_at": now.strftime("%Y-%m-%d %H:%M")})
                user_col.delete_one({"user_id": uid})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกเรียบร้อย!"))
            return

        elif text == "เช็คงาน":
            all_hw = list(homework_col.find())
            days = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์"]
            report = "📋 สรุปการบ้านสัปดาห์นี้\n"
            hw_by_day = {day: [] for day in days}
            for hw in all_hw:
                info = hw['info']
                found = False
                for day in days:
                    if day in info:
                        hw_by_day[day].append(f"📌 {info} (ครู{hw['teacher']})")
                        found = True; break
                if not found: hw_by_day["วันจันทร์"].append(f"📌 {info} (ครู{hw['teacher']})")
            for day in days:
                report += f"\n📍 {day}\n" + ("\n".join(hw_by_day[day]) if hw_by_day[day] else "ยังไม่มีงาน") + "\n"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))
            return

        # --- [5.1] EXAM SYSTEM ---
        elif text == "แจ้งสอบ":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "EXAM", "step": 1, "temp": ""}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📢 [1/2] วิชาและเรื่องที่สอบ?"))
            return

        elif state == "EXAM":
            if step == 1:
                user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📅 [2/2] สอบวันไหน คาบไหน?"))
            elif step == 2:
                exam_col.insert_one({"subject_info": temp, "date_time": text, "created_at": now.strftime("%Y-%m-%d %H:%M")})
                user_col.delete_one({"user_id": uid})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกตารางสอบแล้ว!"))
            return

        elif text == "เช็คตารางสอบ":
            all_exams = list(exam_col.find())
            report = "📅 ตารางสอบ\n" + "\n".join([f"📌 {ex['subject_info']}\n⏰ {ex['date_time']}" for ex in all_exams]) if all_exams else "✨ ยังไม่มีแจ้งสอบจ้า"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))
            return

        # --- [6] RANDOM & OTHERS ---
        elif text == "สุ่มจัดกลุ่ม":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "GROUP", "step": 1}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👥 แบ่งกี่กลุ่มครับ?"))
            return

        elif state == "GROUP":
            try:
                num = int(text)
                students = list(range(1, 41)); random.shuffle(students)
                res = "🎲 ผลสุ่มกลุ่ม\n"
                for i in range(num):
                    res += f"\nกลุ่ม {i+1}: " + ", ".join(map(str, sorted(students[i::num])))
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
            except: line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ พิมพ์เลข 1-40 นะครับ"))
            user_col.delete_one({"user_id": uid})
            return

        elif text == "สุ่มเลขที่":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🎲 เลขที่ {random.randint(1, 40)}"))
            return

        elif text == "ตารางเรียน":
            sch = {"Monday": "ไทย, วิทย์, คณิต", "Tuesday": "สังคม, คณิต, ประวัติ", "Wednesday": "คณิต, ไทย, อังกฤษ", "Thursday": "วิทย์, สังคม, ไทย", "Friday": "พละ, คณิต, ไทย"}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📅 ตารางวันนี้ ({today_en}):\n{sch.get(today_en, 'วันหยุดครับ')}"))
            return

    except Exception as e:
        print(f"Main Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
