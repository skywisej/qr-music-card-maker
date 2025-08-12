# QR Music Deck (Hitster-like, personal use)

This is a small static web app that plays Spotify tracks from printed QR cards, without revealing artist/title/year until you flip the card. It’s designed for personal use (family game nights) and uses the Spotify Web Playback SDK + OAuth PKCE.

## Live structure (GitHub Pages)

```
/ (repo root on GitHub Pages)
├─ login.html
├─ login-callback.html
├─ card-template-v7.html
├─ cards/
│  ├─ html/           (auto‑generated card pages, one per track)
│  └─ qr/             (auto‑generated PNG QR codes that point to cards/html/*.html)
├─ data/
│  └─ tracks.csv      (your track list — artist,title,year,spotify_uri, etc.)
├─ scripts/
│  └─ generate_cards-fixed.py
└─ README.md
```

## Requirements

- Spotify **Premium** (per device attempting playback). Free accounts can scan, but playback calls return 403.
- Modern mobile browser (iOS Safari 15+, Android Chrome 90+ recommended).
- GitHub Pages (or any static host with HTTPS).

## First‑time setup

1. **Spotify App Settings**
   - In the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/), create an app (or reuse your existing one).
   - Add Redirect URI: `https://<your-username>.github.io/<your-repo>/login-callback.html`
   - Copy the **Client ID** and paste it into `login.html` and `login-callback.html` (already set in the patched files if you used mine/this repo path).

2. **Data file**
   - Put your song list in `data/tracks.csv` (see the sample header in the generator script).

3. **Generate cards**
   - Run `scripts/generate_cards-fixed.py`.
   - It will:
     - Build `cards/html/*.html` using `card-template-v7.html`
     - Create `cards/qr/*.png` QR codes pointing at those HTML pages
     - Embed a cache‑buster `?v=v7` to avoid stale pages on phones

4. **Deploy**
   - Commit and push all changes to your GitHub repo.
   - Ensure GitHub Pages is enabled for the repo (main branch /docs not required, root is fine).

## Playing the game

- Open `login.html` on your phone and log in with your own Spotify Premium account.
- You’ll land on the first card page (black screen + play triangle).
- Tap to play/pause. Tap again to reveal **Scan Next**; then scan the next printed card.
- If someone else wants to use their own phone to scan+play, they also need **Premium** and must log in on their phone.

## Common issues & fixes

- **403 on play()**: The account is likely **not Premium** or the Web Playback device hasn’t been activated yet. The app now attempts a transfer before play. Still failing? Open the Spotify app and check “Connect to a device”; you should see **QR Music Deck** appear.
- **Token expired**: After ~1 hour you may see a 401. The page will redirect you to `login.html`. Log in again and continue.
- **Scanner doesn’t detect**: The app uses native `BarcodeDetector` when available and falls back to `jsQR` from a CDN. Ensure good lighting and 6–10 inches from the card.
- **Wrong account**: If a shared device logs in as the wrong person, edit `login.html`, temporarily add `show_dialog=true` to the authorize URL, or clear browser site data and log in again.

## Host‑only playback mode (optional)

If you frequently play with one shared speaker, you can run **host‑only playback**:
- **Idea**: Only the host device (Premium) controls Spotify. All other phones scan and **send** the track URI to the host over a tiny realtime channel (e.g., Firebase Realtime Database or Ably). The host listens and plays the requested track.
- Benefits: Non‑Premium phones can still scan and advance the game; only the host needs Premium and a stable audio output.
- Implementation outline is in `docs/host-mode.md` (to be added).

## Development notes

- Card pages are cache‑busted with `?v=v7` based on `VERSION_TAG`. If you make significant changes, bump the tag in `generate_cards-fixed.py` and re-run.
- The template intentionally hides track metadata (no title/artist/year/album art) while playing.
- Everything is static HTML+JS; no server required unless you enable host‑only mode.
