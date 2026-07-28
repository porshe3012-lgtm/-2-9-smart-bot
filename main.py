import os
import io
import datetime
import random
import time
import requests
import threading
from flask import Flask, request, abort, render_template_string, jsonify, session, redirect, url_for

# MongoDB & Gradio Client
from pymongo import MongoClient
from gradio_client import Client, handle_file

# LINE Bot SDK v1 (สำหรับการรองรับ Flex Message และ Image Message ในระบบห้องเรียน)
from linebot import LineBotApi, WebhookHandler as WebhookHandlerV1
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage, FlexSendMessage
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "kru-mana-super-secret-key-2026")

# ==================================================
# --- [1] CONFIGURATION & ENVIRONMENT VARIABLES ---
# ==================================================
TOKEN = os.environ.get("TOKEN", "")
SECRET = os.environ.get("SECRET", "")
MONGO_URI = os.environ.get("MONGO_URI", "")
HF_SPACE_NAME = os.environ.get("HF_SPACE_NAME", "your-username/your-space-name")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
RENDER_APP_URL = os.environ.get("RENDER_APP_URL", "")

LINE_LOGIN_CLIENT_ID = os.environ.get("LINE_LOGIN_CLIENT_ID", "")
LINE_LOGIN_CLIENT_SECRET = os.environ.get("LINE_LOGIN_CLIENT_SECRET", "")

ADMIN_UID = "U789xxxxYourActualIDxxxx" 

# Initialize LINE Bot API v1
line_bot_api = LineBotApi(TOKEN) if TOKEN else None
handler = WebhookHandlerV1(SECRET) if SECRET else None

# ==================================================
# --- [2] DATABASE SYSTEM (MongoDB) ---
# ==================================================
try:
    client = MongoClient(MONGO_URI)
    db = client['m29_smart_classroom']
    homework_col = db['homework']
    user_col = db['user_state']
    exam_col = db['exams']
    print("MongoDB Connected Successfully!")
except Exception as e:
    print(f"DB Connection Error: {e}")

# ==================================================
# --- [3] ANTI-SPAM & CACHE ---
# ==================================================
user_spam_filter = {} 
BURST_LIMIT = 5        
COOLDOWN_TIME = 0.8    
RESET_THRESHOLD = 2.0  
last_random_number = None  

# ==================================================
# --- [4] GRADIO AI CALLER FUNCTION (Hugging Face) ---
# ==================================================
def ask_huggingface_ai(user_text="", image_bytes=None, image_path=None):
    try:
        ai_client = Client(HF_SPACE_NAME, hf_token=HF_TOKEN if HF_TOKEN else None)
        
        temp_created = False
        if image_bytes and not image_path:
            image_path = "temp_input.jpg"
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            temp_created = True
                
        img_param = handle_file(image_path) if image_path else None

        result = ai_client.predict(
            message=user_text,
            image=img_param,
            api_name="/predict"
        )
        
        if temp_created and os.path.exists(image_path):
            os.remove(image_path)
            
        return result
    except Exception as e:
        err_msg = str(e)
        print(f"AI Connection Error: {err_msg}")
        if "exceeded your ZeroGPU" in err_msg:
            return "ขณะนี้โควต้าประมวลผล AI ชั่วคราวเต็มแล้วครับ นักเรียนโปรดลองใหม่อีกครั้งในอีกสักครู่นะครับ"
        return f"ครูกำลังประมวลผลอยู่หรือเซิร์ฟเวอร์ AI กำลังรีสตาร์ทครับ ลองใหม่อีกครั้งนะครับ (Error: {err_msg})"

# ==================================================
# --- [5] AUTO-PING SELF KEEPALIVE (กัน Render หลับ) ---
# ==================================================
def start_self_ping():
    def ping_loop():
        time.sleep(15)
        while True:
            if RENDER_APP_URL:
                try:
                    target_url = RENDER_APP_URL.rstrip('/') + '/ping'
                    resp = requests.get(target_url, timeout=10)
                    print(f"⏰ [Auto-Ping Status]: {resp.status_code}")
                except Exception as ex:
                    print(f"⚠️ [Auto-Ping Failed]: {ex}")
            time.sleep(600)

    thread = threading.Thread(target=ping_loop, daemon=True)
    thread.start()

start_self_ping()

@app.route("/ping", methods=["GET"])
def ping():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    return f"ครูมานะตื่นอยู่ครับพชรภัทร! เวลาปัจจุบัน: {now.strftime('%H:%M:%S')}", 200

# ==================================================
# --- [6] WEB UI & API ROUTING (HTML / Tailwind CSS) ---
# ==================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ห้องเรียน ม.2/9 - ปรึกษาครูมานะวินัย</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8fafc; font-family: 'Kanit', sans-serif; }
        .chat-container { height: calc(100vh - 140px); }
    </style>
</head>
<body class="flex flex-col h-screen">

    <!-- Header Navigation Bar -->
    <header class="bg-blue-900 text-white p-3.5 shadow-md flex justify-between items-center px-4">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-full bg-amber-400 flex items-center justify-center font-bold text-blue-950 text-xl border-2 border-white">
                👨‍🏫
            </div>
            <div>
                <h1 class="font-bold text-base sm:text-lg leading-tight">ครูมานะวินัย (ม.2/9)</h1>
                <p class="text-xs text-blue-200">ระบบ AI ปรึกษาการเรียนและชีวิตประจำวัน</p>
            </div>
        </div>
        <div>
            {% if user %}
                <div class="flex items-center space-x-2">
                    <img src="{{ user.picture }}" class="w-8 h-8 rounded-full border-2 border-green-400">
                    <span class="text-xs font-medium hidden sm:inline">{{ user.name }}</span>
                    <a href="/logout" class="text-xs bg-red-600 hover:bg-red-700 px-2.5 py-1 rounded text-white font-medium">ออก</a>
                </div>
            {% else %}
                <a href="/login/line" class="bg-green-500 hover:bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 font-medium shadow transition">
                    <i class="fa-brands fa-line text-base"></i> ล็อกอินด้วย LINE
                </a>
            {% endif %}
        </div>
    </header>

    <!-- Chat Messages Window -->
    <main class="flex-1 overflow-y-auto p-4 space-y-4 chat-container max-w-4xl w-full mx-auto" id="chatContainer">
        <div class="flex items-start gap-2.5">
            <div class="w-8 h-8 rounded-full bg-blue-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div>
            <div class="flex flex-col max-w-[85%] sm:max-w-[75%] p-3.5 bg-white border border-gray-200 rounded-e-2xl rounded-es-2xl shadow-sm text-gray-800 text-sm">
                สวัสดีครับนักเรียน ครูชื่อ 'ครูมานะวินัย' ครับ! มีคำถามการเรียน โจทย์การบ้าน หรือเรื่องสงสัยอะไร ส่งข้อความมาให้ครูช่วยดูได้เลยนะครับ!
            </div>
        </div>
    </main>

    <!-- Chat Input Area -->
    <footer class="p-3 bg-white border-t border-gray-200">
        <form id="chatForm" class="flex items-center gap-2 max-w-4xl mx-auto">
            <input type="text" id="messageInput" class="flex-1 bg-gray-100 border border-gray-300 text-gray-900 text-sm rounded-xl focus:ring-blue-500 focus:border-blue-500 p-2.5 outline-none" placeholder="พิมพ์ข้อความคุยกับครูมานะ..." required>
            <button type="submit" id="sendBtn" class="bg-blue-800 hover:bg-blue-900 text-white p-2.5 rounded-xl px-4 transition">
                <i class="fa-solid fa-paper-plane"></i>
            </button>
        </form>
    </footer>

    <script>
        const chatContainer = document.getElementById('chatContainer');
        const chatForm = document.getElementById('chatForm');
        const messageInput = document.getElementById('messageInput');

        function appendMessage(sender, text, isUser = false) {
            const div = document.createElement('div');
            div.className = isUser ? "flex items-start justify-end gap-2.5" : "flex items-start gap-2.5";
            
            const msgBg = isUser ? "bg-blue-600 text-white rounded-s-2xl rounded-ee-2xl" : "bg-white text-gray-800 border border-gray-200 rounded-e-2xl rounded-es-2xl shadow-sm";
            const avatar = isUser ? "" : `<div class="w-8 h-8 rounded-full bg-blue-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div>`;

            div.innerHTML = `
                ${avatar}
                <div class="flex flex-col max-w-[85%] sm:max-w-[75%] p-3.5 ${msgBg} text-sm">
                    <p class="whitespace-pre-line">${text}</p>
                </div>
            `;
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = messageInput.value.trim();
            if (!text) return;

            appendMessage("นักเรียน", text, true);
            messageInput.value = "";
            
            const loadingDiv = document.createElement('div');
            loadingDiv.id = "loadingBubble";
            loadingDiv.className = "flex items-start gap-2.5";
            loadingDiv.innerHTML = `<div class="w-8 h-8 rounded-full bg-blue-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div><div class="p-3 bg-white border border-gray-200 rounded-2xl text-xs text-gray-500">ครูกำลังพิมพ์คำตอบ...</div>`;
            chatContainer.appendChild(loadingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await res.json();
                document.getElementById('loadingBubble').remove();
                appendMessage("ครูมานะ", data.response, false);
            } catch (err) {
                if(document.getElementById('loadingBubble')) document.getElementById('loadingBubble').remove();
                appendMessage("ระบบ", "เกิดข้อผิดพลาดในการเชื่อมต่อครับ", false);
            }
        });
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    user = session.get("user")
    return render_template_string(HTML_TEMPLATE, user=user)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    msg = data.get("message", "")
    ai_reply = ask_huggingface_ai(user_text=msg)
    return jsonify({"response": ai_reply})

# --- LINE LOGIN ---
@app.route("/login/line")
def line_login():
    if not LINE_LOGIN_CLIENT_ID:
        return "กรุณาตั้งค่า LINE_LOGIN_CLIENT_ID ก่อนครับ", 400
    redirect_uri = f"{RENDER_APP_URL.rstrip('/')}/login/line/callback"
    line_auth_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?response_type=code"
        f"&client_id={LINE_LOGIN_CLIENT_ID}&redirect_uri={redirect_uri}"
        f"&state=12345&scope=profile%20openid"
    )
    return redirect(line_auth_url)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ==================================================
# --- [7] LINE WEBHOOK CALLBACK ---
# ==================================================
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

# ==================================================
# --- [8] LINE HANDLER: TEXT MESSAGES ---
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
                if not found: hw_by_day["วันจันทร์"].append(f"📌 {info} (ครู{hw.get('teacher', 'ไม่ระบุ')})")
                    
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

        # --- CHATBOT AI SYSTEM ---
        else:
            if state == "CHAT_AI" or not state:
                ai_reply = ask_huggingface_ai(user_text=text)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
                return

    except Exception as e:
        print(f"Main Handler Error: {e}")

# ==================================================
# --- [9] LINE HANDLER: IMAGE MESSAGES (รับรูปภาพ) ---
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

        # ส่งรูปไปให้ AI วิเคราะห์
        ai_reply = ask_huggingface_ai(user_text="ช่วยอธิบายโจทย์หรือรายละเอียดในรูปนี้ให้ฟังหน่อยครับ", image_bytes=image_bytes)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
        
    except Exception as e:
        print(f"Image Handler Error: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ขออภัยครับ ครูไม่สามารถดาวน์โหลดรูปภาพได้ในขณะนี้"))

# ==================================================
# --- [10] START SERVER ---
# ==================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
