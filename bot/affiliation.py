เช่น "บช.น.", "นครบาล" — โมดูลนี้แมตช์ทั้งสองรูปแบบ
"""
from __future__ import annotations

import re
from typing import Optional, List, Tuple

import pandas as pd


# ================================================================
# Alias map: canonical short-form (ตามที่อยู่ในคอลัมน์ "สังกัด") -> aliases ที่ผู้ใช้พิมพ์
# เรียงจาก "ยาวสุด" ไปสั้นสุด เพื่อกัน prefix collision (เช่น บช.ปส. ก่อน บช.ส.)
# ================================================================
AFFILIATION_ALIASES: List[Tuple[str, List[str]]] = [
    # บช. (กองบัญชาการ) ระดับสำนักงานตำรวจแห่งชาติ
    ("รพ.ตร.", ["รพ.ตร.", "รพตร", "โรงพยาบาลตำรวจ"]),
    ("สกพ.", ["สกพ.", "สกพ", "สำนักงานกำลังพล", "กำลังพล"]),
    ("สตม.", ["บช.สตม.", "บชสตม", "สตม.", "สตม", "สำนักงานตรวจคนเข้าเมือง", "ตรวจคนเข้าเมือง", "ตม."]),
    ("ตชด.", ["บช.ตชด.", "บชตชด", "ตชด.", "ตชด", "ตำรวจตระเวนชายแดน", "ตระเวนชายแดน"]),
    ("ปส.", ["บช.ปส.", "บชปส", "ปส.", "ปส", "ปราบปรามยาเสพติด", "ตำรวจปราบยาเสพติด", "ยาเสพติด"]),
    ("ทท.", ["บช.ทท.", "บชทท", "ทท.", "ตำรวจท่องเที่ยว", "ท่องเที่ยว"]),

    # บช. ภูธรภาค (ภ.1 - ภ.9)
    ("ภ.1", ["บช.ภ.1", "บชภ1", "ภ.1", "ภ1", "ภาค 1", "ภาค1", "ภูธรภาค 1", "ภูธรภาค1", "ตำรวจภูธรภาค 1"]),
    ("ภ.2", ["บช.ภ.2", "บชภ2", "ภ.2", "ภ2", "ภาค 2", "ภาค2", "ภูธรภาค 2", "ภูธรภาค2", "ตำรวจภูธรภาค 2"]),
    ("ภ.3", ["บช.ภ.3", "บชภ3", "ภ.3", "ภ3", "ภาค 3", "ภาค3", "ภูธรภาค 3", "ภูธรภาค3", "ตำรวจภูธรภาค 3"]),
    ("ภ.4", ["บช.ภ.4", "บชภ4", "ภ.4", "ภ4", "ภาค 4", "ภาค4", "ภูธรภาค 4", "ภูธรภาค4", "ตำรวจภูธรภาค 4"]),
    ("ภ.5", ["บช.ภ.5", "บชภ5", "ภ.5", "ภ5", "ภาค 5", "ภาค5", "ภูธรภาค 5", "ภูธรภาค5", "ตำรวจภูธรภาค 5"]),
    ("ภ.6", ["บช.ภ.6", "บชภ6", "ภ.6", "ภ6", "ภาค 6", "ภาค6", "ภูธรภาค 6", "ภูธรภาค6", "ตำรวจภูธรภาค 6"]),
    ("ภ.7", ["บช.ภ.7", "บชภ7", "ภ.7", "ภ7", "ภาค 7", "ภาค7", "ภูธรภาค 7", "ภูธรภาค7", "ตำรวจภูธรภาค 7"]),
    ("ภ.8", ["บช.ภ.8", "บชภ8", "ภ.8", "ภ8", "ภาค 8", "ภาค8", "ภูธรภาค 8", "ภูธรภาค8", "ตำรวจภูธรภาค 8"]),
    ("ภ.9", ["บช.ภ.9", "บชภ9", "ภ.9", "ภ9", "ภาค 9", "ภาค9", "ภูธรภาค 9", "ภูธรภาค9", "ตำรวจภูธรภาค 9"]),

    # บช.น. (นครบาล) และ บช.ก. (สอบสวนกลาง)
    ("น.", ["บช.น.", "บชน.", "บชน", "นครบาล", "ตำรวจนครบาล", "กองบัญชาการตำรวจนครบาล"]),
    ("ก.", ["บช.ก.", "บชก.", "บชก", "สอบสวนกลาง", "ตำรวจสอบสวนกลาง", "กองบัญชาการตำรวจสอบสวนกลาง", "cib"]),
    ("ส.", ["บช.ส.", "บชส.", "บชส", "สันติบาล", "ตำรวจสันติบาล"]),
]

# ลำดับ: เรียงจากยาวสุดก่อน (จำนวนตัวอักษร)
AFFILIATION_ALIASES.sort(key=lambda kv: -max(len(a) for a in kv[1]))

# Display name (แสดงในหัวคำตอบ)
DISPLAY_NAME = {
    "น.": "บช.น. (นครบาล)",
    "ก.": "บช.ก. (สอบสวนกลาง)",
    "ส.": "บช.ส. (สันติบาล)",
    "ปส.": "บช.ปส. (ปราบปรามยาเสพติด)",
    "ตชด.": "บช.ตชด. (ตำรวจตระเวนชายแดน)",
    "สตม.": "บช.สตม. (สำนักงานตรวจคนเข้าเมือง)",
    "ทท.": "บช.ทท. (ตำรวจท่องเที่ยว)",
    "รพ.ตร.": "รพ.ตร. (โรงพยาบาลตำรวจ)",
    "สกพ.": "สกพ. (สำนักงานกำลังพล)",
    **{f"ภ.{i}": f"บช.ภ.{i} (ตำรวจภูธรภาค {i})" for i in range(1, 10)},
}


# ================================================================
# Normalization
# ================================================================
def _normalize(text: str) -> str:
    """ตัดจุด ช่องว่าง ขีด แล้ว lower-case
    "บช.น." -> "บชน"
    "ภ. 8" -> "ภ8"
    "บช.ภ.1" -> "บชภ1"
    """
    if not text:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[\.\-\s_/]+", "", s)
    return s


def _normalize_data_value(value: str) -> str:
    """normalize ค่าใน DataFrame ก่อนเทียบ (เพื่อ match ทั้ง 'น.' และ 'น')"""
    return _normalize(value)


# ================================================================
# Detection / Matching
# ================================================================
# precomputed normalized aliases for speed
_NORMALIZED_ALIASES: List[Tuple[str, List[str]]] = [
    (canon, [_normalize(a) for a in aliases])
    for canon, aliases in AFFILIATION_ALIASES
]


def _find_canonical(text: str) -> Optional[str]:
    """หา canonical short-form จากข้อความที่ผู้ใช้พิมพ์
    คืน canonical (เช่น "น.", "ภ.8") หรือ None
    """
    norm = _normalize(text)
    if not norm:
        return None
    # ลองหา substring match — ต้องเรียงจากยาวสุดก่อน
    for canon, norm_aliases in _NORMALIZED_ALIASES:
        for alias in norm_aliases:
            if not alias:
                continue
            if alias in norm:
                return canon
    return None


def is_affiliation_query(text: str) -> bool:
    """ข้อความนี้ถามเรื่อง 'สังกัด' หรือเปล่า"""
    if not text:
        return False
    # คำสำคัญที่บ่งบอกว่าถามเรื่องสังกัด
    keyword_patterns = [
        r"สังกัด",
        r"อยู่\s*ที่",
        r"ทำงาน\s*ที่",
        r"หน่วยงาน",
        r"กองบัญชาการ",
    ]
    for pat in keyword_patterns:
        if re.search(pat, text):
            return True
    # หรือพิมพ์ alias ตรงๆ
    return _find_canonical(text) is not None


# ================================================================
# Search
# ================================================================
def _person_label(row: pd.Series) -> str:
    """สร้าง label สำหรับแสดงผล (ลอกแบบจาก phone.py)"""
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


def search_affiliation(text: str, contacts_df: pd.DataFrame) -> Optional[str]:
    """ค้นหารายชื่อในสังกัดที่ผู้ใช้ถาม
    คืนสตริงคำตอบ หรือ None ถ้าไม่ใช่คำถามเรื่องสังกัด
    """
    if contacts_df is None or contacts_df.empty:
        return None
    if "สังกัด" not in contacts_df.columns:
        return None

    canon = _find_canonical(text)
    if canon is None:
        return None

    # filter โดย normalize ทั้งสองฝั่ง
    canon_norm = _normalize(canon)
    mask = contacts_df["สังกัด"].fillna("").map(_normalize_data_value) == canon_norm
    matched = contacts_df[mask]

    display = DISPLAY_NAME.get(canon, canon)

    if matched.empty:
        return f"🔎 ค้นหาสังกัด {display}\nยังไม่พบใครในสังกัดนี้ในข้อมูลค่ะ ลองสะกดใหม่ได้นะ 🌷"

    lines = [f"🏛️ {display} — เจอ {len(matched)} คนค่ะ"]
    for _, row in matched.iterrows():
        lines.append(f"• {_person_label(row)}")

    if len(lines) > 51:  # header + 50 บรรทัด
        lines = lines[:51] + [f"… และอีก {len(matched) - 50} คน (พิมพ์ชื่อเล่นเพื่อดูรายละเอียด)"]

    return "\n".join(lines)
