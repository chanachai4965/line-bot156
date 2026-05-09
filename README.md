# LINE BOT — ผกก.156 รุ่นพี่น้อง

บอท LINE สำหรับตอบคำถามภายในกลุ่มไลน์รุ่น โดยอ่านข้อมูลจากไฟล์ Excel ในโฟลเดอร์ `data/`

## คุณสมบัติ

- ✅ ตอบจากชีต **คำถาม คำตอบ** ในไฟล์ Excel โดยตรง
- ✅ ค้นหาข้อมูลบุคคลจาก ชื่อ / นามสกุล / ชื่อเล่น / เลขที่ / สังกัด / ตำแหน่ง
- ✅ ลิสต์วันเกิด: `ใครเกิดเดือน พ.ค. บ้าง`, `เกิดเดือนนี้บ้าง`
- ✅ ดูเดือน-วันเกิดรายคน: `เท็น เกิดวันไหน`, `156 เกิดเดือนไหน`
- ✅ คำสั่งพิเศษ: `บอท กรรมการ`, `บอท เจ้าหน้าที่`
- ✅ โทนตอบ "กวนแบบน่ารัก เป็นกันเอง"
- 🚫 **ห้ามตอบเรื่องอายุ / ปีเกิด เด็ดขาด** — แม้ข้อมูลในไฟล์จะมี วัน/เดือน/ปี ครบ บอทจะตัด **ปี** ออกเสมอก่อนตอบ
- 🔁 รองรับการเพิ่มไฟล์ Excel หลายไฟล์ (วางลงโฟลเดอร์ `data/` แล้วเรียก `/reload`)

## โครงสร้างโปรเจ็กต์

```
LINE BOT/
├── app.py                  # Flask + LINE webhook
├── bot/
│   ├── __init__.py
│   ├── data_loader.py      # โหลดไฟล์ Excel + ตัดคอลัมน์ต้องห้าม (อายุ)
│   ├── qa_engine.py        # สมองของบอท: จับคู่คำถาม-คำตอบ + บล็อกอายุ/ปีเกิด
│   ├── birthday.py         # parse วันเกิด, ตัดปีออก, ตรวจจับเดือนในคำถาม
│   └── responses.py        # ข้อความตอบกวนๆ น่ารัก
├── data/
│   └── contacts.xlsx       # ไฟล์ข้อมูล (วางเพิ่มได้)
├── requirements.txt
├── Procfile                # สำหรับ Railway
├── render.yaml             # สำหรับ Render
├── runtime.txt
├── .env.example
└── README.md
```

## ใช้งานในเครื่อง (Local)

```bash
# 1) สร้าง virtualenv (ทางเลือก)
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 2) ติดตั้ง dependencies
pip install -r requirements.txt

# 3) ตั้งค่า environment
cp .env.example .env
# แก้ไฟล์ .env ใส่ LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET

# 4) รันเซิร์ฟเวอร์
python app.py
# หรือ: gunicorn app:app --bind 0.0.0.0:8000
```

ทดสอบในเครื่องก่อน deploy โดยใช้ `ngrok`:

```bash
ngrok http 8000
# เอา URL https://xxx.ngrok-free.app/callback ไปใส่ใน LINE Developers Console
```

## ขั้นตอนสร้าง LINE Channel

1. ไปที่ [LINE Developers Console](https://developers.line.biz/console/)
2. สร้าง **Provider** ใหม่ (ถ้ายังไม่มี)
3. สร้าง **Messaging API channel** ใหม่
4. ในแท็บ **Messaging API** จะได้:
   - **Channel access token (long-lived)** → กดสร้าง แล้วก็อปไว้ใส่เป็น `LINE_CHANNEL_ACCESS_TOKEN`
5. ในแท็บ **Basic settings**:
   - **Channel secret** → ก็อปไว้ใส่เป็น `LINE_CHANNEL_SECRET`
6. ในแท็บ **Messaging API**:
   - **Webhook URL** = `https://YOUR-DOMAIN/callback`
   - เปิด **Use webhook** = ON
   - **Auto-reply messages** = OFF (ปิด เพื่อให้บอทตอบเองได้)
   - **Greeting messages** = ตามต้องการ
7. **เพิ่มบอทเข้ากลุ่ม**: ไปที่ **OA Manager → Settings → Response settings**
   - เปิด **Allow bot to join group chats**

## Deploy บน Render (ฟรี)

วิธีที่ง่ายที่สุด:

1. push โค้ดทั้งโฟลเดอร์นี้ขึ้น GitHub repo
2. ไปที่ <https://render.com> → **New + → Blueprint**
3. ชี้ไปที่ repo → Render จะอ่าน `render.yaml` ให้อัตโนมัติ
4. ในหน้าตั้งค่า ใส่:
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
5. กด **Apply** รอ build เสร็จ (~3-5 นาที)
6. คัดลอก URL เช่น `https://line-bot-156.onrender.com` → เอาไปวางที่ Webhook URL ใน LINE Developers ตามด้วย `/callback`

> ⚠️ **Render Free** จะ sleep หลังไม่มี traffic 15 นาที ครั้งแรกที่ใครพิมพ์ในกลุ่มอาจช้า 30-60 วิ ครับ
> ถ้าไม่ชอบ → ใช้แผน Starter ($7/mo) หรือใช้ cron-job.org ปิงทุก 10 นาที

## Deploy บน Railway (ฟรี — มีเครดิตเริ่มต้น)

1. push ขึ้น GitHub
2. ไปที่ <https://railway.app> → **New Project → Deploy from GitHub repo**
3. ที่แท็บ **Variables** ใส่:
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
4. ที่แท็บ **Settings → Networking** กด **Generate Domain**
5. คัดลอก URL ไปใส่ Webhook URL ใน LINE Developers ตามด้วย `/callback`

Railway อ่าน `Procfile` เป็นค่าเริ่มต้นอยู่แล้ว ไม่ต้องตั้งค่า build/start เพิ่ม

## เพิ่มไฟล์ข้อมูลใหม่

1. วางไฟล์ `.xlsx` ลงในโฟลเดอร์ `data/` (commit ขึ้น repo แล้ว push)
2. หรือถ้า deploy แล้ว: เรียก `POST /reload?token=YOUR_RELOAD_TOKEN` เพื่อโหลดข้อมูลใหม่

## คำสั่งที่ใช้ในกลุ่มไลน์

ในกลุ่ม บอทจะตอบเฉพาะเมื่อขึ้นต้นด้วย `บอท`, `ถาม`, `/bot`, หรือ `/ask` เพื่อไม่ให้รบกวน

```
บอท ใครหล่อที่สุด
บอท ใครสวยที่สุด
บอท 156
บอท ภ.8
บอท เท็น
บอท ใครเกิดเดือน พ.ค. บ้าง
บอท เกิดเดือนนี้บ้าง
บอท เท็น เกิดวันไหน
บอท 156 เกิดเดือนไหน
บอท กรรมการ
บอท เจ้าหน้าที่
บอท ช่วยเหลือ
```

> 🚫 **เรื่องที่ถามแล้วจะไม่ตอบ** (ฮาร์ดบล็อกในโค้ด)
> - `อายุเท่าไหร่`, `กี่ขวบ`, `กี่ปี`
> - `เกิดปีไหน`, `ปีเกิด`, `เกิด พ.ศ./ค.ศ. ...`, `วันเดือนปีเกิด`
> - คำถามที่มีตัวเลข 4 หลัก + คำว่า "เกิด" (ตีความว่าเป็นปี)
> - `how old`, `age`, `birth year`, `dob`, `date of birth`

ใน 1-1 chat ไม่ต้องขึ้นต้นด้วย `บอท` ก็ได้

## ปรับแต่งโทนการตอบ

แก้ที่ `bot/responses.py`:

- `AGE_REFUSALS` — ข้อความปฏิเสธเรื่องอายุ/ปีเกิด
- `NOT_FOUND` — ข้อความเมื่อหาไม่เจอ
- `GREETINGS` — ข้อความทักทาย
- `HELP_TEXT` — เมนูช่วยเหลือ

## Troubleshooting

| อาการ | สาเหตุที่อาจเป็น | วิธีแก้ |
|-------|------------------|---------|
| 400 Invalid signature | `LINE_CHANNEL_SECRET` ผิด | ตรวจค่าใน .env / dashboard ให้ตรงกับ LINE Developers |
| Webhook verify ไม่ผ่าน | URL ผิด / server หลับ | ลองเปิด URL ตรงๆ ในเบราว์เซอร์ ต้องได้ JSON `{"status":"ok"}` |
| ตอบช้ามากครั้งแรก | Render Free sleep | ใช้ cron-job.org ปิง `/healthz` ทุก 10 นาที |
| บอทไม่ตอบในกลุ่ม | ลืมขึ้นต้นด้วย `บอท` | พิมพ์ `บอท ช่วยเหลือ` ก่อน |

## License

ใช้ภายในรุ่นเท่านั้น 🤝
