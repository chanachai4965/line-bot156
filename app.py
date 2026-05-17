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
    URIAction, PostbackAction, PostbackEvent
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

    if loose(name_part) not in loose(training):
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

    # เลขล้วน → เลขที่
    if q.isdigit():
        add_all(search_by_number(q))
        if results:
            return results

    # ลำดับ: ชื่อ → สังกัด → การอบรม
    add_all(search_by_name_or_nick(q))
    add_all(search_by_affiliation(q))
    add_all(search_by_training(q))

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
#  Webhook
# ============================================================

@app.route("/", methods=["GET"])
def index():
    return "LINE Bot is running. ✅", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "contacts": len(CONTACTS)}, 200


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

    # 1) ลองค้น Q&A ก่อน (ตรงคำถามใดคำถามหนึ่ง → ตอบจากคอลัมน์คำตอบ)
    qa_answer = search_qa(query)
    if qa_answer:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=qa_answer))
        return

    # 2) ถ้าไม่ตรง Q&A → ค้นข้อมูลผู้ติดต่อ
    results = smart_search(query)
    msg = build_results_message(results, query=query)
    if isinstance(msg, list):
        line_bot_api.reply_message(event.reply_token, msg)
    else:
        line_bot_api.reply_message(event.reply_token, msg)


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
