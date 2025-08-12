# How to Update Tracks (Quick Checklist)

1. Edit `data/tracks.csv` with your new songs:
   - Required columns: `artist,title,year,spotify_uri`
   - Optional: `notes`, `difficulty`, etc. (ignored by generator unless you extend it)

2. Run the generator:
   - `python scripts/generate_cards-fixed.py`

3. Verify outputs:
   - `cards/html/` has one HTML per track (open one locally to sanity check)
   - `cards/qr/` has matching PNGs
   - `hitster_deck.pdf` / `deck_duplex.pdf` regenerated if your script writes them

4. Commit & push:
   - `git add cards data scripts`
   - `git commit -m "Update tracks and regenerate cards"`
   - `git push`

5. Reprint (optional):
   - Use the latest `deck_duplex.pdf` to print new cards.

6. On phones:
   - Visit `login.html`, log in again if asked (token rotates ~hourly).
   - Scan a card and confirm playback.
