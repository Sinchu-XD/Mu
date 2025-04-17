import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, Update
from pytgcalls.types import AudioQuality
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic
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
ytmusic = YTMusic()


YDL_OPTS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "nocheckcertificate": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "forceipv4": True,
    "cachedir": False,
    "cookiefile": "cookies/cookies.txt",
}

cached_urls = {}

async def get_stream_url(query: str):
    if query in cached_urls:
        return cached_urls[query]

    search_results = ytmusic.search(query, filter="songs")
    if not search_results:
        raise Exception("Song not found!")

    result = search_results[0]
    video_id = result.get("videoId")
    if not video_id:
        raise Exception("Invalid video ID!")

    title = result.get("title")
    duration = result.get("duration")
    artists = ", ".join([a["name"] for a in result.get("artists", [])])
    thumbnail = result["thumbnails"][-1]["url"]
    url = f"https://www.youtube.com/watch?v={video_id}"

    # Get stream URL via yt-dlp
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, lambda: YoutubeDL(YDL_OPTS).extract_info(url, download=False)
    )

    stream_url = data.get("url")
    if not stream_url:
        raise Exception("No stream URL found!")

    cached_urls[query] = stream_url
    return {
        "stream_url": stream_url,
        "title": title,
        "duration": duration,
        "artists": artists,
        "thumbnail": thumbnail,
        "video_url": url,
    }

async def play(bot: Client, call: PyTgCalls, chat_id: int, query: str):
    if chat_id not in queues:
        queues[chat_id] = deque()
        caption = f"🎵 <b>{song['title']}</b>\n👤 <i>{song['artists']}</i>\n🕒 <code>{song['duration']}</code>\n🔗 <a href='{song['video_url']}'>YouTube</a>"
    await bot.send_photo(
        photo=song["thumbnail"],
        caption=caption,
        parse_mode="html"
    )

    stream_url = await get_stream_url(query)
    media_stream = MediaStream(stream_url, audio_parameters=AudioQuality.HIGH)

    await call.play(
        chat_id,
        media_stream
        )

    return True, None
    
from pytgcalls import filters
@call.on_update(filters.stream_end())
async def handler(client: PyTgCalls, update: Update):
    chat_id = update.chat_id
    # Check if there's a queue for the current chat
    if chat_id in queues:
        # Remove the song that has ended from the queue
        queues[chat_id].popleft()
        
        # If there are still songs in the queue, play the next one
        if queues[chat_id]:
            next_song = queues[chat_id][0]
            stream_url = await get_stream_url(next_song)
            media_stream = MediaStream(stream_url, audio_parameters=AudioQuality.HIGH)

            # Play the next song
            await call.play(chat_id, media_stream)
            await client.send_message(chat_id, f"⏭️ Skipped to the next song: **{next_song}**")
        else:
            # If there are no songs left in the queue, leave the voice chat
            await call.leave_call(chat_id)
            await client.send_message(chat_id, "✅ Queue ended. Left VC.")
    else:
        # If no queue exists for the current chat, leave the voice chat
        await call.leave_call(chat_id)
        await client.send_message(chat_id, "✅ Queue ended. Left VC.")

from pyrogram import filters
@bot.on_message(filters.command("play") & filters.group)
async def play_handler(_, m):
    chat_id = m.chat.id
    query = " ".join(m.command[1:])
    if not query:
        return await m.reply("⚠️ Please provide a song name or URL.")

    msg = await m.reply("🔍 Fetching...")

    if chat_id not in queues:
        queues[chat_id] = deque()

    queues[chat_id].append(query)

    if len(queues[chat_id]) == 1:
        await play(bot, call, chat_id, query)
        await msg.edit(f"🎧 Now playing: **{query}**")
    else:
        await msg.edit(f"✅ Added to queue: **{query}**")

from pyrogram import filters
@bot.on_message(filters.command("skip") & filters.group)
async def skip_handler(_, m):
    chat_id = m.chat.id
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].popleft()
        if queues[chat_id]:
            next_song = queues[chat_id][0]
            await play(bot, call, chat_id, next_song)
            await m.reply(f"⏭️ Skipped. Now playing: **{next_song}**")
        else:
            await call.leave_call(chat_id)
            await m.reply("✅ Queue ended. Left VC.")
    else:
        await m.reply("❌ No song in queue.")

from pyrogram import filters
@bot.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, m):
    chat_id = m.chat.id
    if chat_id in queues and queues[chat_id]:
        text = "**🎶 Current Queue:**\n"
        for i, q in enumerate(queues[chat_id], 1):
            text += f"{i}. {q}\n"
        await m.reply(text)
    else:
        await m.reply("📭 Queue is empty.")

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
        
