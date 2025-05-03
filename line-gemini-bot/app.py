# app.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    StickerMessage, StickerSendMessage,
    ImageMessage, VideoMessage, LocationMessage
)
from gemini import get_ai_response 
import config
from db import init_db
init_db()
from db import save_message
from flask import jsonify
from db import get_history, delete_history
import os

app = Flask(__name__)
line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    
@app.route("/history/<user_id>", methods=['GET'])
def get_user_history(user_id):
    history = get_history(user_id)
    return jsonify([
        {"role": role, "message": msg, "timestamp": ts}
        for role, msg, ts in history
    ])

@app.route("/history/<user_id>", methods=['DELETE'])
def delete_user_history(user_id):
    delete_history(user_id)
    return jsonify({"status": "success", "message": f"歷史紀錄已刪除: {user_id}"})

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_input = event.message.text

    save_message(user_id, "user", user_input)
    ai_reply = get_ai_response(user_input)
    save_message(user_id, "bot", ai_reply)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=ai_reply)
    )

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    sticker = event.message
    line_bot_api.reply_message(
        event.reply_token,
        StickerSendMessage(
            package_id=sticker.package_id,
            sticker_id=sticker.sticker_id
        )
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到圖片 📷")
    )

@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到影片 🎥")
    )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    location = event.message
    reply = f"位置：{location.title or '未命名'}\n地址：{location.address}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run()
