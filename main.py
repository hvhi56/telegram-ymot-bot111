import os
import json
import subprocess
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google.cloud import texttospeech

# 🔑 טעינת מפתח Google TTS מקובץ סביבה
key_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
with open("google_key.json", "w") as f:
    f.write(key_json)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_key.json"

# 🛠 משתני סביבה מה-Render
BOT_TOKEN = '8007934043:AAFKq2Iar3zqM8Juaod9DR90lowAAtSTCx0'
YMOT_TOKEN = '0733181406:80809090'
YMOT_PATH = 'ivr2:2/'

def text_to_mp3(text, filename='output.mp3'):
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="he-IL",
        name="he-IL-Avri",  # קול גברי
        ssml_gender=texttospeech.SsmlVoiceGender.MALE
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.2  # מהירות מוגברת
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    with open(filename, "wb") as out:
        out.write(response.audio_content)

def convert_to_wav(input_file, output_file='output.wav'):
    subprocess.run([
        'ffmpeg', '-i', input_file, '-ar', '8000', '-ac', '1', '-f', 'wav',
        output_file, '-y'
    ])

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
    print("תשובת ימות:", response.text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        print("⚠️ התקבלה הודעה לא טקסטואלית – מדלג")
        return

    text = update.message.text
    print("✅ טקסט שהתקבל:", text)

    text_to_mp3(text)
    convert_to_wav('output.mp3', 'output.wav')
    upload_to_ymot('output.wav')

    os.remove('output.mp3')
    os.remove('output.wav')

# 🟢 Flask לשמירה על פעילות
from keep_alive import keep_alive
keep_alive()

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

print("🚀 הבוט עלה! שלח טקסט בטלגרם והוא יושמע בשלוחה 🎧")
app.run_polling()
