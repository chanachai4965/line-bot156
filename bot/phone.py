"""ตัวจัดการคำถามเรื่องเบอร์โทร — ค้นจากชื่อ/ชื่อเล่น/นามสกุล/เลขที่ → ตอบเบอร์"""
from __future__ import annotations

import re
from typing import Optional, List, Tuple

import pandas as pd

# คำที่บ่งบอกว่าผู้ใช้ "ถามเรื่องเบอร์โทร"
PHONE_QUERY_PATTERNS = [
    r"เบอร์",                      # เบอร์, เบอร์โทร, เบอร์มือถือ, เบอร์ติดต่อ
    r"หมายเลข\s*โทร",
    r"หมายเลข\s*ติดต่อ",
    r"โทรศัพท์",
    r"โทรหา",
    r"ขอ\s*เบอร์",
    r"ติดต่อ",
    r"\bphone\b",
    r"\bmobile\b",
    r"\btel\b",
    r"\bcontact\b",
    r"call\s",
]

# คำที่จะถูกตัดออกก่อนค้นชื่อ — เรียง "ตัวยาวก่อน" เพื่อกัน collision เช่น "ขอ" กิน "ของ"
PHONE_NOISE_WORDS = [
    # 1) คำเฉพาะเรื่องเบอร์ (ตัวยาวก่อน)
    r"ขอเบอร์โทรศัพท์", r"ขอเบอร์มือถือ", r"ขอเบอร์ติดต่อ", r"ขอเบอร์โทร", r"ขอเบอร์",
    r"เบอร์โทรศัพท์", r"เบอร์มือถือ", r"เบอร์ติดต่อ", r"เบอร์โทร", r"เบอร์",
    r"หมายเลขโทรศัพท์", r"หมายเลขติดต่อ", r"หมายเลข",
    r"โทรศัพท์", r"โทรหา", r"โทร",
    r"ติดต่อยังไง", r"ติดต่อได้ที่", r"ติดต่อได้", r"ติดต่อ",
    r"ขอที่ติดต่อ",
    # 2) คำกริยา/คำขอ (ระวัง — ห้ามใช้ "ขอ" เดี่ยว เพราะกินคำว่า "ของ")
    r"บอก", r"ฝาก",
    # 3) คำสุภาพ/คำเรียก
    r"พี่", r"น้อง", r"คุณ", r"ท่าน",
    # 4) คำเชื่อม
    r"ของ", r"ยังไง", r"ที่ไหน", r"หน่อย",
    # 5) ภาษาอังกฤษ
    r"\bphone\s*number\b", r"\bphone\b", r"\bmobile\b",
    r"\btel\b", r"\bcontact\b", r"\bcall\b", r"\bnumber\b",
    r"\bof\b", r"\bplease\b",
]


def is_phone_query(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(re.search(p, t, flags=re.IGNORECASE) for p in PHONE_QUERY_PATTERNS)


def _strip_noise(text: str) -> str:
    t = text
    for w in PHONE_NOISE_WORDS:
        t = re.sub(w, " ", t, flags=re.IGNORECASE)
    t = re.sub(r"[?\.,!?:;\-\u2014\u2013/()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _format_phone(value: str) -> str:
    """จัดรูปแบบเบอร์โทร: 0654959191 → 065-495-9191"""
    if value is None:
        return ""
    s = re.sub(r"\D", "", str(value))
    if not s:
        return str(value).strip()
    # ถ้าหายเลข 0 หน้า (เช่น excel เก็บเป็น int) ใส่ให้
    if len(s) == 9 and not s.startswith("0"):
        s = "0" + s
    if len(s) == 10:
        return f"{s[:3]}-{s[3:6]}-{s[6:]}"
    if len(s) == 9:
        return f"{s[:2]}-{s[2:5]}-{s[5:]}"
    return s


def _person_label(row: pd.Series) -> str:
    ys = str(row.get("ยศ", "")).strip()
    nm = str(row.get("ชื่อ", "")).strip()
    sn = str(row.get("สกุล", "")).strip()
    nick = str(row.get("ชื่อเล่น", "")).strip()
    no = str(row.get("เลขที่", "")).strip()
    head = " ".join(x for x in [ys, nm, sn] if x)
    if nick:
        head += f" ({nick})"
    if no:
        head = f"#{no} {head}"
    return head.strip()


def search_phone(text: str, contacts_df: pd.DataFrame) -> Optional[str]:
    """ค้นเบอร์โทรจาก text — คืน string คำตอบ หรือ None ถ้าไม่ตรง pattern เลย"""
    if contacts_df is None or contacts_df.empty:
        return None
    if "เบอร์มือถือ" not in contacts_df.columns:
        return None

    cleaned = _strip_noise(text).lower()
    if not cleaned:
        return (
            "ขอชื่อ/ชื่อเล่น/เลขที่ ที่อยากได้เบอร์ด้วยครับ\n"
            "เช่น `เบอร์เท็น` หรือ `ขอเบอร์ 156`"
        )

    name_cols = [c for c in ["ชื่อ", "สกุล", "ชื่อเล่น"] if c in contacts_df.columns]
    mask = pd.Series([False] * len(contacts_df))

    # 1) ค้นแบบสตริงรวม
    for col in name_cols:
        mask = mask | contacts_df[col].astype(str).str.lower().str.contains(
            re.escape(cleaned), na=False
        )

    # 2) ค้นทีละ token (สำหรับชื่อ-นามสกุลที่พิมพ์มาคู่กัน หรือมีคำเสริม)
    tokens = [t for t in re.split(r"\s+", cleaned) if len(t) >= 2 and not t.isdigit()]
    for tok in tokens:
        for col in name_cols:
            mask = mask | contacts_df[col].astype(str).str.lower().str.contains(
                re.escape(tok), na=False
            )

    # 3) ค้นด้วยเลขที่ ถ้ามีตัวเลข
    num = re.search(r"\d{1,3}", cleaned)
    if num and "เลขที่" in contacts_df.columns:
        n = num.group(0)
        col = contacts_df["เลขที่"].astype(str).str.strip()
        mask = mask | (col == n) | (col == n.zfill(3)) | (col.str.lstrip("0") == str(int(n)))

    hits = contacts_df[mask]
    if hits.empty:
        return None

    rows: List[Tuple[str, str]] = []
    for _, r in hits.head(10).iterrows():
        phone = _format_phone(r.get("เบอร์มือถือ", ""))
        label = _person_label(r)
        rows.append((label, phone))

    if not rows:
        return None

    lines = [f"📞 {label}\n   {phone or '— ไม่มีเบอร์ในไฟล์'}" for label, phone in rows]
    extra = ""
    if len(hits) > 10:
        extra = f"\n…เจอทั้งหมด {len(hits)} คน แสดง 10 คนแรกนะครับ"
    return "\n\n".join(lines) + extra
