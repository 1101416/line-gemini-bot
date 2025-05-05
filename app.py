from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    StickerMessage, StickerSendMessage,
    ImageMessage, VideoMessage, LocationMessage
)
import config
import google.generativeai as genai
from config import GEMINI_API_KEY
from db import init_db, save_message, get_history, delete_history
import requests 
import os
from datetime import datetime, timedelta
# 初始化資料庫
init_db()

# 設定 Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# 建立模型物件（文字生成模型）
model = genai.GenerativeModel("gemini-1.5-flash")

app = Flask(__name__)
line_bot_api = LineBotApi(config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

import yfinance as yf

def get_stock_price(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.fast_info
        name = info.get("shortName", "未知公司")
        price = info.get("regularMarketPrice", "無資料")
        currency = info.get("currency", "")
        return f"{name} ({symbol})\n最新股價：{price} {currency}"
    except Exception as e:
        return f"查詢失敗：{e}"

from flask import jsonify

@app.route("/history/<user_id>", methods=["GET"])
def api_get_history(user_id):
    rows = get_history(user_id)
    result = [{"user": u, "bot": b, "timestamp": t} for u, b, t in rows]
    return jsonify(result)

@app.route("/history/<user_id>", methods=["DELETE"])
def api_delete_history(user_id):
    delete_history(user_id)
    return jsonify({"status": "deleted"})

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    print("收到 LINE 請求：", body)  # 確認收到 webhook 呼叫

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("無效簽章")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    print(f"[使用者 ID] {user_id}")
    user_msg = event.message.text.strip()
    
    if user_msg == "清除紀錄":
        try:
            delete_url = f"https://line-gemini-bot-kgd6.onrender.com/history/{user_id}"
            res = requests.delete(delete_url)

            if res.status_code == 200:
                reply_text = "你的歷史紀錄已成功刪除。"
            else:
                reply_text = f"無法刪除紀錄（狀態碼：{res.status_code}）"
        except Exception as e:
            reply_text = f"發生錯誤：{str(e)}"
            
        #  直接回傳，不進入其他邏輯
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return
    
     # 查紀錄
    elif user_msg == "查紀錄":
        try:
            history = get_history(user_id)
            if not history:
                reply_text = "沒有找到你的對話紀錄。"
            else:
                # 取最近 5 筆，格式化訊息
                reply_lines = []
                for row in history[-5:]:
                    user_msg, bot_reply, timestamp = row
                    taiwan_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S") + timedelta(hours=8)
                    time_str = taiwan_time.strftime("%Y-%m-%d %H:%M:%S")
                    reply_lines.append(f"{time_str}\n{user_msg}\n{bot_reply}")
                reply_text = "最近的對話紀錄：\n\n" + "\n\n".join(reply_lines)
        except Exception as e:
            reply_text = f"查詢失敗：{str(e)}"
    
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return
    
    # 如果用戶輸入「我的ID」，回傳使用者 ID
    if user_msg == "我的ID":
        reply_text = f"你的使用者 ID 是：\n{user_id}"
    
    # 股票查詢邏輯
    elif "查股票" in user_msg or "股價" in user_msg:
        try:
            parts = user_msg.split()
            if len(parts) >= 2:
                symbol = parts[-1].upper()
                reply_text = get_stock_price(symbol)
            else:
                reply_text = "請輸入股票代號(台股要加.TW/美股)，例如：查股票 2330.TW 或 查股票 AAPL"
        except Exception as e:
            reply_text = f"查詢錯誤：{e}"

    # Gemini AI 生成文字
    else:
        try:
            response = model.generate_content(user_msg)
            reply_text = response.text.strip()
        except Exception as e:
            reply_text = f"發生錯誤：{e}"

    # 儲存對話紀錄
    if user_msg != "清除紀錄":
        save_message(user_id, user_msg, reply_text)

    # 回傳訊息
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
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
        TextSendMessage(text="收到圖片")
    )

@handler.add(MessageEvent, message=VideoMessage)
def handle_video(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="收到影片")
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
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
