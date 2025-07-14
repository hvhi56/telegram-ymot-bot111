import os
import requests
import subprocess
from keep_alive import keep_alive
from gtts import gTTS
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

BOT_TOKEN = '8007934043:AAE3i7WmKrfN-MTBxry8LuEJ-QUY3b1QCNY'
YMOT_TOKEN = '0733181406:80809090'
YMOT_PATH = 'ivr2:2/'

def text_to_mp3(text, filename='output.mp3'):
    tts = gTTS(text=text, lang='iw')
    tts.save(filename)

def convert_to_wav(input_file, output_file='output.wav'):
    subprocess.run([
        'ffmpeg',
        '-i', input_file,
        '-ar', '8000',
        '-ac', '1',
        '-f', 'wav',
        output_file,
        '-y'
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
        print("⚠️ התקבלה הודעה לא טקסטואלית – מתעלם")
        return

    text = update.message.text
    print("✅ טקסט שהתקבל:", text)

    text_to_mp3(text)
    convert_to_wav('output.mp3', 'output.wav')
    upload_to_ymot('output.wav')

    os.remove('output.mp3')
    os.remove('output.wav')


app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

print("✅ הבוט פועל – שלח טקסט והוא יושמע בשלוחה")
keep_alive()
app.run_polling()
