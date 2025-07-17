import os
import json
import subprocess
import requests
import base64
from datetime import datetime
import pytz
import asyncio

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
        15: "ורבע", 16: "ושש עשרה דקות", 17: "ושבע עשרה דקות", 18: "ושמונה עשרה דקות",
        19: "ותשע עשרה דקות", 20: "ועשרים", 21: "ועשרים ואחת דקות", 22: "ועשרים ושתיים דקות",
        23: "ועשרים ושלוש דקות", 24: "ועשרים וארבע דקות", 25: "ועשרים וחמש דקות",
        26: "ועשרים ושש דקות", 27: "ועשרים ושבע דקות", 28: "ועשרים ושמונה דקות",
        29: "ועשרים ותשע דקות", 30: "וחצי",
        31: "ושלושים ואחת דקות", 32: "ושלושים ושתיים דקות", 33: "ושלושים ושלוש דקות",
        34: "ושלושים וארבע דקות", 35: "ושלושים וחמש דקות", 36: "ושלושים ושש דקות",
        37: "ושלושים ושבע דקות", 38: "ושלושים ושמונה דקות", 39: "ושלושים ותשע דקות",
        40: "וארבעים דקות", 41: "וארבעים ואחת דקות", 42: "וארבעים ושתיים דקות",
        43: "וארבעים ושלוש דקות", 44: "וארבעים וארבע דקות", 45: "ושלושת רבעי",
        46: "וארבעים ושש דקות", 47: "וארבעים ושבע דקות", 48: "וארבעים ושמונה דקות",
        49: "וארבעים ותשע דקות", 50: "וחמישים דקות", 51: "וחמישים ואחת דקות",
        52: "וחמישים ושתיים דקות", 53: "וחמישים ושלוש דקות", 54: "וחמישים וארבע דקות",
        55: "וחמישים וחמש דקות", 56: "וחמישים ושש דקות", 57: "וחמישים ושבע דקות",
        58: "וחמישים ושמונה דקות", 59: "וחמישים ותשע דקות"
    }

    hour_12 = hour % 12 or 12
    return f"{hours_map[hour_12]} {minutes_map[minute]}"

# 🧠 יוצר טקסט מלא כולל שעה
def create_full_text(text):
    tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(tz)
    hebrew_time = num_to_hebrew_words(now.hour, now.minute)
    return f"{hebrew_time} במבזקים פלוס. {text}"

# 🎤 יצירת MP3 עם Google TTS
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

# 📥 טיפול בהודעות
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    text = message.text or message.caption
    has_video = message.video is not None

    # ⬅️ שלב 1: קודם מעלים את הווידאו (כדי שיושמע אחרי)
    if has_video:
        video_file = await message.video.get_file()
        await video_file.download_to_drive("video.mp4")
        convert_to_wav("video.mp4", "video.wav")
        upload_to_ymot("video.wav")
        os.remove("video.mp4")
        os.remove("video.wav")

    # ⬅️ שלב 2: עכשיו מעלים את הטקסט (כדי שיושמע ראשון)
    if text:
        full_text = create_full_text(text)
        text_to_mp3(full_text, "output.mp3")
        convert_to_wav("output.mp3", "output.wav")
        upload_to_ymot("output.wav")
        os.remove("output.mp3")
        os.remove("output.wav")

# ♻️ שמירה על חיים (Render)
from keep_alive import keep_alive
keep_alive()

# ▶️ הפעלת הבוט
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))

print("🚀 הבוט עלה! שלח טקסט, תמונה או וידאו – והוא יוקרא ויושמע בשלוחה 🎧")
app.run_polling()
