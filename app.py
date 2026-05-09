"""LINE BOT main app - Flask + LINE Messaging API"""
from __future__ import annotations

import os
import logging
import threading
from flask import Flask, request, abort, jsonify

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    JoinEvent,
    SourceGroup,
    SourceRoom,
)

from bot import answer_message, reload_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("linebot156")

# ---------- ENV ----------
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    log.warning(
        "ยังไม่ได้ตั้งค่า LINE_CHANNEL_ACCESS_TOKEN / LINE_CHANNEL_SECRET "
        "(ตั้งใน .env หรือใน Render/Railway dashboard)"
    )

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN or "DUMMY")
handler = WebhookHandler(CHANNEL_SECRET or "DUMMY")

app = Flask(__name__)

# โหลดข้อมูล Excel ทันทีตอนสตาร์ท (ใน thread แยกเพื่อไม่ให้ block boot)
def _bootstrap():
    try:
        reload_data()
    except Exception as e:  # noqa: BLE001
        log.exception("โหลดข้อมูลไม่สำเร็จ: %s", e)


threading.Thread(target=_bootstrap, daemon=True).start()


# ---------- Routes ----------
@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "service": "ผกก.156 LINE BOT",
            "status": "ok",
            "endpoints": {"webhook": "/callback", "reload": "/reload"},
        }
    )


@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200


@app.route("/reload", methods=["POST", "GET"])
def reload_endpoint():
    """กดเรียกเพื่อรีโหลด Excel หลังเพิ่ม/แก้ไฟล์ในโฟลเดอร์ data/"""
    token = request.args.get("token") or request.headers.get("X-Reload-Token")
    expected = os.environ.get("RELOAD_TOKEN")
    if expected and token != expected:
        abort(403)
    reload_data()
    return jsonify({"status": "reloaded"}), 200


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    log.info("Webhook: %s", body[:300])
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        log.warning("Invalid signature - เช็ค LINE_CHANNEL_SECRET")
        abort(400)
    except Exception:  # noqa: BLE001
        log.exception("Error handling webhook")
        abort(500)
    return "OK", 200


# ---------- LINE event handlers ----------
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event: MessageEvent):
    user_text = (event.message.text or "").strip()
    src_type = type(event.source).__name__
    log.info("[%s] msg=%r", src_type, user_text)

    # ในกลุ่ม/ห้อง: ตอบเฉพาะเมื่อ mention หรือขึ้นต้นด้วยคำสั่งบอท
    if isinstance(event.source, (SourceGroup, SourceRoom)):
        prefix_triggered = any(
            user_text.lower().startswith(p)
            for p in ("/bot", "บอท", "ถาม", "@bot", "@ผกก156", "/ask")
        )
        if not prefix_triggered:
            # ถ้าไม่ trigger ก็เงียบไว้ ไม่งั้นบอทจะเสียงดังเกินไปในกลุ่ม
            return
        # ตัดคำ trigger ออก
        for p in ("/bot", "/ask", "@bot", "@ผกก156", "บอท", "ถาม"):
            if user_text.lower().startswith(p):
                user_text = user_text[len(p):].strip(" :,-")
                break

    reply = answer_message(user_text)
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    except Exception as e:  # noqa: BLE001
        log.exception("ส่งข้อความกลับไม่สำเร็จ: %s", e)


@handler.add(JoinEvent)
def handle_join(event: JoinEvent):
    msg = (
        "สวัสดีครับชาวรุ่น 156! 🐣\n"
        "หนูเป็นบอทประจำรุ่น คอยตอบคำถามให้ครับ\n"
        "ในกลุ่ม พิมพ์นำหน้าด้วย ‘บอท’ หรือ ‘/bot’ แล้วตามด้วยคำถาม\n"
        "เช่น: บอท ใครหล่อที่สุด / บอท 156 / บอท ใครสวยที่สุด\n"
        "พิมพ์ ‘บอท ช่วยเหลือ’ เพื่อดูเมนูทั้งหมดครับ"
    )
    try:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:  # noqa: BLE001
        log.exception("ส่ง welcome ไม่สำเร็จ")


# ---------- Local run ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("DEBUG") == "1")
