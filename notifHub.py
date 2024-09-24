import discord
from discord.ext import commands

class NotificationHub:
    def __init__(self,ctx: commands.Context):
        self.context = ctx 
        self.message_embed= {
            'play': self._get_song_embed,
            'stop': self._get_song_embed,
            'error': self._get_standard_embed,
            'queue': self._get_song_embed,
            } 

    async def send_notif(self, event_name:str,**kwargs):
        try:
            embed = self.message_embed[event_name](**kwargs)
            await self.context.send(embed=embed)
        except IndexError:
            print(f"unknown notification event name: '{event_name}'")

    def _get_standard_embed(self, title: str, description:str):
        embed = discord.Embed(color=self.context.author.color, title=f"{title}", description=description)
        embed.set_footer(text=f"requested by {self.context.author.display_name}")
        return embed
    
    def _get_song_embed(self, title: str, song):
        embed = discord.Embed(color=self.context.author.color, title=title,
                              description=f"[{song.name}]({song.url})")
        embed.set_thumbnail(url=song.thumbnail)
        embed.set_footer(text=f"requested by {self.context.author.display_name}")
        return embed
    
    