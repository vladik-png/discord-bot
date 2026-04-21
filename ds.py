import discord
from discord.ext import commands
import wavelink
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!!', intents=intents)

    async def setup_hook(self):
        node = wavelink.Node(uri="http://127.0.0.1:8080", password="youshallnotpass")
        await wavelink.Pool.connect(client=self, nodes=[node])
        
        await self.load_extension("cogs.music")
        
        await self.tree.sync()

    async def on_ready(self):
        print(f"{self.user.name} is online and ready!")

bot = MusicBot()

if __name__ == "__main__":
    bot.run(TOKEN)