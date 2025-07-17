import os
import json
import subprocess
import requests
import base64
import pytz
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google.cloud import texttospeech

# 🟡 1. כתיבת מפתח JSON מקודד
key_b64 = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_B64")

if not key_b64:
    raise Exception("❌ משתנה GOOGLE_APPLICATION_CREDENTIALS_B64 לא מוגדר או ריק")

try:
    with open("google_key.json", "wb") as f:
        f.write(base64.b64decode(key_b64))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_key.json"
except Exception as e:
    raise Exception("❌ נכשל בכתיבת קובץ JSON מ־BASE64: " + str(e))

# 🛠 משתנים מהסביבה
BOT_TOKEN = os.getenv("BOT_TOKEN")
YMOT_TOKEN = os.getenv("YMOT_TOKEN")
YMOT_PATH = os.getenv("YMOT_PATH", "ivr2:2/")

# ⏰ יצירת טקסט זמן בעברית
def hebrew_time_string():
    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    hour = str(now.hour)
    minute = str(now.minute).zfill(2)
    return f"{hour} {minute}"

# 🎤 Google TTS
def text_to_mp3(text, filename='output.mp3'):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="he-IL",
        name="he-IL-Wavenet-B",
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

# 🎧 המרה ל־WAV בפורמט של ימות
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

# 📩 טיפול בטקסטים מהטלגרם
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        print("⚠️ התקבלה הודעה לא טקסטואלית – מדלג")
        return

    original_text = update.message.text
    print("✅ טקסט שהתקבל:", original_text)

    time_prefix = hebrew_time_string()
    line_name = "במבזקים פלוס"
    full_text = f"{time_prefix} {line_name}. {original_text}"

    print("🗣️ טקסט עם הקדמה:", full_text)

    text_to_mp3(full_text)
    convert_to_wav('output.mp3', 'output.wav')
    upload_to_ymot('output.wav')

    os.remove('output.mp3')
    os.remove('output.wav')

# 🔁 שמירה על פעילות
from keep_alive import keep_alive
keep_alive()

# 🤖 הפעלת הבוט
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

print("🚀 הבוט עלה! שלח טקסט בטלגרם והוא יושמע בשלוחה 🎧")
app.run_polling()
