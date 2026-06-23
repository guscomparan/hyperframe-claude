# Composition layout — title, captions, intro, follow, audio

Exact patterns `build_comp.py` emits. All overlays are `class="clip"` on tracks **above** the
video (track 0). Tracks: 0 video, 1 video-audio, 2 stickers, 3 captions, 4 title, 5 SFX,
6 music.

## Title card (persistent, editable, dark glass)

- **Band height = the hairline, measured per video — never hardcode.** Run
  `python3 edit/detect_head_bounds.py <name>` → writes `videos/<name>/hairline.txt` (top of hair)
  and `videos/<name>/chin.txt` (chin floor for stickers); `build_comp.py` reads the hairline.
  `#title-card { position:absolute; top:0; height:<hairline>px; display:flex; align-items:center;
  justify-content:center }` centers the card in the band between the top of frame and where the
  hair starts. Verify on a rendered frame that it never touches the hair; re-measure for every
  new video (different framing → different hairline).
- Card: **centered text**, two lines allowed, square corners, auto-fit base **66px** (0.75×).
  Dark glass — translucent but a near-black fill (not the old gray), faint rim.
  ```css
  #title-card .card {
    display:inline-block; color:#fff; font-weight:800; text-transform:uppercase;
    letter-spacing:1px; line-height:1.12; padding:22px 36px; border-radius:0;
    max-width:880px; font-size:66px; text-align:center;
    background: rgba(3,4,7,0.46);                      /* DARK translucent (not gray) */
    border: 1.5px solid rgba(255,255,255,0.12);        /* faint rim */
    backdrop-filter: blur(18px) saturate(125%);        /* liquid glass */
    -webkit-backdrop-filter: blur(18px) saturate(125%);
    box-shadow: 0 10px 34px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.14);
    text-shadow: 0 2px 12px rgba(0,0,0,.7);
  }
  ```
  Auto-fit loop: start 66px, shrink by 3 until height ≤ `font*1.12*2 + 48` (≤2 lines), floor 40.
- Editable via composition variables on `<html data-composition-variables=...>`:
  `title` (string) and `accent` (color). Read with `window.__hyperframes.getVariables()`.
  Override at render: `--variables '{"title":"...","accent":"#487d00"}'`.
- **Note:** if `backdrop-filter` doesn't sample the video in render, the translucent fill
  still shows the video through — verify on a real rendered frame.

## Captions (karaoke, white-on-block house style)

- Band centered at chest (`#captions { top:1180px; height:440px; display:flex; align-items:center;
  justify-content:center }`), same zone as stickers.
- White fill + black outline, no container box:
  ```css
  .cgroup .cbg { display:inline-block; max-width:920px; text-align:center; }   /* no background */
  .cgroup .w {
    display:inline-block; padding:2px 10px; color:#fff;
    -webkit-text-stroke:5px #000; paint-order:stroke fill;     /* black outline behind white */
    background-color:transparent; border-radius:0;             /* square block when highlighted */
    text-shadow:0 2px 6px rgba(0,0,0,.35);
  }
  ```
- Active (karaoke) word: a **square accent block appears behind it** —
  `tl.set(ws,{backgroundColor:ACCENT,scale:1.05})`, revert to
  `tl.set(ws,{backgroundColor:"transparent",scale:1})`. **Transient**: only the current word is
  lit; the block clears as the next word activates. ACCENT (`#487d00` green default) is the
  editable `accent` variable. (Previous styles — black fill + white outline w/ green active fill,
  and a black pill + white text — in git history.)
- **Mutual exclusion with stickers** (the load-bearing rule): build sticker on-screen windows
  `[start-0.05, start+dur+0.05]`; for each caption group compute the largest free sub-window
  via `free_window(gs,ge)` (drop if < 0.4s left). Verify zero real overlap before render:
  ```python
  for s in sticks:
    a,b = s['start']-.05, s['start']+s['dur']+.05
    for g in groups:
      assert not (g['start']<b and g['end']>a) or (min(b,g['end'])-max(a,g['start']))<=0  # boundary touch ok
  ```
- Every group gets a hard `tl.set(el,{opacity:0,visibility:"hidden"}, g.end)` kill + a
  self-lint pass.

## Intro (zoom + camera SFX)

```js
tl.fromTo("#intro-wrap", {scale:1.18,opacity:0}, {scale:1,opacity:1,duration:1.3,ease:"power2.out"}, 0);
```
`#intro-wrap` is a **non-timed** div wrapping the video (animate the wrapper, not the clip —
the framework forces clip opacity to 1). Camera SFX clip at `data-start="0.05"`.

## Follow / CTA scene

Special-cased in `sticker_html()` when `brand=="follow"`: a `.follow-scene` flex column with
the user's circular avatar (`<user>-avatar.png`), an `@handle` pill, and a **CSS** SÍGUEME
button (red pill, white border, white "+" in a circle). Reuses the `#stk-{i}` id so the
generic scale-pop + pop-click apply. Avatar built by `scripts/make_avatar.py` (center-square
crop, circular mask, white ring + thin dark outline).

## Audio levels

```html
<audio id="base-audio" ... data-track-index="1" data-volume="1"></audio>
<audio id="bg-music" src="music/background-music.mp3" ... data-track-index="6" data-volume="0.178"></audio> <!-- -15 dB -->
<audio id="sfx-camera" src="assets/sfx/camera.mp3" data-start="0.05" data-duration="0.35" data-track-index="5" data-volume="0.7"></audio>
<!-- one pop-click per sticker on track 5, volume 0.6 -->
```
MUSIC/MUSIC_DB come from `config.py` (**default −15 dB**). `volume = 10^(dB/20)`: −15 dB → 0.178.
Music spans full `TOTAL` and hard-cuts at the end. `TOTAL` is read from `edit/edl.json` so it
tracks the cut automatically.
