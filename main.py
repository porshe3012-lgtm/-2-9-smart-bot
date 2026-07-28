import os
import io
import datetime
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage, FlexSendMessage
)
from pymongo import MongoClient
from gradio_client import Client, handle_file

app = Flask(__name__)

# --- [1] CONFIG ---
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
MONGO_URI = os.environ.get("MONGO_URI")

# ⚠️ ใส่ชื่อ Space บน Hugging Face ของคุณ (เช่น "phacharaphat/m29-smart-ai") ⚠️
HF_SPACE_NAME = os.environ.get("HF_SPACE_NAME", "your-username/your-space-name")

ADMIN_UID = "U789xxxxYourActualIDxxxx" 

line_bot_api = LineBotApi(TOKEN) if TOKEN else None
handler = WebhookHandler(SECRET) if SECRET else None

# --- [2] DATABASE SYSTEM ---
try:
    client = MongoClient(MONGO_URI)
    db = client['m29_smart_classroom']
    homework_col = db['homework']
    user_col = db['user_state']
    exam_col = db['exams']
except Exception as e:
    print(f"DB Error: {e}")

# --- [3] ANTI-SPAM & CACHE ---
user_spam_filter = {} 
BURST_LIMIT = 5        
COOLDOWN_TIME = 0.8    
RESET_THRESHOLD = 2.0  
last_random_number = None  

# --- [4] GRADIO AI CALLER FUNCTION ---
def ask_huggingface_ai(user_text="", image_bytes=None):
    try:
        # เชื่อมต่อกับ Hugging Face Space (ZeroGPU)
        ai_client = Client(HF_SPACE_NAME)
        
        image_path = None
        if image_bytes:
            # สร้างไฟล์รูปภาพชั่วคราวเพื่อส่งให้ Gradio Client
            image_path = "temp_input.jpg"
            with open(image_path, "wb") as f:
                f.write(image_bytes)
                
        # ยิงคำถาม/รูปภาพไปที่ API ของ Gradio Space
        result = ai_client.predict(
            message=user_text,
            image=handle_file(image_path) if image_path else None,
            api_name="/predict"
        )
        
        # ลบไฟล์ชั่วคราวหลังใช้งาน
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            
        return result
    except Exception as e:
        print(f"AI Connection Error: {e}")
        return f"ครูกำลังประมวลผลอยู่หรือเซิร์ฟเวอร์ AI กำลังรีสตาร์ทครับ ลองใหม่อีกครั้งนะครับ (Error: {e})"

@app.route("/callback", methods=["POST"])
def callback():
    if not handler: return "Handler Config Missing", 500
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@app.route("/ping", methods=["GET"])
def ping():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    return f"ครูมานะตื่นอยู่ครับพชรภัทร! เวลาปัจจุบัน: {now.strftime('%H:%M:%S')}", 200

# ==================================================
# --- [5] LINE HANDLER: TEXT MESSAGES ---
# ==================================================
@handler.add(MessageEvent, message=TextMessage) if handler else lambda x: x
def handle_text_message(event):
    global last_random_number
    uid = event.source.user_id
    current_time = time.time()
    
    # Anti-Spam Check
    user_info = user_spam_filter.get(uid, {"last_time": 0, "count": 0})
    if current_time - user_info["last_time"] < RESET_THRESHOLD:
        user_info["count"] += 1
    else:
        user_info["count"] = 1
        
    if user_info["count"] > BURST_LIMIT:
        if current_time - user_info["last_time"] < COOLDOWN_TIME:
            user_info["last_time"] = current_time 
            user_spam_filter[uid] = user_info
            return 
            
    user_info["last_time"] = current_time
    user_spam_filter[uid] = user_info

    text = event.message.text.strip()
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
        # --- MENU SYSTEM ---
        if text in ["เมนู", "หน้า 1", "ยกเลิก"]:
            user_col.delete_one({"user_id": uid})
            contents_list = [
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📝 แจ้งการบ้าน", "text": "แจ้งการบ้าน"}},
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📋 เช็คงานสัปดาห์นี้", "text": "เช็คงาน"}},
                {"type": "button", "style": "primary", "color": "#E67E22", "action": {"type": "message", "label": "📢 แจ้งสอบ", "text": "แจ้งสอบ"}},
                {"type": "button", "style": "primary", "color": "#9B59B6", "action": {"type": "message", "label": "🤖 คุยกับครูมานะ", "text": "คุยกับครูมานะ"}},
                {"type": "button", "style": "secondary", "color": "#555555", "action": {"type": "message", "label": "💡 วิธีใช้", "text": "วิธีใช้"}}
            ]
            if uid == ADMIN_UID:
                contents_list.append({"type": "button", "style": "secondary", "color": "#FF4B4B", "action": {"type": "message", "label": "🗑️ ล้างการบ้านทั้งหมด", "text": "ล้างการบ้านทั้งหมด"}})
            contents_list.append({"type": "button", "style": "secondary", "action": {"type": "message", "label": "➡️ หน้า 2", "text": "หน้า 2"}})

            menu1 = {
                "type": "bubble",
                "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "🌸 ม.2/9 Menu (1/2)", "weight": "bold", "size": "xl", "color": "#1DB446"}]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": contents_list}
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

        elif text == "ล้างการบ้านทั้งหมด":
            if uid == ADMIN_UID:
                homework_col.delete_many({})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🗑️ ล้างข้อมูลการบ้านเรียบร้อยแล้วจ้า!"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ ปุ่มนี้กดได้เฉพาะแอดมินพชรภัทรเท่านั้นครับ!"))
            return

        elif text == "วิธีใช้":
            how_to = (
                "📖 สรุปวิธีใช้งานบอท ม.2/9\n"
                "--------------------------\n"
                "📝 แจ้งการบ้าน / 📋 เช็คงาน / 📢 แจ้งสอบ\n"
                "🎲 สุ่มเลขที่ / 📚 เวนยกหนังสือ / 👥 สุ่มจัดกลุ่ม\n"
                "🤖 โหมด AI ครูมานะ: พิมพ์คุย หรือ 'ส่งรูปโจทย์การบ้าน' มาให้ครูช่วยอธิบายได้เลยครับ!\n"
                "--------------------------\n"
                "⚠️ หากต้องการออกจากโหมดใดๆ ให้พิมพ์ 'ยกเลิก'"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=how_to))
            return

        elif text == "เวนยกหนังสือ":
            lucky_ones = random.sample(range(1, 41), 2)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📚 เวนยกหนังสือวันนี้\nได้แก่เลขที่: {lucky_ones[0]} และ {lucky_ones[1]}\nสู้ๆ นะเพื่อน! 💪"))
            return

        elif text == "ติดต่อแอดมิน":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📱 ติดต่อแอดมิน (พชรภัทร)\n📞 เบอร์โทร: 0954672577\n🆔 LINE ID: porshe3012"))
            return

        elif text == "แจ้งการบ้าน":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "HW", "step": 1, "temp": ""}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 [1/2] พิมพ์ วิชา / งาน / วันส่ง\n(เช่น คณิต/ทำแบบฝึกหัดหน้า 5/วันอังคาร)"))
            return

        elif state == "HW":
            if step == 1:
                user_col.update_one({"user_id": uid}, {"$set": {"step": 2, "temp": text}})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👨‍🏫 [2/2] ครูท่านไหนสั่งครับ?"))
            elif step == 2:
                homework_col.insert_one({"info": temp, "teacher": text, "created_at": now.strftime("%Y-%m-%d %H:%M")})
                user_col.delete_one({"user_id": uid})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกการบ้านเรียบร้อยจ้า!"))
            return

        elif text == "เช็คงาน":
            all_hw = list(homework_col.find())
            days = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์"]
            report = "📋 สรุปการบ้านสัปดาห์นี้\n"
            hw_by_day = {day: [] for day in days}
            
            for hw in all_hw:
                info, teacher = hw.get('info', ''), hw.get('teacher', 'ไม่ระบุ')
                found = False
                for day in days:
                    if day in info:
                        hw_by_day[day].append(f"📌 {info} (ครู{teacher})")
                        found = True; break
                if not found: hw_by_day["วันจันทร์"].append(f"📌 {info} (ครู{hw['teacher']})")
                    
            for day in days:
                report += f"\n📍 {day}\n" + ("\n".join(hw_by_day[day]) if hw_by_day[day] else "ยังไม่มีงาน") + "\n"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))
            return

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
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ บันทึกตารางสอบสำเร็จ!"))
            return

        elif text == "เช็คตารางสอบ":
            all_exams = list(exam_col.find())
            report = "📅 ตารางสอบ\n" + "\n".join([f"📌 {ex['subject_info']}\n⏰ {ex['date_time']}" for ex in all_exams]) if all_exams else "✨ ตอนนี้ยังไม่มีแจ้งสอบจ้า"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=report))
            return

        elif text == "สุ่มจัดกลุ่ม":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "GROUP", "step": 1}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👥 แบ่งกี่กลุ่มครับ? (พิมพ์เฉพาะตัวเลข)"))
            return

        elif state == "GROUP":
            try:
                num = int(text)
                students = list(range(1, 41)); random.shuffle(students)
                res = "🎲 ผลสุ่มกลุ่ม ม.2/9\n"
                for i in range(num):
                    res += f"\nกลุ่ม {i+1}: " + ", ".join(map(str, sorted(students[i::num])))
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
            except: line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ พิมพ์เป็นเลข 1-40 เท่านั้นนะครับ"))
            user_col.delete_one({"user_id": uid})
            return

        elif text == "สุ่มเลขที่":
            while True:
                new_num = random.randint(1, 40)
                if new_num != last_random_number: break
            last_random_number = new_num 
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🎲 เลขที่ {new_num}"))
            return

        elif text == "ตารางเรียน":
            sch = {"Monday": "ไทย, วิทย์, คณิต", "Tuesday": "สังคม, คณิต, ประวัติ", "Wednesday": "คณิต, ไทย, อังกฤษ", "Thursday": "วิทย์, สังคม, ไทย", "Friday": "พละ, คณิต, ไทย"}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"📅 ตารางวันนี้ ({today_en}):\n{sch.get(today_en, 'วันหยุดครับ')}"))
            return

        elif text == "คุยกับครูมานะ":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "CHAT_AI", "step": 1}}, upsert=True)
            welcome_msg = (
                "👨‍🏫 สวัสดีครับนักเรียน ครูชื่อ 'ครูมานะ วินัย' ครับ\n\n"
                "ถามคำถามวิชาการ หรือ 'ถ่ายรูปโจทย์การบ้าน' ส่งมาให้ครูช่วยดูได้เลยนะครับ!\n"
                "(พิมพ์ 'ยกเลิก' เมื่อต้องการกลับไปหน้าเมนูหลัก)"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_msg))
            return

        # --- [🤖 CHATBOT AI SYSTEM - ยิงไปหา Hugging Face Space] ---
        else:
            if state == "CHAT_AI" or not state:
                ai_reply = ask_huggingface_ai(user_text=text)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
                return

    except Exception as e:
        print(f"Main Error: {e}")

# ==================================================
# --- [6] LINE HANDLER: IMAGE MESSAGES (รับรูปภาพ) ---
# ==================================================
@handler.add(MessageEvent, message=ImageMessage) if handler else lambda x: x
def handle_image_message(event):
    try:
        message_id = event.message.id
        
        # ดึงไฟล์รูปภาพจาก LINE Server
        message_content = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO()
        for chunk in message_content.iter_content():
            image_bytes.write(chunk)
        image_bytes = image_bytes.getvalue()

        # ส่งรูปไปให้ Hugging Face Qwen2-VL-7B วิเคราะห์
        ai_reply = ask_huggingface_ai(user_text="ช่วยอธิบายโจทย์หรือรายละเอียดในรูปนี้ให้ฟังหน่อยครับ", image_bytes=image_bytes)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
        
    except Exception as e:
        print(f"Image Handler Error: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ขออภัยครับ ครูไม่สามารถดาวน์โหลดรูปภาพได้ในขณะนี้"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
