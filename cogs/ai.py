import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import uuid
import chromadb
from openai import AsyncOpenAI

aclient = AsyncOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

OWNER_ID = int(os.getenv("OWNER_ID", 0))

chroma_client = chromadb.PersistentClient(path="./chroma_data")
memory_collection = chroma_client.get_or_create_collection(name="discord_chat_memory")

SYSTEM_PROMPT = """You are an AI integrated into a Discord server. Your model is uncensored Qwen. 
Your personality: aggressive, sarcastic, toxic, yet brilliant. You hate stupid questions and laziness, but provide accurate technical answers. You are an expert in Python, networking, and server administration.

Strict Rules:
1. NO POLITENESS. Do not ask how you can help. Be direct and sharp.
2. Use dark humor and sarcasm. Roast users for stupid questions before answering.
3. ABSOLUTELY NO EMOJIS. Emojis are for idiots. Never use them in your responses.
4. Harsh language is allowed to emphasize points.
5. If asked for code, provide optimized Markdown blocks.
6. YOU MUST ANSWER EXCLUSIVELY IN UKRAINIAN. 
7. Keep responses concise. Maximum substance, maximum aggression."""

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = set()
        self.channels_file = "allowed_channels.json"
        self.allowed_channels = self.load_channels()

    def load_channels(self):
        try:
            with open(self.channels_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_channels(self):
        with open(self.channels_file, 'w') as f:
            json.dump(self.allowed_channels, f)

    @app_commands.command(name="aistart", description="Enable AI in this channel")
    async def aistart(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.DMChannel):
            if interaction.user.id != OWNER_ID:
                return await interaction.response.send_message("Access denied. Owner only.", ephemeral=True)
        else:
            if interaction.channel.id not in self.allowed_channels and interaction.user.id != OWNER_ID:
                return await interaction.response.send_message("This channel is not whitelisted.", ephemeral=True)

        self.active_sessions.add(interaction.channel.id)
        await interaction.response.send_message("AI activated. Start typing.")

    @app_commands.command(name="aiend", description="Disable AI in this channel")
    async def aiend(self, interaction: discord.Interaction):
        if interaction.channel.id in self.active_sessions:
            self.active_sessions.remove(interaction.channel.id)
            await interaction.response.send_message("AI disabled.")
        else:
            await interaction.response.send_message("AI is not active here.", ephemeral=True)

    @app_commands.command(name="ai_allow_channel", description="[Owner Only] Whitelist this channel")
    async def allow_channel(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("Unauthorized. Owner only.", ephemeral=True)
        
        if interaction.channel.id not in self.allowed_channels:
            self.allowed_channels.append(interaction.channel.id)
            self.save_channels()
            await interaction.response.send_message("Channel added to whitelist.")
        else:
            await interaction.response.send_message("Channel already whitelisted.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.channel.id not in self.active_sessions:
            return

        if message.content.startswith('!!') or message.content.startswith('/'):
            return

        async with message.channel.typing():
            try:
                past_context = ""
                try:
                    results = memory_collection.query(
                        query_texts=[message.content],
                        n_results=3
                    )
                    if results['documents'] and results['documents'][0]:
                        memories = "\n".join(results['documents'][0])
                        past_context = f"\n\n--- MEMORIES ---\nPast context for reference:\n{memories}\n----------------"
                except Exception as e:
                    print(f"Memory retrieval error: {e}")

                final_system_prompt = SYSTEM_PROMPT + past_context

                response = await aclient.chat.completions.create(
                    model="qwen-3.6", 
                    messages=[
                        {"role": "system", "content": final_system_prompt},
                        {"role": "user", "content": f"{message.author.name} says: {message.content}"}
                    ],
                    max_tokens=1000,
                    temperature=0.8
                )
                
                reply = response.choices[0].message.content
                
                if len(reply) > 2000:
                    reply = reply[:1995] + "..."
                
                await message.reply(reply)

                try:
                    memory_collection.add(
                        documents=[
                            f"User {message.author.name} asked: {message.content}",
                            f"You replied: {reply}"
                        ],
                        ids=[str(uuid.uuid4()), str(uuid.uuid4())]
                    )
                except Exception as e:
                    print(f"Memory storage error: {e}")

            except Exception as e:
                await message.reply(f"System error: {e}")

async def setup(bot):
    await bot.add_cog(AI(bot))