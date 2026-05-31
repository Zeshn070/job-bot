#!/usr/bin/env python3
"""One-shot: check jobs once, post new ones, then exit. (For manual/seed runs.)"""
import os
import asyncio
import aiohttp
import discord

from main import (
    GUILD_ID, PEOPLE, fetch_jobs, format_job, load_seen, save_seen, job_ok,
)

TOKEN = os.environ["DISCORD_TOKEN"]
intents = discord.Intents.default()
client = discord.Client(intents=intents)
seen = load_seen()


@client.event
async def on_ready():
    try:
        guild = client.get_guild(GUILD_ID)
        async with aiohttp.ClientSession() as session:
            for person in PEOPLE:
                ch = discord.utils.get(guild.text_channels, name=person["channel"])
                if ch is None:
                    print(f"channel #{person['channel']} not found", flush=True)
                    continue
                jobs = await fetch_jobs(session, person["postcode"])
                jobs = [j for j in jobs if job_ok(j)]
                new = [j for j in jobs if j.get("id") and j["id"] not in seen]
                # cap the seed run so we don't dump 20 at once
                new = new[:6]
                for job in reversed(new):
                    await ch.send(format_job(job))
                    seen.add(job["id"])
                    await asyncio.sleep(1)
                print(f"#{person['channel']}: posted {len(new)} job(s)", flush=True)
        save_seen(seen)
    finally:
        await client.close()


client.run(TOKEN)
