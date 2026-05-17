from .affiliation import is_affiliation_query, search_affiliation
"""สมองของบอท - รับข้อความ, จับคู่ข้อมูล, ส่งคำตอบกลับ"""

import os
import re
import unicodedata
from typing import Optional, List

import pandas as pd

from .data_loader import load_all_excels, get_contacts_df, get_qa_df
from .birthday import parse_birth, format_day_month, detect_month_in_query, THAI_MONTHS_FULL
from .affiliation import search_affiliation
from .responses import (
    AGE_REFUSALS,
    NOT_FOUND,
    GREETINGS,
    HELP_TEXT,
    BIRTH_NOT_FOUND,
    random_pick,
)

# ---------- Banned keywords (ห้ามตอบเด็ดขาด) ----------
# จะตอบเรื่องอายุ/ปีเกิดไม่ได้เลย แต่ "เดือนเกิด/วันเกิด" ตอบได้
AGE_PATTERNS = [
    r"อายุ",
    r"ปีเกิด",
    r"เกิด\s*ปี",                    # "เกิดปีไหน", "เกิดปี 2533"
    r"เกิด\s*พ\.?\s*ศ\.?",           # "เกิด พ.ศ."
    r"เกิด\s*ค\.?\s*ศ\.?",           # "เกิด ค.ศ."
    r"เกิด\s*เมื่อ\s*ปี",
    r"เกิด\s*เมื่อ\s*\d{4}",
    r"เกิด.*\b\d{4}\b",              # "เกิด ... 2533"  (ต้องมีปีตัวเลข)
    r"พ\.?\s*ศ\.?\s*\d",             # "พ.ศ. 2530"
    r"ค\.?\s*ศ\.?\s*\d",             # "ค.ศ. 1987"
    r"กี่\s*ขวบ",
    r"กี่\s*ปี",
    r"วัน\s*เดือน\s*ปี\s*เกิด",     # ขอครบทั้งวัน เดือน ปี = ห้าม
    r"how\s*old",
    r"\bage\b",
    r"\bdob\b",
    r"birth\s*year",
    r"date\s*of\s*birth",
    r"year\s*of\s*birth",
]

# คำที่บ่งบอกว่าผู้ใช้ "ถามเรื่องวันเกิด/เดือนเกิด" (ไม่ใช่ปี/อายุ)
BIRTH_QUERY_PATTERNS = [
    r"เกิด\s*เดือน",
    r"เดือน\s*เกิด",
    r"เกิด\s*วัน",
    r"วัน\s*เกิด",
    r"birthday",
    r"birth\s*day",
    r"birth\s*month",
    r"เกิด\s*เมื่อ\s*ไหร่",
    r"เกิด\s*วันที่",
]

GREETING_PATTERNS = [
    r"^\s*(สวัสดี|หวัดดี|hi|hello|hey|ดีครับ|ดีค่ะ|ดีจ้า)",
]

HELP_KEYWORDS = ["ช่วยเหลือ", "help", "เมนู", "คำสั่ง", "วิธีใช้"]

COMMITTEE_KEYWORDS = ["กรรมการ", "ประธาน", "รองประธาน", "ที่ปรึกษา"]
STAFF_KEYWORDS = ["เจ้าหน้าที่", "จนท", "ประจำหลักสูตร", "อาจารย์"]


# ---------- Module state ----------
_DATA_DIR = os.environ.get(
    "DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
)

_sheets: dict = {}
_contacts_df: pd.DataFrame = pd.DataFrame()
_qa_df: pd.DataFrame = pd.DataFrame()


def reload_data() -> None:
    """โหลด/รีโหลดข้อมูลจากไฟล์ Excel"""
    global _sheets, _contacts_df, _qa_df
    _sheets = load_all_excels(_DATA_DIR)
    _contacts_df = get_contacts_df(_sheets)
    _qa_df = get_qa_df(_sheets)
    print(
        f"[qa_engine] โหลดข้อมูลแล้ว: ชีต={list(_sheets.keys())}, "
        f"ติดต่อ={len(_contacts_df)} แถว, Q&A={len(_qa_df)} แถว"
    )


# ---------- Helpers ----------
def _norm(text: str) -> str:
    """ตัดช่องว่างซ้ำ + lowercase + normalize unicode"""
    if text is None:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_age_question(msg: str) -> bool:
    m = _norm(msg)
    return any(re.search(p, m) for p in AGE_PATTERNS)


def _is_birth_query(msg: str) -> bool:
    m = _norm(msg)
    return any(re.search(p, m) for p in BIRTH_QUERY_PATTERNS)


def _is_greeting(msg: str) -> bool:
    m = _norm(msg)
    return any(re.search(p, m) for p in GREETING_PATTERNS)


def _is_help(msg: str) -> bool:
    m = _norm(msg)
    return any(k in m for k in HELP_KEYWORDS)


def _format_contact_row(row: pd.Series) -> str:
    """สร้างข้อความรายละเอียดบุคคล - ตัดอายุ/ปีเกิดทิ้งเสมอ"""
    parts: List[str] = []
    order = [
        "เลขที่",
        "ปฏิบัติหน้าที่",
        "ฝ่าย",
        "สังกัด",
        "ยศ",
        "ชื่อ",
        "สกุล",
        "ชื่อเล่น",
        "ตำแหน่งปัจจุบัน",
        "เบอร์มือถือ",
        "การอบรม",
        "รุ่นที่อบรม",
    ]
    for col in order:
        if col in row.index:
            val = str(row.get(col, "")).strip()
            if val and val.lower() != "nan":
                parts.append(f"• {col}: {val}")

    name_full = " ".join(
        x for x in [str(row.get("ยศ", "")).strip(), str(row.get("ชื่อ", "")).strip(), str(row.get("สกุล", "")).strip()] if x
    )
    nick = str(row.get("ชื่อเล่น", "")).strip()
    header = f"👮 {name_full}" + (f" ({nick})" if nick else "")
    return header + "\n" + "\n".join(parts) if parts else header


def _search_qa(msg: str) -> Optional[str]:
    """หาในชีต ‘คำถาม คำตอบ’ - คำถามแต่ละแถวอาจคั่นด้วย ',' หลายแบบ"""
    if _qa_df.empty:
        return None
    m = _norm(msg)
    best: Optional[tuple] = None  # (score, answer)
    for _, row in _qa_df.iterrows():
        q_raw = str(row.get("คำถาม", "")).strip()
        a_raw = str(row.get("คำตอบ", "")).strip()
        if not q_raw or not a_raw:
            continue
        # อาจมีหลายคำถามคั่นด้วย , หรือ /
        for q in re.split(r"[,/|]", q_raw):
            q_n = _norm(q)
            if not q_n:
                continue
            if q_n == m:
                return a_raw
            if q_n in m or m in q_n:
                score = len(q_n)
                if best is None or score > best[0]:
                    best = (score, a_raw)
    return best[1] if best else None


def _search_contacts(msg: str) -> Optional[str]:
    """ค้นหาในรายชื่อบุคคล"""
    if _contacts_df.empty:
        return None
    m = _norm(msg)

    # ค้นด้วยเลขที่ (ตัวเลขล้วน หรือ "เลขที่ 156", "no.156")
    num_match = re.search(r"(?:เลขที่|no\.?|#)?\s*(\d{1,3})", m)
    if num_match and "เลขที่" in _contacts_df.columns:
        raw = num_match.group(1)
        no_zero = str(int(raw))           # "41"
        with_zero3 = no_zero.zfill(3)     # "041"
        with_zero_orig = raw              # ตามที่ user พิมพ์
        targets = {raw, no_zero, with_zero3, with_zero_orig}
        col = _contacts_df["เลขที่"].astype(str).str.strip()
        # normalize ทั้งสองฝั่งให้ตัด zero ซ้ายก่อนเทียบ เพื่อรองรับทุกแบบ
        col_norm = col.str.lstrip("0")
        hits = _contacts_df[col.isin(targets) | (col_norm == no_zero)]
        # ตรวจสอบว่าข้อความสั้นพอจะตีความว่าเป็นการค้นเลขที่
        if not hits.empty and len(m) <= 12:
            rows = [_format_contact_row(r) for _, r in hits.iterrows()]
            return "\n\n".join(rows[:5])

    # ค้นด้วยชื่อ/นามสกุล/ชื่อเล่น (substring match)
    name_cols = [c for c in ["ชื่อ", "สกุล", "ชื่อเล่น"] if c in _contacts_df.columns]
    if name_cols:
        mask = pd.Series([False] * len(_contacts_df))
        for col in name_cols:
            mask = mask | _contacts_df[col].astype(str).str.lower().str.contains(
                re.escape(m), na=False
            )
        hits = _contacts_df[mask]
        if not hits.empty:
            rows = [_format_contact_row(r) for _, r in hits.head(5).iterrows()]
            extra = ""
            if len(hits) > 5:
                extra = f"\n\n…เจอทั้งหมด {len(hits)} คน แสดง 5 คนแรกนะครับ"
            return "\n\n".join(rows) + extra

    # ค้นด้วยสังกัด/ตำแหน่ง
    other_cols = [c for c in ["สังกัด", "ตำแหน่งปัจจุบัน", "ปฏิบัติหน้าที่", "ฝ่าย"] if c in _contacts_df.columns]
    if other_cols and len(m) >= 2:
        mask = pd.Series([False] * len(_contacts_df))
        for col in other_cols:
            mask = mask | _contacts_df[col].astype(str).str.lower().str.contains(
                re.escape(m), na=False
            )
        hits = _contacts_df[mask]
        if not hits.empty:
            # แสดงแบบสรุป (ชื่อเล่น/เลขที่)
            lines = []
            for _, r in hits.head(15).iterrows():
                lines.append(
                    f"• #{str(r.get('เลขที่','')).strip()} "
                    f"{str(r.get('ยศ','')).strip()} "
                    f"{str(r.get('ชื่อ','')).strip()} "
                    f"{str(r.get('สกุล','')).strip()} "
                    f"({str(r.get('ชื่อเล่น','')).strip()})"
                )
            extra = (
                f"\n…เจอทั้งหมด {len(hits)} คน แสดง 15 คนแรกนะครับ"
                if len(hits) > 15
                else ""
            )
            return f"พบ {len(hits)} คนที่เกี่ยวข้องครับ:\n" + "\n".join(lines) + extra

    return None


def _strip_name_words(text: str) -> str:
    """ตัดคำเกี่ยวกับ ‘เกิด/เดือน/วัน/คำถาม’ ออก เหลือเฉพาะส่วนที่น่าจะเป็นชื่อ"""
    t = text
    for pat in [
        r"ขอ\s*ทราบ", r"ขอทราบ", r"บอก", r"ใคร", r"บ้าง",
        r"เกิดเดือน", r"เดือนเกิด", r"เกิดวันที่", r"เกิดวัน",
        r"วันเกิด", r"เกิดเมื่อไหร่", r"เกิด",
        r"เดือนนี้", r"เดือนหน้า", r"เดือน",
        r"วันที่", r"วัน",
        # คำถามทั่วไปที่ตามท้ายมักไม่ใช่ชื่อ
        r"ที่ไหน", r"ตอนไหน", r"เมื่อไหร่", r"เท่าไหร่",
        r"ไหน", r"อะไร", r"อย่างไร", r"ยังไง", r"ที่", r"ของ",
        r"birthday", r"birth\s*day", r"birth\s*month",
        r"this\s*month", r"next\s*month", r"\bof\b", r"\bin\b",
    ]:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)
    t = re.sub(r"[?\.,!?:;\-\u2014\u2013/()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _format_birthdays_in_month(month: int) -> str:
    if _contacts_df.empty or "วันเดือนปีเกิด" not in _contacts_df.columns:
        return random_pick(BIRTH_NOT_FOUND)

    rows: list[tuple[int, pd.Series]] = []
    for _, r in _contacts_df.iterrows():
        parsed = parse_birth(r.get("วันเดือนปีเกิด", ""))
        if parsed and parsed[1] == month:
            rows.append((parsed[0], r))

    if not rows:
        return f"เดือน{THAI_MONTHS_FULL[month - 1]} หนูไม่เจอใครเกิดเดือนนี้เลยครับ 🙃"

    rows.sort(key=lambda x: x[0])
    lines = []
    for day, r in rows:
        no = str(r.get("เลขที่", "")).strip()
        ys = str(r.get("ยศ", "")).strip()
        nm = str(r.get("ชื่อ", "")).strip()
        sn = str(r.get("สกุล", "")).strip()
        nick = str(r.get("ชื่อเล่น", "")).strip()
        tag = f"#{no}" if no else ""
        nick_part = f" ({nick})" if nick else ""
        lines.append(f"• {day:>2} — {tag} {ys} {nm} {sn}{nick_part}".replace("  ", " ").strip())

    header = f"🎂 ชาวรุ่น 156 ที่เกิดเดือน{THAI_MONTHS_FULL[month - 1]} ({len(rows)} คน)"
    return header + "\n" + "\n".join(lines)


def _format_person_birth(query_remainder: str) -> Optional[str]:
    """ค้นบุคคลในส่วนที่เหลือของข้อความ → ตอบ ‘ชื่อ เกิดวันที่ X เดือน Y’ (ไม่มีปี)
    รองรับหลายโทเค็นในคำถาม เช่น 'เท็น' / 'พี่เท็น' / 'ทศพล กิติลาภ'
    """
    q = _norm(query_remainder)
    if not q or _contacts_df.empty:
        return None
    if "วันเดือนปีเกิด" not in _contacts_df.columns:
        return None

    name_cols = [c for c in ["ชื่อ", "สกุล", "ชื่อเล่น"] if c in _contacts_df.columns]
    mask = pd.Series([False] * len(_contacts_df))

    # 1) ค้นด้วย string เต็ม
    for col in name_cols:
        mask = mask | _contacts_df[col].astype(str).str.lower().str.contains(
            re.escape(q), na=False
        )

    # 2) ค้นทีละ token (ตัวยาว ≥ 2)
    tokens = [t for t in re.split(r"\s+", q) if len(t) >= 2 and not t.isdigit()]
    for tok in tokens:
        for col in name_cols:
            mask = mask | _contacts_df[col].astype(str).str.lower().str.contains(
                re.escape(tok), na=False
            )

    # 3) รองรับการระบุเลขที่ เช่น "156 เกิดวันไหน"
    num = re.search(r"(?:เลขที่|no\.?|#)?\s*(\d{1,3})", q)
    if num and "เลขที่" in _contacts_df.columns:
        n = num.group(1)
        col = _contacts_df["เลขที่"].astype(str).str.strip()
        mask = mask | (col.str.lstrip("0") == str(int(n)))

    hits = _contacts_df[mask]
    if hits.empty:
        return None

    out = []
    for _, r in hits.head(10).iterrows():
        parsed = parse_birth(r.get("วันเดือนปีเกิด", ""))
        ys = str(r.get("ยศ", "")).strip()
        nm = str(r.get("ชื่อ", "")).strip()
        sn = str(r.get("สกุล", "")).strip()
        nick = str(r.get("ชื่อเล่น", "")).strip()
        head = f"{ys} {nm} {sn}".strip()
        if nick:
            head += f" ({nick})"
        if parsed:
            out.append(f"🎂 {head} — เกิด {format_day_month(parsed[0], parsed[1])}")
        else:
            out.append(f"🎂 {head} — ไม่มีข้อมูลวันเกิดในไฟล์ครับ")
    extra = ""
    if len(hits) > 10:
        extra = f"\n…เจอทั้งหมด {len(hits)} คน แสดง 10 คนแรกนะครับ"
    return "\n".join(out) + extra


def _handle_birth_query(text: str) -> Optional[str]:
    """จัดการคำถามเรื่องวันเกิด/เดือนเกิด — ตัดปีออกเสมอ
    คืน None ถ้าไม่ตรง pattern เพื่อให้ qa_engine ลำดับถัดไปทำงานต่อ
    """
    if not _is_birth_query(text):
        return None

    # 1) ระบุเดือนตรงๆ → ลิสต์คนทั้งเดือน
    month = detect_month_in_query(text)
    if month:
        return _format_birthdays_in_month(month)

    # 2) ระบุชื่อ/เลขที่ → ตอบเดือน-วันของคนนั้น
    remainder = _strip_name_words(text)
    if remainder:
        person = _format_person_birth(remainder)
        if person:
            return person

    # 3) ถามคำถามเกี่ยวกับวันเกิดแต่ไม่ระบุใคร/เดือน → คืน hint
    return (
        "พิมพ์แบบนี้ได้นะครับ 😉\n"
        "• ‘ใครเกิดเดือน พ.ค.’ → ลิสต์คนทั้งเดือน\n"
        "• ‘เกิดเดือนนี้บ้าง’ → ของเดือนปัจจุบัน\n"
        "• ‘เท็น เกิดวันไหน’ / ‘156 เกิดเดือนไหน’ → ดูเป็นรายคน\n"
        "(ปีเกิด/อายุไม่บอกนะครับ ความลับ 🤫)"
    )


def _list_committee() -> str:
    df = _sheets.get("กรรมการรุ่น")
    if df is None or df.empty:
        return random_pick(NOT_FOUND)
    lines = []
    for _, r in df.head(60).iterrows():
        lines.append(
            f"• [{str(r.get('ปฏิบัติหน้าที่','')).strip()}] "
            f"{str(r.get('ยศ','')).strip()} "
            f"{str(r.get('ชื่อ','')).strip()} "
            f"{str(r.get('สกุล','')).strip()} "
            f"({str(r.get('ชื่อเล่น','')).strip()})"
        )
    return "👑 กรรมการรุ่น 156\n" + "\n".join(lines)


def _list_staff() -> str:
    df = _sheets.get("จนท.ประจำหลักสูตร")
    if df is None or df.empty:
        return random_pick(NOT_FOUND)
    lines = []
    for _, r in df.iterrows():
        lines.append(
            f"• [{str(r.get('ปฏิบัติหน้าที่','')).strip()}] "
            f"{str(r.get('ยศ','')).strip()} "
            f"{str(r.get('ชื่อ','')).strip()} "
            f"{str(r.get('สกุล','')).strip()} "
            f"({str(r.get('ชื่อเล่น','')).strip()})"
        )
    return "🎓 เจ้าหน้าที่ประจำหลักสูตร\n" + "\n".join(lines)


# ---------- Public API ----------
def answer_message(text: str) -> str:
    """รับข้อความผู้ใช้ -> คืนข้อความตอบกลับ"""
    if not text or not text.strip():
        return random_pick(GREETINGS)

    # 0) บอตรีโหลดข้อมูลถ้ายังไม่เคยโหลด
    if _contacts_df.empty and _qa_df.empty and not _sheets:
        reload_data()

    # 1) HARD BLOCK: ห้ามตอบเรื่องอายุ/ปีเกิด เด็ดขาด
    if _is_age_question(text):
        return random_pick(AGE_REFUSALS)

    # 2) ทักทาย / ขอความช่วยเหลือ
    if _is_help(text):
        return HELP_TEXT
    if _is_greeting(text):
        return random_pick(GREETINGS)

    m = _norm(text)

    # 3) คำสั่งพิเศษ
    if any(k in m for k in COMMITTEE_KEYWORDS):
        return _list_committee()
    if any(k in m for k in STAFF_KEYWORDS):
        return _list_staff()

    # 3.5) คำถามเกี่ยวกับวันเกิด/เดือนเกิด (ตัดปีออกเสมอ)
    birth_ans = _handle_birth_query(text)
    if birth_ans is not None:
        return birth_ans

    # 4) จับคู่กับชีตคำถาม-คำตอบก่อน (ของรุ่นเอง)
    qa_ans = _search_qa(text)
    if qa_ans:
        # กรณีคำตอบมีหลายอันคั่น , (เช่น "159 หมิวคนสวย,แต่จริงๆ 041 ก็สวยครับ")
        return qa_ans.replace(",", "\n")

    # 4.5) ค้นหาตามสังกัด
    aff_result = search_affiliation(text, _contacts_df)
    if aff_result:
        return aff_result


    # 5) ค้นในรายชื่อบุคคล
    contact_ans = _search_contacts(text)
    if contact_ans:
        return contact_ans

    # 6) ตอบไม่ทราบแบบกวนๆ
    return random_pick(NOT_FOUND)
