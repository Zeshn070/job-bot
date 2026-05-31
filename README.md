# Job Bot — Adzuna → Discord

Posts new warehouse / fast-food / part-time jobs within ~10 miles of each
postcode into the matching Discord channel. Never double-posts.

## Replit setup

1. Put `main.py`, `keep_alive.py`, and `requirements.txt` in your repl
   (push them to the GitHub repo your repl is linked to).
2. In Replit, open the **Secrets** tab (lock icon) and add:
   - `DISCORD_TOKEN` = your bot token
   - `GUILD_ID` = `1509876009749450852`
   - `ADZUNA_APP_ID` = your Adzuna App ID
   - `ADZUNA_APP_KEY` = your Adzuna App Key
3. Press **Run**. It logs in, checks jobs immediately, then every 3 hours.
4. (Keep it awake) Copy your repl's web URL, make a free account at
   **uptimerobot.com**, add an HTTP monitor pinging that URL every 5 minutes.

## Notes
- The **builder bot** must still be in the server (it's the same bot token).
- Adzuna's `distance` is in **kilometres**; 16 km ≈ 10 miles (set in `main.py`).
- Edit `WHAT_OR` in `main.py` to change job types; `CHECK_EVERY_HOURS` to change
  how often it looks.
- `seen_jobs.json` is created automatically to remember posted jobs.
