# gemini.py
import google.generativeai as genai

# 設定 API 金鑰
genai.configure(api_key="AIzaSyC9q9XCyrurFHX-YTFRSan7MRKTFmGF7wA")

# 初始化模型（可根據需要使用不同模型）
model = genai.GenerativeModel('gemini-pro')

def get_ai_response(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"[Gemini 發生錯誤] {str(e)}"
