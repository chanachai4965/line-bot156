"""
สคริปต์แปลง contacts.xlsx → contacts.json
- ใช้ตอนอัปเดตข้อมูล (เพิ่ม/แก้ไขสมาชิก) ในไฟล์ Excel
- รัน:  python convert_xlsx_to_json.py contacts.xlsx
- ผลลัพธ์:  contacts.json ในโฟลเดอร์เดียวกัน

ความสำคัญ:
- จะ "ตัดปีเกิด" และ "ไม่เก็บอายุ" ในผลลัพธ์ JSON
- เพื่อให้บอทไม่สามารถเปิดเผยปีเกิด/อายุได้
"""

import sys
import os
import re
import json

import pandas as pd


def strip_year(s):
    """ตัดปี (4 หลัก) ที่อยู่ท้ายข้อความออก เหลือเฉพาะวันที่+เดือน"""
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = re.sub(r"\s*\d{4}\s*$", "", s)
    return s.strip()


def gdrive_to_direct(url):
    """แปลง Google Drive view link เป็น direct image link"""
    if pd.isna(url) or not url:
        return ""
    url = str(url).strip()
    m = re.search(r"/d/([A-Za-z0-9_-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=view&id={m.group(1)}"
    return url


def safe_str(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def convert(xlsx_path, out_path=None):
    df = pd.read_excel(xlsx_path)
    df.columns = [c.strip() for c in df.columns]

    contacts = []
    for _, row in df.iterrows():
        contacts.append({
            "no": int(row["เลขที่"]) if not pd.isna(row.get("เลขที่")) else 0,
            "affiliation": safe_str(row.get("สังกัด")),
            "rank": safe_str(row.get("ยศ")),
            "first_name": safe_str(row.get("ชื่อ")),
            "last_name": safe_str(row.get("สกุล")),
            "nickname": safe_str(row.get("ชื่อเล่น")),
            "position": safe_str(row.get("ตำแหน่งปัจจุบัน")),
            "phone": safe_str(row.get("เบอร์มือถือ")),
            "birthday": strip_year(row.get("วันเดือนปีเกิด")),  # ❌ ไม่มีปี
            "training": safe_str(row.get("การอบรม")),
            "training_class": safe_str(row.get("รุ่นที่อบรม")),
            "image_url": gdrive_to_direct(row.get("รูปภาพ")),
            # *** ไม่เก็บฟิลด์ "อายุ" ลง JSON เพื่อความเป็นส่วนตัว ***
        })

    if out_path is None:
        out_path = os.path.join(os.path.dirname(os.path.abspath(xlsx_path)), "contacts.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)

    print(f"✅ แปลง {len(contacts)} รายการ → {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ใช้งาน:  python convert_xlsx_to_json.py contacts.xlsx [output.json]")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    convert(src, dst)
