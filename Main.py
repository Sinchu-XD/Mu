import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import AudioQuality
from yt_dlp import YoutubeDL
from random import shuffle

API_ID = 12345
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
SESSION_STRING = "your_user_session_string"

bot = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("Assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call = PyTgCalls(assistant)

queues = {}

async def get_youtube_audio(query: str):
    loop = asyncio.get_event_loop()
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
        'extract_flat': 'in_playlist',
        'forceurl': True,
        'cookiefile': 'cookies.txt',
    }

    def extract():
        with YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    info = await loop.run_in_executor(None, extract)

    if 'entries' in info:
        info = info['entries'][0]
    return {
        'title': info.get('title'),
        'url': info.get('url'),
        'webpage_url': info.get('webpage_url'),
    }


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
        media_stream = MediaStream(song['url'], quality=AudioQuality.HIGH)
        await call.play(chat_id, media_stream)
        await message.reply(f"▶️ Now playing: [{song['title']}]({song['webpage_url']})", disable_web_page_preview=True)
    else:
        await message.reply(f"📥 Added to queue: [{song['title']}]({song['webpage_url']})", disable_web_page_preview=True)


@bot.on_message(filters.command("skip") & filters.group)
async def skip_command(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        return await message.reply("❌ Nothing in queue to skip.")
    
    skipped = queues[chat_id].pop(0)

    if queues[chat_id]:
        next_song = queues[chat_id][0]
        media_stream = MediaStream(next_song['url'], quality=AudioQuality.HIGH)
        await call.play(chat_id, media_stream)
        await message.reply(f"⏭ Skipped. Now playing: [{next_song['title']}]({next_song['webpage_url']})", disable_web_page_preview=True)
    else:
        # Auto-play related song if available
        try:
            related = await get_youtube_audio(skipped['title'])
            queues[chat_id].append(related)
            media_stream = MediaStream(related['url'], quality=AudioQuality.HIGH)
            await call.play(chat_id, media_stream)
            await message.reply(f"🔁 Auto-playing related song: [{related['title']}]({related['webpage_url']})", disable_web_page_preview=True)
        except Exception as e:
            await call.leave_call(chat_id)
            queues.pop(chat_id, None)
            await message.reply("⏹ Queue empty. Stopped playback.")


@bot.on_message(filters.command("pause") & filters.group)
async def pause_command(_, message: Message):
    await call.pause(message.chat.id)
    await message.reply("⏸ Music paused.")


@bot.on_message(filters.command("resume") & filters.group)
async def resume_command(_, message: Message):
    await call.resume(message.chat.id)
    await message.reply("▶️ Music resumed.")


@bot.on_message(filters.command("stop") & filters.group)
async def stop_command(_, message: Message):
    chat_id = message.chat.id
    await call.leave_call(chat_id)
    queues.pop(chat_id, None)
    await message.reply("⏹ Stopped playback and cleared queue.")


@bot.on_message(filters.command("queue") & filters.group)
async def show_queue(_, message: Message):
    chat_id = message.chat.id
    if chat_id not in queues or not queues[chat_id]:
        return await message.reply("📭 Queue is empty.")
    
    text = "🎶 **Current Queue:**\n"
    for i, song in enumerate(queues[chat_id], 1):
        text += f"{i}. [{song['title']}]({song['webpage_url']})\n"
    await message.reply(text, disable_web_page_preview=True)


@bot.on_message(filters.command("clear") & filters.group)
async def clear_queue(_, message: Message):
    chat_id = message.chat.id
    queues.pop(chat_id, None)
    await call.leave_call(chat_id)
    await message.reply("🗑 Queue cleared and left voice chat.")


@bot.on_message(filters.command("shuffle") & filters.group)
async def shuffle_queue(_, message: Message):
    chat_id = message.chat.id
    if chat_id in queues and len(queues[chat_id]) > 1:
        current = queues[chat_id][0]
        rest = queues[chat_id][1:]
        shuffle(rest)
        queues[chat_id] = [current] + rest
        await message.reply("🔀 Queue shuffled.")
    else:
        await message.reply("❌ Not enough songs to shuffle.")


@bot.on_message(filters.command("remove") & filters.group)
async def remove_from_queue(_, message: Message):
    chat_id = message.chat.id
    if len(message.command) < 2:
        return await message.reply("❌ Usage: `/remove [index]`")
    try:
        index = int(message.command[1]) - 1
        if chat_id not in queues or index < 1 or index >= len(queues[chat_id]):
            return await message.reply("❌ Invalid index.")
        removed = queues[chat_id].pop(index)
        await message.reply(f"🗑 Removed: **{removed['title']}**")
    except Exception:
        await message.reply("❌ Invalid index or error removing.")


async def start_bot():
    await bot.start()
    await assistant.start()
    await call.start()
    print("✅ Music bot running with assistant.")
    await asyncio.get_event_loop().create_future()


if __name__ == "__main__":
    asyncio.run(start_bot())
  
