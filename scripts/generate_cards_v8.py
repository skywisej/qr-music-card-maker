
# ================================================================
# QR Music Deck Generator v8
# - Reads tracks from CSV and/or Spotify playlists
# - Fills metadata (title, artist, year) from Spotify if missing
# - Generates per-track HTML from a template with SPOTIFY_TRACK_URI
# - Builds front/back printable PDF with mirrored backs
# ================================================================

import os, sys, csv, re, argparse, math
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from typing import List, Dict, Any, Iterable
from dataclasses import dataclass

# Optional Spotify (only needed for playlist fetch or metadata fill)
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except Exception:
    spotipy = None

# Images / PDF
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyPDF2 import PdfReader, PdfWriter

# ---------------- Config Defaults ----------------
DEFAULT_TEMPLATE = Path("card-template-v7.html")  # or card-template-v7.1-debug.html while testing
DEFAULT_VERSION  = "v7.2"
DEFAULT_BASE_URL = ""  # e.g. "https://yourname.github.io/qr-music-card-maker/cards/html/"
DEFAULT_HTML_DIR = Path("cards/html")
DEFAULT_QR_DIR   = Path("cards/qrcodes")
DEFAULT_CSV      = Path("data/tracks.csv")

# Card layout (Letter portrait, 4 x 2 grid, 60 mm squares by default)
COLS = 3
ROWS = 4
CARD_W = 60 * mm
CARD_H = 60 * mm
X_START = 18 * mm   # left margin
Y_START = 22 * mm   # top margin from top edge for first row
Y_SHIFT = 0 * mm    # back side vertical tweak for duplex alignment

BACK_FONT     = "Helvetica"
TITLE_FONT_SZ = 9.0
ARTIST_FONT_SZ= 8.5
YEAR_FONT_SZ  = 22

# ---------------- Data Model ----------------
@dataclass
class Track:
    uri: str
    title: str
    artist: str
    year: str
    album: str = ""
    release_date: str = ""
    explicit: bool = False

# ---------------- Utilities ----------------
SPOTIFY_TRACK_ID_RE = re.compile(r"(?:spotify:track:|open\.spotify\.com/track/)?([A-Za-z0-9]{22})")

def norm_track_uri(s: str) -> str:
    s = s.strip()
    m = SPOTIFY_TRACK_ID_RE.search(s)
    if not m:
        return ""
    return "spotify:track:" + m.group(1)

def parse_year(release_date: str) -> str:
    rel = (release_date or "").strip()
    if not rel:
        return ""
    # release_date can be YYYY, YYYY-MM, or YYYY-MM-DD
    return rel.split("-")[0]

def ensure_dirs(*paths: Iterable[Path]):
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)

def wrap_lines(text: str, font: str, size: float, max_width: float) -> List[str]:
    # Simple word wrap using reportlab width measurement
    words = (text or "").split()
    lines = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if stringWidth(trial, font, size) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]  # cap at 3 lines for neat backs

# ---------------- Spotify helpers ----------------
def make_sp_client() -> Any:
    if spotipy is None:
        raise RuntimeError("spotipy not installed. Run: pip install spotipy python-dotenv")
    cid = os.getenv("SPOTIPY_CLIENT_ID")
    secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redir = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8080/callback")
    if not cid or not secret:
        raise RuntimeError("Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in .env")
    scope = "playlist-read-private user-read-email"
    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=cid,
            client_secret=secret,
            redirect_uri=redir,
            scope=scope
        )
    )

def fetch_playlist_tracks(sp: Any, playlist: str, limit: int | None = None) -> List[Track]:
    uri = norm_track_uri(playlist.replace("playlist:", "track:"))  # normalize; we'll handle playlist via API
    # Actually parse playlist id separately
    m = re.search(r"(?:spotify:playlist:|open\.spotify\.com/playlist/)([A-Za-z0-9]{22})", playlist)
    if not m:
        raise ValueError(f"Not a playlist URL/URI: {playlist}")
    pid = m.group(1)

    out: List[Track] = []
    seen = set()
    offset = 0
    got = 1
    while got:
        page = sp.playlist_items(pid, offset=offset, additional_types=("track",))
        items = page.get("items", [])
        got = len(items)
        offset += got
        for it in items:
            tr = it.get("track") or {}
            if not tr or tr.get("id") is None:
                continue
            tid = tr.get("id")
            if tid in seen: 
                continue
            seen.add(tid)
            uri = "spotify:track:" + tid
            artist_names = ", ".join(a["name"] for a in (tr.get("artists") or []))
            album = (tr.get("album") or {}).get("name","")
            rel = (tr.get("album") or {}).get("release_date","")
            out.append(Track(
                uri=uri,
                title=tr.get("name",""),
                artist=artist_names,
                year=parse_year(rel) or "",
                album=album,
                release_date=rel,
                explicit=bool(tr.get("explicit", False))
            ))
            if limit and len(out) >= limit:
                return out
        if not page.get("next"):
            break
    return out

def fill_missing_from_spotify(sp: Any, tracks: List[Track]) -> None:
    # batch lookup where year/title/artist missing
    need_ids = [t.uri.split(":")[-1] for t in tracks if not (t.title and t.artist and t.year)]
    for i in range(0, len(need_ids), 50):
        batch = need_ids[i:i+50]
        if not batch: 
            continue
        res = sp.tracks(batch).get("tracks", [])
        info = {tr["id"]: tr for tr in res if tr}
        for t in tracks:
            tid = t.uri.split(":")[-1]
            if tid in info:
                tr = info[tid]
                if not t.title:  t.title = tr.get("name","")
                if not t.artist: t.artist= ", ".join(a["name"] for a in (tr.get("artists") or []))
                if not t.year:
                    rel = (tr.get("album") or {}).get("release_date","")
                    t.year = parse_year(rel) or ""
                if not t.album:
                    t.album = (tr.get("album") or {}).get("name","")
                if not t.release_date:
                    t.release_date = (tr.get("album") or {}).get("release_date","")
                t.explicit = bool(tr.get("explicit", False))

# ---------------- CSV helpers ----------------
CSV_HEADER = ["uri","title","artist","year","album","release_date","explicit"]

def read_csv(path: Path) -> List[Track]:
    if not path.exists(): 
        return []
    rows = []
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            uri = norm_track_uri(row.get("uri",""))
            if not uri:
                continue
            rows.append(Track(
                uri=uri,
                title=row.get("title",""),
                artist=row.get("artist",""),
                year=row.get("year",""),
                album=row.get("album",""),
                release_date=row.get("release_date",""),
                explicit=(str(row.get("explicit","")).lower() in ("1","true","yes"))
            ))
    return rows

def write_csv(path: Path, tracks: List[Track]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for t in tracks:
            w.writerow(dict(
                uri=t.uri,
                title=t.title,
                artist=t.artist,
                year=t.year,
                album=t.album,
                release_date=t.release_date,
                explicit=("true" if t.explicit else "false")
            ))

# ---------------- HTML & QR ----------------
def build_card_html(template_text: str, track_uri: str) -> str:
    return template_text.replace("SPOTIFY_TRACK_URI", track_uri)

def generate_assets(tracks: List[Track], template_path: Path, base_url: str, version_tag: str, html_dir: Path, qr_dir: Path) -> List[str]:
    template = template_path.read_text(encoding="utf-8")
    ensure_dirs(html_dir, qr_dir)

    html_names: List[str] = []
    for idx, t in enumerate(tracks, start=1):
        html_name = f"track{idx:04}.html"
        html_path = html_dir / html_name
        html = build_card_html(template, t.uri)
        html_path.write_text(html, encoding="utf-8")
        # QR points to hosted URL if base_url given; otherwise relative path
        url = f"{base_url}{html_name}" if base_url else html_name
        # always add cache buster
        if "?" in url: 
            url = f"{url}&v={version_tag}"
        else:
            url = f"{url}?v={version_tag}"
        qr_img = qrcode.make(url)
        qr_path = qr_dir / (html_name.replace(".html",".png"))
        qr_img.save(qr_path)
        html_names.append(html_name)
    return html_names

# ---------------- PDF building ----------------
def build_pdfs(tracks: List[Track], html_names: List[str]):
    # Front and Back PDFs
    front = canvas.Canvas("deck_front.pdf", pagesize=letter)
    back  = canvas.Canvas("deck_back.pdf",  pagesize=letter)

    cells_per_page = COLS * ROWS
    page_count = math.ceil(len(tracks) / cells_per_page)

    def draw_front_cell(pdf, ix, col, row, qr_path):
        x = X_START + col * CARD_W
        y = letter[1] - Y_START - (row + 1) * CARD_H
        S = CARD_W - 20*mm
        x_qr = x + (CARD_W - S) / 2
        y_qr = y + (CARD_H - S) / 2
        pdf.drawImage(str(qr_path), x_qr, y_qr, width=S, height=S)
        pdf.rect(x, y, CARD_W, CARD_H, stroke=1, fill=0)

    def draw_back_cell(pdf, ix, col, row, title, artist, year):
        x = X_START + col * CARD_W
        y = letter[1] - Y_START - (row + 1) * CARD_H
        mirror_x = letter[0] - x - CARD_W
        y_back   = y - Y_SHIFT
        pdf.rect(mirror_x, y_back, CARD_W, CARD_H, stroke=1, fill=0)

        # Year centered near top
        year_txt = (year or "")
        pdf.setFont(BACK_FONT, YEAR_FONT_SZ)
        w = stringWidth(year_txt, BACK_FONT, YEAR_FONT_SZ)
        pdf.drawString(mirror_x + (CARD_W - w)/2, y_back + CARD_H - 18*mm, year_txt)

        # Title (wrap)
        maxw = CARD_W - 12*mm
        py = y_back + CARD_H/2 + 6*mm
        for line in wrap_lines(title or "", BACK_FONT, TITLE_FONT_SZ, maxw):
            w = stringWidth(line, BACK_FONT, TITLE_FONT_SZ)
            pdf.setFont(BACK_FONT, TITLE_FONT_SZ)
            pdf.drawString(mirror_x + (CARD_W - w)/2, py, line)
            py -= 4.2*mm

        # Artist (wrap)
        py -= 2.5*mm
        for line in wrap_lines(artist or "", BACK_FONT, ARTIST_FONT_SZ, maxw):
            w = stringWidth(line, BACK_FONT, ARTIST_FONT_SZ)
            pdf.setFont(BACK_FONT, ARTIST_FONT_SZ)
            pdf.drawString(mirror_x + (CARD_W - w)/2, py, line)
            py -= 4.0*mm

    # iterate pages
    for page in range(page_count):
        start = page * cells_per_page
        end   = min(start + cells_per_page, len(tracks))
        subset = tracks[start:end]
        # Fronts
        for i, t in enumerate(subset):
            col = i % COLS
            row = i // COLS
            qr_path = Path("cards/qrcodes") / (f"track{start + i + 1:04}.png")
            draw_front_cell(front, start+i, col, row, qr_path)
        front.showPage()

        # Backs
        for i, t in enumerate(subset):
            col = i % COLS
            row = i // COLS
            draw_back_cell(back, start+i, col, row, t.title, t.artist, t.year)
        back.showPage()

    front.save()
    back.save()

    # Interleave into deck_duplex.pdf
    out = PdfWriter()
    fpages = PdfReader("deck_front.pdf").pages
    bpages = PdfReader("deck_back.pdf").pages
    for fp, bp in zip(fpages, bpages):
        out.add_page(fp)
        out.add_page(bp)
    with open("deck_duplex.pdf", "wb") as fh:
        out.write(fh)
    print("Created deck_duplex.pdf – front/back interleaved")

# ---------------- Main ----------------
def main():
    ap = argparse.ArgumentParser(description="QR Music Deck Generator v8")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="CSV file to read/write tracks")
    ap.add_argument("--write-csv", action="store_true", help="Write combined track list back to --csv")
    ap.add_argument("--playlists", nargs="*", default=[], help="Spotify playlist URLs/URIs to import")
    ap.add_argument("--limit", type=int, default=None, help="Max tracks per playlist to import")
    ap.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="Public base URL for hosted cards/html")
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="HTML template with SPOTIFY_TRACK_URI placeholder")
    ap.add_argument("--version", type=str, default=DEFAULT_VERSION, help="Cache buster tag for ?v=")
    ap.add_argument("--dedupe", action="store_true", help="De-duplicate tracks by URI")
    ap.add_argument("--non-explicit-only", action="store_true", help="Drop explicit tracks (handy for family accounts)")
    args = ap.parse_args()

    # Load existing CSV if present
    tracks = read_csv(args.csv)

    # Import from playlists if requested
    if args.playlists:
        if spotipy is None:
            print("spotipy is required for playlist import. pip install spotipy python-dotenv")
            sys.exit(2)
        sp = make_sp_client()
        for pl in args.playlists:
            fetched = fetch_playlist_tracks(sp, pl, limit=args.limit)
            print(f"Imported {len(fetched)} tracks from {pl}")
            tracks.extend(fetched)

    # Normalize & dedupe
    normed = []
    seen = set()
    for t in tracks:
        uri = norm_track_uri(t.uri)
        if not uri:
            continue
        if args.non_explicit_only and t.explicit:
            continue
        key = uri
        if args.dedupe and key in seen:
            continue
        seen.add(key)
        normed.append(Track(uri=uri, title=t.title, artist=t.artist, year=t.year,
                            album=t.album, release_date=t.release_date, explicit=t.explicit))
    tracks = normed

    # Fill missing metadata if needed
    if any(not (t.title and t.artist and t.year) for t in tracks) and args.playlists:
        sp = 'sp' if isinstance(sp, str) else (locals().get('sp') if 'sp' in locals() else None)
        if sp is None and spotipy is not None:
            sp = make_sp_client()
        if sp is not None:
            fill_missing_from_spotify(sp, tracks)
        else:
            print("Skipping metadata fill (spotipy not available)")

    # Optionally write back CSV
    if args.write_csv:
        write_csv(args.csv, tracks)
        print(f"Wrote {len(tracks)} tracks to {args.csv}")

    # Generate HTML + QR + PDFs
    html_names = generate_assets(tracks, args.template, args.base_url, args.version, DEFAULT_HTML_DIR, DEFAULT_QR_DIR)
    build_pdfs(tracks, html_names)
    print(f"Created {len(html_names)} card HTML files in {DEFAULT_HTML_DIR} and QR PNGs in {DEFAULT_QR_DIR}")

if __name__ == "__main__":
    main()
