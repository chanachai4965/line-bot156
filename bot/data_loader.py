"""โหลดข้อมูลจากไฟล์ Excel ทุกไฟล์ในโฟลเดอร์ data/"""
from __future__ import annotations

import os
import glob
import pandas as pd
from typing import Dict, List

# คอลัมน์ที่ "ห้ามตอบเด็ดขาด" - ตัดออกตั้งแต่โหลด
# หมายเหตุ: คอลัมน์ "วันเดือนปีเกิด" เก็บไว้ภายในเพื่อใช้ตอบ "เดือนเกิด/วันเกิด"
# แต่ qa_engine จะ strip ปีออกก่อนตอบเสมอ
FORBIDDEN_COLUMNS = {
    "อายุ",
    "อายุ ",  # มีช่องว่างต่อท้ายในไฟล์ต้นฉบับ
    "age",
}

# คอลัมน์วันเกิดที่จะ normalize ให้เป็นชื่อมาตรฐาน "วันเดือนปีเกิด"
BIRTH_DATE_ALIASES = {
    "วันเดือนปีเกิด",
    "วันเกิด",
    "dob",
    "birthday",
    "birth_date",
    "date_of_birth",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ลบช่องว่างหัวท้าย + รวมชื่อคอลัมน์วันเกิดให้เป็น 'วันเดือนปีเกิด'"""
    df = df.copy()
    new_cols = []
    aliases_lower = {a.strip().lower() for a in BIRTH_DATE_ALIASES}
    for c in df.columns:
        c2 = str(c).strip()
        if c2.lower() in aliases_lower:
            c2 = "วันเดือนปีเกิด"
        new_cols.append(c2)
    df.columns = new_cols
    return df


def _drop_forbidden(df: pd.DataFrame) -> pd.DataFrame:
    """ตัดคอลัมน์ที่เกี่ยวกับอายุ/วันเกิด/ปีเกิด ทิ้ง"""
    cols_to_drop = [c for c in df.columns if c.strip().lower() in {x.strip().lower() for x in FORBIDDEN_COLUMNS}]
    return df.drop(columns=cols_to_drop, errors="ignore")


def load_all_excels(data_dir: str) -> Dict[str, pd.DataFrame]:
    """อ่านไฟล์ .xlsx/.xls ทุกไฟล์ในโฟลเดอร์ -> dict{sheet_name: df}
    ถ้ามีหลายไฟล์ที่มีชีตชื่อเดียวกัน จะ append ต่อกัน
    """
    sheets: Dict[str, List[pd.DataFrame]] = {}
    patterns = ["*.xlsx", "*.xls", "*.xlsm"]
    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(data_dir, p)))

    for fp in sorted(files):
        try:
            xls = pd.ExcelFile(fp)
        except Exception as e:  # noqa: BLE001
            print(f"[data_loader] อ่านไฟล์ {fp} ไม่ได้: {e}")
            continue
        for sheet_name in xls.sheet_names:
            try:
                df = pd.read_excel(fp, sheet_name=sheet_name, dtype=str)
            except Exception as e:  # noqa: BLE001
                print(f"[data_loader] อ่านชีต {sheet_name} ใน {fp} ไม่ได้: {e}")
                continue
            df = _normalize_columns(df)
            df = _drop_forbidden(df)
            df = df.fillna("")
            sheets.setdefault(sheet_name.strip(), []).append(df)

    merged: Dict[str, pd.DataFrame] = {}
    for name, parts in sheets.items():
        try:
            merged[name] = pd.concat(parts, ignore_index=True)
        except Exception:  # noqa: BLE001
            merged[name] = parts[0]
    return merged


def get_contacts_df(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """รวมชีตที่ดูเหมือนเป็นรายชื่อบุคคลให้เป็น DataFrame เดียว
    - ตัด row ซ้ำที่มาจากหลายชีต (ใช้ ชื่อ+สกุล+ชื่อเล่น+เลขที่ เป็น key)
    """
    candidates = []
    for name, df in sheets.items():
        cols = set(df.columns)
        if {"ชื่อ", "สกุล"}.issubset(cols) or "ชื่อเล่น" in cols:
            candidates.append(df)
    if not candidates:
        return pd.DataFrame()
    merged = pd.concat(candidates, ignore_index=True).fillna("")
    dedup_cols = [c for c in ["เลขที่", "ชื่อ", "สกุล", "ชื่อเล่น"] if c in merged.columns]
    if dedup_cols:
        merged = merged.drop_duplicates(subset=dedup_cols, keep="first").reset_index(drop=True)
    return merged


def get_qa_df(sheets: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """หาชีตคำถาม-คำตอบ"""
    for name, df in sheets.items():
        cols = set(df.columns)
        if {"คำถาม", "คำตอบ"}.issubset(cols):
            return df.fillna("")
    return pd.DataFrame(columns=["คำถาม", "คำตอบ"])
