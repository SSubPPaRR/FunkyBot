from concurrent.futures import thread
from re import L
from threading import Thread
import threading
import discord
from discord.ext import commands
import MusicCog
import os
from dotenv import load_dotenv 

myIntents= discord.Intents.default()
myIntents.message_content = True;

client = commands.Bot(command_prefix="funk_",intents=myIntents)

music = MusicCog.Music()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if "<@!891047888304611348>" in message.content:
        print(message.content)
        if message.guild.voice_client in client.voice_clients:
            await message.channel.send("What im just chilling :sunglasses:")

    await client.process_commands(message)


@client.command(name="play", aliases=['p'])
async def play(ctx, *url: str):
    player = music.get_player(guild_id=ctx.guild.id)

    if ctx.author.voice is None:
        await ctx.send("you are not in a voice channel")
    else:
        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            print("adding bot to vc")
            await voice_channel.connect()
        elif ctx.voice_client.channel.id != voice_channel.id:
            print("moving bot to vc")
            await ctx.voice_client.move_to(voice_channel)

        if not player:
            player = music.create_player(ctx, ffmpeg_error_betterfix=True)
            await player.queue_song(url)
            await player.play()
        elif not ctx.voice_client.is_playing():
            await player.queue_song(url)
        else:
            await player.queue_song(url)
            await player.play()


@client.command(name="leave", aliases=['lv'])
async def leave(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice.is_connected():
        await voice.disconnect()
    else:
        await ctx.send(embed=standard_embed(ctx, "The bot is not connected to a voice channel."))


@client.command(name="pause", aliases=['ps'])
async def pause(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    song = await player.pause()
    embed = discord.Embed(color=ctx.author.color, title=f"⏸ Paused {song.name}")
    embed.set_footer(text=f"requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@client.command(name="resume")
async def resume(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    song = await player.resume()
    await ctx.send(embed=standard_embed(ctx, f"▶ Resumed {song.name}"))


@client.command(name="stop")
async def stop(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    await player.stop()
    await ctx.send(embed=standard_embed(ctx, "🙉 PLAYBACK STOPPED 🙉"))


@client.command(name="queue", aliases=['q'])
async def queue(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    queue_list = ""
    pos = 0
    for song in player.queue.tracks:
        queue_list += f"{pos})[{song.name}]({song.url})\n"
        pos += 1
    embed = discord.Embed(color=ctx.author.color, title="🌳 QUEUE 🌳", description=queue_list)
    await ctx.send(embed=embed)


@client.command(name="now playing", aliases=['np'])
async def np(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    await player.now_playing()


@client.command(name="skip", aliases=['sk'])
async def skip(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    data = await player.skip()
    await ctx.send(embed=standard_embed(ctx, f"🙉 Skipped {data[0].name} 🙉"))


@client.command(name="remove", aliases=['rm'])
async def remove(ctx, index):
    player = music.get_player(guild_id=ctx.guild.id)
    song = await player.remove_from_queue(int(index))
    await ctx.send(embed=standard_embed(ctx, f"🙉 Removed {song.name} from queue 🙉"))


@client.command(name="loop", aliases=['lp'])
async def loop(ctx):
    player = music.get_player(guild_id=ctx.guild.id)
    song = await player.toggle_song_loop()
    state = None
    if song.is_looping:
        state = "Enabled"
    else:
        state = "Disabled"

    embed = discord.Embed(color=ctx.author.color, title=f"🔁 {state} loop for {song.name}")
    embed.set_footer(text=f"requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


def standard_embed(ctx, title: str):
    embed = discord.Embed(color=ctx.author.color, title=f"{title}")
    embed.set_footer(text=f"requested by {ctx.author.display_name}")
    return embed


async def np_embed(ctx, song):
    embed = discord.Embed(color=ctx.author.color, title="🪘 NOW PLAYING 🪘",
                          description=f"[{song.name}]({song.url})")
    embed.set_thumbnail(url=song.thumbnail)
    embed.set_footer(text=f"requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)

load_dotenv() 
TOKEN = os.getenv('BOT_KEY')
client.run(token=TOKEN)
