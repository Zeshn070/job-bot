#!/usr/bin/env python3
"""
Adzuna -> Discord job poster.

Checks Adzuna for warehouse / fast-food / part-time jobs within 10 miles of each
person's postcode and posts NEW listings into their channel. Remembers what it
has already posted so it never double-posts.

Designed to run forever on Replit (with the keep_alive web server) or anywhere
else (Railway cron, your own PC). Schedule = CHECK_EVERY_HOURS below.

Required environment variables (set these in Replit "Secrets"):
    DISCORD_TOKEN     - your bot token
    GUILD_ID          - your server id (1509876009749450852)
    ADZUNA_APP_ID     - from developer.adzuna.com
    ADZUNA_APP_KEY    - from developer.adzuna.com
"""
import os
import json
import asyncio

import aiohttp
import discord
from discord.ext import tasks

# Optional keep-alive web server (only used on Replit). Safe if missing.
try:
    from keep_alive import keep_alive
except Exception:
    keep_alive = None

TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
ADZUNA_APP_ID = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]

CHECK_EVERY_HOURS = 6          # how often to look for new jobs
RESULTS_PER_CHECK = 20         # per category, per person
MAX_POST_PER_CHECK = 3         # cap posts per person per cycle (no flooding)
DISTANCE_KM = 16               # Adzuna uses KILOMETRES — 16 km ~= 10 miles
SEEN_FILE = "seen_jobs.json"   # dedupe store

# Who gets what. channel = exact Discord channel name; postcode drives the search.
PEOPLE = [
    {"channel": "jobs-you-sm1",     "postcode": "SM1 4BL"},
    {"channel": "jobs-friend-sw15", "postcode": "SW15 4JQ"},
]

# Adzuna job categories to pull from — these map to attainable, no-degree roles.
CATEGORIES = [
    "logistics-warehouse-jobs",     # warehouse, picker/packer (main target)
    "customer-services-jobs",       # customer service / assistant roles
    "part-time-jobs",               # part-time / easy entry roles
]

# Extra brand searches — pulls jobs from popular fast-food / high-street chains.
BRAND_KEYWORDS = "mcdonalds kfc burger king subway greggs costa pret nandos dominos pizza hut starbucks"

# Extra keyword search — temp / night-shift roles you asked for.
EXTRA_KEYWORDS = "warehouse night shift nights temporary temp seasonal customer service"

# Drop anything whose TITLE contains these — senior/professional roles you'd be
# unlikely to get matched to. Keeps the channel to realistic, attainable jobs.
EXCLUDE_TITLE_WORDS = {
    "manager", "senior", "lead", "supervisor", "head", "principal", "director",
    "executive", "engineer", "developer", "analyst", "consultant", "officer",
    "underwriter", "architect", "specialist", "coordinator", "qualified",
    "nurse", "accountant", "solicitor", "devops", "designer", "controller",
    "advisor", "adviser", "chef de", "sous", "estimator", "surveyor", "auditor",
    "teacher", "paralegal", "registered", "deputy", "regional", "account ",
    # No driving licence — exclude anything needing a car/van/licence:
    "driver", "delivery", "courier", "rider", "driving", "hgv", "7.5t",
    "forklift", "flt", "van ", "chauffeur", "cdl", "lgv", "multidrop",
}


def job_ok(job):
    """True if the job looks entry-level / attainable."""
    title = (job.get("title") or "").lower()
    return not any(w in title for w in EXCLUDE_TITLE_WORDS)


# --------------------------------------------------------------------------- #
def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(sorted(seen), f)
    except Exception as e:
        print(f"warn: couldn't save seen file: {e}", flush=True)


async def fetch_jobs(session, postcode):
    """Pull recent jobs from each attainable category near the postcode."""
    url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    all_jobs = {}
    for category in CATEGORIES:
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": RESULTS_PER_CHECK,
            "category": category,
            "where": postcode,
            "distance": DISTANCE_KM,
            "sort_by": "date",
            "part_time": 1,            # PART-TIME ONLY
            "content-type": "application/json",
        }
        try:
            async with session.get(url, params=params) as r:
                if r.status != 200:
                    body = await r.text()
                    print(f"Adzuna {r.status} ({category}, {postcode}): {body[:120]}", flush=True)
                    continue
                data = await r.json()
                for j in data.get("results", []):
                    if j.get("id"):
                        all_jobs[j["id"]] = j  # dedupe across categories
        except Exception as e:
            print(f"fetch error ({category}): {e}", flush=True)
        await asyncio.sleep(0.3)  # gentle on the API

    # Extra pass: fast-food / high-street brand jobs (KFC, McDonald's, etc.)
    brand_params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": RESULTS_PER_CHECK,
        "what_or": BRAND_KEYWORDS,
        "where": postcode,
        "distance": DISTANCE_KM,
        "sort_by": "date",
        "part_time": 1,            # PART-TIME ONLY
        "content-type": "application/json",
    }
    try:
        async with session.get(url, params=brand_params) as r:
            if r.status == 200:
                data = await r.json()
                for j in data.get("results", []):
                    if j.get("id"):
                        all_jobs[j["id"]] = j
    except Exception as e:
        print(f"brand fetch error: {e}", flush=True)
    await asyncio.sleep(0.3)

    # Extra pass: temp / night-shift / customer-service keywords
    kw_params = dict(brand_params, what_or=EXTRA_KEYWORDS)
    try:
        async with session.get(url, params=kw_params) as r:
            if r.status == 200:
                data = await r.json()
                for j in data.get("results", []):
                    if j.get("id"):
                        all_jobs[j["id"]] = j
    except Exception as e:
        print(f"keyword fetch error: {e}", flush=True)

    # newest first
    return sorted(all_jobs.values(), key=lambda j: j.get("created", ""), reverse=True)


def format_job(job):
    title = job.get("title", "Job")
    company = (job.get("company") or {}).get("display_name", "Unknown")
    loc = (job.get("location") or {}).get("display_name", "")
    url = job.get("redirect_url", "")
    salary_min = job.get("salary_min")
    salary = f" • £{int(salary_min):,}+" if salary_min else ""
    contract = job.get("contract_time", "") or ""
    contract = f" • {contract.replace('_', ' ')}" if contract else ""
    return f"**{title}**\n{company} — {loc}{salary}{contract}\n{url}"


intents = discord.Intents.default()
client = discord.Client(intents=intents)
seen = load_seen()


@tasks.loop(hours=CHECK_EVERY_HOURS)
async def check_jobs():
    await client.wait_until_ready()
    guild = client.get_guild(GUILD_ID)
    if guild is None:
        print("guild not found", flush=True)
        return

    async with aiohttp.ClientSession() as session:
        for person in PEOPLE:
            channel = discord.utils.get(guild.text_channels, name=person["channel"])
            if channel is None:
                print(f"channel #{person['channel']} not found", flush=True)
                continue

            jobs = await fetch_jobs(session, person["postcode"])
            jobs = [j for j in jobs if job_ok(j)]
            # part-time only: drop anything explicitly marked full-time
            jobs = [j for j in jobs if j.get("contract_time") != "full_time"]
            new_jobs = [j for j in jobs if j.get("id") and j["id"] not in seen]
            new_jobs = new_jobs[:MAX_POST_PER_CHECK]
            # Oldest-first so they appear in chronological order in the channel.
            for job in reversed(new_jobs):
                try:
                    await channel.send(format_job(job))
                    seen.add(job["id"])
                    await asyncio.sleep(1)  # gentle on rate limits
                except Exception as e:
                    print(f"post error: {e}", flush=True)
            print(f"#{person['channel']}: {len(new_jobs)} new job(s)", flush=True)

    save_seen(seen)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}", flush=True)
    if not check_jobs.is_running():
        check_jobs.start()


if __name__ == "__main__":
    if keep_alive:
        keep_alive()  # tiny web server so Replit/UptimeRobot can keep it awake
    client.run(TOKEN)
