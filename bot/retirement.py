"""โมดูลค้นหาคนเกษียณตามปี พ.ศ. (รองรับช่วง 2559-2575)

ข้อควรระวัง: ฟีเจอร์นี้คำนวณปีเกษียณจากปีเกิด ดังนั้นการตอบคำถาม
"ใครเกษียณปี XXXX" จะเปิดเผยปีเกิดทางอ้อม — ต้องยอมรับ trade-off นี้
"""
from __future__ import annotations

import re
from typing import Optional, List

import pandas as pd

from .birthday import THAI_MONTH_VARIANTS

# ขอบเขตปี พ.ศ. ที่รองรับ
RETIRE_YEAR_MIN = 2559
RETIRE_YEAR_MAX = 2575

# Keyword ที่บ่งบอกว่าถามเรื่องเกษียณ
RETIREMENT_PATTERNS = [
    r"เกษียณ",
    r"เกษียน",       # สะกดผิดที่พบบ่อย
    r"retire",
    r"retirement",
    r"ครบ\s*เกษียณ",
    r"ปลดเกษียณ",
]


# ================================================================
# Birth date parsing — ครั้งนี้ต้องการ "ปีเต็ม" (ต่างจาก birthday.py
# ที่จงใจทิ้งปี) เพื่อเอาไปคำนวณปีเกษียณ
# ================================================================
THAI_MONTH_TO_NUM = {}
for num, variants in THAI_MONTH_VARIANTS.items():
    for v in variants:
        THAI_MONTH_TO_NUM[v.lower()] = num


def _parse_birth_full(value: str) -> Optional[tuple[int, int, int]]:
    """แปลง 'วันเดือนปีเกิด' เป็น (day, month, year_BE)
    รองรับรูปแบบ:
      - "14 ตุลาคม 2530"
      - "2516-03-11" (ISO, ปี ค.ศ.)
      - "14/10/2530" (slash, ปี พ.ศ.)
      - "14-10-2530"
    คืน None ถ้า parse ไม่ได้
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None

    # ISO format: YYYY-MM-DD (เป็น ค.ศ.)
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y_ce, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # ถ้า y < 2200 น่าจะเป็น ค.ศ. -> แปลงเป็น พ.ศ.
        y_be = y_ce + 543 if y_ce < 2200 else y_ce
        return (d, mo, y_be)

    # Slash/dash: D/M/Y (ปี พ.ศ.)
    m = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # ถ้า y < 2400 น่าจะเป็น ค.ศ.
        y_be = y + 543 if y < 2400 else y
        return (d, mo, y_be)

    # Thai: "14 ตุลาคม 2530"
    m = re.match(r"^(\d{1,2})\s*([\u0E00-\u0E7Fa-zA-Z\.]+)\s*(\d{4})", s)
    if m:
        d = int(m.group(1))
        month_str = m.group(2).strip().lower()
        y = int(m.group(3))
        mo = THAI_MONTH_TO_NUM.get(month_str)
        if mo is None:
            # ลองตัดจุดออก
            mo = THAI_MONTH_TO_NUM.get(month_str.replace(".", ""))
        if mo is None:
            return None
        y_be = y + 543 if y < 2400 else y
        return (d, mo, y_be)

    return None


# ================================================================
# คำนวณปีเกษียณ
# ================================================================
def compute_retirement_year_be(birth_year_be: int, birth_month: int) -> int:
    """ปีเกษียณ (พ.ศ.) ตามกฎ ก.พ.
    - เกษียณ 30 ก.ย. ของปีงบประมาณที่อายุครบ 60
    - ปีงบ ไทย: 1 ต.ค. - 30 ก.ย.
    """
    if birth_month >= 10:  # ต.ค./พ.ย./ธ.ค.
        return birth_year_be + 61
    return birth_year_be + 60


# ================================================================
# Detection
# ================================================================
def _extract_year_be(text: str) -> Optional[int]:
    """ดึงเลขปี พ.ศ. 4 หลัก จากข้อความ - คืน None ถ้าไม่มี"""
    # หา 4-digit number
    matches = re.findall(r"\b(\d{4})\b", text)
    for m in matches:
        y = int(m)
        # ถ้าเป็น ค.ศ. แปลงเป็น พ.ศ.
        if 2000 <= y <= 2050:
            y_be = y + 543
        elif 2500 <= y <= 2700:
            y_be = y
        else:
            continue
        if RETIRE_YEAR_MIN <= y_be <= RETIRE_YEAR_MAX:
            return y_be
    return None


def is_retirement_query(text: str) -> bool:
    """ข้อความนี้ถามเรื่อง 'เกษียณ' หรือเปล่า"""
    if not text:
        return False
    for pat in RETIREMENT_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True
    return False


# ================================================================
# Search
# ================================================================
def _person_label(row: pd.Series) -> str:
    parts = []
    nickname = str(row.get("ชื่อเล่น", "")).strip()
    name = str(row.get("ชื่อ", "")).strip()
    surname = str(row.get("สกุล", "")).strip()
    seat = str(row.get("เลขที่", "")).strip()
    if nickname:
        parts.append(f"พี่{nickname}")
    if name or surname:
        parts.append(f"({name} {surname})".replace("  ", " ").strip())
    label = " ".join(parts) if parts else "(ไม่ทราบชื่อ)"
    if seat:
        label = f"#{seat} {label}"
    return label


def search_retirement(text: str, contacts_df: pd.DataFrame) -> Optional[str]:
    """ค้นหาคนเกษียณตามปี พ.ศ. ที่ผู้ใช้ถาม
    คืนสตริงคำตอบ หรือ None ถ้าไม่เข้าเงื่อนไข
    """
    if contacts_df is None or contacts_df.empty:
        return None
    if "วันเดือนปีเกิด" not in contacts_df.columns:
        return None

    target_year = _extract_year_be(text)
    if target_year is None:
        return (
            f"🔎 ลองระบุปี พ.ศ. ที่ต้องการดูค่ะ (รองรับ {RETIRE_YEAR_MIN}-{RETIRE_YEAR_MAX})\n"
            f"เช่น \"บอท ใครเกษียณปี 2570\""
        )

    # คำนวณปีเกษียณของทุกแถว
    matches: List[pd.Series] = []
    for _, row in contacts_df.iterrows():
        parsed = _parse_birth_full(row.get("วันเดือนปีเกิด", ""))
        if parsed is None:
            continue
        _, month, year_be = parsed
        retire_be = compute_retirement_year_be(year_be, month)
        if retire_be == target_year:
            matches.append(row)

    if not matches:
        return f"🔎 ปี พ.ศ. {target_year}\nยังไม่พบใครเกษียณปีนี้ค่ะ 🌷"

    lines = [f"🎓 เกษียณปี พ.ศ. {target_year} — เจอ {len(matches)} คนค่ะ"]
    for row in matches:
        lines.append(f"• {_person_label(row)}")

    if len(lines) > 51:
        lines = lines[:51] + [f"… และอีก {len(matches) - 50} คน"]

    return "\n".join(lines)


# ================================================================
# ทางเลือก A: ตอบเฉพาะจำนวน ไม่บอกชื่อ (เพื่อลด privacy exposure)
# ================================================================
def search_retirement_count_only(text: str, contacts_df: pd.DataFrame) -> Optional[str]:
    """เวอร์ชันที่ตอบเฉพาะจำนวน ไม่บอกชื่อ"""
    if contacts_df is None or contacts_df.empty:
        return None
    if "วันเดือนปีเกิด" not in contacts_df.columns:
        return None

    target_year = _extract_year_be(text)
    if target_year is None:
        return (
            f"🔎 ลองระบุปี พ.ศ. ที่ต้องการดูค่ะ (รองรับ {RETIRE_YEAR_MIN}-{RETIRE_YEAR_MAX})"
        )

    count = 0
    for _, row in contacts_df.iterrows():
        parsed = _parse_birth_full(row.get("วันเดือนปีเกิด", ""))
        if parsed is None:
            continue
        _, month, year_be = parsed
        if compute_retirement_year_be(year_be, month) == target_year:
            count += 1

    return f"🎓 ปี พ.ศ. {target_year} มีคนเกษียณ {count} คนค่ะ (ขอสงวนรายชื่อนะคะ 🤫)"
