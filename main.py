import os
import json
import subprocess
import requests
import base64
from datetime import datetime
import pytz

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google.cloud import texttospeech

# 🟡 כתיבת קובץ מפתח Google מ־BASE64
key_b64 = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")
if not key_b64:
    raise Exception("❌ משתנה GOOGLE_APPLICATION_CREDENTIALS_B64 לא מוגדר או ריק")

try:
    with open("google_key.json", "wb") as f:
        f.write(base64.b64decode(key_b64))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_key.json"
except Exception as e:
    raise Exception("❌ נכשל בכתיבת קובץ JSON מ־BASE64: " + str(e))

# 🛠 משתנים מ־Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
YMOT_TOKEN = os.getenv("YMOT_TOKEN")
YMOT_PATH = os.getenv("YMOT_PATH", "ivr2:2/")

# 🔢 המרת מספרים לעברית
def num_to_hebrew_words(hour, minute):
    hours_map = {
        1: "אחת", 2: "שתיים", 3: "שלוש", 4: "ארבע", 5: "חמש",
        6: "שש", 7: "שבע", 8: "שמונה", 9: "תשע", 10: "עשר",
        11: "אחת עשרה", 12: "שתים עשרה"
    }

    minutes_map = {
        0: "אפס", 1: "ודקה", 2: "ושתי דקות", 3: "ושלוש דקות", 4: "וארבע דקות", 5: "וחמש דקות",
        6: "ושש דקות", 7: "ושבע דקות", 8: "ושמונה דקות", 9: "ותשע דקות", 10: "ועשרה",
        11: "ואחת עשרה דקות", 12: "ושתים עשרה דקות", 13: "ושלוש עשרה דקות", 14: "וארבע עשרה דקות",
        15: "וחמש עשרה דקות", 16: "ושש עשרה דקות", 17: "ושבע עשרה דקות", 18: "ושמונה עשרה דקות",
        19: "ותשע עשרה דקות", 20: "ועשרים", 21: "עשרים ואחת", 22: "עשרים ושתיים",
        23: "עשרים ושלוש", 24: "עשרים וארבע", 25: "עשרים וחמש", 26: "עשרים ושש",
        27: "עשרים ושבע", 28: "עשרים ושמונה", 29: "עשרים ותשע", 30: "וחצי",
        31: "שלושים ואחת", 32: "שלושים ושתיים", 33: "שלושים ושלוש",
        34: "שלושים וארבע", 35: "שלושים וחמש", 36: "שלושים ושש",
        37: "שלושים ושבע", 38: "שלושים ושמונה", 39: "שלושים ותשע",
        40: "וארבעים דקות", 41: "ארבעים ואחת", 42: "ארבעים ושתיים",
        43: "ארבעים ושלוש", 44: "ארבעים וארבע", 45: "ארבעים וחמש",
        46: "ארבעים ושש", 47: "ארבעים ושבע", 48: "ארבעים ושמונה",
        49: "ארבעים ותשע", 50: "וחמישים דקות", 51: "חמישים ואחת",
        52: "חמישים ושתיים", 53: "חמישים ושלוש", 54: "חמישים וארבע",
        55: "חמישים וחמש", 56: "חמישים ושש", 57: "חמישים ושבע",
        58: "חמישים ושמונה", 59: "חמישים ותשע"
    }

    hour_12 = hour % 12 or 12
    return f"{hours_map[hour_12]} {minutes_map[minute]}"

# 🎤 יצירת MP3 עם Google TTS
def text_to_mp3(text, filename='output.mp3'):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="he-IL",
        name="he-IL-Wavenet-B",  # קול גברי
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.2
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    with open(filename, "wb") as out:
        out.write(response.audio_content)

# 🎧 המרה ל־WAV בפורמט ימות
def convert_to_wav(input_file, output_file='output.wav'):
    subprocess.run([
        'ffmpeg', '-i', input_file, '-ar', '8000', '-ac', '1', '-f', 'wav',
        output_file, '-y'
    ])

# 📤 העלאה לשלוחה
def upload_to_ymot(wav_file_path):
    url = 'https://call2all.co.il/ym/api/UploadFile'
    with open(wav_file_path, 'rb') as f:
        files = {'file': (os.path.basename(wav_file_path), f, 'audio/wav')}
        data = {
            'token': YMOT_TOKEN,
            'path': YMOT_PATH,
            'convertAudio': '1',
            'autoNumbering': 'true'
        }
        response = requests.post(url, data=data, files=files)
    print("📞 תגובת ימות:", response.text)

# 🤖 טיפול בהודעות טקסט מהבוט
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        print("⚠️ התקבלה הודעה לא טקסטואלית – מדלג")
        return

    text = update.message.text
    print("✅ טקסט שהתקבל:", text)

    # ⏰ שעה לפי שעון ישראל
    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    hebrew_time = num_to_hebrew_words(now.hour, now.minute)

    full_text = f"{hebrew_time} במבזקים פלוס. {text}"

    text_to_mp3(full_text)
    convert_to_wav('output.mp3', 'output.wav')
    upload_to_ymot('output.wav')

    os.remove('output.mp3')
    os.remove('output.wav')

# ♻️ שמירה על חיים (Render)
from keep_alive import keep_alive
keep_alive()

# ▶️ הפעלת הבוט
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

print("🚀 הבוט עלה! שלח טקסט בטלגרם והוא יושמע בשלוחה 🎧")
app.run_polling()
