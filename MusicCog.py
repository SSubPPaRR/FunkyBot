import os
import re
import aiohttp
import discord
from dotenv import load_dotenv
import spotipy
import asyncio

from yt_dlp import YoutubeDL
from spotipy.oauth2 import SpotifyClientCredentials

from notifHub import NotificationHub


class EmptyQueue(Exception):
    """Cannot skip because queue is empty"""


class NotConnectedToVoice(Exception):
    """Cannot create the player because bot is not connected to voice"""


class NotPlaying(Exception):
    """Cannot <do something> because nothing is being played"""


class PlayerAlreadyExist(Exception):
    """Player already exist for this guild"""


class InvalidVolumeValue(Exception):
    """Invalid volume value was enter, value must be between 0-100"""

load_dotenv() 
URL_REG = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
SPOTIFY = "^https?:\/\/(open\.spotify\.com\/track)\/(.*)$"
SPOTIFY_PLAYLIST = "^https?:\/\/(open\.spotify\.com\/playlist)\/(.*)$"
YOUTUBE_PLAYLIST = "^https?:\/\/(www.youtube.com|youtube.com)\/playlist(.*)$"
SPOTIFY_ID = os.getenv('SPOTIFY_API_ID')
SPOTIFY_KEY = os.getenv('SPOTIFY_API_KEY')
YT_USR = os.getenv('YT_USER')
YT_PASS = os.getenv('YT_PASSWORD')

spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_ID,
    client_secret=SPOTIFY_KEY
))

ydl = YoutubeDL(
    {"format": "bestaudio/best", "restrictfilenames": True, "noplaylist": False, "nocheckcertificate": True,
     "ignoreerrors": True, "logtostderr": False, "quiet": True, "no_warnings": True, "source_address": "0.0.0.0",
     "username": YT_USR, "password":YT_PASS, "verbose": True})


def is_url(url):
    if re.match(URL_REG, url):
        return True
    else:
        return False


async def search(query):
    url = f"https://www.youtube.com/results?search_query={query}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            html = await resp.text()
    index = html.find('watch?v')
    url = ""
    while True:
        char = html[index]
        if char == '"':
            break
        url += char
        index += 1
    url = f"https://www.youtube.com/{url}"
    return url


def check_queue(ctx, opts, music, after, on_play, loop):
    try:
        song = music.queue[ctx.guild.id][0]
    except IndexError:
        return
    if not song.is_looping:
        try:
            music.queue[ctx.guild.id].pop(0)
        except IndexError:
            return
        if len(music.queue[ctx.guild.id]) > 0:
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(music.queue[ctx.guild.id][0].source, **opts))
            ctx.voice_client.play(source, after=lambda error: after(ctx, opts, music, after, on_play, loop))
            song = music.queue[ctx.guild.id][0]
            if on_play:
                loop.create_task(on_play(ctx, song))
    else:
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(music.queue[ctx.guild.id][0].source, **opts))
        ctx.voice_client.play(source, after=lambda error: after(ctx, opts, music, after, on_play, loop))
        song = music.queue[ctx.guild.id][0]
        if on_play:
            loop.create_task(on_play(ctx, song))


async def get_video_data(url, loop):
    if is_url(url[0]) and not re.match(SPOTIFY, url[0]):
        # check if spotify playlist
        if re.match(SPOTIFY_PLAYLIST, url[0]):
            meta = spotify.playlist(url[0])
            song_name_list = meta['tracks']['items']
            song_list = []
            for track in song_name_list:
                try:
                    track_name = track['track']['name'] + " " + track['track']['artists'][0]['name']
                    url = tuple(map(str, track_name.split(' ')))
                    url = await search(url)
                    data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                    source = data["url"]
                    url = "https://www.youtube.com/watch?v=" + data["id"]
                    title = data["title"]
                    description = data["description"]
                    likes = data["like_count"]
                    # dislikes = data["dislike_count"]
                    views = data["view_count"]
                    duration = data["duration"]
                    thumbnail = data["thumbnail"]
                    channel = data["uploader"]
                    channel_url = data["uploader_url"]
                    song_list.append(Song(source, url, title, description,
                                          views, duration, thumbnail, channel, channel_url, False))
                except Exception as e:
                    print(f'Error occured at track {track["track"]["name"]}')
                    continue
            return song_list
        # check if yt playlist
        elif re.match(YOUTUBE_PLAYLIST, url[0]):
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(url[0], download=False))
            return [
                Song(song['url'], "https://www.youtube.com/watch?v=" + data["id"], song['title'], song['description'],
                     song['view_count'],
                     song['duration'], song['thumbnail'],
                     song['uploader'], song['uploader_url'], False) for song in data['entries']]
        # for other links
        else:
            # get track data
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(url[0], download=False))
            source = data["url"]
            url = "https://www.youtube.com/watch?v=" + data["id"]
            title = data["title"]
            description = data["description"]
            likes = data["like_count"]
            # dislikes = data["dislike_count"]
            views = data["view_count"]
            duration = data["duration"]
            thumbnail = data["thumbnail"]
            channel = data["uploader"]
            channel_url = data["uploader_url"]
            return [Song(source, url, title, description, views, duration, thumbnail, channel, channel_url, False)]
    else:
        # check if spotify song
        if re.match(SPOTIFY, url[0]):
            meta = spotify.track(url[0])
            temp_url = meta['name'] + " " + meta['artists'][0]['name']
            url = tuple(map(str, temp_url.split(' ')))
            
        #    yt search options
        url = await search(url)
        data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        source = data["url"]
        url = "https://www.youtube.com/watch?v=" + data["id"]
        title = data["title"]
        description = data["description"]
        likes = data["like_count"]
        # dislikes = data["dislike_count"]
        views = data["view_count"]
        duration = data["duration"]
        thumbnail = data["thumbnail"]
        channel = data["uploader"]
        channel_url = data["uploader_url"]
        return [Song(source, url, title, description, views, duration, thumbnail, channel, channel_url, False)]



class MusicPlayer(object):
    def __init__(self, ctx, music, hub:NotificationHub, **kwargs):
        self.ctx = ctx
        self.voice = ctx.voice_client
        self.loop = ctx.bot.loop
        self.music = music
        self.queue = Queue()
        self.notif_hub = hub 
        ffmpeg_error = kwargs.get("ffmpeg_error_betterfix", kwargs.get("ffmpeg_error_fix"))
        if ffmpeg_error and "ffmpeg_error_betterfix" in kwargs.keys():
            self.ffmpeg_opts = {"options": "-vn -loglevel quiet -hide_banner -nostats",
                                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 0 -nostdin"}
        elif ffmpeg_error:
            self.ffmpeg_opts = {"options": "-vn",
                                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 0 -nostdin"}
        else:
            self.ffmpeg_opts = {"options": "-vn", "before_options": "-nostdin"}

    async def play(self, up_next='', pos=None):
        try:
            track_src = None
            if up_next == '+':
                track_src = self.queue.next_track()
            elif up_next == '-':
                track_src = self.queue.previous_track()
            elif up_next == '*':
                track_src = self.queue.goto(pos)
            else:
                track_src = self.queue.current_track()

            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(track_src.source, **self.ffmpeg_opts))
            self.voice.play(source, after=lambda error: self.do_after())
            await self.now_playing()
        except discord.errors.ClientException:
            pass

    def do_after(self):
        try:
            fut = asyncio.run_coroutine_threadsafe(self.play(up_next='+'), self.loop)
            fut.result()
        except IndexError:
            print('End of queue')

    async def queue_song(self, query: str):
        songs = await get_video_data(query, self.loop)
        self.queue.add_tracks(songs)
        # or len(self.queue.tracks) > 1
        if self.voice.is_playing(): 
            await self.on_queue_message(songs, query)

    async def stop(self):
        self.voice.stop()
        self.queue.clear()
        await self.delete()

    async def resume(self):
        self.voice.resume()

    async def pause(self):
        self.voice.pause()

    async def skip(self):
        try:
            if self.voice.is_playing:
                self.voice.stop()
                await self.play(up_next='+')
        except IndexError:
            await self.notif_hub.send_notif('error', title="🪘 Problem occurred 🪘", description=f"Cant skip, end of queue")
                                  

    async def set_looping(self, state: bool):
        self.queue.looping = state

    async def change_volume(self, vol):
        if vol < 0 or vol > 100:
            raise InvalidVolumeValue
        else:
            self.voice.source.volume = (vol / 100)

    async def delete(self):
        self.music.players.pop(self.ctx.guild.id)

    async def now_playing(self):
        song = self.queue.current_track()
        await self.notif_hub.send_notif(event_name='play',title="🪘 NOW PLAYING 🪘", song=song)
        
    async def on_queue_message(self, songs, query):
        if len(songs) == 1:
            song = songs[0]
        else:
            song = Song(None, query, str(len(self.queue.tracks)) +
                        " tracks", None, None, None, songs[0].thumbnail, None, None, False)

        # embed = discord.Embed(color=self.ctx.author.color, title="🐒 ADDED TO QUEUE 🐒",
        #                       description=f"[{song.name}]({song.url})")
        # embed.set_thumbnail(url=song.thumbnail)
        # embed.set_footer(text=f"requested by {self.ctx.author.display_name}")
        # await self.ctx.send(embed=embed)
        await self.notif_hub.send_notif('queue',title="🐒 ADDED TO QUEUE 🐒" ,song=song)


class Song(object):
    def __init__(self, source, url, title, description, views, duration, thumbnail, channel, channel_url, loop):
        self.source = source
        self.url = url
        self.title = title
        self.description = description
        self.views = views
        self.name = title
        self.duration = duration
        self.thumbnail = thumbnail
        self.channel = channel
        self.channel_url = channel_url
        self.is_looping = loop


class Queue(object):
    def __init__(self, **kwargs):
        self.tracks = []
        self.pointer = 0
        self.looping = False

    def current_track(self):
        return self.tracks[self.pointer]

    def next_track(self):
        if self.looping and self.pointer == len(self.tracks) - 1:
            self.pointer = 0
        else:
            self.pointer += 1
        return self.current_track()

    def previous_track(self):
        if self.looping and self.pointer == 0:
            self.pointer = len(self.tracks) - 1
        else:
            self.pointer -= 1
        return self.current_track()

    def add_track(self, song: Song):
        self.tracks.append(song)

    def add_tracks(self, song: list[Song]):
        self.tracks.extend(song)

    def remove_track(self, index: int):
        self.tracks.pop(index)

    def goto(self, index: int):
        self.pointer = index
        return self.current_track()

    def clear(self):
        self.tracks.clear()


class Music(object):
    def __init__(self):
        self.players = {}

    def create_player(self, ctx, **kwargs):
        if not ctx.voice_client:
            raise NotConnectedToVoice("Cannot create the player because bot is not connected to voice")
        if ctx.guild.id in self.players.keys():
            raise PlayerAlreadyExist
        else:
            hub = NotificationHub(ctx=ctx)
            player = MusicPlayer(ctx, self, hub, **kwargs)
            self.players[ctx.guild.id] = player
            return player

    def get_player(self, **kwargs) -> MusicPlayer|None:
        guild = kwargs.get("guild_id")
        channel = kwargs.get("channel_id")
        players = self.players
        for player_id in self.players:
            if guild and channel and players[player_id].ctx.guild.id == guild and \
                    players[player_id].voice.channel.id == channel:
                return players[player_id]
            elif not guild and channel and players[player_id].voice.channel.id == channel:
                return players[player_id]
            elif not channel and guild and players[player_id].ctx.guild.id == guild:
                return players[player_id]
        else:
            return None
