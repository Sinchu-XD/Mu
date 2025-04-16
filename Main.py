import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import AudioQuality
from yt_dlp import YoutubeDL
from random import shuffle
import time

API_ID = 6067591
API_HASH = "94e17044c2393f43fda31d3afe77b26b"
BOT_TOKEN = "7913409153:AAEvv86Q96KqjU6-fvj_JOBKp4_MHH9H4Wk"
SESSION_STRING = "BQBclYcAfwPhsOaYEN9rZiJTeqV1e-mW90J3pxU5lU-HRDBDir4n236Uy6xowZLnSJ83DDyV-7m8NommEpFKXVZMwRR41bXxvE8JzhIcLIJnCP5yObgE3yRkljsE36qEsdVYTgggdMSHrhoFWZG5YuOIJ0hi1HpqzOJhocARqoVbys1-CNSjTAEXdNB3knhatAqkHVnHfWcgvtshc3iiru3Gjpl9lXaPnLL5p5GP11dL8vRS4Dob-8nZW2vEkXqsD4-Ce6BAD8m4RIqTsomtrQCgaH4ugYfpFuKVr_oz04hUTjB4MzXK-Wr_Fz5Lk42PnrE3wWEwhsfgOVu8AM02YlKLV77MegAAAAHKUdR6AA"

bot = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("Assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call = PyTgCalls(assistant)

queues = {}

TEMP_AUDIO_DIR = "temp_audio"
if not os.path.exists(TEMP_AUDIO_DIR):
    os.makedirs(TEMP_AUDIO_DIR)

async def get_youtube_audio(query: str):
    loop = asyncio.get_event_loop()

    # Define yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',          # Best available audio quality
        'extractaudio': True,                # Extract audio only (no video)
        'audioformat': 'mp3',                # Output audio format (mp3)
        'outtmpl': f'{TEMP_AUDIO_DIR}/%(id)s.%(ext)s',  # Template for saved file path
        'nocheckcertificate': True,          # Ignore SSL certificate errors
        'ignoreerrors': True,               # Don't stop on errors
        'quiet': True,                       # Suppress output to avoid clutter
        'no_warnings': True,                 # Suppress warnings
        'default_search': 'auto',            # Default search engine for the query
        'cookiefile': 'cookies/cookies.txt', # Path to cookies file for authentication
    }

    # Define a function to run the yt-dlp extraction process
    def extract():
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    # Run the extraction function asynchronously
    info = await loop.run_in_executor(None, extract)

    # Check if the result contains entries (in case of a playlist search)
    if 'entries' in info:
        info = info['entries'][0]

    # Return the relevant information
    return {
        'title': info.get('title'),
        'url': info.get('url'),
        'webpage_url': info.get('webpage_url'),
    }

# Optimized play function
async def play(chat_id, song):
    try:
        stream_url = song['url']
        
        # Start the stream immediately (avoid waiting for full download)
        media_stream = MediaStream(stream_url, audio_parameters=AudioQuality.STUDIO)

        await call.play(
            chat_id,
            media_stream
        )

        return True, None
    except Exception as e:
        return False, f"Error: <code>{e}</code>"

@bot.on_message(filters.command("play") & filters.group)
async def play_command(_, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        return await message.reply("❌ Please provide a song name or YouTube link.")
    
    query = message.text.split(None, 1)[1]
    song = await get_youtube_audio(query)

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(song)

    if len(queues[chat_id]) == 1:
        success, error_message = await play(chat_id, song)
        if success:
            await message.reply(f"▶️ Now playing: [{song['title']}]({song['webpage_url']})", disable_web_page_preview=True)
        else:
            await message.reply(error_message)
    else:
        await message.reply(f"📥 Added to queue: [{song['title']}]({song['webpage_url']})", disable_web_page_preview=True)

# Skip command with queue optimization
@bot.on_message(filters.command("skip") & filters.group)
async def skip_command(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        return await message.reply("❌ Nothing in queue to skip.")
    
    skipped = queues[chat_id].pop(0)
    if queues[chat_id]:
        next_song = queues[chat_id][0]
        await play(chat_id, next_song)
        await message.reply(f"⏭ Skipped. Now playing: [{next_song['title']}]({next_song['webpage_url']})", disable_web_page_preview=True)
    else:
        await call.leave_call(chat_id)
        queues.pop(chat_id, None)
        await message.reply("⏹ Queue empty. Stopped playback.")

# Main bot loop
async def main():
    await bot.start()
    await assistant.start()
    await call.start()
    print("✅ Music bot running.")
    await asyncio.get_event_loop().create_future()

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
        
