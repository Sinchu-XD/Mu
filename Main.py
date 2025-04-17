import asyncio
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, Update
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

# Define your API keys and tokens
API_ID = 6067591
API_HASH = "94e17044c2393f43fda31d3afe77b26b"
BOT_TOKEN = "7913409153:AAEvv86Q96KqjU6-fvj_JOBKp4_MHH9H4Wk"
SESSION_STRING = "BQBclYcAfwPhsOaYEN9rZiJTeqV1e-mW90J3pxU5lU-HRDBDir4n236Uy6xowZLnSJ83DDyV-7m8NommEpFKXVZMwRR41bXxvE8JzhIcLIJnCP5yObgE3yRkljsE36qEsdVYTgggdMSHrhoFWZG5YuOIJ0hi1HpqzOJhocARqoVbys1-CNSjTAEXdNB3knhatAqkHVnHfWcgvtshc3iiru3Gjpl9lXaPnLL5p5GP11dL8vRS4Dob-8nZW2vEkXqsD4-Ce6BAD8m4RIqTsomtrQCgaH4ugYfpFuKVr_oz04hUTjB4MzXK-Wr_Fz5Lk42PnrE3wWEwhsfgOVu8AM02YlKLV77MegAAAAHKUdR6AA"

# Initialize the bot, assistant client, and call handler
bot = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("Assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call = PyTgCalls(assistant)

# Queue to hold songs
queues = {}

# Cache to store song URLs
cached_urls = {}

# YTMusic API instance
ytmusic = YTMusic()

# YouTubeDL options for extracting stream URLs
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

# Function to get stream URL for a song based on the query
async def get_stream_url(query: str):
    if query in cached_urls:
        return cached_urls[query]

    # Perform the search for the song using YTMusic API
    print(f"Searching for {query} on YTMusic...")
    search_results = ytmusic.search(query, filter="songs")
    if not search_results:
        raise Exception(f"Song '{query}' not found in YTMusic search!")

    result = search_results[0]
    video_id = result.get("videoId")
    if not video_id:
        raise Exception(f"Invalid video ID for song: {query}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"Found video URL: {url}")

    # Extract stream info using yt-dlp
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, lambda: YoutubeDL(YDL_OPTS).extract_info(url, download=False))
        if isinstance(data, dict) and "url" in data:
            stream_url = data["url"]
            cached_urls[query] = stream_url
            return stream_url
        else:
            raise Exception(f"Failed to extract stream URL for {query}. Data: {data}")
    except Exception as e:
        raise Exception(f"Error extracting stream URL for {query}: {str(e)}")

# Function to play a song (No message sending here)
async def play_song(chat_id: int, query: str):
    try:
        stream_url = await get_stream_url(query)

        # Create media stream and play the song
        media_stream = MediaStream(stream_url, audio_parameters=AudioQuality.HIGH)
        await call.play(chat_id, media_stream)

        # Add song to the queue
        queues.setdefault(chat_id, deque()).append(query)

    except Exception as e:
        # If any error occurs, log it
        print(f"Error: {str(e)}")

# Function to handle the queue end event (when the song finishes)
async def handle_queue_end(client: PyTgCalls, update: Update):
    chat_id = update.chat_id
    if chat_id in queues:
        queues[chat_id].popleft()
        if queues[chat_id]:
            next_song = queues[chat_id][0]
            await play_song(chat_id, next_song)
            await client.send_message(chat_id, f"⏭️ Skipped to the next song: **{next_song}**")
        else:
            await call.leave_call(chat_id)
            await client.send_message(chat_id, "✅ Queue ended. Left VC.")
    else:
        await call.leave_call(chat_id)
        await client.send_message(chat_id, "✅ Queue ended. Left VC.")

# Listen to stream end event from pytgcalls
from pytgcalls import filters
@call.on_update(filters.stream_end())
async def stream_end_handler(client: PyTgCalls, update: Update):
    await handle_queue_end(client, update)

# Command to play a song
from pyrogram import Client, filters
@bot.on_message(filters.command("play") & filters.group)
async def play_handler(_, m: Message):
    chat_id = m.chat.id
    query = " ".join(m.command[1:])

    if not query:
        return await m.reply("⚠️ Please provide a song name or URL.")

    # Add the song to the queue first
    queues.setdefault(chat_id, deque()).append(query)

    msg = await m.reply("🔍 Fetching...")

    # Check if it's the first song in the queue
    if len(queues[chat_id]) == 1:
        await play_song(chat_id, query)
        await msg.edit(f"🎧 Now playing: **{query}**")
    else:
        await msg.edit(f"✅ Added to queue: **{query}**")

# Command to skip a song
from pyrogram import Client, filters
@bot.on_message(filters.command("skip") & filters.group)
async def skip_handler(_, m: Message):
    chat_id = m.chat.id
    if chat_id in queues and queues[chat_id]:
        if len(queues[chat_id]) == 1:  # If there's only one song left in the queue
            await call.leave_call(chat_id)
            await m.reply("✅ Queue ended. Left VC.")
        else:
            queues[chat_id].popleft()
            if queues[chat_id]:
                next_song = queues[chat_id][0]
                await play_song(chat_id, next_song)
                await m.reply(f"⏭️ Skipped. Now playing: **{next_song}**")
    else:
        await m.reply("❌ No song in queue.")

# Command to show the queue
from pyrogram import Client, filters
@bot.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, m: Message):
    chat_id = m.chat.id
    if chat_id in queues and queues[chat_id]:
        text = "**🎶 Current Queue:**\n" + "\n".join([f"{i+1}. {q}" for i, q in enumerate(queues[chat_id])])
        await m.reply(text)
    else:
        await m.reply("📭 Queue is empty.")

# Main function to start the bot
async def main():
    await bot.start()
    await assistant.start()
    await call.start()
    print("✅ Music bot running.")
    await asyncio.get_event_loop().create_future()

# Start the bot
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
        
