import re
import aiohttp
import discord
import spotipy
import youtube_dl
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials


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


URL_REG = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
SPOTIFY = "^https?:\/\/(open\.spotify\.com\/track)\/(.*)$"
SPOTIFY_PLAYLIST = "^https?:\/\/(open\.spotify\.com\/playlist)\/(.*)$"
YOUTUBE_PLAYLIST = "^https?:\/\/(www.youtube.com|youtube.com)\/playlist(.*)$"

spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id="32c2e5a0ffb7427fa2e5107e87f839a9",
    client_secret="0fbdb385fd954a0799691cdb502fda5d"
))

youtube_dl.utils.bug_reports_message = lambda: ''
ydl = youtube_dl.YoutubeDL(
    {"format": "bestaudio/best", "restrictfilenames": True, "noplaylist": False, "nocheckcertificate": True,
     "ignoreerrors": True, "logtostderr": False, "quiet": True, "no_warnings": True, "source_address": "0.0.0.0"})


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
        # check if yt playlist
        if re.match(SPOTIFY_PLAYLIST, url[0]):
            meta = spotify.playlist(url[0])
            song_name_list = meta['tracks']['items']
            song_list = []
            for track in song_name_list:
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
            return song_list
        # check if spotify playlist
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


class Music(object):
    def __init__(self):
        self.players = {}

    def create_player(self, ctx, **kwargs):
        if not ctx.voice_client:
            raise NotConnectedToVoice("Cannot create the player because bot is not connected to voice")
        player = MusicPlayer(ctx, self, **kwargs)
        if ctx.guild.id in self.players.keys():
            raise PlayerAlreadyExist
        else:
            self.players[ctx.guild.id] = player
            return player

    def get_player(self, **kwargs):
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


class MusicPlayer(object):
    def __init__(self, ctx, music, **kwargs):
        self.ctx = ctx
        self.voice = ctx.voice_client
        self.loop = ctx.bot.loop
        self.music = music
        self.queue = Queue()
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
        if self.voice.is_playing() or len(self.queue.tracks) > 1:
            await self.on_queue_message(songs)

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
            embed = discord.Embed(color=self.ctx.author.color, title="🪘 Problem occurred 🪘",
                                  description=f"Cant skip, end of queue")
            embed.set_footer(text=f"{self.ctx.author.display_name}")
            await self.ctx.send(embed=embed)

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
        embed = discord.Embed(color=self.ctx.author.color, title="🪘 NOW PLAYING 🪘",
                              description=f"[{song.name}]({song.url})")
        embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"requested by {self.ctx.author.display_name}")
        await self.ctx.send(embed=embed)

    async def on_queue_message(self, songs):
        if len(songs) == 1:
            song = songs[0]
        else:
            song = Song(None, self.queue.current_track(), str(len(self.queue.tracks)) +
                        " tracks", None, None, None, None, None, None, False)

        embed = discord.Embed(color=self.ctx.author.color, title="🐒 ADDED TO QUEUE 🐒",
                              description=f"[{song.name}]({song.url})")
        embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"requested by {self.ctx.author.display_name}")
        await self.ctx.send(embed=embed)


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
        self.position = 0
        self.looping = False

    def current_track(self):
        return self.tracks[self.position]

    def next_track(self):
        if self.looping and self.position == len(self.tracks):
            self.position = 0
        else:
            self.position += 1
        return self.current_track()

    def previous_track(self):
        if self.looping and self.position == 0:
            self.position = len(self.tracks) - 1
        else:
            self.position -= 1
        return self.current_track()

    def add_track(self, song: Song):
        self.tracks.append(song)

    def add_tracks(self, song: list[Song]):
        self.tracks.extend(song)

    def remove_track(self, index: int):
        self.tracks.pop(index)

    def goto(self, index: int):
        self.position = index
        return self.current_track()

    def clear(self):
        self.tracks.clear()
