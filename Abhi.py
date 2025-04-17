import asyncio
from pyrogram import Client, filters
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream, AudioQuality
from ytmusicapi import YTMusic
from yt_dlp import YoutubeDL
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_ID = 6067591  # Your API ID
API_HASH = "94e17044c2393f43fda31d3afe77b26b"  # Your API Hash
BOT_TOKEN = "7913409153:AAEvv86Q96KqjU6-fvj_JOBKp4_MHH9H4Wk"  # Your Bot Token
SESSION_STRING = "BQBclYcAfwPhsOaYEN9rZiJTeqV1e-mW90J3pxU5lU-HRDBDir4n236Uy6xowZLnSJ83DDyV-7m8NommEpFKXVZMwRR41bXxvE8JzhIcLIJnCP5yObgE3yRkljsE36qEsdVYTgggdMSHrhoFWZG5YuOIJ0hi1HpqzOJhocARqoVbys1-CNSjTAEXdNB3knhatAqkHVnHfWcgvtshc3iiru3Gjpl9lXaPnLL5p5GP11dL8vRS4Dob-8nZW2vEkXqsD4-Ce6BAD8m4RIqTsomtrQCgaH4ugYfpFuKVr_oz04hUTjB4MzXK-Wr_Fz5Lk42PnrE3wWEwhsfgOVu8AM02YlKLV77MegAAAAHKUdR6AA"  # Session String for Assistant

# Initialize bot and assistant clients
bot = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("Assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

# Initialize PyTgCalls with assistant client
call = PyTgCalls(assistant)
ytmusic = YTMusic()

# Store user-specific data (e.g., song requests) in a dictionary
user_data = {}

# Function to search YouTube Music and get best audio stream URL along with metadata
async def get_audio_url(query: str):
    search_results = ytmusic.search(query, filter="songs")
    if not search_results:
        return None

    video_id = search_results[0].get("videoId")
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "cookiefile": "cookies/cookies.txt",
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "url": info["url"],
            "title": info["title"],
            "duration": info["duration"],  # Duration in seconds
            "uploader": info["uploader"],  # Artist/Author Name
            "thumbnail": info["thumbnail"],  # Thumbnail URL
        }

# Add user to the data dictionary
def add_user_to_data(user_id: int, song_title: str):
    if user_id not in user_data:
        user_data[user_id] = {"songs_requested": []}
    user_data[user_id]["songs_requested"].append(song_title)

@bot.on_message(filters.command("play") & filters.group)
async def play_handler(_, message):
    chat_id = message.chat.id
    query = " ".join(message.command[1:])

    if not query:
        return await message.reply("❗ Please provide a song name.\nExample: `/play Faded`", quote=True)

    msg = await message.reply("🔍 Searching for the song...")

    try:
        # Check if the assistant (bot) is in a VC before playing a song
        song_info = await get_audio_url(query)
        if not song_info:
            return await msg.edit("❌ No results found.")

        # Fetching details
        audio_url = song_info["url"]
        song_title = song_info["title"]
        song_duration = song_info["duration"]
        song_uploader = song_info["uploader"]
        song_thumbnail = song_info["thumbnail"]

        # Formatting the song duration (in seconds)
        minutes = song_duration // 60
        seconds = song_duration % 60
        formatted_duration = f"{minutes:02}:{seconds:02}"

        # Prepare the message with song details
        requested_by = message.from_user.mention
        user_id = message.from_user.id

        # Add song to user's requested songs
        add_user_to_data(user_id, song_title)

        await msg.edit(
            f"🎧 **Now Streaming**:\n"
            f"**Title**: {song_title}\n"
            f"**Artist**: {song_uploader}\n"
            f"**Duration**: {formatted_duration}\n"
            f"**Requested By**: {requested_by}\n"
            f"[Listen Now]({audio_url})"
        )

        # Play the song using `call.play()`
        media_stream = MediaStream(
            audio_url,
            audio_parameters=AudioQuality.HIGH
        )
        await call.play(chat_id, media_stream)

        # Optionally send thumbnail
        await bot.send_photo(chat_id, song_thumbnail, caption="Now Playing!")

    except Exception as e:
        await msg.edit(f"❌ Error:\n`{e}`")


@bot.on_message(filters.command("stop") & filters.group)
async def stop_handler(_, message):
    chat_id = message.chat.id

    try:
        # Leave the call using `call.leave_call()`
        await call.leave_call(chat_id)
        await message.reply("⛔️ Stopped streaming.")
    except Exception as e:
        await message.reply(f"❌ Error:\n`{e}`")


@bot.on_message(filters.command("nowplaying") & filters.group)
async def now_playing_handler(_, message):
    chat_id = message.chat.id
    # For simplicity, we assume that the bot is currently playing something
    # Ideally, you would keep track of this in a database or variable
    
    # Example of song info, you could fetch this dynamically or track current playing
    current_song = {
        "title": "Faded",
        "artist": "Alan Walker",
        "duration": "03:32",
        "requested_by": message.from_user.mention,
    }

    await message.reply(
        f"🎧 **Currently Playing**:\n"
        f"**Title**: {current_song['title']}\n"
        f"**Artist**: {current_song['artist']}\n"
        f"**Duration**: {current_song['duration']}\n"
        f"**Requested By**: {current_song['requested_by']}\n"
        f"Use `/stop` to stop the stream."
    )


@bot.on_message(filters.command("queue") & filters.group)
async def queue_handler(_, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["songs_requested"]:
        return await message.reply("🔹 You haven't requested any songs yet.")

    queue_list = "\n".join([f"{i+1}. {song}" for i, song in enumerate(user_data[user_id]["songs_requested"])])
    await message.reply(f"🔹 **Your Requested Songs Queue**:\n{queue_list}")


@bot.on_message(filters.command("help") & filters.group)
async def help_handler(_, message):
    help_text = (
        "ℹ️ **Commands**:\n"
        "/play [song name] - Search and play a song.\n"
        "/stop - Stop the current stream.\n"
        "/nowplaying - Shows current song info.\n"
        "/queue - View your song request queue.\n"
        "/help - Displays this help message."
    )
    await message.reply(help_text)


async def main():
    await bot.start()
    await assistant.start()
    await call.start()
    print("Bot & Voice Chat Client started.")
    await idle()  # Keeps the program running
    await bot.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
  
