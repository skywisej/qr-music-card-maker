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
from pathlib import Path

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
# removed the need to create playlists by going to SDK mode

BASE_URL   = "https://skywisej.github.io/qr-music-card-maker/cards/html/"   # <-- moved higher in program
# ---------- SECTION 4 : Deck settings ----------
TRACK_IDS = [
    "3KkXRkHbMCARz0aVfEt68P",   # Sunflower
    "5Z01UMMf7V1o0MzF86s6WJ",   # Lose Yourself
    "4Dvkj6JhhA12EX05fT7y2e",   # As It Was
    "7qiZfU4dY1lWllzX7mPBI3",   # Shape of You
    "2WfaOiMkCvy7F5fcp2zZ8L"    # Take On Me
]
OUTPUT_PDF = "hitster_deck.pdf"

TEMPLATE_HTML = Path("card-template-v3.html")  # file you actually open
VERSION_TAG = 'v4' # bump to bust cache

# ---------- SECTION 5 : Prepare folders ----------
os.makedirs("cards/html", exist_ok=True)
os.makedirs("cards/qrcodes", exist_ok=True)

# ---------- SECTION 6 : Fetch track metadata ----------
tracks = sp.tracks(TRACK_IDS)["tracks"]

# ---------- SECTION 7 : Create PDF + HTML ----------
# ---------- SECTION 7 : Build a 4×2 grid per sheet ----------
from reportlab.lib.units import mm
Y_SHIFT = 4.5 * mm     # positive nudges BACK side DOWN; tweak ± until it lines up


COLS, ROWS      = 3, 4
CARD_W, CARD_H  = 60*mm, 60*mm            # tweak size here
X_START, Y_START = 15*mm, 15*mm           # page margin

pdf_front = canvas.Canvas("deck_front.pdf", pagesize=letter)
pdf_back  = canvas.Canvas("deck_back.pdf",  pagesize=letter)

cells_filled = 0
for idx, track in enumerate(tracks, start=1):
    if track is None:
        continue

    title   = track["name"]
    artist  = track["artists"][0]["name"]
    year    = track["album"]["release_date"][:4]
    track_id  = track["id"]
    track_uri = f"spotify:track:{track_id}"

    # 1. create HTML stub from template
    html_name = f"track{idx}.html"
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as tpl:
        html_stub = tpl.read().replace("SPOTIFY_TRACK_URI", track_uri)
    with open(f"cards/html/{html_name}", "w", encoding="utf-8") as fh:
        fh.write(html_stub)


    # 2. make QR (front)
    #DEBUG_URL= "https://skywisej.github.io/qr-music-card-maker/cards/html/track1.html"
    #print("DEBUG_URL:", BASE_URL + html_name)
    qr_img = qrcode.make(f"{BASE_URL}{html_name}?v={VERSION_TAG}")
    qr_path = f"cards/qrcodes/{html_name.replace('.html','.png')}"
    qr_img.save(qr_path)

    # 3. grid position
    col = cells_filled % COLS
    row = cells_filled // COLS
    x   = X_START + col * CARD_W
    y   = letter[1] - Y_START - (row + 1) * CARD_H

    # ---- FRONT SHEET (center QR) ----
    S = CARD_W - 20*mm                           # QR size: 10 mm margin left/right
    x_qr = x + (CARD_W - S) / 2                  # center horizontally
    y_qr = y + (CARD_H - S) / 2                  # center vertically
    pdf_front.drawImage(qr_path, x_qr, y_qr,     # draw at (x_qr,y_qr)
                        width=S, height=S)
    pdf_front.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)  # cut guide

    # ---- BACK SHEET (mirror LEFT‑RIGHT, centered date top-half + wrapped title/artist) ----
    from reportlab.pdfbase.pdfmetrics import stringWidth
    import textwrap

    # compute the left edge of this mirrored card
    mirror_x = letter[0] - x - CARD_W        # flip horizontally
    y_back   = y - Y_SHIFT                   # apply duplex correction
    pdf_back.rect(mirror_x, y_back, CARD_W, CARD_H, stroke=1, fill=0)    # draw the card border

    # helper to center text by measuring its width
    def draw_centered(text, py, font_name, font_size):
        pdf_back.setFont(font_name, font_size)
        text_w = stringWidth(text, font_name, font_size)
        px = mirror_x + (CARD_W - text_w) / 2
        pdf_back.drawString(px, py, text)

    # vertical positions (from bottom of card)
    padding = 10 * mm
    line_spacing = 6 * mm

    # amount of vertical space between wrapped title lines
    TITLE_LINE_SPACING = .5 * mm    # ↓ make smaller for tighter title lines

    # amount of vertical space between title block and artist
    ARTIST_GAP = 1 * mm            # ↓ make smaller for tighter title→artist
    
    # 1. date center in top half
    date_font, date_size = "Helvetica-Bold", 45
    date_y = y_back + CARD_H * 0.5 # halfway between top and midline
    draw_centered(year, date_y, date_font, date_size)

    #vertical baseline for the block below date
    block_top = date_y - date_size/2 -(5*mm)
    
    # 2. TITLE — wrap if needed, two lines max
    title_font, title_size = "Helvetica-Bold", 12
    max_width = CARD_W - 10*mm  # allow 5 mm margin each side
    
    # wrap on word boundaries to fit the max_width
    wrapped = textwrap.wrap(title, 
        width=100,  # a rough character count; we'll filter by actual width next
    )
    # refine by actual string width
    lines = []
    for line in wrapped:
        if stringWidth(line, title_font, title_size) <= max_width:
            lines.append(line)
        else:
            # further break very long single words
            words = textwrap.wrap(line, width=int(len(line) * max_width / stringWidth(line, title_font, title_size)))
            lines.extend(words)

    # take at most 2 lines
    lines = lines[:2]

    # draw each title line
    for i, txt in enumerate(lines):
        py = block_top - i * (title_size + TITLE_LINE_SPACING)
        draw_centered(txt, py, title_font, title_size)

    # 3. ARTIST — below the title lines
    artist_font, artist_size = "Helvetica", 10
    artist_y = block_top - len(lines) * (title_size + TITLE_LINE_SPACING) - ARTIST_GAP
    draw_centered(artist, artist_y, artist_font, artist_size)

    cells_filled += 1
    if cells_filled == COLS * ROWS:
        pdf_front.showPage()
        pdf_back.showPage()
        cells_filled = 0

pdf_front.save()
pdf_back.save()
# --- Combine front & back into one duplex‑ready PDF ---
from PyPDF2 import PdfReader, PdfWriter

out = PdfWriter()
front_pages = PdfReader("deck_front.pdf").pages
back_pages  = PdfReader("deck_back.pdf").pages

for f, b in zip(front_pages, back_pages):
    out.add_page(f)
    out.add_page(b)

with open("deck_duplex.pdf", "wb") as fh:
    out.write(fh)
#print("Created deck_front.pdf and deck_back.pdf (4×2 grid)")
print("Created deck_duplex.pdf – front/back interleaved")
#print("Done!  Check hitster_deck.pdf and cards/ folders.")
