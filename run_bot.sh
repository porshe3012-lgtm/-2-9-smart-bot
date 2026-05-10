#!/bin/bash
until python main.py; do
    echo "⚠️ บอทหลุด/พัง (Exit code $?). กำลังเริ่มใหม่ใน 5 วินาที..." >&2
    sleep 5
done
