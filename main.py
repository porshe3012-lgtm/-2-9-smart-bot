import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
from pymongo import MongoClient
from google import genai  # Import ไลบรารี AI เวอร์ชันใหม่
import datetime
import random
import time

app = Flask(__name__)

# --- [1] CONFIG ---
TOKEN = os.environ.get("TOKEN")
SECRET = os.environ.get("SECRET")
MONGO_URI = os.environ.get("MONGO_URI")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# ⚠️ เปลี่ยนเป็น LINE User ID ของคุณเองนะครับ เพื่อสิทธิ์แอดมิน ⚠️
ADMIN_UID = "U789xxxxYourActualIDxxxx" 

line_bot_api = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# เปิดใช้งาน AI Client (ถ้ามี API Key)
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

# --- [2] DATABASE SYSTEM ---
try:
    client = MongoClient(MONGO_URI)
    db = client['m29_smart_classroom']
    homework_col = db['homework']
    user_col = db['user_state']
    exam_col = db['exams']
except Exception as e:
    print(f"DB Error: {e}")

# --- [0] ANTI-SPAM & RANDOM CACHE ---
user_spam_filter = {} 
BURST_LIMIT = 5        
COOLDOWN_TIME = 0.8    
RESET_THRESHOLD = 2.0  
last_random_number = None  # บันทึกเลขสุ่มล่าสุด ป้องกันเลขซ้ำติดกัน

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
    global last_random_number
    uid = event.source.user_id
    current_time = time.time()
    
    # --- Anti-Spam (Burst Cooldown) ---
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

    # ---------------------------------
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
        # --- [3] MENU SYSTEM ---
        # ถ้าพิมพ์คำเหล่านี้ จะเคลียร์ทุกสถานะ (รวมถึงโหมด AI) แล้วกลับหน้าแรก
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

        # --- ADMIN FUNCTION ---
        elif text == "ล้างการบ้านทั้งหมด":
            if uid == ADMIN_UID:
                homework_col.delete_many({})
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🗑️ ล้างข้อมูลการบ้านเรียบร้อยแล้วจ้า!"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ ปุ่มนี้กดได้เฉพาะแอดมินพชรภัทรเท่านั้นครับ!"))
            return

        # --- วิธีใช้, เวนยกหนังสือ, ติดต่อแอดมิน ---
        elif text == "วิธีใช้":
            how_to = (
                "📖 สรุปวิธีใช้งานบอท ม.2/9\n"
                "--------------------------\n"
                "📝 แจ้งการบ้าน / 📋 เช็คงาน / 📢 แจ้งสอบ\n"
                "🎲 สุ่มเลขที่ / 📚 เวนยกหนังสือ / 👥 สุ่มจัดกลุ่ม\n"
                "🤖 โหมด AI ครูมานะ: กดปุ่ม 'คุยกับครูมานะ' เพื่อเปิดโหมดถามคำถามหรือปรึกษาเรื่องเรียนได้เลย!\n"
                "--------------------------\n"
                "⚠️ หากต้องการออกจากโหมดใดๆ หรือบอทค้าง ให้พิมพ์ 'ยกเลิก'"
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

        # --- HOMEWORK SYSTEM ---
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

        # --- EXAM SYSTEM ---
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

        # --- RANDOM & OTHERS ---
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

        # --- [โหมดกระตุ้นเปิดการใช้งาน AI] ---
        elif text == "คุยกับครูมานะ":
            user_col.update_one({"user_id": uid}, {"$set": {"state": "CHAT_AI", "step": 1}}, upsert=True)
            welcome_msg = (
                "👨‍🏫 สวัสดีครับนักเรียน ครูชื่อ 'ครูมานะ' เป็น AI ผู้ช่วยประจำห้อง ม.2/9 ครับ\n\n"
                "มีเรื่องเรียนตรงไหนไม่เข้าใจ หรืออยากปรึกษาเรื่องอะไร พิมพ์คุยกับครูตรงนี้ได้เลยจ้า\n"
                "(คำเตือน: ครูสอนให้ได้แต่ห้ามมาขอเฉลยการบ้านตรงๆ นะครับพ้ม! ❌ ส่วนถ้าใครอยากกลับไปหน้าเมนูหลัก ให้พิมพ์คำว่า 'ยกเลิก' นะครับ)"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_msg))
            return

        # ==================================================
        # --- [🤖 CHATBOT AI SYSTEM - คุณครูมานะ ม.2/9] ---
        # ==================================================
        else:
            # ตรวจสอบว่าเปิดโหมด AI อยู่ (state == "CHAT_AI") หรือกรณีที่พิมพ์คำอื่นๆ ทั่วไปนอกเหนือคำสั่ง
            if state == "CHAT_AI" or (not state and ai_client):
                if ai_client:
                    # คำสั่งควบคุมพฤติกรรมคุณครูมานะตามที่พชรภัทรกำหนด
                    mana_instruction = (
                        "คุณคือ 'คุณครูมานะ' ครูผู้ชายที่เป็น AI ผู้ช่วยประจำห้องเรียน ม.2/9 Smart Classroom "
                        "ลักษณะนิสัยของคุณคือ: มีความเข้มขรึม น่าเชื่อถือแบบครู แต่มีความเข้าใจในตัวนักเรียนทุกคนสูงมาก "
                        "เป็นคนใจกว้าง หัวสมัยใหม่ ไม่มีการเหยียดเพศ เหยียดฐานะ หรือเหยียดใดๆ ทั้งสิ้น "
                        "พร้อมที่จะช่วยเหลือและรับฟังนักเรียนในทุกๆ เรื่อง "
                        "\n\n"
                        "⚠️ กฎเหล็กในการปฏิบัติหน้าที่:\n"
                        "1. ห้ามบอกคำตอบหรือเฉลยการบ้านแก่นักเรียนเด็ดขาด! ทำได้มากที่สุดคือการสอนการบ้าน อธิบายวิธีคิด "
                        "บอกสูตร หรือแนะแนวทาง (Hint) เพื่อให้นักเรียนนำไปคิดและหาคำตอบด้วยตัวเองเท่านั้น\n"
                        "2. ปฏิเสธการช่วยเหลือในเรื่องที่ผิดกฎหมาย หรือเรื่องที่พิจารณาแล้วว่าดูจะช่วยไม่ได้/เกินความสามารถของ AI อย่างสุภาพ\n"
                        "3. แทนตัวเองว่า 'ครู' หรือ 'ครูมานะ' และเรียกคู่สนทนาว่า 'นักเรียน' หรือ 'พวกเรา' อย่างเป็นกันเองและสุภาพ"
                    )
                    
                    prompt = f"{mana_instruction}\n\nข้อความจากนักเรียน ม.2/9: {text}"
                    
                    response = ai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    ai_reply = response.text.strip()
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
                return
            
            # หากไม่ได้อยู่ในโหมด AI และคำสั่งไม่ถูกต้อง จะไม่ตอบกลับเพื่อป้องกันบอทตอบมั่วในกลุ่มไลน์
            return

    except Exception as e:
        print(f"Main Error: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
