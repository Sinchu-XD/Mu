import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import AudioQuality
from yt_dlp import YoutubeDL
from random import shuffle
from collections import deque
import time

API_ID = 6067591
API_HASH = "94e17044c2393f43fda31d3afe77b26b"
BOT_TOKEN = "7913409153:AAEvv86Q96KqjU6-fvj_JOBKp4_MHH9H4Wk"
SESSION_STRING = "BQBclYcAfwPhsOaYEN9rZiJTeqV1e-mW90J3pxU5lU-HRDBDir4n236Uy6xowZLnSJ83DDyV-7m8NommEpFKXVZMwRR41bXxvE8JzhIcLIJnCP5yObgE3yRkljsE36qEsdVYTgggdMSHrhoFWZG5YuOIJ0hi1HpqzOJhocARqoVbys1-CNSjTAEXdNB3knhatAqkHVnHfWcgvtshc3iiru3Gjpl9lXaPnLL5p5GP11dL8vRS4Dob-8nZW2vEkXqsD4-Ce6BAD8m4RIqTsomtrQCgaH4ugYfpFuKVr_oz04hUTjB4MzXK-Wr_Fz5Lk42PnrE3wWEwhsfgOVu8AM02YlKLV77MegAAAAHKUdR6AA"

bot = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("Assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call = PyTgCalls(assistant)

queues = {}
cache = {}
fetch_lock = asyncio.Semaphore(3)

TEMP_AUDIO_DIR = "temp_audio"
if not os.path.exists(TEMP_AUDIO_DIR):
    os.makedirs(TEMP_AUDIO_DIR)



# OptimiYDL_OPTS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "source_address": "0.0.0.0",
    "forceipv4": True,
    "cachedir": False,
    "cookiefile": "cookies/cookies.txt",
}

cached_urls = {}

async def get_stream_url(query: str):
    if query in cached_urls:
        return cached_urls[query]

    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: YoutubeDL(YDL_OPTS).extract_info(query, download=False)
    )

    url = data["url"]
    cached_urls[query] = url
    return url


async def play(chat_id, query):
    try:
        stream_url = await get_media_stream_url(query)
        
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
    query = message.text.split(None, 1)[1] if len(message.command) > 1 else None

    if not query:
        return await message.reply("❌ Send a song name or YouTube URL.")

    msg = await message.reply("🔍 Searching...")

    # Check if we're already streaming the song
    if chat_id in queues and query in queues[chat_id]:
        return await msg.edit_text(f"🎶 Already in the queue: {query}")

    # Add song to the queue
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    queues[chat_id].append(query)

    # Stream the song
    success, error = await play(chat_id, query)

    if success:
        await msg.edit_text(f"🎶 Now Playing: {query}")
    else:
        await msg.edit_text(error)



@bot.on_message(filters.command("skip") & filters.group)
async def skip_command(_, message: Message):
    chat_id = message.chat.id

    if chat_id not in queues or not queues[chat_id]:
        return await message.reply("❌ Queue is empty.")

    queues[chat_id].popleft()

    if queues[chat_id]:
        next_song = queues[chat_id][0]
        success, error = await play(chat_id, next_song)
        if success:
            await message.reply(f"⏭ Now playing: [{next_song['title']}]({next_song['webpage_url']})", disable_web_page_preview=True)
        else:
            await message.reply(error)
    else:
        # Don't leave VC, just stop playback
        await call.leave_call(chat_id)
        await message.reply("✅ Playback stopped.")
        queues.pop(chat_id)

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
        
