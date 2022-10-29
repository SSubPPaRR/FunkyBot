import aiohttp
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

try:
    import youtube_dl
    import discord

    has_voice = True
except ImportError:
    has_voice = False
    raise ImportError('Failed to import packages [youtube_dl, discord]')

URL_REG = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
SPOTIFY = "^https?:\/\/(open\.spotify\.com\/track)\/(.*)$"
SPOTIFY_PLAYLIST = "^https?:\/\/(open\.spotify\.com\/playlist)\/(.*)$"
YOUTUBE_PLAYLIST = "^https?:\/\/(www.youtube.com|youtube.com)\/playlist(.*)$"

spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id="32c2e5a0ffb7427fa2e5107e87f839a9",
    client_secret="0fbdb385fd954a0799691cdb502fda5d"
))

if has_voice:
    youtube_dl.utils.bug_reports_message = lambda: ''
    ydl = youtube_dl.YoutubeDL(
        {"format": "bestaudio/best", "restrictfilenames": True, "noplaylist": False, "nocheckcertificate": True,
         "ignoreerrors": True, "logtostderr": False, "quiet": True, "no_warnings": True, "source_address": "0.0.0.0"})


class EmptyQueue(Exception):
    """Cannot skip because queue is empty"""


class NotConnectedToVoice(Exception):
    """Cannot create the player because bot is not connected to voice"""


class NotPlaying(Exception):
    """Cannot <do something> because nothing is being played"""


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


# or re.match(SPOTIFY, url) or re.match(SPOTIFY_PLAYLIST, url)
def is_url(url):
    if re.match(URL_REG, url):
        return True
    else:
        return False


async def get_video_data(url, loop):
    if not has_voice:
        raise RuntimeError("DiscordUtils[voice] install needed in order to use voice")
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
                # likes = data["like_count"]
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
            # likes = data["like_count"]
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
        # likes = data["like_count"]
        # dislikes = data["dislike_count"]
        views = data["view_count"]
        duration = data["duration"]
        thumbnail = data["thumbnail"]
        channel = data["uploader"]
        channel_url = data["uploader_url"]
        return [Song(source, url, title, description, views, duration, thumbnail, channel, channel_url, False)]


def check_queue(ctx, opts, music, after, on_play, loop):
    if not has_voice:
        raise RuntimeError("DiscordUtils[voice] install needed in order to use voice")
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
                loop.create_task(on_play(ctx))
    else:
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(music.queue[ctx.guild.id][0].source, **opts))
        ctx.voice_client.play(source, after=lambda error: after(ctx, opts, music, after, on_play, loop))
        song = music.queue[ctx.guild.id][0]
        if on_play:
            loop.create_task(on_play(ctx))


class Music(object):
    def __init__(self):
        if not has_voice:
            raise RuntimeError("DiscordUtils[voice] install needed in order to use voice")
        self.queue = {}
        self.players = []

    def create_player(self, ctx, **kwargs):
        if not ctx.voice_client:
            raise NotConnectedToVoice("Cannot create the player because bot is not connected to voice")
        player = MusicPlayer(ctx, self, **kwargs)
        self.players.append(player)
        return player

    def get_player(self, **kwargs):
        guild = kwargs.get("guild_id")
        channel = kwargs.get("channel_id")
        for player in self.players:
            if guild and channel and player.ctx.guild.id == guild and player.voice.channel.id == channel:
                return player
            elif not guild and channel and player.voice.channel.id == channel:
                return player
            elif not channel and guild and player.ctx.guild.id == guild:
                return player
        else:
            return None


class MusicPlayer(object):
    def __init__(self, ctx, music, **kwargs):
        if not has_voice:
            raise RuntimeError("DiscordUtils[voice] install needed in order to use voice")
        self.ctx = ctx
        self.voice = ctx.voice_client
        self.loop = ctx.bot.loop
        self.music = music
        if self.ctx.guild.id not in self.music.queue.keys():
            self.music.queue[self.ctx.guild.id] = []
        self.after_func = check_queue
        self.on_play_func = None
        self.on_queue_func = self.on_skip_func = self.on_stop_func = self.on_pause_func = self.on_resume_func = self.on_loop_toggle_func = self.on_volume_change_func = self.on_remove_from_queue_func = None

        ffmpeg_error = kwargs.get("ffmpeg_error_betterfix", kwargs.get("ffmpeg_error_fix"))
        if ffmpeg_error and "ffmpeg_error_betterfix" in kwargs.keys():
            self.ffmpeg_opts = {"options": "-vn -loglevel quiet -hide_banner -nostats",
                                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 0 -nostdin"}
        elif ffmpeg_error:
            self.ffmpeg_opts = {"options": "-vn",
                                "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 0 -nostdin"}
        else:
            self.ffmpeg_opts = {"options": "-vn", "before_options": "-nostdin"}

    def disable(self):
        self.music.players.remove(self)

    def on_queue(self, func):
        self.on_queue_func = func

    def on_play(self, func):
        self.on_play_func = func

    def on_skip(self, func):
        self.on_skip_func = func

    def on_stop(self, func):
        self.on_stop_func = func

    def on_pause(self, func):
        self.on_pause_func = func

    def on_resume(self, func):
        self.on_resume_func = func

    def on_loop_toggle(self, func):
        self.on_loop_toggle_func = func

    def on_volume_change(self, func):
        self.on_volume_change_func = func

    def on_remove_from_queue(self, func):
        self.on_remove_from_queue_func = func

    # adding playlist support
    async def queue(self, url, ):
        songs = await get_video_data(url, self.loop)
        self.music.queue[self.ctx.guild.id].extend(songs)
        if self.on_queue_func:
            self.loop.create_task(self.on_queue_func(self.ctx))
        return songs

    async def play(self):
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(self.music.queue[self.ctx.guild.id][0].source, **self.ffmpeg_opts))
        self.voice.play(source,
                        after=lambda error: self.after_func(self.ctx, self.ffmpeg_opts, self.music, self.after_func,
                                                            self.on_play_func, self.loop))
        song = self.music.queue[self.ctx.guild.id][0]
        if self.on_play_func:
            self.loop.create_task(self.on_play_func(self.ctx))
        return song

    async def skip(self, force=False):
        if len(self.music.queue[self.ctx.guild.id]) == 0:
            raise NotPlaying("Cannot skip because nothing is being played")
        elif not len(self.music.queue[self.ctx.guild.id]) > 1 and not force:
            raise EmptyQueue("Cannot skip because queue is empty")
        else:
            old = self.music.queue[self.ctx.guild.id][0]
            old.is_looping = False if old.is_looping else False
            self.voice.stop()
            try:
                new = self.music.queue[self.ctx.guild.id][0]
                if self.on_skip_func:
                    await self.on_skip_func(self.ctx, old, new)
                return old, new
            except IndexError:
                if self.on_skip_func:
                    await self.on_skip_func(self.ctx, old)
                return old

    async def stop(self):
        try:
            self.music.queue[self.ctx.guild.id] = []
            self.voice.stop()
            self.music.players.remove(self)
        except:
            raise NotPlaying("Cannot stop because nothing is being played")
        if self.on_stop_func:
            await self.on_stop_func(self.ctx)

    async def pause(self):
        try:
            self.voice.pause()
            song = self.music.queue[self.ctx.guild.id][0]
        except:
            raise NotPlaying("Cannot pause because nothing is being played")
        if self.on_pause_func:
            await self.on_pause_func(self.ctx, song)
        return song

    async def resume(self):
        try:
            self.voice.resume()
            song = self.music.queue[self.ctx.guild.id][0]
        except:
            raise NotPlaying("Cannot resume because nothing is being played")
        if self.on_resume_func:
            await self.on_resume_func(self.ctx, song)
        return song

    def current_queue(self):
        try:
            return self.music.queue[self.ctx.guild.id]
        except KeyError:
            raise EmptyQueue("Queue is empty")

    def now_playing(self):
        try:
            return self.music.queue[self.ctx.guild.id][0]
        except:
            return None

    async def toggle_song_loop(self):
        try:
            song = self.music.queue[self.ctx.guild.id][0]
        except:
            raise NotPlaying("Cannot loop because nothing is being played")
        if not song.is_looping:
            song.is_looping = True
        else:
            song.is_looping = False
        if self.on_loop_toggle_func:
            await self.on_loop_toggle_func(self.ctx, song)
        return song

    async def change_volume(self, vol):
        self.voice.source.volume = vol
        try:
            song = self.music.queue[self.ctx.guild.id][0]
        except:
            raise NotPlaying("Cannot loop because nothing is being played")
        if self.on_volume_change_func:
            await self.on_volume_change_func(self.ctx, song, vol)
        return song, vol

    async def remove_from_queue(self, index):
        if index == 0:
            try:
                song = self.music.queue[self.ctx.guild.id][0]
            except:
                raise NotPlaying("Cannot loop because nothing is being played")
            await self.skip(force=True)
            return song
        song = self.music.queue[self.ctx.guild.id][index]
        self.music.queue[self.ctx.guild.id].pop(index)
        if self.on_remove_from_queue_func:
            await self.on_remove_from_queue_func(self.ctx, song)
        return song

    def delete(self):
        self.music.players.remove(self)


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
