# LINE Bot - ค้นหาข้อมูลผู้บริหาร/เพื่อนร่วมสังกัด

บอท LINE สำหรับค้นหาข้อมูลผู้บริหาร/เจ้าหน้าที่ พิมพ์ค้นหาได้หลากหลายแบบ พูดจาเป็นกันเอง 😎

## ฟีเจอร์

- 🔍 ค้นหาด้วย **ชื่อจริง / นามสกุล / ชื่อเล่น**
- 🔢 ค้นด้วย **เลขที่** (พิมพ์ `#1`)
- 🏢 ค้นด้วย **สังกัด** ครอบคลุมหลายชื่อเรียก
  - `บช.น.` / `นครบาล` / `น.` / `บชน.` → เจอเดียวกัน
  - `ภ.8` / `บช.ภ.8` / `ภาค8` → เจอเดียวกัน
- 🎓 ค้นด้วย **การอบรม** เช่น `นรต.`, `นรต.65`, `กอน.`
- 👥 ปุ่ม "ดูคนสังกัดเดียวกัน" บนการ์ดแต่ละใบ
- 🖼️ แสดงรูปภาพในรูปแบบ Flex Message
- ☎️ ปุ่มโทรตรงจากการ์ด
- 🎓 **ค้นหาคนเกษียณ** — ตามปี พ.ศ. ในช่วง 2559-2575
- เช่น `บอท ใครเกษียณปี 2570`, `บอท คนเกษียณ 2568`
- ⚠️ หมายเหตุ: คำนวณจากปีเกิด ดังนั้นจะเปิดเผยปีเกิดทางอ้อม

## 🔒 ความเป็นส่วนตัว (สำคัญ)

- ❌ **ไม่แสดงปีเกิด** เด็ดขาด
- ❌ **ไม่แสดงอายุ** เด็ดขาด
- ✅ แสดงเฉพาะ **วัน + เดือน เกิด** (เช่น `14 ตุลาคม`)
- ฟิลด์อายุถูก *ไม่เก็บลง JSON* ตั้งแต่ขั้นแปลงข้อมูล

## โครงสร้างไฟล์

```
.
├── app.py                      # Flask + LINE webhook
├── contacts.json               # ข้อมูล (ไม่มีปีเกิด/อายุ)
├── convert_xlsx_to_json.py     # สคริปต์แปลง xlsx → json
├── requirements.txt            # Python dependencies
├── Procfile                    # สำหรับ Render/Heroku/Railway
├── runtime.txt                 # ระบุเวอร์ชัน Python
├── .env.example                # ตัวอย่าง environment variables
└── .gitignore
```

## วิธีติดตั้ง (Local)

```bash
# 1) ติดตั้ง dependencies
pip install -r requirements.txt

# 2) ตั้งค่า env
cp .env.example .env
# แก้ไข .env ใส่ token ของคุณ

# 3) รัน
python app.py

# 4) เปิด ngrok (สำหรับทดสอบ webhook กับ LINE)
ngrok http 5000
# เอา URL ที่ได้ไปตั้งเป็น Webhook URL ใน LINE Developer Console
# จำได้ว่าต้องเป็น https://xxxxx.ngrok.io/callback
```

## วิธี Deploy ขึ้น Render (แนะนำ)

1. Push โค้ดขึ้น GitHub
2. ไปที่ https://render.com → New → Web Service → เลือก repo
3. ตั้งค่า
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Environment Variables:**
     - `LINE_CHANNEL_ACCESS_TOKEN`
     - `LINE_CHANNEL_SECRET`
4. Deploy แล้วเอา URL `https://xxx.onrender.com/callback` ไปตั้งใน LINE Console

## วิธีอัปเดตข้อมูลผู้ติดต่อ

แก้ไขไฟล์ `contacts.xlsx` → แปลงใหม่ → push ขึ้น GitHub

```bash
python convert_xlsx_to_json.py contacts.xlsx
git add contacts.json
git commit -m "update contacts"
git push
```

## ตัวอย่างการใช้งาน

| ผู้ใช้พิมพ์ | บอทจะ |
|---|---|
| `กนกวรรณ` | หาคนชื่อ "กนกวรรณ" |
| `มะเหมี่ยว` | หาคนชื่อเล่น "มะเหมี่ยว" |
| `#1` | คนเลขที่ 1 |
| `บช.น.` หรือ `นครบาล` หรือ `บชน.` | คนใน บช.น. ทั้งหมด |
| `ภ.8` หรือ `ภาค8` | คนใน บช.ภ.8 ทั้งหมด |
| `นรต.` | คนที่อบรม นรต. ทั้งหมด |
| `นรต.65` | คนที่อบรม นรต. รุ่น 65 |
| `help` | เปิดคู่มือ |

## License

Private - สำหรับใช้ภายในองค์กรเท่านั้น

### 📐 สูตรคำนวณปีเกษียณ
- เกิดเดือน ม.ค.–ก.ย. → ปีเกษียณ = ปีเกิด + 60
- เกิดเดือน ต.ค.–ธ.ค. → ปีเกษียณ = ปีเกิด + 61
- (ตามกฎปีงบประมาณไทย: 1 ต.ค. – 30 ก.ย.)
