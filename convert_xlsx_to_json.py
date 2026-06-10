"""
สคริปต์แปลง contacts.xlsx → contacts.json
- ใช้ตอนอัปเดตข้อมูล (เพิ่ม/แก้ไขสมาชิก) ในไฟล์ Excel
- รัน:  python convert_xlsx_to_json.py contacts.xlsx
- ผลลัพธ์:  contacts.json ในโฟลเดอร์เดียวกัน

ความสำคัญ:
- จะ "ตัดปีเกิด" และ "ไม่เก็บอายุ" ในผลลัพธ์ JSON
- เพื่อให้บอทไม่สามารถเปิดเผยปีเกิด/อายุได้
- คำนวณ "ปีเกษียณ" (พ.ศ.) จากวันเดือนปีเกิด ตามระเบียบราชการไทย
  (เกษียณ 30 ก.ย. ของปีงบประมาณที่อายุ 60 ปีบริบูรณ์)
"""

import sys
import os
import re
import json

import pandas as pd

THAI_MONTHS = {
    "มกราคม": 1, "กุมภาพันธ์": 2, "มีนาคม": 3, "เมษายน": 4, "พฤษภาคม": 5,
    "มิถุนายน": 6, "กรกฎาคม": 7, "สิงหาคม": 8, "กันยายน": 9,
    "ตุลาคม": 10, "พฤศจิกายน": 11, "ธันวาคม": 12,
}


def parse_thai_date(s):
    """แปลง '14 ตุลาคม 2530' → (14, 10, 2530) หรือ (None, None, None)"""
    if pd.isna(s):
        return (None, None, None)
    s = str(s).strip()
    m = re.match(r"^\s*(\d{1,2})\s+([ก-๙]+)\s+(\d{4})\s*$", s)
    if not m:
        return (None, None, None)
    day = int(m.group(1))
    month_name = m.group(2)
    year_be = int(m.group(3))  # ปี พ.ศ.
    month = THAI_MONTHS.get(month_name)
    if not month:
        return (None, None, None)
    return (day, month, year_be)


def calc_retirement_year(day, month, year_be):
    """
    คำนวณปีเกษียณ (พ.ศ.) ตามระเบียบราชการไทย
    - เกษียณ 30 ก.ย. ของปีงบประมาณที่อายุ 60 ปีบริบูรณ์
    - ปีงบประมาณไทย: 1 ต.ค. – 30 ก.ย.
    - ถ้าเกิดวันที่ 1 ต.ค. ขึ้นไป → เกษียณปี (พ.ศ.เกิด + 61)
    - ถ้าเกิด 30 ก.ย. หรือก่อนหน้า → เกษียณปี (พ.ศ.เกิด + 60)
    """
    if not day or not month or not year_be:
        return None
    if month >= 10:  # ต.ค. (10), พ.ย. (11), ธ.ค. (12) → ปีงบประมาณถัดไป
        return year_be + 61
    return year_be + 60


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
    # ---- ชีทแรก: contacts ----
    df = pd.read_excel(xlsx_path, sheet_name=0)
    df.columns = [c.strip() for c in df.columns]

    contacts = []
    for _, row in df.iterrows():
        bday_raw = row.get("วันเดือนปีเกิด")
        _d, _m, _y = parse_thai_date(bday_raw)
        retirement_year = calc_retirement_year(_d, _m, _y)
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
            "retirement_year": retirement_year,  # ✅ ปีเกษียณ (พ.ศ.) — ข้อมูลสาธารณะ
            # *** ไม่เก็บฟิลด์ "อายุ" ลง JSON เพื่อความเป็นส่วนตัว ***
        })

    base_dir = os.path.dirname(os.path.abspath(xlsx_path))
    if out_path is None:
        out_path = os.path.join(base_dir, "contacts.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)
    print(f"✅ แปลง contacts {len(contacts)} รายการ → {out_path}")

    # ---- ชีท "คำถาม คำตอบ" → qa.json ----
    try:
        qa_df = pd.read_excel(xlsx_path, sheet_name="คำถาม คำตอบ")
        qa_df.columns = [c.strip() for c in qa_df.columns]
        qa_list = []
        for _, row in qa_df.iterrows():
            q = row.get("คำถาม")
            a = row.get("คำตอบ")
            if pd.isna(q) or pd.isna(a):
                continue
            q_str = str(q).strip()
            a_str = str(a).strip()
            if not q_str or not a_str:
                continue
            # คำถามหลายแบบคั่นด้วยคอมมา
            questions = [x.strip() for x in re.split(r"[,，]", q_str) if x.strip()]
            qa_list.append({"questions": questions, "answer": a_str})
        qa_path = os.path.join(base_dir, "qa.json")
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(qa_list, f, ensure_ascii=False, indent=2)
        print(f"✅ แปลง Q&A {len(qa_list)} รายการ → {qa_path}")
    except Exception as e:
        print(f"⚠️  ข้ามชีท Q&A: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ใช้งาน:  python convert_xlsx_to_json.py contacts.xlsx [output.json]")
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    convert(src, dst)
