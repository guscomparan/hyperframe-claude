# HyperFrames gotchas (learned the hard way)

## Overlays must be clips OVER the video, or they vanish in render

When a composition has a `<video>` track, the render pipeline composites decoded video frames
as layers ordered by track index. **Plain (non-`class="clip"`) page elements render in the
base layer UNDER the video** — invisible in the MP4 even though they look fine in a plain
browser, pass lint/validate/inspect, and have a high CSS `z-index`.

Fix: every overlay container (captions, title, stickers, SFX, music) must be a
`class="clip"` element with `data-start`/`data-duration`/`data-track-index` on a track number
above the video (video=0). Children inside a clip can be plain divs animated by GSAP.

Proven with a minimal test: a non-clip text div over a video disappeared; the same text inside
a clip div rendered above the video.

## Animate a non-timed wrapper, not the clip, for opacity

The framework forces `opacity:1` on active clips. To fade something (e.g. the intro zoom,
a cutout), wrap it in a **non-timed** div and animate the wrapper.

## Headless seek screenshots are unreliable for QC

Injecting `tl.seek(t)` + a Chrome `--screenshot` fights the player runtime (it re-seeks/plays
from 0 under virtual-time) and video frames don't decode offline. For QC, render the real MP4
and extract frames with ffmpeg — the renderer is deterministic and authoritative. Use the
headless probe only for overlay-layout sanity, never for "is the timing right."

## Determinism

No `Math.random()`, `Date.now()`, `new Date()`, network fetches, or `repeat:-1`. Build
timelines synchronously (not inside async/promises/timeouts). Register on
`window.__timelines["<composition-id>"]`.

## index.html is generated — rebuild it after ANY cut change

`build_comp.py` overwrites `index.html` every run. Make all edits in `build_comp.py` (and
`build_cut.py`), never directly in `index.html`, or they're lost on the next rebuild.
**`export.sh`/`hyperframes render` do NOT run `build_comp.py`** — after re-cutting (new
`mentions.json`/`cut_words.json`) you must re-run `python3 edit/build_comp.py` or you'll render
a stale composition. Sanity-check: `index.html` mtime should be newer than `edit/mentions.json`.

## Sticker `<img>` clips: set explicit width AND height (not height:auto)

The render engine stretched sticker images vertically when they used `width:Npx` + CSS
`height:auto`. Always emit **both** `width` and `height` inline (computed from the PNG's real
aspect in `stk_geom`) and add `object-fit: contain` to the `.stk` rule. Do not rely on
`height:auto` for image clips in the render. Verify aspect on an actual rendered frame — plain
`file://` browser screenshots don't run the HyperFrames player (clips stay hidden → black), so
the only reliable check is a real `hyperframes render` frame.

## Kie result/CDN 403s

Send `User-Agent: Mozilla/5.0` on all Kie API calls and `curl -A "Mozilla/5.0"` for downloads.
Upload host is `kieai.redpandaai.co`, not `api.kie.ai`. (Full details in
[sticker-pipeline.md](sticker-pipeline.md).)
