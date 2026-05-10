#!/bin/bash

# --- ตั้งค่าตรงนี้ ---
PORT=5000
LOG_FILE="tunnel.log"

echo "🚀 Cloudflared Monitor Started..."
echo "📊 Logging to: $LOG_FILE"

while true; do
    # เช็คว่ามี process cloudflared ทำงานอยู่ไหม
    if pgrep -x "cloudflared" > /dev/null
    then
        # ถ้ายังอยู่ ไม่ทำอะไร รอ 10 วินาทีเช็คใหม่
        sleep 10
    else
        echo "⚠️ Cloudflared ดับ! กำลังเริ่มเชื่อมต่อใหม่..."
        # รัน cloudflared แบบเก็บ Log เพื่อเอาไว้ดู URL ใหม่
        # ใช้พอร์ต 5000 ตามที่พชรภัทรตั้งใน Flask
        nohup cloudflared tunnel --url http://localhost:$PORT > $LOG_FILE 2>&1 &
        echo "✅ สั่งรันใหม่เรียบร้อย รอเช็ค URL ใน $LOG_FILE"
        sleep 15
    fi
done

