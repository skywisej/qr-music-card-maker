# ================================================================
#  HITSTER CARD GENERATOR  –  One‑Track‑Playlist version
#  ---------------------------------------------------------------
#  Creates private 1‑track playlists so the embed shows square art
#  (no banner). Generates HTML stubs, QR codes, and a printable PDF.
# ================================================================

# ---------- SECTION 0 : Imports ----------
from dotenv import load_dotenv
load_dotenv()

import os, json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ---------- SECTION 1 : Credentials ----------
CLIENT_ID     = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("SPOTIPY_REDIRECT_URI")       # http://127.0.0.1:8080/callback

# ---------- SECTION 2 : Spotify User‑Auth ----------
scope = "playlist-modify-private"
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=scope))
USER_ID = sp.current_user()['id']

# ---------- SECTION 3 : Track → Playlist cache ----------
CACHE_FILE = "playlist_cache.json"
pl_cache = json.load(open(CACHE_FILE)) if os.path.exists(CACHE_FILE) else {}

def get_embed_url(track_id: str) -> str:
    """Return a playlist embed URL (square art) for the given track ID."""
    if track_id not in pl_cache:
        # Create private 1‑track playlist once
        playlist = sp.user_playlist_create(
            user=USER_ID,
            name=f"HITSTER_CARD_{track_id[:6]}",
            public=False,
            description="Auto playlist for Hitster card")
        sp.playlist_add_items(playlist['id'], [f"spotify:track:{track_id}"])
        pl_cache[track_id] = playlist['id']
        json.dump(pl_cache, open(CACHE_FILE, "w"), indent=2)
    pl_id = pl_cache[track_id]
    # view=coverart gives square art, theme=0 sets dark background
    return f"https://open.spotify.com/embed/playlist/{pl_id}?view=coverart&theme=0"

# ---------- SECTION 4 : Deck settings ----------
TRACK_IDS = [
    "3KkXRkHbMCARz0aVfEt68P",   # Sunflower
    "5Z01UMMf7V1o0MzF86s6WJ",   # Lose Yourself
    "4Dvkj6JhhA12EX05fT7y2e",   # As It Was
    "7qiZfU4dY1lWllzX7mPBI3",   # Shape of You
    "2WfaOiMkCvy7F5fcp2zZ8L"    # Take On Me
]
OUTPUT_PDF = "hitster_deck.pdf"
BASE_URL   = "https://skywisej.github.io/qr-music-card-maker/"   # <-- Phase 4: replace with GitHub Pages URL
TEMPLATE_HTML = "card-template.html"  # file you just saved

# ---------- SECTION 5 : Prepare folders ----------
os.makedirs("cards/html", exist_ok=True)
os.makedirs("cards/qrcodes", exist_ok=True)

# ---------- SECTION 6 : Fetch track metadata ----------
tracks = sp.tracks(TRACK_IDS)["tracks"]

# ---------- SECTION 7 : Create PDF + HTML ----------
pdf = canvas.Canvas(OUTPUT_PDF, pagesize=letter)
W, H = letter

for idx, track in enumerate(tracks, start=1):
    if track is None:               # (rare – ID unavailable in region)
        print(f"Track {TRACK_IDS[idx-1]} unavailable; skipped.")
        continue

    title   = track['name']
    artist  = track['artists'][0]['name']
    year    = track['album']['release_date'][:4]
    track_id = track['id']
    
    # ----- HTML stub via SDK template -----
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as tpl:
        html_stub = tpl.read().replace(
            "SPOTIFY_TRACK_URI",
            f"spotify:track:{track_id}"
        )

    html_name = f"track{idx}.html"
    with open(f"cards/html/{html_name}", "w", encoding="utf-8") as fh:
        fh.write(html_stub)

    # ----- Generate QR -----
    qr_img = qrcode.make(BASE_URL + html_name)
    qr_path = f"cards/qrcodes/{html_name.replace('.html','.png')}"
    qr_img.save(qr_path)

    # ----- PDF front (QR) -----
    pdf.drawImage(qr_path, 60, H-360, width=280, height=280)
    pdf.showPage()

    # ----- PDF back (info) -----
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(60, H-100, title)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(60, H-130, artist)
    pdf.drawString(60, H-150, f"Released: {year}")
    pdf.showPage()

pdf.save()
print("Done!  Check hitster_deck.pdf and cards/ folders.")
