import discord
from discord.ext import commands, tasks
from discord import app_commands
import wavelink
import aiohttp
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

RADIO_STATIONS = {
    "Lux FM (Ukraine)": "https://icecastdc.luxnet.ua/lux",
    "Hit FM (Ukraine)": "https://online.hitfm.ua/HitFM",
    "BBC Radio 1 (UK)": "http://stream.live.vc.bbcmedia.co.uk/bbc_radio_one"
}

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.idle_timers = {}
        super().__init__(command_prefix='!!', intents=intents)

    async def setup_hook(self):
        node = wavelink.Node(uri="http://127.0.0.1:8080", password="youshallnotpass")
        await wavelink.Pool.connect(client=self, nodes=[node])
        await self.tree.sync()
        self.afk_check.start()

    async def on_ready(self):
        print(f"{self.user.name} is online")

    @tasks.loop(seconds=20)
    async def afk_check(self):
        for player in self.voice_clients:
            guild_id = player.guild.id
            
            if not player.playing and not player.paused:
                if guild_id not in self.idle_timers:
                    self.idle_timers[guild_id] = datetime.datetime.now()
                else:
                    elapsed = (datetime.datetime.now() - self.idle_timers[guild_id]).total_seconds()
                    if elapsed >= 120: # 2 minutes
                        print(f"Disconnecting from {player.guild.name} due to inactivity.")
                        await player.disconnect()
                        self.idle_timers.pop(guild_id, None)
            else:
                self.idle_timers.pop(guild_id, None)

bot = MusicBot()

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

async def play_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if not current:
        return [app_commands.Choice(name=n, value=v) for n, v in RADIO_STATIONS.items()]
    
    choices = []
    url = "https://de1.api.radio-browser.info/json/stations/search"
    params = {"name": current, "limit": 20, "hidebroken": "true", "order": "clickcount", "reverse": "true"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for s in data:
                        name = f"{s.get('name', 'Unknown')[:80]} [{s.get('countrycode', '??')}]"
                        u = s.get("url_resolved", "") or s.get("url", "")
                        if u and len(u) <= 100:
                            choices.append(app_commands.Choice(name=name, value=u))
    except: pass
    return choices[:25]

@bot.tree.command(name="play", description="Play a song, playlist or radio station")
@app_commands.describe(input="Search query, URL or choose from radio list")
@app_commands.autocomplete(input=play_autocomplete)
async def play(interaction: discord.Interaction, input: str):
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)
        else:
            await interaction.response.send_message("You must be in a voice channel.", ephemeral=True)
            return

    player: wavelink.Player = interaction.guild.voice_client
    await interaction.response.defer()
    
    tracks = await wavelink.Playable.search(input)
    if not tracks:
        await interaction.followup.send("No results found.")
        return

    if isinstance(tracks, wavelink.Playlist):
        player.queue.put(tracks)
        msg = f"Added playlist: **{tracks.name}**"
    else:
        track = tracks[0]
        player.queue.put(track)
        msg = f"Added: **{track.title}**"

    if not player.playing:
        await player.play(player.queue.get())
    
    await interaction.followup.send(msg)

@bot.tree.command(name="destroy", description="Clear the queue and stop music")
async def destroy(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        player: wavelink.Player = interaction.guild.voice_client
        player.queue.clear()
        await player.stop()
        await interaction.response.send_message("💥 Queue cleared and music stopped.")
    else:
        await interaction.response.send_message("Bot is not in a voice channel.", ephemeral=True)

@bot.tree.command(name="stop", description="Stop music and leave the channel")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        player: wavelink.Player = interaction.guild.voice_client
        await player.stop()
        await player.disconnect()
        await interaction.response.send_message("⏹️ Stopped and disconnected.")
    else:
        await interaction.response.send_message("Bot is not connected.", ephemeral=True)

@bot.tree.command(name="queue", description="Show the music queue")
async def queue(interaction: discord.Interaction):
    if not interaction.guild.voice_client:
        return await interaction.response.send_message("Not connected.", ephemeral=True)
    
    player: wavelink.Player = interaction.guild.voice_client
    if player.queue.is_empty and not player.current:
        return await interaction.response.send_message("The queue is empty.")

    embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
    if player.current:
        embed.add_field(name="Now Playing", value=player.current.title, inline=False)
    
    if not player.queue.is_empty:
        upcoming = list(player.queue)[:10]
        text = "\n".join(f"{i+1}. {t.title}" for i, t in enumerate(upcoming))
        embed.add_field(name="Up Next", value=text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shuffle", description="Shuffle the tracks in the queue")
async def shuffle(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        player: wavelink.Player = interaction.guild.voice_client
        player.queue.shuffle()
        await interaction.response.send_message("🔀 Queue shuffled!")

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.skip(force=True)
        await interaction.response.send_message("⏭️ Skipped.")

bot.run(TOKEN)