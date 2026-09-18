import asyncio
import os
import logging
import random
import aiosqlite
import urllib.request
import urllib.parse
import json
import base64
import time
import re
from pyrogram import Client, filters, idle
from pyrogram.types import LinkPreviewOptions
from pytgcalls import PyTgCalls
from pytgcalls import filters as call_filters
from pytgcalls.types import MediaStream, AudioQuality
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pytgcalls").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

_0x_log = logging.getLogger("Userbot")
_0x_log.setLevel(logging.INFO)

_0x_dir = os.path.dirname(os.path.abspath(__file__))
_0x_env = os.path.join(_0x_dir, ".env")
load_dotenv(dotenv_path=_0x_env)

_0x_a = int(os.getenv("API_ID", 0))
_0x_b = os.getenv("API_HASH", "")
_0x_c = os.getenv("SESSION_STRING", os.getenv("STRING_SESSION", ""))
_0x_d = int(os.getenv("OWNER_ID", 0))
_0x_e = os.getenv("PREFIX", ".")

_0x_f = os.getenv("SPOTIFY_CLIENT_ID", "")
_0x_g = os.getenv("SPOTIFY_CLIENT_SECRET", "")

if not _0x_a or not _0x_b or not _0x_c or not _0x_d:
    _0x_log.error("Missing configuration in .env file.")
    exit(1)

_0x_app = Client(
    "music_userbot",
    api_id=_0x_a,
    api_hash=_0x_b,
    session_string=_0x_c
)

_0x_call = PyTgCalls(_0x_app)

_0x_db = os.path.join(_0x_dir, "database.db")

async def _0x_db_init():
    async with aiosqlite.connect(_0x_db) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS sudoers (
                user_id INTEGER PRIMARY KEY
            )
            """
        )
        await db.commit()

async def _0x_db_add(user_id: int):
    async with aiosqlite.connect(_0x_db) as db:
        await db.execute("INSERT OR IGNORE INTO sudoers (user_id) VALUES (?)", (user_id,))
        await db.commit()

async def _0x_db_del(user_id: int):
    async with aiosqlite.connect(_0x_db) as db:
        await db.execute("DELETE FROM sudoers WHERE user_id = ?", (user_id,))
        await db.commit()

async def _0x_db_list() -> list:
    async with aiosqlite.connect(_0x_db) as db:
        async with db.execute("SELECT user_id FROM sudoers") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def _0x_check_sudo(user_id: int) -> bool:
    if user_id == _0x_d:
        return True
    sudoers = await _0x_db_list()
    return user_id in sudoers

async def _0x_filter_func(_, __, message):
    if not message.from_user:
        return False
    return await _0x_check_sudo(message.from_user.id)

_0x_sudo = filters.create(_0x_filter_func)

_0x_q_dict = {}
_0x_curr_dict = {}
_0x_loop_dict = {}
_0x_msg_dict = {}

def _0x_q_add(chat_id: int, song_dict: dict):
    if chat_id not in _0x_q_dict:
        _0x_q_dict[chat_id] = []
    _0x_q_dict[chat_id].append(song_dict)

def _0x_q_get(chat_id: int) -> list:
    return _0x_q_dict.get(chat_id, [])

def _0x_q_pop(chat_id: int) -> dict | None:
    if chat_id in _0x_q_dict and len(_0x_q_dict[chat_id]) > 0:
        return _0x_q_dict[chat_id].pop(0)
    return None

def _0x_q_clear(chat_id: int):
    if chat_id in _0x_q_dict:
        _0x_q_dict[chat_id] = []
    if chat_id in _0x_curr_dict:
        _0x_curr_dict[chat_id] = None

def _0x_q_remove(chat_id: int, index: int) -> bool:
    if chat_id in _0x_q_dict and 0 <= index < len(_0x_q_dict[chat_id]):
        _0x_q_dict[chat_id].pop(index)
        return True
    return False

def _0x_q_set_curr(chat_id: int, song_dict: dict | None):
    _0x_curr_dict[chat_id] = song_dict

def _0x_q_get_curr(chat_id: int) -> dict | None:
    return _0x_curr_dict.get(chat_id)

def _0x_q_set_loop(chat_id: int, enable: bool):
    _0x_loop_dict[chat_id] = enable

def _0x_q_get_loop(chat_id: int) -> bool:
    return _0x_loop_dict.get(chat_id, False)

def _0x_q_shuffle(chat_id: int) -> bool:
    if chat_id in _0x_q_dict and len(_0x_q_dict[chat_id]) > 1:
        random.shuffle(_0x_q_dict[chat_id])
        return True
    return False

def _0x_fmt_dur(seconds) -> str:
    if seconds is None or seconds == 0:
        return "Live Stream"
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "Live Stream"
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

async def _0x_del_prev(chat_id: int):
    old_msg_id = _0x_msg_dict.get(chat_id)
    if old_msg_id:
        try:
            await _0x_app.delete_messages(chat_id, old_msg_id)
        except Exception:
            pass
        _0x_msg_dict[chat_id] = None

_0x_s_tk = {
    "token": "",
    "expires_at": 0
}

def _0x_s_pr(url: str) -> tuple[str, str] | None:
    pattern = r"spotify\.com/(track|playlist|album)/([a-zA-Z0-9]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1), match.group(2)
    uri_pattern = r"spotify:(track|playlist|album):([a-zA-Z0-9]+)"
    match = re.search(uri_pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None

async def _0x_s_gt() -> str | None:
    global _0x_s_tk
    if not _0x_f or not _0x_g:
        return None
    if _0x_s_tk["token"] and time.time() < _0x_s_tk["expires_at"]:
        return _0x_s_tk["token"]
    def _fetch():
        try:
            auth_str = f"{_0x_f}:{_0x_g}"
            auth_base64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            req = urllib.request.Request(
                "https://accounts.spotify.com/api/token",
                data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode('utf-8'),
                headers={
                    "Authorization": f"Basic {auth_base64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as res:
                data = json.loads(res.read().decode('utf-8'))
                access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                if access_token:
                    _0x_s_tk["token"] = access_token
                    _0x_s_tk["expires_at"] = time.time() + expires_in - 60
                    return access_token
        except Exception as e:
            _0x_log.error(f"Spotify token extraction failed: {e}")
        return None
    return await asyncio.to_thread(_fetch)

async def _0x_s_ft(spotify_type: str, spotify_id: str) -> list[dict]:
    token = await _0x_s_gt()
    if not token:
        return []
    def _fetch():
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0"
        }
        try:
            if spotify_type == "track":
                url = f"https://api.spotify.com/v1/tracks/{spotify_id}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as res:
                    track = json.loads(res.read().decode('utf-8'))
                    artists = ", ".join([a["name"] for a in track["artists"]])
                    return [{
                        "title": track["name"],
                        "artist": artists,
                        "query": f"{track['name']} {artists}",
                        "duration": int(track["duration_ms"] / 1000),
                        "webpage_url": track["external_urls"].get("spotify", "")
                    }]
            elif spotify_type == "playlist":
                tracks = []
                url = f"https://api.spotify.com/v1/playlists/{spotify_id}/tracks?limit=100"
                while url:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as res:
                        data = json.loads(res.read().decode('utf-8'))
                        for item in data.get("items", []):
                            track = item.get("track")
                            if not track:
                                continue
                            artists = ", ".join([a["name"] for a in track["artists"]])
                            tracks.append({
                                "title": track["name"],
                                "artist": artists,
                                "query": f"{track['name']} {artists}",
                                "duration": int(track["duration_ms"] / 1000),
                                "webpage_url": track["external_urls"].get("spotify", "")
                            })
                        url = data.get("next")
                return tracks
            elif spotify_type == "album":
                tracks = []
                url = f"https://api.spotify.com/v1/albums/{spotify_id}/tracks?limit=50"
                while url:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as res:
                        data = json.loads(res.read().decode('utf-8'))
                        for track in data.get("items", []):
                            artists = ", ".join([a["name"] for a in track["artists"]])
                            tracks.append({
                                "title": track["name"],
                                "artist": artists,
                                "query": f"{track['name']} {artists}",
                                "duration": int(track["duration_ms"] / 1000),
                                "webpage_url": track["external_urls"].get("spotify", "")
                            })
                        url = data.get("next")
                return tracks
        except Exception as e:
            _0x_log.error(f"Spotify details extraction failed: {e}")
        return []
    return await asyncio.to_thread(_fetch)

async def _0x_s_lp(client, message, url: str) -> list[dict]:
    for _ in range(4):
        try:
            msg = await client.get_messages(message.chat.id, message.id)
            if msg and msg.web_page:
                web = msg.web_page
                if "spotify" in web.url.lower():
                    title = web.title
                    desc = web.description
                    if title:
                        artist = "Unknown Artist"
                        if desc:
                            clean_desc = desc.replace("Listen to", "").replace("on Spotify.", "").strip()
                            if " - song by " in clean_desc:
                                artist = clean_desc.split(" - song by ")[0].strip()
                            elif " · Song · " in clean_desc:
                                artist = clean_desc.split(" · Song · ")[0].strip()
                            else:
                                parts = clean_desc.split("·")
                                if parts:
                                    artist = parts[0].strip()
                                    if title.lower() in artist.lower() and len(parts) > 1:
                                        artist = parts[1].strip()
                        return [{
                            "title": title,
                            "artist": artist,
                            "query": f"{title} {artist}",
                            "duration": 0,
                            "webpage_url": url
                        }]
                break
        except Exception:
            pass
        await asyncio.sleep(1)
    return []

class _0x_NullLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

_0x_ck = os.path.join(_0x_dir, "cookies.txt")

async def _0x_search(query: str):
    def _extract():
        is_link = query.startswith("http://") or query.startswith("https://")
        video_urls = [query] if is_link else []
        
        if not is_link:
            # 1. Primary Method: Direct YouTube HTML Scraping
            try:
                search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
                req = urllib.request.Request(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    }
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', html)
                    if ids:
                        seen = set()
                        unique_ids = [x for x in ids if not (x in seen or seen.add(x))]
                        for vid in unique_ids[:5]:
                            video_urls.append(f"https://www.youtube.com/watch?v={vid}")
            except Exception as e:
                _0x_log.error(f"HTML search error: {e}")

            # 2. Secondary Method: Public Invidious / Piped search fallback if HTML blocked
            if not video_urls:
                for invidious in ["https://inv.nadeko.net/api/v1/search?q=", "https://invidious.nerdvpn.de/api/v1/search?q="]:
                    try:
                        inv_req = urllib.request.Request(
                            f"{invidious}{urllib.parse.quote(query)}&type=video",
                            headers={"User-Agent": "Mozilla/5.0"}
                        )
                        with urllib.request.urlopen(inv_req, timeout=5) as inv_resp:
                            data = json.loads(inv_resp.read().decode("utf-8"))
                            for item in data[:3]:
                                if "videoId" in item:
                                    video_urls.append(f"https://www.youtube.com/watch?v={item['videoId']}")
                        if video_urls:
                            break
                    except Exception:
                        pass

        if not video_urls:
            video_urls = [f"ytsearch1:{query}"]

        has_cookie = os.path.exists(_0x_ck) and os.path.getsize(_0x_ck) > 20
        
        def _get_opts(use_cookie=False, clients=None):
            if clients is None:
                clients = ['android', 'ios']
            opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/18/22/best',
                'noplaylist': True,
                'nocheckcertificate': True,
                'ignoreerrors': True,
                'quiet': True,
                'no_warnings': True,
                'logger': _0x_NullLogger(),
                'source_address': '0.0.0.0',
                'extractor_args': {
                    'youtube': {
                        'player_client': clients
                    }
                }
            }
            if use_cookie and has_cookie:
                opts['cookiefile'] = _0x_ck
            return opts
            
        def _resolve_result(res, opts):
            if not res:
                return None
            stream_url = res.get('url')
            if not stream_url and 'formats' in res and res['formats']:
                audio_formats = [
                    f for f in res['formats']
                    if f.get('url') and f.get('acodec') != 'none' and (f.get('vcodec') == 'none' or not f.get('vcodec'))
                ]
                if audio_formats:
                    stream_url = audio_formats[-1]['url']
                else:
                    valid_formats = [f for f in res['formats'] if f.get('url')]
                    if valid_formats:
                        stream_url = valid_formats[-1]['url']
            
            if not stream_url and res.get('webpage_url'):
                try:
                    with YoutubeDL(opts) as ydl_inner:
                        single_info = ydl_inner.extract_info(res['webpage_url'], download=False)
                        if single_info:
                            stream_url = single_info.get('url')
                            if not stream_url and 'formats' in single_info:
                                valid_formats = [f for f in single_info['formats'] if f.get('url')]
                                if valid_formats:
                                    stream_url = valid_formats[-1]['url']
                except Exception:
                    pass

            return {
                'title': res.get('title', 'Unknown Title'),
                'duration': res.get('duration', 0),
                'url': res.get('webpage_url') or res.get('url') or query,
                'stream_url': stream_url,
                'uploader': res.get('uploader') or res.get('artist') or 'Unknown Artist'
            }

        attempts = [
            (False, ['android', 'ios']),
            (False, ['android']),
            (False, ['web', 'android'])
        ]
        if has_cookie:
            attempts.append((True, ['android', 'ios']))

        for target_url in video_urls:
            for use_ck, clients in attempts:
                opts = _get_opts(use_cookie=use_ck, clients=clients)
                try:
                    with YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(target_url, download=False)
                        if info:
                            if 'entries' in info and info['entries']:
                                parsed = _resolve_result(info['entries'][0], opts)
                                if parsed and parsed.get('stream_url'):
                                    return parsed
                            elif 'entries' not in info:
                                parsed = _resolve_result(info, opts)
                                if parsed and parsed.get('stream_url'):
                                    return parsed
                except Exception as e:
                    _0x_log.error(f"Search extract error for {target_url}: {e}")

        return None

    return await asyncio.to_thread(_extract)

async def _0x_stream(chat_id: int, song_dict: dict) -> bool:
    try:
        flags = getattr(MediaStream.Flags, "IGNORE", 0) if hasattr(MediaStream, "Flags") else 0
        stream_kwargs = {
            "audio_parameters": AudioQuality.HIGH,
            "ffmpeg_parameters": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -vn"
        }
        if flags:
            stream_kwargs["video_flags"] = flags

        try:
            await _0x_call.play(chat_id, MediaStream(song_dict['stream_url'], **stream_kwargs))
        except TypeError:
            await _0x_call.play(
                chat_id,
                MediaStream(
                    song_dict['stream_url'],
                    audio_parameters=AudioQuality.HIGH
                )
            )
        _0x_q_set_curr(chat_id, song_dict)
        return True
    except Exception as e:
        _0x_log.error(f"Playback error for {chat_id}: {e}", exc_info=True)
        return False

async def _0x_next(chat_id: int):
    if _0x_q_get_loop(chat_id):
        current = _0x_q_get_curr(chat_id)
        if current:
            resolved = await _0x_search(current['query'])
            if resolved:
                current['stream_url'] = resolved['stream_url']
                success = await _0x_stream(chat_id, current)
                if success:
                    return
    next_song = _0x_q_pop(chat_id)
    if next_song:
        resolved = await _0x_search(next_song['query'])
        if not resolved:
            try:
                await _0x_app.send_message(chat_id, f"❌ Failed to resolve **{next_song['title']}**.")
            except Exception:
                pass
            await _0x_next(chat_id)
            return
        next_song['stream_url'] = resolved['stream_url']
        next_song['duration'] = resolved['duration']
        next_song['webpage_url'] = resolved['url']
        
        await _0x_del_prev(chat_id)
        
        success = await _0x_stream(chat_id, next_song)
        if not success:
            try:
                await _0x_app.send_message(chat_id, f"❌ Streaming error **{next_song['title']}**.")
            except Exception:
                pass
            await _0x_next(chat_id)
            return
        try:
            duration = _0x_fmt_dur(next_song['duration'])
            caption = f"**🎵 Now Playing**\n\n"
            caption += f"**Song:** [{next_song['title']}]({next_song['webpage_url']})\n"
            caption += f"**Artist:** {next_song['artist']}\n"
            caption += f"**Duration:** {duration}\n"
            caption += f"**Requested by:** {next_song['requester']}"
            sent_msg = await _0x_app.send_message(chat_id, caption, link_preview_options=LinkPreviewOptions(is_disabled=True))
            _0x_msg_dict[chat_id] = sent_msg.id
        except Exception as e:
            _0x_log.error(f"Playing announce error: {e}")
    else:
        _0x_q_set_curr(chat_id, None)
        try:
            await _0x_call.leave_call(chat_id)
        except Exception:
            pass
        await _0x_del_prev(chat_id)
        try:
            sent_msg = await _0x_app.send_message(chat_id, "⏹ Queue is empty. Left voice chat.")
            await asyncio.sleep(8)
            await sent_msg.delete()
        except Exception:
            pass

@_0x_call.on_update(call_filters.stream_end())
async def _0x_end_h(client, update):
    chat_id = update.chat_id
    await _0x_next(chat_id)

async def _0x_start(chat_id: int, song_dict: dict):
    queue = _0x_q_get(chat_id)
    current = _0x_q_get_curr(chat_id)
    if not current and not queue:
        if not song_dict['stream_url']:
            resolved = await _0x_search(song_dict['query'])
            if not resolved:
                return -1
            song_dict['stream_url'] = resolved['stream_url']
            song_dict['duration'] = resolved['duration']
            song_dict['webpage_url'] = resolved['url']
            song_dict['title'] = resolved['title']
            song_dict['artist'] = resolved['uploader']
        
        await _0x_del_prev(chat_id)
        
        success = await _0x_stream(chat_id, song_dict)
        if success:
            return 1
        else:
            return -2
    else:
        _0x_q_add(chat_id, song_dict)
        return 0

async def _0x_get_user_id(client, message) -> int | None:
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    if len(message.command) < 2:
        return None
    arg = message.command[-1]
    if arg.isdigit() or (arg.startswith("-") and arg[1:].isdigit()):
        return int(arg)
    if arg.startswith("@"):
        arg = arg[1:]
    try:
        user = await client.get_users(arg)
        return user.id
    except Exception:
        return None


# ----------------- USERBOT COMMAND HANDLERS -----------------

@_0x_app.on_message(filters.command(["play", "p"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_play(client, message):
    if len(message.command) < 2:
        try:
            await _0x_app.send_message(message.chat.id, f"Usage: `{_0x_e}play <song>` or `{_0x_e}p <song>`")
        except Exception:
            pass
        return
        
    query = " ".join(message.command[1:])
    status_msg = None
    try:
        status_msg = await _0x_app.send_message(message.chat.id, "🔎 Searching...")
    except Exception:
        pass
    
    spotify_info = _0x_s_pr(query)
    if spotify_info:
        s_type, s_id = spotify_info
        tracks = []
        if _0x_f and _0x_g:
            if status_msg:
                try:
                    await status_msg.edit_text(f"🚀 Fetching Spotify {s_type} details...")
                except Exception:
                    pass
            tracks = await _0x_s_ft(s_type, s_id)
        if not tracks and s_type == "track":
            if status_msg:
                try:
                    await status_msg.edit_text("⏳ Waiting for Telegram link preview...")
                except Exception:
                    pass
            tracks = await _0x_s_lp(client, message, query)
        if not tracks:
            if not _0x_f or not _0x_g:
                try:
                    await _0x_app.send_message(
                        message.chat.id,
                        "⚠️ Spotify API is not configured.\n"
                        "Note: Single tracks work automatically once Telegram displays link preview."
                    )
                except Exception:
                    pass
            else:
                try:
                    await _0x_app.send_message(message.chat.id, "❌ Failed to fetch Spotify metadata.")
                except Exception:
                    pass
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            return
            
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
        requester = message.from_user.first_name if message.from_user else "Unknown"
        
        if len(tracks) > 1:
            added_count = 0
            for t in tracks:
                song_dict = {
                    'title': t['title'],
                    'artist': t['artist'],
                    'query': t['query'],
                    'duration': t['duration'],
                    'webpage_url': t['webpage_url'],
                    'requester': requester,
                    'source': 'spotify',
                    'stream_url': None
                }
                await _0x_start(message.chat.id, song_dict)
                added_count += 1
            try:
                await _0x_app.send_message(message.chat.id, f"🎵 Added **{added_count}** tracks from Spotify to the queue.")
            except Exception:
                pass
        else:
            t = tracks[0]
            song_dict = {
                'title': t['title'],
                'artist': t['artist'],
                'query': t['query'],
                'duration': t['duration'],
                'webpage_url': t['webpage_url'],
                'requester': requester,
                'source': 'spotify',
                'stream_url': None
            }
            status = await _0x_start(message.chat.id, song_dict)
            if status == 1:
                duration = _0x_fmt_dur(t['duration'])
                caption = f"**🎵 Now Playing**\n\n"
                caption += f"**Song:** [{t['title']}]({t['webpage_url']})\n"
                caption += f"**Artist:** {t['artist']}\n"
                caption += f"**Duration:** {duration}\n"
                caption += f"**Requested by:** {requester}"
                sent_msg = await _0x_app.send_message(message.chat.id, caption, link_preview_options=LinkPreviewOptions(is_disabled=True))
                _0x_msg_dict[message.chat.id] = sent_msg.id
            elif status == 0:
                try:
                    await _0x_app.send_message(message.chat.id, f"➕ **Added to Queue:** {t['title']}")
                except Exception:
                    pass
        return
        
    song_info = await _0x_search(query)
    if not song_info:
        try:
            await _0x_app.send_message(message.chat.id, "❌ Failed to find song.")
        except Exception:
            pass
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
        return
        
    requester = message.from_user.first_name if message.from_user else "Unknown"
    duration = _0x_fmt_dur(song_info['duration'])
    
    song_dict = {
        'title': song_info['title'],
        'artist': song_info['uploader'],
        'query': song_info['url'],
        'webpage_url': song_info['url'],
        'duration': song_info['duration'],
        'requester': requester,
        'source': 'youtube',
        'stream_url': song_info['stream_url']
    }
    
    status = await _0x_start(message.chat.id, song_dict)
    if status == 1:
        caption = f"**🎵 Now Playing**\n\n"
        caption += f"**Song:** [{song_info['title']}]({song_info['url']})\n"
        caption += f"**Artist:** {song_info['uploader']}\n"
        caption += f"**Duration:** {duration}\n"
        caption += f"**Requested by:** {requester}"
        sent_msg = await _0x_app.send_message(message.chat.id, caption, link_preview_options=LinkPreviewOptions(is_disabled=True))
        _0x_msg_dict[message.chat.id] = sent_msg.id
    elif status == 0:
        try:
            await _0x_app.send_message(message.chat.id, f"➕ **Added to Queue:** {song_info['title']}")
        except Exception:
            pass
            
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

@_0x_app.on_message(filters.command(["skip", "s", "next"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_skip(client, message):
    chat_id = message.chat.id
    if chat_id not in (await _0x_call.calls):
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    _0x_q_set_loop(chat_id, False)
    status = None
    try:
        status = await _0x_app.send_message(chat_id, "⏭ **Skipping...**")
    except Exception:
        pass
    await _0x_next(chat_id)
    await asyncio.sleep(3)
    if status:
        try:
            await status.delete()
        except Exception:
            pass

@_0x_app.on_message(filters.command(["pause", "ps"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_pause(client, message):
    chat_id = message.chat.id
    if chat_id in (await _0x_call.calls):
        await _0x_call.pause(chat_id)
        try:
            await _0x_app.send_message(chat_id, "⏸ **Stream paused.**")
        except Exception:
            pass
    else:
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass

@_0x_app.on_message(filters.command(["resume", "r"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_resume(client, message):
    chat_id = message.chat.id
    if chat_id in (await _0x_call.calls):
        await _0x_call.resume(chat_id)
        try:
            await _0x_app.send_message(chat_id, "▶️ **Stream resumed.**")
        except Exception:
            pass
    else:
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass

@_0x_app.on_message(filters.command(["stop", "st", "end"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_stop(client, message):
    chat_id = message.chat.id
    if chat_id in (await _0x_call.calls):
        _0x_q_clear(chat_id)
        _0x_q_set_loop(chat_id, False)
        try:
            await _0x_call.leave_call(chat_id)
        except Exception:
            pass
        await _0x_del_prev(chat_id)
        try:
            await _0x_app.send_message(chat_id, "⏹ **Stream stopped and queue cleared.**")
        except Exception:
            pass
    else:
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass

@_0x_app.on_message(filters.command(["queue", "q"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_queue(client, message):
    chat_id = message.chat.id
    queue = _0x_q_get(chat_id)
    current = _0x_q_get_curr(chat_id)
    text = ""
    if current:
        text += f"**🎧 Now Playing:** [{current['title']}]({current['webpage_url']}) (Requested by: {current['requester']})\n\n"
    if not queue:
        if current:
            text += "No upcoming songs in queue."
        else:
            text = "The queue is empty."
        try:
            await _0x_app.send_message(chat_id, text, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception:
            pass
        return
    text += f"**📋 Current Queue ({len(queue)} songs):**\n"
    for i, song in enumerate(queue[:15]):
        text += f"**{i + 1}.** [{song['title']}]({song['webpage_url']}) | *{song['artist']}* (Requested by: {song['requester']})\n"
    if len(queue) > 15:
        text += f"\n... and **{len(queue) - 15}** more songs."
    try:
        await _0x_app.send_message(chat_id, text, link_preview_options=LinkPreviewOptions(is_disabled=True))
    except Exception:
        pass

@_0x_app.on_message(filters.command(["current", "c"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_current(client, message):
    chat_id = message.chat.id
    current = _0x_q_get_curr(chat_id)
    if not current:
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    text = f"**🎧 Currently Playing:**\n\n"
    text += f"**Title:** {current['title']}\n"
    text += f"**Artist:** {current['artist']}\n"
    if current.get('duration'):
        text += f"**Duration:** {_0x_fmt_dur(current['duration'])}\n"
    text += f"**Requested by:** {current['requester']}\n"
    text += f"**Link:** [Click Here]({current['webpage_url']})"
    try:
        await _0x_app.send_message(chat_id, text, link_preview_options=LinkPreviewOptions(is_disabled=True))
    except Exception:
        pass

@_0x_app.on_message(filters.command(["volume", "vol"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_volume(client, message):
    chat_id = message.chat.id
    if chat_id not in (await _0x_call.calls):
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    if len(message.command) < 2:
        try:
            await _0x_app.send_message(chat_id, f"Usage: `{_0x_e}volume <1-200>`")
        except Exception:
            pass
        return
    try:
        vol = int(message.command[1])
    except ValueError:
        try:
            await _0x_app.send_message(chat_id, "Enter a number between 1 and 200.")
        except Exception:
            pass
        return
    if vol < 1 or vol > 200:
        try:
            await _0x_app.send_message(chat_id, "Volume must be between 1 and 200.")
        except Exception:
            pass
        return
    try:
        await _0x_call.change_volume_call(chat_id, vol)
        await _0x_app.send_message(chat_id, f"🔊 **Volume set to {vol}%**")
    except Exception as e:
        try:
            await _0x_app.send_message(chat_id, f"Failed to change volume: {e}")
        except Exception:
            pass

@_0x_app.on_message(filters.command("mute", prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_mute(client, message):
    chat_id = message.chat.id
    if chat_id not in (await _0x_call.calls):
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    try:
        await _0x_call.mute(chat_id)
        await _0x_app.send_message(chat_id, "🔇 **Stream muted.**")
    except Exception as e:
        try:
            await _0x_app.send_message(chat_id, f"Failed to mute: {e}")
        except Exception:
            pass

@_0x_app.on_message(filters.command("unmute", prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_unmute(client, message):
    chat_id = message.chat.id
    if chat_id not in (await _0x_call.calls):
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    try:
        await _0x_call.unmute(chat_id)
        await _0x_app.send_message(chat_id, "🔊 **Stream unmuted.**")
    except Exception as e:
        try:
            await _0x_app.send_message(chat_id, f"Failed to unmute: {e}")
        except Exception:
            pass

@_0x_app.on_message(filters.command(["loop", "l"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_loop(client, message):
    chat_id = message.chat.id
    if chat_id not in (await _0x_call.calls):
        try:
            await _0x_app.send_message(chat_id, "Nothing is playing.")
        except Exception:
            pass
        return
    current_loop = _0x_q_get_loop(chat_id)
    new_loop = not current_loop
    _0x_q_set_loop(chat_id, new_loop)
    status = "Enabled" if new_loop else "Disabled"
    try:
        await _0x_app.send_message(chat_id, f"🔁 **Loop mode has been {status} for this track.**")
    except Exception:
        pass

@_0x_app.on_message(filters.command(["shuffle", "sh"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_shuffle(client, message):
    chat_id = message.chat.id
    shuffled = _0x_q_shuffle(chat_id)
    if shuffled:
        try:
            await _0x_app.send_message(chat_id, "🔀 **Queue successfully shuffled!**")
        except Exception:
            pass
    else:
        try:
            await _0x_app.send_message(chat_id, "Not enough songs in queue (need at least 2).")
        except Exception:
            pass

@_0x_app.on_message(filters.command(["help", "h"], prefixes=_0x_e) & _0x_sudo & filters.group)
async def _0x_cmd_help(client, message):
    help_text = (
        "🌟 **Professional Music Selfbot Help Menu** 🌟\n\n"
        "Here is a list of available commands. Prefix is `.` (or your configured prefix).\n\n"
        "🎵 **Playback Controls:**\n"
        f"• `{_0x_e}play` | `{_0x_e}p` `<song>` - Play a song or playlist (YouTube, Spotify, JioSaavn)\n"
        f"• `{_0x_e}skip` | `{_0x_e}s` - Skip the current song\n"
        f"• `{_0x_e}pause` | `{_0x_e}ps` - Pause streaming\n"
        f"• `{_0x_e}resume` | `{_0x_e}r` - Resume streaming\n"
        f"• `{_0x_e}stop` | `{_0x_e}st` | `{_0x_e}end` - Stop streaming and clear queue\n\n"
        "📋 **Queue & Status:**\n"
        f"• `{_0x_e}queue` | `{_0x_e}q` - View the current queue\n"
        f"• `{_0x_e}current` | `{_0x_e}c` - View details of the currently playing song\n"
        f"• `{_0x_e}loop` | `{_0x_e}l` - Toggle loop mode for the current song\n"
        f"• `{_0x_e}shuffle` | `{_0x_e}sh` - Shuffle the songs in the queue\n\n"
        "🔊 **Volume Controls:**\n"
        f"• `{_0x_e}volume` | `{_0x_e}vol` `<1-200>` - Set streaming volume\n"
        f"• `{_0x_e}mute` - Mute stream\n"
        f"• `{_0x_e}unmute` - Unmute stream\n\n"
        "🛡️ **Admin Commands (Owner Only):**\n"
        f"• `{_0x_e}add` `<user_id/@username>` - Add a user to Sudoers list\n"
        f"• `{_0x_e}del` | `{_0x_e}remove` `<user_id/@username>` - Remove a user from Sudoers list\n"
        f"• `{_0x_e}sudolist` - List all Sudoers\n"
        f"• `{_0x_e}clearadmins` - Erase all Sudoers from database\n"
    )
    try:
        await _0x_app.send_message(message.chat.id, help_text)
    except Exception:
        pass

@_0x_app.on_message(filters.command("add", prefixes=_0x_e) & filters.group)
async def _0x_cmd_add(client, message):
    if message.from_user.id != _0x_d:
        try:
            await _0x_app.send_message(message.chat.id, "❌ Only the Owner can manage sudo users.")
        except Exception:
            pass
        return
    user_id = await _0x_get_user_id(client, message)
    if not user_id:
        try:
            await _0x_app.send_message(message.chat.id, f"Usage: `{_0x_e}add <user_id/@username>` or reply with `{_0x_e}add`.")
        except Exception:
            pass
        return
    await _0x_db_add(user_id)
    try:
        await _0x_app.send_message(message.chat.id, f"✅ User `{user_id}` has been added to Sudoers.")
    except Exception:
        pass

@_0x_app.on_message(filters.command(["del", "remove"], prefixes=_0x_e) & filters.group)
async def _0x_cmd_del(client, message):
    if message.from_user.id != _0x_d:
        try:
            await _0x_app.send_message(message.chat.id, "❌ Only the Owner can manage sudo users.")
        except Exception:
            pass
        return
    user_id = await _0x_get_user_id(client, message)
    if not user_id:
        try:
            await _0x_app.send_message(message.chat.id, f"Usage: `{_0x_e}del <user_id/@username>` or reply with `{_0x_e}del`.")
        except Exception:
            pass
        return
    await _0x_db_del(user_id)
    try:
        await _0x_app.send_message(message.chat.id, f"✅ User `{user_id}` has been removed from Sudoers.")
    except Exception:
        pass

@_0x_app.on_message(filters.command("sudolist", prefixes=_0x_e) & filters.group)
async def _0x_cmd_sudolist(client, message):
    if message.from_user.id != _0x_d:
        try:
            await _0x_app.send_message(message.chat.id, "❌ Only the Owner can view the Sudoers list.")
        except Exception:
            pass
        return
    sudoers = await _0x_db_list()
    if not sudoers:
        try:
            await _0x_app.send_message(message.chat.id, f"**Sudo Users:**\n\nOwner: `{_0x_d}`\nNo other sudo users.")
        except Exception:
            pass
        return
    text = f"**Sudo Users:**\n\nOwner: `{_0x_d}`\n"
    for idx, user in enumerate(sudoers):
        text += f"{idx + 1}. `{user}`\n"
    try:
        await _0x_app.send_message(message.chat.id, text)
    except Exception:
        pass

@_0x_app.on_message(filters.command("clearadmins", prefixes=_0x_e) & filters.group)
async def _0x_cmd_clearadmins(client, message):
    if message.from_user.id != _0x_d:
        try:
            await _0x_app.send_message(message.chat.id, "❌ Only the Owner can clear admins.")
        except Exception:
            pass
        return
    async with aiosqlite.connect(_0x_db) as db:
        await db.execute("DELETE FROM sudoers;")
        await db.commit()
    try:
        await _0x_app.send_message(message.chat.id, "✅ **All sudo admins have been cleared from the database!**")
    except Exception:
        pass

async def _0x_start_bot():
    _0x_log.info("Starting Userbot Client...")
    await _0x_app.start()
    _0x_log.info("Userbot Client Started.")
    _0x_log.info("Starting PyTgCalls Client...")
    await _0x_call.start()
    _0x_log.info("PyTgCalls Client Started.")
    _0x_log.info("Initializing Database...")
    await _0x_db_init()
    _0x_log.info("Database Initialized.")
    _0x_log.info("Music Userbot is now running. Use Ctrl+C to stop.")
    await idle()
    _0x_log.info("Stopping PyTgCalls Client...")
    try:
        await _0x_call.stop()
    except AttributeError:
        pass
    except Exception as e:
        _0x_log.warning(f"Error stopping PyTgCalls: {e}")
    _0x_log.info("Stopping Userbot Client...")
    await _0x_app.stop()
    _0x_log.info("Music Userbot Stopped.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_0x_start_bot())
