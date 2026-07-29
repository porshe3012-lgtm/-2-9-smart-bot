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

# LINE Bot SDK v1
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
homework_col = None
exam_col = None
user_col = None

try:
    if MONGO_URI:
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
# --- [4] GRADIO AI CALLER FUNCTION ---
# ==================================================
def ask_huggingface_ai(user_text="", image_bytes=None, image_path=None):
    try:
        hf_token = HF_TOKEN if HF_TOKEN else None
        ai_client = Client(HF_SPACE_NAME, token=hf_token)
        
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
        return f"ครูกำลังประมวลผลอยู่หรือเซิร์ฟเวอร์ AI กำลังรีสตาร์ทครับ ลองใหม่อีกครั้งนะครับ"

# ==================================================
# --- [5] AUTO-PING SELF KEEPALIVE ---
# ==================================================
def start_self_ping():
    def ping_loop():
        time.sleep(15)
        while True:
            if RENDER_APP_URL:
                try:
                    clean_url = RENDER_APP_URL.strip().rstrip('/')
                    target_url = clean_url + '/ping'
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
    return f"ครูมานะตื่นอยู่ครับ! เวลาปัจจุบัน: {now.strftime('%H:%M:%S')}", 200

# ==================================================
# --- [6] WEB DASHBOARD UI (Tailwind CSS + Animation) ---
# ==================================================
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Classroom ม.2/9 Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Kanit:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
    <style>
        body { font-family: 'Kanit', sans-serif; background-color: #f8fafc; }
        .active-tab { border-b-4 border-indigo-600 text-indigo-600 font-bold; }
    </style>
</head>
<body class="pb-12 text-gray-800">

    <!-- Header / Navbar -->
    <header class="bg-indigo-900 text-white shadow-lg sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 py-3 flex justify-between items-center">
            <div class="flex items-center space-x-3 transition-transform duration-300 hover:scale-105">
                <div class="w-10 h-10 rounded-xl bg-amber-400 flex items-center justify-center font-bold text-indigo-950 text-xl border-2 border-white shadow">
                    🏫
                </div>
                <div>
                    <h1 class="font-bold text-lg leading-tight">ห้องเรียน ม.2/9</h1>
                    <p class="text-xs text-indigo-200">ระบบการเรียนและปรึกษา AI ครูมานะวินัย</p>
                </div>
            </div>
            <div>
                {% if user %}
                    <div class="flex items-center space-x-2 bg-indigo-800 px-3 py-1.5 rounded-xl border border-indigo-700">
                        <img src="{{ user.picture }}" class="w-7 h-7 rounded-full border border-green-400">
                        <span class="text-xs font-medium hidden sm:inline">{{ user.name }}</span>
                        <a href="/logout" class="text-xs bg-red-500 hover:bg-red-600 px-2.5 py-1 rounded-lg text-white transition duration-200">ออก</a>
                    </div>
                {% else %}
                    <a href="/login/line" class="bg-emerald-500 hover:bg-emerald-600 text-white px-3.5 py-2 rounded-xl text-xs flex items-center gap-1.5 font-medium shadow-md transition duration-300 transform hover:scale-105 active:scale-95">
                        <i class="fa-brands fa-line text-base"></i> ล็อกอิน LINE
                    </a>
                {% endif %}
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="bg-white border-b border-gray-200 text-gray-500 text-sm font-medium flex justify-around max-w-6xl mx-auto px-2">
            <button onclick="switchTab('dashboard')" id="tab-dashboard" class="py-3 px-4 flex items-center gap-2 active-tab transition-all duration-200">
                <i class="fa-solid fa-square-poll-vertical"></i>แดชบอร์ดงาน
            </button>
            <button onclick="switchTab('tools')" id="tab-tools" class="py-3 px-4 flex items-center gap-2 transition-all duration-200">
                <i class="fa-solid fa-dice"></i>เครื่องมือห้องเรียน
            </button>
            <button onclick="switchTab('ai')" id="tab-ai" class="py-3 px-4 flex items-center gap-2 transition-all duration-200">
                <i class="fa-solid fa-robot"></i>คุยกับครูมานะ AI
            </button>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-6xl mx-auto px-4 mt-6">

        <!-- TAB 1: DASHBOARD -->
        <div id="section-dashboard" class="space-y-6 animate__animated animate__fadeIn animate__faster">
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Card: แจ้งการบ้าน -->
                <div class="bg-white p-5 rounded-2xl shadow-sm border border-gray-100 transition-all duration-300 hover:shadow-md">
                    <h3 class="font-bold text-gray-800 text-base mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-pen-to-square text-indigo-600"></i> เพิ่มการบ้านใหม่
                    </h3>
                    <form id="addHwForm" class="space-y-3">
                        <input type="text" id="hwInfo" placeholder="วิชา / รายละเอียดงาน / วันส่ง" class="w-full bg-gray-50 border border-gray-200 text-sm rounded-xl p-2.5 outline-none focus:border-indigo-500 transition-all duration-200" required>
                        <div class="flex gap-2">
                            <input type="text" id="hwTeacher" placeholder="ชื่อครูผู้สอน" class="w-1/2 bg-gray-50 border border-gray-200 text-sm rounded-xl p-2.5 outline-none focus:border-indigo-500 transition-all duration-200" required>
                            <button type="submit" class="w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-xl p-2.5 transition-all duration-200 active:scale-95">
                                <i class="fa-solid fa-plus mr-1"></i> บันทึกงาน
                            </button>
                        </div>
                    </form>
                </div>

                <!-- Card: แจ้งสอบ -->
                <div class="bg-white p-5 rounded-2xl shadow-sm border border-gray-100 transition-all duration-300 hover:shadow-md">
                    <h3 class="font-bold text-gray-800 text-base mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-bullhorn text-amber-500"></i> เพิ่มแจ้งสอบ
                    </h3>
                    <form id="addExamForm" class="space-y-3">
                        <input type="text" id="examSubject" placeholder="วิชา / เรื่องที่สอบ" class="w-full bg-gray-50 border border-gray-200 text-sm rounded-xl p-2.5 outline-none focus:border-indigo-500 transition-all duration-200" required>
                        <div class="flex gap-2">
                            <input type="text" id="examDate" placeholder="วัน/เวลา สอบ" class="w-1/2 bg-gray-50 border border-gray-200 text-sm rounded-xl p-2.5 outline-none focus:border-indigo-500 transition-all duration-200" required>
                            <button type="submit" class="w-1/2 bg-amber-500 hover:bg-amber-600 text-white font-medium text-sm rounded-xl p-2.5 transition-all duration-200 active:scale-95">
                                <i class="fa-solid fa-plus mr-1"></i> บันทึกตารางสอบ
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Homework List Section -->
            <div class="bg-white p-5 rounded-2xl shadow-sm border border-gray-100">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="font-bold text-gray-800 text-lg flex items-center gap-2">
                        <i class="fa-solid fa-list-check text-indigo-600"></i> รายการการบ้านทั้งหมด
                    </h2>
                    <button onclick="loadDashboardData()" class="text-xs text-indigo-600 hover:underline flex items-center gap-1 transition"><i class="fa-solid fa-rotate-right"></i> รีเฟรช</button>
                </div>
                <div id="homeworkList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <p class="text-gray-400 text-sm col-span-full text-center py-6">กำลังโหลดข้อมูลการบ้าน...</p>
                </div>
            </div>

            <!-- Exam List Section -->
            <div class="bg-white p-5 rounded-2xl shadow-sm border border-gray-100">
                <h2 class="font-bold text-gray-800 text-lg mb-4 flex items-center gap-2">
                    <i class="fa-solid fa-calendar-check text-rose-500"></i> ตารางสอบควิซ / ปลายภาค
                </h2>
                <div id="examList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <p class="text-gray-400 text-sm col-span-full text-center py-6">กำลังโหลดตารางสอบ...</p>
                </div>
            </div>

        </div>

        <!-- TAB 2: CLASSROOM TOOLS -->
        <div id="section-tools" class="hidden space-y-6 animate__animated animate__fadeIn animate__faster">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Tool 1: สุ่มเลขที่ -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 text-center transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
                    <div class="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-3 text-xl shadow-inner">🎲</div>
                    <h3 class="font-bold text-gray-800 text-base mb-1">สุ่มเลขที่</h3>
                    <p class="text-xs text-gray-400 mb-4">สุ่มผู้โชคดีตอบคำถาม (1-40)</p>
                    <div id="randomResult" class="text-4xl font-extrabold text-indigo-600 mb-4 my-2 h-10 flex items-center justify-center">-</div>
                    <button onclick="runRandomStudent()" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm py-2.5 rounded-xl transition duration-200 active:scale-95 shadow-sm">สุ่มเลย!</button>
                </div>

                <!-- Tool 2: เวรยกหนังสือ -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 text-center transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
                    <div class="w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-3 text-xl shadow-inner">📚</div>
                    <h3 class="font-bold text-gray-800 text-base mb-1">เวรยกหนังสือประจำวัน</h3>
                    <p class="text-xs text-gray-400 mb-4">สุ่มเพื่อน 2 คนไปยกหนังสือ</p>
                    <div id="bookDutyResult" class="text-lg font-bold text-amber-600 mb-4 my-2 h-10 flex items-center justify-center">-</div>
                    <button onclick="runBookDuty()" class="w-full bg-amber-500 hover:bg-amber-600 text-white font-medium text-sm py-2.5 rounded-xl transition duration-200 active:scale-95 shadow-sm">สุ่มเวรยกหนังสือ</button>
                </div>

                <!-- Tool 3: สุ่มจัดกลุ่ม -->
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 text-center transition-all duration-300 hover:-translate-y-1 hover:shadow-lg">
                    <div class="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-3 text-xl shadow-inner">👥</div>
                    <h3 class="font-bold text-gray-800 text-base mb-1">สุ่มแบ่งกลุ่ม</h3>
                    <div class="flex items-center justify-center gap-2 mb-4">
                        <span class="text-xs text-gray-500">จำนวนกลุ่ม:</span>
                        <input type="number" id="groupCount" value="4" min="2" max="10" class="w-16 bg-gray-50 border border-gray-200 text-center text-sm rounded-lg p-1 outline-none">
                    </div>
                    <button onclick="runRandomGroup()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm py-2.5 rounded-xl transition duration-200 active:scale-95 shadow-sm">สุ่มแบ่งกลุ่ม</button>
                </div>
            </div>

            <!-- Group Result Box -->
            <div id="groupResultBox" class="hidden bg-white p-6 rounded-2xl shadow-sm border border-gray-100 animate__animated animate__fadeInUp">
                <h4 class="font-bold text-gray-800 text-md mb-3"><i class="fa-solid fa-users text-emerald-600"></i> ผลการแบ่งกลุ่ม</h4>
                <div id="groupResultContainer" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 text-sm"></div>
            </div>
        </div>

        <!-- TAB 3: AI CHATBOT -->
        <div id="section-ai" class="hidden animate__animated animate__fadeIn animate__faster">
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[75vh]">
                <!-- Chat Window Header -->
                <div class="p-4 bg-indigo-50 border-b border-indigo-100 flex items-center gap-3">
                    <div class="w-9 h-9 rounded-full bg-indigo-900 text-white flex items-center justify-center font-bold text-sm shadow">ครู</div>
                    <div>
                        <h4 class="font-bold text-gray-800 text-sm">ปรึกษาครูมานะวินัย (AI)</h4>
                        <p class="text-xs text-indigo-500">พร้อมช่วยอธิบายการบ้าน 24 ชั่วโมง</p>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto p-4 space-y-4" id="chatContainer">
                    <div class="flex items-start gap-2.5 animate__animated animate__fadeInLeft animate__faster">
                        <div class="w-8 h-8 rounded-full bg-indigo-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div>
                        <div class="max-w-[80%] p-3.5 bg-indigo-50/70 border border-indigo-100 rounded-2xl rounded-tl-none text-gray-800 text-sm shadow-sm">
                            สวัสดีครับนักเรียน! มีโจทย์การบ้านข้อไหนสงสัย หรืออยากให้ครูช่วยอธิบายเรื่องอะไร พิมพ์ถามเข้ามาได้เลยนะครับ
                        </div>
                    </div>
                </div>

                <div class="p-3 bg-white border-t border-gray-200">
                    <form id="chatForm" class="flex items-center gap-2">
                        <input type="text" id="messageInput" class="flex-1 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-xl p-2.5 outline-none focus:border-indigo-500 transition" placeholder="พิมพ์คำถามที่ต้องการถามครู..." required>
                        <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white p-2.5 rounded-xl px-4 transition-all duration-200 active:scale-95 shadow">
                            <i class="fa-solid fa-paper-plane"></i>
                        </button>
                    </form>
                </div>
            </div>
        </div>

    </main>

    <script>
        // Tab Switcher
        function switchTab(tab) {
            ['dashboard', 'tools', 'ai'].forEach(t => {
                document.getElementById(`section-${t}`).classList.add('hidden');
                document.getElementById(`tab-${t}`).classList.remove('active-tab');
            });
            document.getElementById(`section-${tab}`).classList.remove('hidden');
            document.getElementById(`tab-${tab}`).classList.add('active-tab');
        }

        // Fetch Dashboard Data
        async function loadDashboardData() {
            try {
                const res = await fetch('/api/dashboard_data');
                const data = await res.json();
                
                // Render Homework
                const hwBox = document.getElementById('homeworkList');
                if(data.homework.length === 0) {
                    hwBox.innerHTML = '<p class="text-gray-400 text-sm col-span-full text-center py-6">🎉 ไม่มีงานค้างในระบบเลยครับ!</p>';
                } else {
                    hwBox.innerHTML = data.homework.map(hw => `
                        <div class="p-4 rounded-xl border border-indigo-100 bg-indigo-50/40 relative animate__animated animate__fadeIn">
                            <span class="text-xs font-semibold px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-700 mb-2 inline-block">ครู${hw.teacher}</span>
                            <p class="font-medium text-gray-800 text-sm mb-1">${hw.info}</p>
                            <p class="text-xs text-gray-400">บันทึกเมื่อ: ${hw.created_at}</p>
                        </div>
                    `).join('');
                }

                // Render Exams
                const examBox = document.getElementById('examList');
                if(data.exams.length === 0) {
                    examBox.innerHTML = '<p class="text-gray-400 text-sm col-span-full text-center py-6">✨ ยังไม่มีประกาศสอบครับ</p>';
                } else {
                    examBox.innerHTML = data.exams.map(ex => `
                        <div class="p-4 rounded-xl border border-amber-100 bg-amber-50/40 animate__animated animate__fadeIn">
                            <p class="font-bold text-amber-800 text-sm mb-1">📌 ${ex.subject_info}</p>
                            <p class="text-xs text-amber-600">⏰ วัน/เวลา: ${ex.date_time}</p>
                        </div>
                    `).join('');
                }
            } catch(e) { console.error(e); }
        }

        // Add Homework
        document.getElementById('addHwForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const info = document.getElementById('hwInfo').value;
            const teacher = document.getElementById('hwTeacher').value;
            await fetch('/api/add_homework', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ info, teacher })
            });
            document.getElementById('hwInfo').value = '';
            document.getElementById('hwTeacher').value = '';
            loadDashboardData();
        });

        // Add Exam
        document.getElementById('addExamForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const subject_info = document.getElementById('examSubject').value;
            const date_time = document.getElementById('examDate').value;
            await fetch('/api/add_exam', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ subject_info, date_time })
            });
            document.getElementById('examSubject').value = '';
            document.getElementById('examDate').value = '';
            loadDashboardData();
        });

        // Random Tools
        function runRandomStudent() {
            const resultBox = document.getElementById('randomResult');
            resultBox.classList.add('animate__animated', 'animate__bounceIn');
            const num = Math.floor(Math.random() * 40) + 1;
            resultBox.innerText = `เลขที่ ${num}`;
            setTimeout(() => resultBox.classList.remove('animate__animated', 'animate__bounceIn'), 1000);
        }

        function runBookDuty() {
            const resultBox = document.getElementById('bookDutyResult');
            resultBox.classList.add('animate__animated', 'animate__fadeIn');
            let n1 = Math.floor(Math.random() * 40) + 1;
            let n2 = Math.floor(Math.random() * 40) + 1;
            while(n1 === n2) n2 = Math.floor(Math.random() * 40) + 1;
            resultBox.innerText = `เลขที่ ${n1} และ เลขที่ ${n2}`;
            setTimeout(() => resultBox.classList.remove('animate__animated', 'animate__fadeIn'), 1000);
        }

        function runRandomGroup() {
            const count = parseInt(document.getElementById('groupCount').value) || 4;
            let students = Array.from({length: 40}, (_, i) => i + 1).sort(() => Math.random() - 0.5);
            let groups = Array.from({length: count}, () => []);
            students.forEach((s, idx) => groups[idx % count].push(s));
            
            const container = document.getElementById('groupResultContainer');
            container.innerHTML = groups.map((g, idx) => `
                <div class="p-3 bg-gray-50 rounded-xl border border-gray-200">
                    <span class="font-bold text-indigo-600">กลุ่ม ${idx+1}:</span> ${g.sort((a,b)=>a-b).join(', ')}
                </div>
            `).join('');
            document.getElementById('groupResultBox').classList.remove('hidden');
        }

        // AI Chat System
        document.getElementById('chatForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('messageInput');
            const text = input.value.trim();
            if(!text) return;

            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML += `
                <div class="flex items-start justify-end gap-2.5 animate__animated animate__fadeInRight animate__faster">
                    <div class="max-w-[80%] p-3.5 bg-indigo-600 text-white rounded-2xl rounded-tr-none text-sm shadow-sm">${text}</div>
                </div>
            `;
            input.value = '';
            chatContainer.scrollTop = chatContainer.scrollHeight;

            const loadingId = 'loading-' + Date.now();
            chatContainer.innerHTML += `
                <div id="${loadingId}" class="flex items-start gap-2.5 animate__animated animate__fadeIn animate__faster">
                    <div class="w-8 h-8 rounded-full bg-indigo-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div>
                    <div class="p-3 bg-gray-100 rounded-2xl text-xs text-gray-500 flex items-center gap-2">
                        <span>ครูมานะกำลังคิดคำตอบ</span>
                        <div class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce"></div>
                        <div class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                        <div class="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    </div>
                </div>
            `;
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });
                const data = await res.json();
                document.getElementById(loadingId).remove();
                chatContainer.innerHTML += `
                    <div class="flex items-start gap-2.5 animate__animated animate__fadeInLeft animate__faster">
                        <div class="w-8 h-8 rounded-full bg-indigo-900 text-white flex items-center justify-center text-xs font-bold shrink-0">ครู</div>
                        <div class="max-w-[80%] p-3.5 bg-indigo-50/70 border border-indigo-100 rounded-2xl rounded-tl-none text-gray-800 text-sm shadow-sm">${data.response}</div>
                    </div>
                `;
                chatContainer.scrollTop = chatContainer.scrollHeight;
            } catch(e) {
                if(document.getElementById(loadingId)) document.getElementById(loadingId).remove();
            }
        });

        // Initial Load
        loadDashboardData();
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    user = session.get("user")
    return render_template_string(DASHBOARD_TEMPLATE, user=user)

# ==================================================
# --- [7] API ENDPOINTS FOR WEB DASHBOARD ---
# ==================================================
@app.route("/api/dashboard_data", methods=["GET"])
def api_dashboard_data():
    hw_list = []
    exam_list = []
    if homework_col is not None:
        hw_list = list(homework_col.find({}, {"_id": 0}))
    if exam_col is not None:
        exam_list = list(exam_col.find({}, {"_id": 0}))
    return jsonify({"homework": hw_list, "exams": exam_list})

@app.route("/api/add_homework", methods=["POST"])
def api_add_homework():
    if homework_col is not None:
        data = request.json or {}
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        homework_col.insert_one({
            "info": data.get("info", ""),
            "teacher": data.get("teacher", ""),
            "created_at": now.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify({"status": "ok"})

@app.route("/api/add_exam", methods=["POST"])
def api_add_exam():
    if exam_col is not None:
        data = request.json or {}
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
        exam_col.insert_one({
            "subject_info": data.get("subject_info", ""),
            "date_time": data.get("date_time", ""),
            "created_at": now.strftime("%Y-%m-%d %H:%M")
        })
    return jsonify({"status": "ok"})

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
        return "กรุณาตั้งค่า LINE_LOGIN_CLIENT_ID ใน Environment Variables ก่อนครับ", 400
    
    base_url = RENDER_APP_URL.strip().rstrip('/') if RENDER_APP_URL else "https://2-9-smart-bot-h6pg.onrender.com"
    redirect_uri = f"{base_url}/login/line/callback"
    
    line_auth_url = (
        f"https://access.line.me/oauth2/v2.1/authorize?response_type=code"
        f"&client_id={LINE_LOGIN_CLIENT_ID}&redirect_uri={redirect_uri}"
        f"&state=12345&scope=profile%20openid"
    )
    return redirect(line_auth_url)

@app.route("/login/line/callback")
def line_login_callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed", 400

    base_url = RENDER_APP_URL.strip().rstrip('/') if RENDER_APP_URL else "https://2-9-smart-bot-h6pg.onrender.com"
    redirect_uri = f"{base_url}/login/line/callback"

    # 1. ขอ Access Token จาก LINE
    token_url = "https://api.line.me/oauth2/v2.1/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": LINE_LOGIN_CLIENT_ID,
        "client_secret": LINE_LOGIN_CLIENT_SECRET
    }
    
    res = requests.post(token_url, data=payload, headers=headers)
    res_data = res.json()
    access_token = res_data.get("access_token")

    if not access_token:
        return f"Login Error: {res_data.get('error_description', 'Failed to get token')}", 400

    # 2. ดึงข้อมูล Profile ผู้ใช้
    profile_url = "https://api.line.me/v2/profile"
    profile_headers = {"Authorization": f"Bearer {access_token}"}
    profile_res = requests.get(profile_url, headers=profile_headers).json()

    # 3. บันทึกลง Session
    session["user"] = {
        "uid": profile_res.get("userId"),
        "name": profile_res.get("displayName"),
        "picture": profile_res.get("pictureUrl", "https://via.placeholder.com/150")
    }

    return redirect(url_for("home"))

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

# ==================================================
# --- [8] LINE WEBHOOK CALLBACK & HANDLERS ---
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

@handler.add(MessageEvent, message=TextMessage) if handler else lambda x: x
def handle_text_message(event):
    global last_random_number
    uid = event.source.user_id
    current_time = time.time()
    
    # Anti-Spam
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
    
    try:
        # 1. เช็คคำสั่งออกจากโหมด AI / กลับหน้าเมนูหลัก
        exit_keywords = ["ยกเลิก", "ออกจากโหมด", "หน้า 1", "เมนู", "วิธีใช้", "ติดต่อแอดมิน"]
        if text in exit_keywords:
            if user_col is not None:
                user_col.delete_one({"user_id": uid}) # ล้าง State ออกจาก DB ทันที
            
            if text in ["ยกเลิก", "ออกจากโหมด"]:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ออกจากโหมดคุยกับครูมานะแล้วครับ มีอะไรให้ช่วยเหลือเลือกเมนูได้เลยครับ"))
                return

            # เมนูหลัก Flex Message
            contents_list = [
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📝 แจ้งการบ้าน", "text": "แจ้งการบ้าน"}},
                {"type": "button", "style": "primary", "color": "#05B4B2", "action": {"type": "message", "label": "📋 เช็คงานสัปดาห์นี้", "text": "เช็คงาน"}},
                {"type": "button", "style": "primary", "color": "#E67E22", "action": {"type": "message", "label": "📢 แจ้งสอบ", "text": "แจ้งสอบ"}},
                {"type": "button", "style": "primary", "color": "#9B59B6", "action": {"type": "message", "label": "🤖 คุยกับครูมานะ", "text": "คุยกับครูมานะ"}}
            ]
            menu1 = {
                "type": "bubble",
                "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "🌸 ม.2/9 Menu", "weight": "bold", "size": "xl", "color": "#1DB446"}]},
                "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": contents_list}
            }
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="Menu", contents=menu1))
            return

        # 2. เช็คการเข้าโหมดครูมานะ
        if text in ["คุยกับครูมานะ", "ครูมานะ"]:
            if user_col is not None:
                user_col.update_one({"user_id": uid}, {"$set": {"state": "ai_chat"}}, upsert=True)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="สวัสดีครับนักเรียน! มีโจทย์การบ้านข้อไหนสงสัย พิมพ์ถามเข้ามาได้เลยนะครับ\n\n(หากต้องการออกจากโหมดนี้ ให้พิมพ์ว่า 'ยกเลิก' ได้เลยครับ)"))
            return

        # 3. ตรวจสอบว่าผู้ใช้อยู่ในโหมด AI หรือไม่
        current_state = None
        if user_col is not None:
            user_doc = user_col.find_one({"user_id": uid})
            if user_doc:
                current_state = user_doc.get("state")

        if current_state == "ai_chat":
            ai_reply = ask_huggingface_ai(user_text=text)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
            return

        # 4. คำสั่งเมนูปกติอื่นๆ
        if text == "เช็คงาน":
            hw_list = list(homework_col.find({})) if homework_col is not None else []
            if not hw_list:
                reply_txt = "🎉 ไม่มีรายการการบ้านค้างในขณะนี้ครับ"
            else:
                reply_txt = "📋 รายการการบ้านทั้งหมด:\n" + "\n".join([f"- {h.get('info')} (ครู{h.get('teacher')})" for h in hw_list])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_txt))
            return

        # ถ้าไม่ตรงเงื่อนไขใดเลย ให้ส่ง AI ตอบแบบสั้นๆ หรือแจ้งเมนู
        ai_reply = ask_huggingface_ai(user_text=text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))

    except Exception as e:
        print(f"LINE Handler Error: {e}")

@handler.add(MessageEvent, message=ImageMessage) if handler else lambda x: x
def handle_image_message(event):
    try:
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        image_bytes = io.BytesIO()
        for chunk in message_content.iter_content():
            image_bytes.write(chunk)
        image_bytes = image_bytes.getvalue()

        ai_reply = ask_huggingface_ai(user_text="ช่วยอธิบายโจทย์ในรูปนี้ให้หน่อยครับ", image_bytes=image_bytes)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=ai_reply))
    except Exception as e:
        print(f"Image Handler Error: {e}")

# ==================================================
# --- [9] START SERVER ---
# ==================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
