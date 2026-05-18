"""
LINE Bot - ค้นหาข้อมูลผู้บริหาร/เพื่อนร่วมสังกัด
==================================================
รองรับการค้นหา:
- ตามเลขที่
- ตามชื่อจริง / นามสกุล / ชื่อเล่น
- ตามสังกัด (ครอบคลุมหลายชื่อเรียก เช่น บช.น./นครบาล/น./บชน.)
- ตามการอบรม เช่น นรต., กอน. ฯลฯ
- ดูคนสังกัดเดียวกัน

ข้อกำหนดความเป็นส่วนตัว (สำคัญมาก):
- ❌ ห้ามแสดง "อายุ" และ "ปีเกิด" เด็ดขาด
- ✅ แสดงได้แค่ "วันเกิด" (วัน + เดือน)
"""

import os
import re
import json
import random
import logging
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, BubbleContainer, CarouselContainer,
    BoxComponent, TextComponent, ImageComponent, SeparatorComponent,
    URIAction, PostbackAction, PostbackEvent,
    JoinEvent
)

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Flask + LINE SDK ----------
app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    logger.warning("⚠️  ยังไม่ตั้งค่า LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ---------- โหลดข้อมูล ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_PATH = os.path.join(BASE_DIR, "contacts.json")
QA_PATH = os.path.join(BASE_DIR, "qa.json")
GROUP_IDS_PATH = os.path.join(BASE_DIR, "group_ids.json")
CRON_SECRET = os.getenv("CRON_SECRET", "")

with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
    CONTACTS = json.load(f)

logger.info(f"📂 โหลดข้อมูล {len(CONTACTS)} รายการ")

# โหลด Q&A (อาจไม่มีไฟล์ก็ได้)
QA_LIST = []
if os.path.exists(QA_PATH):
    with open(QA_PATH, "r", encoding="utf-8") as f:
        QA_LIST = json.load(f)
    logger.info(f"💬 โหลด Q&A {len(QA_LIST)} รายการ "
                f"({sum(len(qa.get('questions',[])) for qa in QA_LIST)} คำถาม)")


# ============================================================
#  ALIAS ของสังกัด - ชื่อเดียวกันเรียกได้หลายแบบ
#  key = สังกัดต้นทาง (ตรงตามไฟล์ contacts.json)
#  value = list ของคำที่ผู้ใช้อาจพิมพ์มา
# ============================================================
AFFILIATION_ALIASES = {
    "บช.น.": ["บช.น", "บชน", "น.", "นครบาล", "ตำรวจนครบาล", "กองบัญชาการตำรวจนครบาล"],
    "บช.ก.": ["บช.ก", "บชก", "ก.", "สอบสวนกลาง", "บก.", "กองบัญชาการตำรวจสอบสวนกลาง"],
    "บช.ภ.1": ["ภ.1", "ภาค1", "ตำรวจภูธรภาค1", "บชภ1"],
    "บช.ภ.2": ["ภ.2", "ภาค2", "ตำรวจภูธรภาค2", "บชภ2"],
    "บช.ภ.3": ["ภ.3", "ภาค3", "ตำรวจภูธรภาค3", "บชภ3"],
    "บช.ภ.4": ["ภ.4", "ภาค4", "ตำรวจภูธรภาค4", "บชภ4"],
    "บช.ภ.5": ["ภ.5", "ภาค5", "ตำรวจภูธรภาค5", "บชภ5"],
    "บช.ภ.6": ["ภ.6", "ภาค6", "ตำรวจภูธรภาค6", "บชภ6"],
    "บช.ภ.7": ["ภ.7", "ภาค7", "ตำรวจภูธรภาค7", "บชภ7"],
    "บช.ภ.8": ["ภ.8", "ภาค8", "ตำรวจภูธรภาค8", "บชภ8"],
    "บช.ภ.9": ["ภ.9", "ภาค9", "ตำรวจภูธรภาค9", "บชภ9"],
    "บช.ปส.": ["บช.ปส", "บชปส", "ปส.", "ปราบปรามยาเสพติด", "ยาเสพติด"],
    "บช.ส.": ["บช.ส", "บชส", "ส.", "สันติบาล"],
    "บช.สอท.": ["บช.สอท", "บชสอท", "สอท.", "สอท", "ไซเบอร์", "อาชญากรรมทางเทคโนโลยี"],
    "บช.ตชด.": ["บช.ตชด", "บชตชด", "ตชด.", "ตชด", "ตำรวจตระเวนชายแดน", "ตระเวนชายแดน"],
    "บช.ทท.": ["บช.ทท", "บชทท", "ทท.", "ทท", "ท่องเที่ยว", "ตำรวจท่องเที่ยว"],
    "บช.ศ.": ["บช.ศ", "บชศ", "ศ.", "ศึกษา", "ตำรวจศึกษา"],
    "รพ.ตร.": ["รพ.ตร", "รพตร", "รพ.", "โรงพยาบาลตำรวจ", "หมอ", "พยาบาล"],
    "สตม.": ["สตม", "ตม.", "ตม", "ตรวจคนเข้าเมือง", "อิมมิเกรชั่น", "immigration"],
    "สพฐ.ตร.": ["สพฐ.ตร", "สพฐตร", "สพฐ.", "สพฐ", "พิสูจน์หลักฐาน", "พฐ"],
    "รร.นรต.": ["รร.นรต", "รรนรต", "นรต", "โรงเรียนนายร้อยตำรวจ", "นายร้อยตำรวจ", "สามพราน"],
    "สยศ.ตร.(ขึ้นตรง ตร.)": ["สยศ.ตร", "สยศตร", "สยศ.", "สยศ", "ยุทธศาสตร์"],
    "ตท.(ขึ้นตรง ตร.)": ["ตท.", "ตท", "เตรียมทหาร", "โรงเรียนเตรียมทหาร"],
    "กมค.(ขึ้นตรง ตร.)": ["กมค.", "กมค", "กฎหมาย", "กฎหมายและคดี"],
    "จต.(ขึ้นตรง ตร.)": ["จต.", "จต", "จเร", "จเรตำรวจ"],
    "สกพ.(ขึ้นตรง ตร.)": ["สกพ.", "สกพ", "กำลังพล"],
    "สง.ก.ตร.(ขึ้นตรง ตร.)": ["สง.ก.ตร", "สงก.ตร", "ก.ตร.", "ก.ตร", "กตร"],
    "สกบ.(ขึ้นตรง ตร.)": ["สกบ.", "สกบ", "ส่งกำลังบำรุง", "พลาธิการ"],
    "สงป.(ขึ้นตรง ตร.)": ["สงป.", "สงป", "งบประมาณ"],
    "สทส.": ["สทส", "เทคโนโลยี", "ไอที", "it"],
    "สตส.": ["สตส", "ตรวจสอบ", "ตรวจสอบภายใน"],
    "วน.(ขึ้นตรง ตร.)": ["วน.", "วน", "วินัย"],
    "ป.ป.ช.(ภาคี)": ["ปปช", "ป.ป.ช", "ป.ป.ช.", "ปราบปรามทุจริต"],
    "ป.ป.ส.(ภาคี)": ["ปปส", "ป.ป.ส", "ป.ป.ส.", "ปราบปรามยาเสพติด(สำนัก)"],
    "ปปง.(ภาคี)": ["ปปง", "ปปง.", "ฟอกเงิน", "ป้องกันและปราบปรามการฟอกเงิน"],
    "กรมการปกครอง(ภาคี)": ["กรมการปกครอง", "ปกครอง", "มหาดไทย"],
    "ธนาคารแห่งประเทศไทย(ภาคี)": ["ธปท", "แบงค์ชาติ", "แบงก์ชาติ", "ธนาคารแห่งประเทศไทย", "ธ.แห่งประเทศไทย"],
    "องค์การสงเคราะห์ทหารผ่านศึก(ภาคี)": ["ผ่านศึก", "ทหารผ่านศึก", "องค์การสงเคราะห์ทหารผ่านศึก"],
}


# ============================================================
#  ฟังก์ชันช่วย
# ============================================================

def normalize(s) -> str:
    """ตัดช่องว่าง + lower-case (คงตัวอักษรไทย/จุดไว้)"""
    if s is None:
        return ""
    return re.sub(r"\s+", "", str(s)).lower()


def loose(s) -> str:
    """
    ตัดวงเล็บ/จุด/ช่องว่าง/ขีด เพื่อเทียบยืดหยุ่นที่สุด
    - ตัด "(ขึ้นตรง ตร.)", "(ภาคี)" ฯลฯ ออกก่อน เพราะไม่ใช่ส่วนสำคัญของชื่อสังกัด
    """
    if s is None:
        return ""
    s = re.sub(r"\([^)]*\)", "", str(s))  # ตัดข้อความในวงเล็บออก
    return re.sub(r"[.\s\-_/]+", "", s).lower()


def full_name(c: dict) -> str:
    parts = [c.get("rank", ""), c.get("first_name", ""), c.get("last_name", "")]
    return " ".join(p for p in parts if p)


def contains_all_tokens(text: str, query: str) -> bool:
    text_n = normalize(text)
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    if not tokens:
        return False
    return all(normalize(t) in text_n for t in tokens)


def match_affiliation(contact_aff: str, query: str) -> bool:
    """
    เทียบสังกัดแบบครอบคลุม (anti-false-positive):

    1) ตัดวงเล็บ (ขึ้นตรง ตร.), (ภาคี) ออกก่อนเทียบ (เพื่อค้นชื่อหน่วยปกติ)
    2) Exact match กับ canonical หรือ alias
    3) ถ้า contact มี alias ที่ตรงเป๊ะกับ query → ผ่าน
    4) สำหรับ alias ที่ยาวพอ (>= 5) อนุญาต substring แบบสองทาง
    5) สำหรับ canonical ที่ยาวพอ (>= 4) อนุญาต substring สองทาง
    6) NEW: เทียบ "tag" ในวงเล็บด้วย → ค้น "ภาคี" / "ขึ้นตรง ตร." ได้

    หลีกเลี่ยงการ match ระหว่างสังกัดต่างชนิดที่บังเอิญมีตัวอักษรร่วมกัน
    เช่น "บช.สอท." ต้องไม่ match "บช.ส."
    """
    if not query or not contact_aff:
        return False

    # ตัด "(" และ ")" ออกจาก query (เก็บเนื้อหาภายในไว้)
    # เพื่อให้ผู้ใช้พิมพ์ "(ภาคี)" หรือ "(ขึ้นตรง ตร.)" ได้
    query_cleaned = re.sub(r"[()]", " ", query)
    q = loose(query_cleaned)
    if not q:
        return False

    a = loose(contact_aff)

    # 1) exact match กับ canonical
    if q == a:
        return True

    # 2) เช็ค alias ของ canonical ของ contact นี้
    matched_aliases = None
    for canon, aliases in AFFILIATION_ALIASES.items():
        if loose(canon) == a:
            matched_aliases = aliases
            break

    if matched_aliases is not None:
        # 2a) exact match กับ alias ใดๆ
        for al in matched_aliases:
            al_l = loose(al)
            if al_l and q == al_l:
                return True
        # 2b) alias ยาว (>=5) → substring สองทาง
        for al in matched_aliases:
            al_l = loose(al)
            if al_l and len(al_l) >= 5 and len(q) >= 5:
                if q in al_l or al_l in q:
                    return True
    else:
        # 3) ไม่มี alias map - ใช้ partial match ถ้ายาวพอ (>= 4 ตัว ทั้งสองฝั่ง)
        if len(a) >= 4 and len(q) >= 4 and (q in a or a in q):
            return True

    # 4) เทียบกับ "tag" ในวงเล็บ เช่น "(ภาคี)", "(ขึ้นตรง ตร.)"
    #    เพื่อให้ผู้ใช้ค้น "ภาคี" หรือ "ขึ้นตรง ตร." แล้วเจอทุกหน่วยที่มี tag นั้น
    for tag in re.findall(r"\(([^)]+)\)", contact_aff):
        tag_l = re.sub(r"[.\s\-_/]+", "", tag).lower()
        if not tag_l:
            continue
        if q == tag_l:
            return True
        if len(q) >= 3 and len(tag_l) >= 3 and (q in tag_l or tag_l in q):
            return True

    return False


# ============================================================
#  วันเกิด - ค้นหาตามวัน/เดือน
# ============================================================

THAI_MONTHS_FULL = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

# map คำต่างๆ → เลขเดือน 1-12 (รองรับชื่อเต็ม, ตัวย่อ, ตัวเลข)
THAI_MONTH_MAP = {}
_short = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
          "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
for i in range(1, 13):
    full = THAI_MONTHS_FULL[i]
    short = _short[i]
    for key in [full, short, short.replace(".", ""), str(i), f"{i:02d}"]:
        THAI_MONTH_MAP[key.lower()] = i


def parse_month_token(token: str):
    """
    แปลงคำที่อ้างอิงเดือน → 1-12 หรือ None
    รองรับ:
    - ชื่อเต็ม: 'มกราคม'
    - ตัวย่อ: 'ม.ค.' / 'ม.ค' / 'มค' / 'ม. ค.' (มีช่องว่างระหว่างจุดก็ได้)
    - ตัวเลข: '1' / '01' / '5'
    - ชื่อเดือนไม่ครบสมบูรณ์: 'พฤษภา' / 'มกรา' / 'ตุลา' (≥4 ตัวอักษร, ไม่กำกวม)
    """
    if not token:
        return None

    t = token.strip().lower()
    if not t:
        return None

    # 1) ตรงเป๊ะ
    if t in THAI_MONTH_MAP:
        return THAI_MONTH_MAP[t]

    # 2) ตัด . ออก
    t2 = t.replace(".", "")
    if t2 in THAI_MONTH_MAP:
        return THAI_MONTH_MAP[t2]

    # 3) ตัดทั้ง . และ space ออก (รองรับ 'ม. ค.', 'พ . ค .' ฯลฯ)
    t3 = re.sub(r"[.\s\-_/]+", "", t2)
    if t3 in THAI_MONTH_MAP:
        return THAI_MONTH_MAP[t3]
    # ลอง map key หลังตัด . space ด้วย (เผื่อ key เป็นชื่อเต็ม)
    if t3:
        for k, v in THAI_MONTH_MAP.items():
            k_clean = re.sub(r"[.\s\-_/]+", "", k)
            if k_clean == t3:
                return v

    # 4) ชื่อเดือนไม่สมบูรณ์: prefix-match กับชื่อเต็มไทย (≥4 ตัวอักษร, ไม่กำกวม)
    if len(t3) >= 4:
        candidates = []
        for i in range(1, 13):
            full_clean = re.sub(r"[.\s]+", "", THAI_MONTHS_FULL[i]).lower()
            if full_clean.startswith(t3):
                candidates.append(i)
        if len(candidates) == 1:
            return candidates[0]

    return None


def parse_birthday_field(birthday: str):
    """แปลง '14 ตุลาคม' → (14, 10) หรือ (None, None)"""
    if not birthday:
        return (None, None)
    parts = birthday.strip().split()
    if len(parts) < 2:
        return (None, None)
    try:
        day = int(parts[0])
    except ValueError:
        return (None, None)
    month = parse_month_token(" ".join(parts[1:]))
    return (day, month)


# คำ trigger ที่บอกว่ากำลังค้นวันเกิด
BIRTHDAY_TRIGGER = re.compile(
    r"^(เกิดวันนี้|วันเกิดวันนี้|เกิด|วันเกิด|เดือนเกิด|เกิดเดือน|เดือน)\s*(.*)$"
)


def parse_birthday_query(query: str):
    """
    คืนค่า (day, month, is_today) ถ้าเป็นคำค้นวันเกิด
    หรือคืน None ถ้าไม่ใช่

    หมายเหตุ: bare-token ที่เป็น "เลขล้วน" จะไม่ถือว่าเป็นชื่อเดือน
    (เช่น "5" คือเลขที่ของคนคนหนึ่ง ไม่ใช่ "เดือนพฤษภาคม")
    ผู้ใช้ต้องระบุบริบทชัดเจน เช่น "เดือน 5" หรือ "เกิด 5 มกราคม" จึงจะตีความเป็นวันเกิด
    """
    q = query.strip()
    if not q:
        return None

    # เช็คเป็นชื่อเดือนไทยล้วนๆ ก่อน (ห้าม bare digit เป็นเดือน)
    if not q.isdigit():
        m_only = parse_month_token(q)
        if m_only:
            return (None, m_only, False)

    m = BIRTHDAY_TRIGGER.match(q)
    if not m:
        return None

    keyword = m.group(1)
    rest = m.group(2).strip()

    # "เกิดวันนี้" / "วันเกิดวันนี้"
    if keyword in ("เกิดวันนี้", "วันเกิดวันนี้"):
        return (None, None, True)

    if not rest:
        # "เกิด" / "วันเกิด" เปล่าๆ → วันเกิดวันนี้
        if keyword in ("เกิด", "วันเกิด"):
            return (None, None, True)
        return None

    # parse rest: อาจเป็น "วันนี้" / "เดือน X" / "D" / "D เดือน" / "เดือน"
    if rest in ("วันนี้", "today"):
        return (None, None, True)

    # ตัด "เดือน" / "วันที่" ออกถ้ามี
    rest = re.sub(r"^(เดือน|วันที่)\s*", "", rest).strip()

    # ลองเป็นเดือนล้วน
    m_month = parse_month_token(rest)
    if m_month:
        return (None, m_month, False)

    # ลอง pattern "D เดือน" หรือ "D"
    tokens = rest.split()
    day = None
    month = None
    if tokens:
        try:
            day = int(tokens[0])
            if not (1 <= day <= 31):
                day = None
        except ValueError:
            day = None
        if len(tokens) >= 2:
            month = parse_month_token(" ".join(tokens[1:]))

    if day is None and month is None:
        return None
    return (day, month, False)


def _today_thai():
    """คืน (day, month) ของวันนี้ตามเวลาไทย"""
    from datetime import datetime, timezone, timedelta
    bkk = datetime.now(timezone(timedelta(hours=7)))
    return (bkk.day, bkk.month)


def search_by_birthday(query: str):
    """
    ค้นรายชื่อตามวันเกิด
    คืน (results, label) ถ้าเป็นคำค้นวันเกิด
    หรือ None ถ้าไม่ใช่
    """
    parsed = parse_birthday_query(query)
    if parsed is None:
        return None

    day, month, is_today = parsed
    if is_today:
        d, m = _today_thai()
        day, month = d, m
        label = f"เกิดวันที่ {d} {THAI_MONTHS_FULL[m]} (วันนี้)"
    elif day and month:
        label = f"เกิดวันที่ {day} {THAI_MONTHS_FULL[month]}"
    elif month and not day:
        label = f"เกิดเดือน{THAI_MONTHS_FULL[month]}"
    elif day and not month:
        label = f"เกิดวันที่ {day} (ทุกเดือน)"
    else:
        return None

    results = []
    for c in CONTACTS:
        bd_day, bd_month = parse_birthday_field(c.get("birthday", ""))
        if day is not None and bd_day != day:
            continue
        if month is not None and bd_month != month:
            continue
        if bd_day is None and bd_month is None:
            continue
        results.append(c)

    # เรียงตามวัน (ภายในเดือนเดียว) หรือเรียงตามเดือน-วัน
    def _sort_key(c):
        d, m = parse_birthday_field(c.get("birthday", ""))
        return (m or 99, d or 99)
    results.sort(key=_sort_key)

    return (results, label)


def match_training(contact: dict, query: str) -> bool:
    """ค้นหาการอบรม เช่น 'นรต.' / 'นรต.65' / 'นรต 65' / 'กอน'"""
    training = str(contact.get("training", ""))
    klass = str(contact.get("training_class", ""))
    if not training:
        return False

    q = query.strip()
    m = re.match(r"^(.+?)\s*\.?\s*(\d+)?$", q)
    if not m:
        return False
    name_part = m.group(1).strip()
    class_part = m.group(2)

    name_l = loose(name_part)
    train_l = loose(training)
    # ป้องกัน empty string match: ถ้า name_part หลัง loose ว่าง → ไม่ match
    if not name_l or not train_l:
        return False
    if name_l not in train_l:
        return False
    if class_part:
        return normalize(class_part) == normalize(klass)
    return True


# ============================================================
#  ตรรกะค้นหา
# ============================================================

def search_by_number(num_text: str):
    try:
        n = int(num_text)
    except ValueError:
        return []
    return [c for c in CONTACTS if c.get("no") == n]


def search_by_name_or_nick(query: str):
    results = []
    for c in CONTACTS:
        combined = f"{c.get('first_name','')} {c.get('last_name','')} {c.get('nickname','')}"
        if contains_all_tokens(combined, query):
            results.append(c)
    return results


def search_by_affiliation(query: str):
    return [c for c in CONTACTS if match_affiliation(c.get("affiliation", ""), query)]


def search_by_training(query: str):
    return [c for c in CONTACTS if match_training(c, query)]


def search_by_position(query: str):
    """
    ค้นหา 'หน่วยย่อย/พื้นที่' จากฟิลด์ position (สน./สภ./บก./กก./ส.ทล. ฯลฯ)
    ใช้ substring match แบบหลวม (ตัด .,ช่องว่าง,ขีด ทิ้ง)

    ตัวอย่าง:
    - 'อุดมสุข'      → 'รอง ผกก.สส.สน.อุดมสุข'
    - 'สน.ลุมพินี'   → 'รอง ผกก.(สอบสวน) สน.ลุมพินี'
    - 'ลำพูน'        → 'รอง ผกก.สภ.เมืองลำพูน'
    - 'ทล.2'         → 'สวญ.ส.ทล.2 กก.2 บก.ทล.'

    หมายเหตุ: ต้องยาวอย่างน้อย 3 ตัวอักษร (หลัง normalize)
    เพื่อกัน false positive จากคำสั้นๆ
    """
    if not query:
        return []
    q_loose = loose(query)
    if len(q_loose) < 3:
        return []
    results = []
    for c in CONTACTS:
        pos = c.get("position", "")
        if not pos:
            continue
        if q_loose in loose(pos):
            results.append(c)
    return results


def search_qa(query: str):
    """
    ค้นหา Q&A: เทียบจากคอลัมน์ 'คำถาม' เท่านั้น (ไม่นำคำตอบมาเทียบ)
    คืนค่า answer (str) ถ้าเจอ หรือ None ถ้าไม่เจอ

    ลำดับการเทียบ:
    1) exact match (normalize - ตัดช่องว่าง/lowercase)
    2) ตรงกันแบบหลวม (loose - ตัดเครื่องหมายวรรคตอนด้วย)
    """
    if not QA_LIST:
        return None
    q_norm = normalize(query)
    q_loose = loose(query)
    if not q_norm:
        return None

    # 1) exact normalize match
    for qa in QA_LIST:
        for q in qa.get("questions", []):
            if normalize(q) == q_norm:
                return qa.get("answer", "")

    # 2) loose match (ตัดเครื่องหมายวรรคตอนด้วย)
    for qa in QA_LIST:
        for q in qa.get("questions", []):
            q_l = loose(q)
            if q_l and q_l == q_loose:
                return qa.get("answer", "")

    return None


def smart_search(query: str):
    """ค้นแบบรวม"""
    seen = set()
    results = []

    def add_all(items):
        for c in items:
            if c["no"] not in seen:
                seen.add(c["no"])
                results.append(c)

    q = query.strip()

    # #เลขที่
    if q.startswith("#"):
        add_all(search_by_number(q[1:]))
        return results

    # "สังกัด ..."
    m = re.match(r"^(สังกัด|affiliation)\s+(.+)$", q, re.IGNORECASE)
    if m:
        add_all(search_by_affiliation(m.group(2)))
        return results

    # "อบรม ..."
    m = re.match(r"^(อบรม|training)\s+(.+)$", q, re.IGNORECASE)
    if m:
        add_all(search_by_training(m.group(2)))
        return results

    # "หน่วย ..." / "ตำแหน่ง ..." / "สน. ..." / "สภ. ..." → ค้น position โดยตรง
    m = re.match(r"^(หน่วย|ตำแหน่ง|position)\s+(.+)$", q, re.IGNORECASE)
    if m:
        add_all(search_by_position(m.group(2)))
        return results

    # เลขล้วน → เลขที่
    if q.isdigit():
        add_all(search_by_number(q))
        if results:
            return results

    # ลำดับ: ชื่อ → สังกัด → การอบรม
    add_all(search_by_name_or_nick(q))
    add_all(search_by_affiliation(q))
    add_all(search_by_training(q))

    # ค้น position (สน./สภ./ฯลฯ) เฉพาะกรณีที่หาไม่เจอเลย เพื่อกัน substring
    # ไปชนกับสังกัดอื่นโดยบังเอิญ (เช่น 'บช.ส.' loose='บชส' อาจชน 'บช.สอท.')
    if not results:
        add_all(search_by_position(q))

    return results


# ============================================================
#  ข้อความกวนๆ เป็นกันเอง
# ============================================================

WELCOME = (
    "ว่าไงงงงงง 👋\n"
    "หาใครอยู่ ป้อนชื่อ/นามสกุล/ชื่อเล่น/สังกัด/เลขที่ มาเลยจ้า\n"
    "ไม่ก็พิมพ์  บอท help  เดี๋ยวสอนให้ 😎\n\n"
    "📌 ถ้าอยู่ในกลุ่ม ต้องพิมพ์ \"บอท\" หรือ \"bot\" นำหน้าก่อนนะ\n"
    "   เช่น  บอท กนกวรรณ  /  bot ภ.8"
)

HELP_TEXT = (
    "📖 คู่มือใช้งาน (ฉบับลัด สั้น ง่าย)\n"
    "─────────────────\n"
    "💬 ในกลุ่ม: ต้องพิมพ์ \"บอท\" หรือ \"bot\" นำหน้า\n"
    "   เช่น  บอท กนกวรรณ  /  bot #1  /  บอท ภ.8\n"
    "   ในแชทเดี่ยวกับบอท ไม่ต้องเรียก พิมพ์ตรงๆ ได้เลย\n\n"
    "👤 หาคน:\n"
    "   พิมพ์ชื่อ / นามสกุล / ชื่อเล่น ได้เลย\n"
    "   เช่น  บอท กนกวรรณ  หรือ  บอท มะเหมี่ยว\n\n"
    "🔢 หาด้วยเลขที่:\n"
    "   พิมพ์  บอท #1  (มี # นำหน้า)\n\n"
    "🏢 หาตามสังกัด (พิมพ์ได้หลายแบบ):\n"
    "   บช.น. / นครบาล / น. / บชน. → เจอเดียวกัน\n"
    "   ภ.8 / บช.ภ.8 / ภาค8 → เจอเดียวกัน\n"
    "   หรือพิมพ์  บอท สังกัด บช.น.  ก็ได้\n\n"
    "🎓 หาตามการอบรม:\n"
    "   บอท นรต.  /  บอท นรต.65  /  บอท กอน.\n\n"
    "📍 หาตามหน่วยย่อย / พื้นที่ (สน./สภ./บก./กก.):\n"
    "   บอท อุดมสุข        → สน.อุดมสุข\n"
    "   บอท สน.ลุมพินี     → สน.ลุมพินี\n"
    "   บอท ลำพูน          → สภ.เมืองลำพูน\n"
    "   บอท หน่วย ทล.2     → ระบุชัดด้วยคำว่า \"หน่วย\"\n\n"
    "🎂 ค้นหาวันเกิด:\n"
    "   บอท เกิดวันนี้           → ใครเกิดวันนี้\n"
    "   บอท เกิด มกราคม         → ใครเกิดเดือนมกราคม\n"
    "   บอท เดือน ตุลาคม         → คนที่เกิดเดือนตุลาคม\n"
    "   บอท เกิด 14 ตุลาคม      → คนที่เกิด 14 ต.ค.\n"
    "   บอท เกิด 14              → คนที่เกิดวันที่ 14 (ทุกเดือน)\n\n"
    "🎉 อวยพรวันเกิดอัตโนมัติ (เฉพาะในกลุ่ม):\n"
    "   เช้า 08:00 น. ทุกวัน บอทจะอวยพร + ขึ้นการ์ดให้\n"
    "   บอท ลงทะเบียน      → สมัครรับ (กลุ่มที่บอทอยู่จะลงทะเบียนเอง)\n"
    "   บอท ยกเลิกวันเกิด  → เลิกรับ\n\n"
    "💡 Tip: ที่การ์ดมีปุ่ม \"👥 ดูคนสังกัดเดียวกัน\" กดเล่นได้\n\n"
    "พิมพ์  บอท help  เพื่อเปิดเมนูนี้อีกครั้งจ้า ✌️"
)

NOT_FOUND_LINES = [
    "อืมมม หาไม่เจอเลยอะ 🤔 ลองพิมพ์ใหม่ดูได้ไหม?",
    "ไม่เจอจริงๆ ฮะ ลองชื่อเล่นแทนดูมั้ย? 😅",
    "หาไม่เจอนะ คนนี้อาจไม่อยู่ในระบบเรา 🥲",
    "บ่จิ๊ ไม่มีในลิสต์ 555 ลองคำอื่นดูจ้า",
]

FOUND_ONE_LINES = [
    "เจอแล้วจ้าาา 🎯",
    "ตามนี้เลย 👇",
    "อันนี้ใช่ปะ?",
    "ปังงง! เจอแล้ว ✨",
]

FOUND_MANY_LINES = [
    "เจอเพียบบบ {n} คนเลย 🔥",
    "โห {n} คนเลยน้า เลือกดูได้ตามสะดวก 😎",
    "{n} คน ตามนี้จ้าาา 👀",
    "มี {n} คนที่ตรง ลองเลื่อนดูนะ →",
]


def _pick(lines):
    return random.choice(lines)


# ============================================================
#  สร้าง Flex Message
# ============================================================

PLACEHOLDER_IMG = "https://placehold.co/600x600/cccccc/333333?text=No+Image"


def safe_image(url: str) -> str:
    """ถ้า url ว่างหรือไม่ใช่ https → ใช้ placeholder"""
    if not url:
        return PLACEHOLDER_IMG
    url = url.strip()
    if not url.lower().startswith("https://"):
        return PLACEHOLDER_IMG
    return url


def build_contact_bubble(c: dict) -> BubbleContainer:
    """การ์ด 1 คน - ไม่แสดงปีเกิด/อายุเด็ดขาด"""
    name_line = full_name(c)
    nick = c.get("nickname", "")
    title = name_line if not nick else f"{name_line}  ({nick})"

    rows = []

    def add_row(icon, label, value):
        if not value:
            return
        rows.append(BoxComponent(
            layout="baseline",
            spacing="sm",
            contents=[
                TextComponent(text=f"{icon} {label}", color="#888888", size="sm", flex=3),
                TextComponent(text=str(value), wrap=True, color="#111111", size="sm", flex=6),
            ],
        ))

    add_row("🔢", "เลขที่", c.get("no"))
    add_row("🏢", "สังกัด", c.get("affiliation"))
    add_row("💼", "ตำแหน่ง", c.get("position"))
    add_row("📱", "เบอร์", c.get("phone"))
    add_row("🎂", "วันเกิด", c.get("birthday"))   # *** ไม่มีปี ไม่มีอายุ ***
    training_full = c.get("training", "")
    if c.get("training_class"):
        training_full = f"{training_full} รุ่น {c.get('training_class')}".strip()
    add_row("🎓", "การอบรม", training_full)

    image_url = safe_image(c.get("image_url", ""))

    footer_contents = []
    phone = c.get("phone", "")
    if phone:
        footer_contents.append(
            BoxComponent(
                layout="vertical",
                contents=[TextComponent(
                    text="📞 โทรเลย",
                    color="#ffffff",
                    align="center",
                    weight="bold",
                )],
                background_color="#1DB446",
                corner_radius="md",
                padding_all="sm",
                action=URIAction(uri=f"tel:{phone}", label="โทร"),
            )
        )

    footer_contents.append(
        BoxComponent(
            layout="vertical",
            contents=[TextComponent(
                text="👥 ดูคนสังกัดเดียวกัน",
                color="#ffffff",
                align="center",
                weight="bold",
                size="sm",
            )],
            background_color="#0367D3",
            corner_radius="md",
            padding_all="sm",
            action=PostbackAction(
                data=f"action=same_aff&aff={c.get('affiliation','')}",
                display_text=f"สังกัด {c.get('affiliation','')}",
            ),
        )
    )

    bubble = BubbleContainer(
        hero=ImageComponent(
            url=image_url,
            size="full",
            aspect_ratio="1:1",
            aspect_mode="cover",
        ),
        body=BoxComponent(
            layout="vertical",
            spacing="md",
            contents=[
                TextComponent(text=title, weight="bold", size="lg", wrap=True),
                SeparatorComponent(),
                BoxComponent(layout="vertical", spacing="sm", contents=rows),
            ],
        ),
        footer=BoxComponent(
            layout="vertical",
            spacing="sm",
            contents=footer_contents,
        ),
    )
    return bubble


def build_birthday_message(results, label: str):
    """สร้างข้อความผลลัพธ์การค้นหาวันเกิด (มี header เป็น label เช่น 'เกิดเดือนตุลาคม')"""
    if not results:
        return TextSendMessage(
            text=f"ไม่มีใครในระบบ{label}เลยอะ 🤔"
        )

    header = f"🎂 {label} มีทั้งหมด {len(results)} คน"

    # สรุปเป็นข้อความ (ไม่ส่งการ์ดให้รก) - แสดง: ชื่อ, สังกัด, วันเกิด (วัน+เดือน เท่านั้น)
    lines = [header, ""]
    for c in results:
        bd = c.get("birthday", "")
        lines.append(
            f"#{c['no']}  {full_name(c)}  ({c.get('nickname','-')})"
            f"\n     🏢 {c.get('affiliation','')}"
            f"\n     🎂 {bd}"
        )

    text_msg = "\n".join(lines)
    # LINE จำกัด text ~5000 ตัวอักษร — เผื่อไว้ตัดถ้ายาวเกิน
    if len(text_msg) > 4800:
        text_msg = text_msg[:4750] + "\n...\n(พิมพ์ #เลขที่ เพื่อดูคนคนนั้นได้)"

    # เพิ่ม Flex carousel ของ 10 คนแรก เพื่อให้ดูการ์ดได้สะดวก
    LIMIT = 10
    if len(results) <= LIMIT:
        bubbles = [build_contact_bubble(c) for c in results]
    else:
        bubbles = [build_contact_bubble(c) for c in results[:LIMIT]]

    msgs = [TextSendMessage(text=text_msg)]
    if bubbles:
        msgs.append(FlexSendMessage(
            alt_text=label,
            contents=CarouselContainer(contents=bubbles),
        ))
    return msgs


def build_results_message(results, query=""):
    if not results:
        return TextSendMessage(
            text=f"{_pick(NOT_FOUND_LINES)}\n\n🔍 คำที่หา: \"{query}\"\nพิมพ์ help เพื่อดูวิธีใช้นะ"
        )

    if len(results) == 1:
        return [
            TextSendMessage(text=_pick(FOUND_ONE_LINES)),
            FlexSendMessage(
                alt_text=f"ข้อมูล {full_name(results[0])}",
                contents=build_contact_bubble(results[0]),
            ),
        ]

    LIMIT = 10
    msg_text = _pick(FOUND_MANY_LINES).format(n=len(results))

    if len(results) <= LIMIT:
        bubbles = [build_contact_bubble(c) for c in results]
        return [
            TextSendMessage(text=msg_text),
            FlexSendMessage(
                alt_text=f"พบ {len(results)} รายการ",
                contents=CarouselContainer(contents=bubbles),
            ),
        ]

    # เกิน 10 → ส่งสรุปข้อความ + การ์ด 10 ใบแรก
    bubbles = [build_contact_bubble(c) for c in results[:LIMIT]]
    lines = [
        f"{msg_text}",
        f"⚠️ ส่งการ์ดได้แค่ {LIMIT} คนนะ ที่เหลือพิมพ์ #เลขที่ ดูได้",
        "",
        "📋 รายชื่อทั้งหมด:",
    ]
    for c in results:
        lines.append(f"#{c['no']}  {full_name(c)}  [{c.get('affiliation','')}]")
    return [
        TextSendMessage(text="\n".join(lines)),
        FlexSendMessage(
            alt_text=f"พบ {len(results)} รายการ",
            contents=CarouselContainer(contents=bubbles),
        ),
    ]


# ============================================================
#  จัดการ Group ID (สำหรับส่งคำอวยพรวันเกิด)
# ============================================================

def load_group_ids() -> list:
    """โหลดรายชื่อ group_id ที่บอทอยู่ในกลุ่ม"""
    if not os.path.exists(GROUP_IDS_PATH):
        return []
    try:
        with open(GROUP_IDS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("group_ids", [])
    except Exception as e:
        logger.error(f"Error loading group_ids.json: {e}")
        return []


def save_group_ids(ids: list) -> None:
    """บันทึก group_id (ใช้สำหรับ auto-register; ถ้า Render free tier filesystem
    ไม่ persist ระหว่าง redeploy แนะนำให้ตั้ง BIRTHDAY_GROUP_IDS ใน env แทน)"""
    try:
        with open(GROUP_IDS_PATH, "w", encoding="utf-8") as f:
            json.dump(ids, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving group_ids.json: {e}")


def add_group_id(group_id: str) -> bool:
    """เพิ่ม group_id; คืน True ถ้าเป็น id ใหม่"""
    if not group_id:
        return False
    ids = load_group_ids()
    if group_id in ids:
        return False
    ids.append(group_id)
    save_group_ids(ids)
    logger.info(f"➕ ลงทะเบียนกลุ่มใหม่: {group_id}")
    return True


def get_birthday_target_groups() -> list:
    """ดึง group_id ที่จะส่งคำอวยพร
    ถ้าตั้ง BIRTHDAY_GROUP_IDS ใน env (comma-separated) จะใช้อันนั้นแทน
    ไม่งั้นใช้รายชื่อที่ auto-register
    """
    env = os.getenv("BIRTHDAY_GROUP_IDS", "").strip()
    if env:
        return [g.strip() for g in env.split(",") if g.strip()]
    return load_group_ids()


# ============================================================
#  สร้างคำอวยพรวันเกิด
# ============================================================

BIRTHDAY_GREETINGS = [
    "🎂🎉 สุขสันต์วันเกิด {who}! ขอให้สุขภาพแข็งแรง รวยเฮง พลังเต็มทุกวันน้าาาา 💪✨",
    "🎉🎁 HBD {who}!! วันที่ดีที่สุดของปีเลย ขอให้สมหวังทุกๆ เรื่อง 🎂",
    "✨🎂 สุขสันต์วันเกิดน้าาาา {who}! ปีนี้ขอให้ปังกว่าทุกปี รวยๆ เฮงๆ 🥳",
    "🎈🎉 Happy Birthday {who}! ขอให้แข็งแรง ปลอดภัย สุขใจทุกวัน 💗",
    "🌟🎂 วันเกิดแล้วน้าาา {who} ขอให้เจอแต่สิ่งดีๆ ปังๆ ทั้งงานทั้งใจ ❤️",
]


def _who_str(c: dict) -> str:
    name = full_name(c)
    nick = c.get("nickname", "")
    if nick:
        return f"{name} ({nick})"
    return name


def build_birthday_announcement(people: list):
    """
    สร้างข้อความอวยพรวันเกิดสำหรับคนวันเกิดวันนี้ + การ์ดบุคคล
    คืน list ของ message (text + flex carousel)
    """
    if not people:
        return []

    d, m = _today_thai()
    header_lines = [
        f"🎂🎉 วันเกิดวันนี้ ({d} {THAI_MONTHS_FULL[m]}) 🎉🎂",
        f"มีทั้งหมด {len(people)} คนน้าาา 🥳",
        "",
    ]
    for p in people:
        greet = random.choice(BIRTHDAY_GREETINGS).format(who=_who_str(p))
        header_lines.append(greet)
        header_lines.append("")

    text_msg = TextSendMessage(text="\n".join(header_lines).strip())

    # การ์ดสูงสุด 10 ใบ (LINE limit)
    bubbles = [build_contact_bubble(p) for p in people[:10]]
    msgs = [text_msg]
    if bubbles:
        msgs.append(FlexSendMessage(
            alt_text=f"วันเกิดวันนี้ {len(people)} คน",
            contents=CarouselContainer(contents=bubbles),
        ))
    return msgs


def find_birthday_people_today() -> list:
    """หาคนที่เกิดวันนี้ (ตามเวลาไทย)"""
    d, m = _today_thai()
    res = []
    for c in CONTACTS:
        bd, bm = parse_birthday_field(c.get("birthday", ""))
        if bd == d and bm == m:
            res.append(c)
    return res


# ============================================================
#  Webhook
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "LINE Bot is running. ✅", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "contacts": len(CONTACTS)}, 200


@app.route("/cron/birthday", methods=["GET", "POST"])
def cron_birthday():
    """
    Endpoint สำหรับ external cron มาเรียกทุกวัน (เช่น 08:00 น.) เพื่อส่งคำอวยพร
    ป้องกันด้วย ?token=<CRON_SECRET>

    ตัวอย่างการตั้งค่า cron-job.org:
      URL: https://<your-app>.onrender.com/cron/birthday?token=<CRON_SECRET>
      Method: GET
      Schedule: ทุกวัน 08:00 (Asia/Bangkok)
    """
    # ตรวจสอบ token (ถ้าตั้ง CRON_SECRET ใน env ไว้)
    if CRON_SECRET:
        token = request.args.get("token", "") or request.headers.get("X-Cron-Token", "")
        if token != CRON_SECRET:
            logger.warning("⚠️  /cron/birthday: invalid or missing token")
            abort(403)

    people = find_birthday_people_today()
    d, m = _today_thai()
    today_str = f"{d}/{m}"

    if not people:
        logger.info(f"🎂 cron/birthday: ไม่มีใครเกิดวันนี้ ({today_str})")
        return {"status": "no_birthdays", "date": today_str}, 200

    group_ids = get_birthday_target_groups()
    if not group_ids:
        logger.warning(f"🎂 มี {len(people)} คนเกิดวันนี้ แต่ยังไม่มีกลุ่มลงทะเบียน")
        return {
            "status": "no_groups_registered",
            "date": today_str,
            "people": [_who_str(p) for p in people],
        }, 200

    messages = build_birthday_announcement(people)

    sent, failed = [], []
    for gid in group_ids:
        try:
            line_bot_api.push_message(gid, messages)
            sent.append(gid)
            logger.info(f"📤 ส่งคำอวยพรไปยัง group {gid} แล้ว")
        except Exception as e:
            logger.error(f"❌ push ไป {gid} ล้มเหลว: {e}")
            failed.append({"group_id": gid, "error": str(e)})

    return {
        "status": "ok",
        "date": today_str,
        "people_count": len(people),
        "people": [_who_str(p) for p in people],
        "sent_groups": len(sent),
        "failed_groups": len(failed),
        "failures": failed,
    }, 200


@app.route("/cron/birthday/preview", methods=["GET"])
def cron_birthday_preview():
    """Dry-run: ดูว่าวันนี้ใครเกิด + ข้อความที่จะส่ง (ไม่ push จริง)"""
    if CRON_SECRET:
        token = request.args.get("token", "")
        if token != CRON_SECRET:
            abort(403)
    people = find_birthday_people_today()
    d, m = _today_thai()
    if not people:
        return {"status": "no_birthdays", "date": f"{d}/{m}"}, 200
    msgs = build_birthday_announcement(people)
    return {
        "status": "preview",
        "date": f"{d}/{m}",
        "people": [_who_str(p) for p in people],
        "text_preview": msgs[0].text if msgs else "",
        "registered_groups": len(get_birthday_target_groups()),
    }, 200


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        abort(400)
    return "OK"


# ในกลุ่ม/ห้อง: ผู้ใช้ต้องพิมพ์ "บอท" หรือ "bot" ขึ้นต้นก่อน บอทถึงจะตอบ
# ในแชทเดี่ยว: ตอบทุกข้อความ (ไม่ต้องเรียก)
TRIGGER_PATTERN = re.compile(r"^\s*(บอท|bot)\s*[:：,，]?\s*(.*)$", re.IGNORECASE | re.DOTALL)


def extract_query(event_source_type: str, text: str):
    """
    คืนค่า query หลังตัดคำเรียกออก หรือ None ถ้าไม่ควรตอบ
    - 1-on-1 (user): ตอบทุกข้อความ
    - group/room: ต้องมี 'บอท' หรือ 'bot' นำหน้าเท่านั้น
    """
    if event_source_type == "user":
        return text.strip()

    m = TRIGGER_PATTERN.match(text)
    if not m:
        return None  # ไม่เรียกบอท → เงียบ
    rest = m.group(2).strip()
    return rest  # อาจเป็น "" ถ้าพิมพ์แค่ "บอท"


@handler.add(MessageEvent, message=TextMessage)
def on_text(event):
    text = (event.message.text or "").strip()
    if not text:
        return

    source_type = event.source.type  # 'user' | 'group' | 'room'
    query = extract_query(source_type, text)
    if query is None:
        return  # ในกลุ่มที่ไม่ได้เรียก "บอท"/"bot" → เงียบไม่ตอบ

    # ถ้าในกลุ่มเรียก "บอท" เฉยๆ ไม่ระบุคำค้น → แสดงต้อนรับ
    if not query:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME))
        return

    low = query.lower()
    if low in {"help", "ช่วยเหลือ", "เมนู", "menu", "/help", "?"}:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=HELP_TEXT))
        return

    if low in {"hi", "hello", "สวัสดี", "หวัดดี", "ดี", "start", "/start"}:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=WELCOME))
        return

    # คำสั่งลงทะเบียน/ดูสถานะกลุ่ม
    if low in {"ลงทะเบียน", "register", "สมัคร", "สมัครรับวันเกิด"}:
        if source_type not in ("group", "room"):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="คำสั่งนี้ใช้ในกลุ่มเท่านั้นนะจ๊ะ 😅"
            ))
            return
        gid = (getattr(event.source, "group_id", None)
               or getattr(event.source, "room_id", None))
        added = add_group_id(gid)
        msg = ("ลงทะเบียนกลุ่มเรียบร้อย! 🎉\n"
               "วันเกิดของคนในระบบ บอทจะส่งคำอวยพรในห้องนี้ทุกเช้า 08:00 น. จ้า 🎂"
               if added else
               "กลุ่มนี้ลงทะเบียนไว้แล้วครับ ✓\n"
               "รอเช้าวันเกิดได้เลยน้า 🎂")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    if low in {"ยกเลิกวันเกิด", "unregister", "เลิกสมัคร"}:
        if source_type not in ("group", "room"):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="คำสั่งนี้ใช้ในกลุ่มเท่านั้นนะ"
            ))
            return
        gid = (getattr(event.source, "group_id", None)
               or getattr(event.source, "room_id", None))
        ids = load_group_ids()
        if gid in ids:
            ids.remove(gid)
            save_group_ids(ids)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="ยกเลิกการส่งคำอวยพรในกลุ่มนี้แล้วจ้า ✋"
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="กลุ่มนี้ยังไม่เคยลงทะเบียนนะ"
            ))
        return

    # 1) ค้นวันเกิดก่อน (เกิด/วันเกิด/เดือนเกิด/ชื่อเดือน)
    bday = search_by_birthday(query)
    if bday is not None:
        bday_results, bday_label = bday
        msg = build_birthday_message(bday_results, bday_label)
        if isinstance(msg, list):
            line_bot_api.reply_message(event.reply_token, msg)
        else:
            line_bot_api.reply_message(event.reply_token, msg)
        return

    # 2) ค้นรายชื่อ (ชื่อ/สังกัด/อบรม) — ข้อมูลจริงสำคัญกว่าคำถามทั่วไป
    results = smart_search(query)
    if results:
        msg = build_results_message(results, query=query)
        if isinstance(msg, list):
            line_bot_api.reply_message(event.reply_token, msg)
        else:
            line_bot_api.reply_message(event.reply_token, msg)
        return

    # 3) ถ้าไม่เจอในรายชื่อ → ลองค้น Q&A (เทียบจากคอลัมน์ "คำถาม" เท่านั้น)
    qa_answer = search_qa(query)
    if qa_answer:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=qa_answer))
        return

    # 4) ไม่เจอเลย — ตอบไม่พบ
    msg = build_results_message([], query=query)
    line_bot_api.reply_message(event.reply_token, msg)


@handler.add(JoinEvent)
def on_join(event):
    """บอทถูกเชิญเข้ากลุ่ม → ลงทะเบียนอัตโนมัติ + ทักทาย"""
    source_type = event.source.type
    gid = (getattr(event.source, "group_id", None)
           or getattr(event.source, "room_id", None))
    if gid:
        added = add_group_id(gid)
        logger.info(f"🤝 JoinEvent: {source_type} {gid} (new={added})")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(
        text=(
            "ว่าไง พวกเร้าาาา 👋 บอทมาเป็นเพื่อนแล้ว\n"
            "─────────────────\n"
            "🔍 ค้นข้อมูล: พิมพ์ \"บอท ชื่อ/สังกัด/#เลข\"\n"
            "🎂 วันเกิดของใครในระบบ บอทจะส่งคำอวยพรในห้องนี้\n"
            "    ทุกเช้า 08:00 น. อัตโนมัติเลยจ้า\n\n"
            "พิมพ์ \"บอท help\" ดูคู่มือได้น้า ✌️"
        )
    ))


@handler.add(PostbackEvent)
def on_postback(event):
    data = event.postback.data or ""
    params = dict(p.split("=", 1) for p in data.split("&") if "=" in p)
    action = params.get("action", "")

    if action == "same_aff":
        aff = params.get("aff", "")
        results = search_by_affiliation(aff)
        msg = build_results_message(results, query=f"สังกัด {aff}")
        if isinstance(msg, list):
            line_bot_api.reply_message(event.reply_token, msg)
        else:
            line_bot_api.reply_message(event.reply_token, msg)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
