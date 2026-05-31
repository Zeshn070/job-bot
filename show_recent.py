#!/usr/bin/env python3
"""Print the most recent job posts from each channel (read-only)."""
import os, asyncio, discord

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
CHANNELS = ["jobs-you-sm1", "jobs-friend-sw15"]

intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    try:
        guild = client.get_guild(GUILD_ID)
        for name in CHANNELS:
            ch = discord.utils.get(guild.text_channels, name=name)
            print(f"\n=== #{name} (latest) ===")
            if not ch:
                print("  (channel not found)"); continue
            msgs = [m async for m in ch.history(limit=6) if client.user == m.author]
            for m in reversed(msgs):
                first = m.content.split("\n")[0].replace("**", "")
                print("  •", first[:70])
    finally:
        await client.close()


client.run(TOKEN)
