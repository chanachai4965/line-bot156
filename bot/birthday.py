"""ตัวช่วยเรื่องวันเกิด — แสดงเฉพาะ วัน + เดือน เท่านั้น (ห้ามเปิดเผยปี/อายุ)"""
from __future__ import annotations

import re
import datetime
from typing import Optional, Tuple

# เดือนภาษาไทยแบบเต็ม (index 0 = มกราคม)
THAI_MONTHS_FULL = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน",
    "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
    "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]

# คำในข้อความผู้ใช้ที่หมายถึงเดือน 1-12 (เรียงจากตัวยาวที่สุดก่อนเพื่อ match ก่อน)
THAI_MONTH_VARIANTS: dict[int, list[str]] = {
    1: ["มกราคม", "มกรา", "ม.ค.", "มค", "january", "jan"],
    2: ["กุมภาพันธ์", "กุมภา", "ก.พ.", "กพ", "february", "feb"],
    3: ["มีนาคม", "มีนา", "มี.ค.", "มีค", "march", "mar"],
    4: ["เมษายน", "เมษา", "เม.ย.", "เมย", "april", "apr"],
    5: ["พฤษภาคม", "พฤษภา", "พ.ค.", "พค", "may"],
    6: ["มิถุนายน", "มิถุนา", "มิ.ย.", "มิย", "june", "jun"],
    7: ["กรกฎาคม", "กรกฎา", "ก.ค.", "กค", "july", "jul"],
    8: ["สิงหาคม", "สิงหา", "ส.ค.", "สค", "august", "aug"],
    9: ["กันยายน", "กันยา", "ก.ย.", "กย", "september", "sept", "sep"],
    10: ["ตุลาคม", "ตุลา", "ต.ค.", "ตค", "october", "oct"],
    11: ["พฤศจิกายน", "พฤศจิกา", "พ.ย.", "พย", "november", "nov"],
    12: ["ธันวาคม", "ธันวา", "ธ.ค.", "ธค", "december", "dec"],
}


def parse_birth(value) -> Optional[Tuple[int, int]]:
    """รับสตริงวันเกิด → คืน (day, month) เท่านั้น ตัดปีทิ้งเสมอ
    รองรับ:
      - "14 ตุลาคม 2530"
      - "7 กุมภาพันธ์ 2531"
      - "2516-03-11" / "2516-03-11 00:00:00"
      - datetime / date / pandas Timestamp
    """
    if value is None:
        return None

    # datetime-like
    if hasattr(value, "month") and hasattr(value, "day"):
        try:
            d = int(value.day)
            m = int(value.month)
            if 1 <= m <= 12 and 1 <= d <= 31:
                return (d, m)
        except Exception:  # noqa: BLE001
            pass

    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None

    # ISO 1: YYYY-MM-DD
    iso = re.match(r"^\s*\d{4}-(\d{1,2})-(\d{1,2})", s)
    if iso:
        m, d = int(iso.group(1)), int(iso.group(2))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return (d, m)

    # ไทย: "14 ตุลาคม 2530" / "7 ก.พ. 2531" / "7 กุมภาพันธ์"
    thai = re.match(
        r"^\s*(\d{1,2})\s*([\u0e00-\u0e7f.]+)\s*\d{0,4}\s*$",
        s,
    )
    if thai:
        d = int(thai.group(1))
        word = thai.group(2).rstrip(".")
        # เรียงชื่อเดือนยาวก่อน เพื่อ match แบบ exact ก่อน
        candidates = []
        for m, names in THAI_MONTH_VARIANTS.items():
            for n in names:
                candidates.append((n.rstrip("."), m))
        candidates.sort(key=lambda x: -len(x[0]))
        for n, m in candidates:
            if word == n or word.startswith(n):
                if 1 <= d <= 31:
                    return (d, m)

    # Slash: "14/10/2530" or "14/10/87"
    slash = re.match(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}\s*$", s)
    if slash:
        d, m = int(slash.group(1)), int(slash.group(2))
        if 1 <= m <= 12 and 1 <= d <= 31:
            return (d, m)

    return None


def format_day_month(day: int, month: int) -> str:
    """13, 2 → '13 กุมภาพันธ์'"""
    if not (1 <= month <= 12):
        return ""
    return f"{day} {THAI_MONTHS_FULL[month - 1]}"


def detect_month_in_query(text: str) -> Optional[int]:
    """หาเดือนที่ผู้ใช้ระบุในข้อความ (1-12) - คืน None ถ้าไม่มี
    รองรับ: 'เดือนนี้', 'เดือนหน้า', 'เดือน 5', 'เดือน พ.ค.', 'พฤษภาคม', 'May'
    """
    if not text:
        return None
    t = text.lower()

    # เดือนนี้/เดือนหน้า
    if "เดือนนี้" in t or "this month" in t:
        return datetime.datetime.now().month
    if "เดือนหน้า" in t or "next month" in t:
        return datetime.datetime.now().month % 12 + 1

    # "เดือน 5" / "เดือน 12"
    num = re.search(r"เดือน\s*(\d{1,2})", t)
    if num:
        n = int(num.group(1))
        if 1 <= n <= 12:
            return n

    # ชื่อเดือน (full / abbreviation)
    # เรียงตัวยาวก่อน เพื่อกัน match พลาด เช่น 'พฤษภา' ก่อน 'พ'
    candidates = []
    for m, names in THAI_MONTH_VARIANTS.items():
        for n in names:
            candidates.append((n, m))
    candidates.sort(key=lambda x: -len(x[0]))
    for name, m in candidates:
        if name in t:
            return m

    return None
