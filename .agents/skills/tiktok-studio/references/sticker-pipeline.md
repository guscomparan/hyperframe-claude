# Sticker pipeline — Kie AI generation + keying

Cartoon "sticker" overlays in one consistent flat die-cut style. Two models, same style.

## Fresh per video — never recycle (read first)

Every video gets its OWN images, generated from ITS transcript. Do **not** reuse the sticker
PNGs sitting in `assets/stickers/` from a previous video just because the names match — they
were drawn for different content and will look off-topic (the #1 quality failure). Workflow for
a new video: read the transcript → list the moments worth an image → generate each one fresh →
map them in `MENTIONS`. If you're reusing the project folder, treat `assets/stickers/` as the
previous video's and regenerate from scratch (ideally work in a fresh folder — see SKILL.md
Hard Rule 8).

## Everything is a CARTOON grounded in the REAL asset (no plain logos, no blind generation)

The house style is flat cartoon die-cut stickers — BUT each is a cartoon **redraw of the real
thing**, fed to `nano-banana-edit` as an `image_urls` reference so it stays faithful:

- **Real brand** → download the real logo, upload to Kie, `nano-banana-edit` → cartoon die-cut
  sticker (faithful shape/colors/lettering). Plain downloaded logos read as "stock"; blind
  `nano-banana` guesses go off-model — **both were rejected by the user.**
- **Real, named person** → fetch the photo (Wikimedia `Special:FilePath/<Name>.jpg?width=600`
  or official press) and `nano-banana-edit` it into a **cartoon caricature that keeps the
  likeness**, framed as a rounded card / circle. (Bare-photo via `scripts/make_avatar.py` still
  works, but the channel's current style is cartoon-from-photo.)
- **Country** → download the real flag, `nano-banana-edit` → cute cartoon waving flag.
- **Concept / action / analogy** → minimal cartoon **scene, 1–3 characters** (`nano-banana`).

A full upload-ref → `nano-banana-edit` → key generator for a sticker set lives at
`videos/<name>/gen_stickers.py` (write one per video; see git history for a worked example with
LOGO / FLAG / emblem prompts). Reference PNGs: GitHub org avatars
`github.com/<Org>.png?size=600` (real logos as PNG) and the Wikimedia API `thumburl` for
flags/seals/SVGs: `commons.wikimedia.org/w/api.php?action=query&titles=File:<F>&prop=imageinfo&iiprop=url&iiurlwidth=600&format=json`.

## Kie AI API (key in `.env` as `KIEAI_API_KEY`)

- **Create task**: `POST https://api.kie.ai/api/v1/jobs/createTask`
  ```json
  { "model": "google/nano-banana",
    "input": { "prompt": "...", "output_format": "png", "aspect_ratio": "1:1" } }
  ```
- **Poll**: `GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=...` → wait for
  `data.state == "success"`; image URL at `JSON.parse(data.resultJson).resultUrls[0]`.
  States: `waiting | queuing | generating | success | fail`.
- **Gotchas (verified):**
  - Send `User-Agent: Mozilla/5.0` on **every** call and download the result with
    `curl -A "Mozilla/5.0"` — the result CDN 403s the default Python urllib UA.
  - File upload host is `https://kieai.redpandaai.co/api/file-base64-upload`
    (the `api.kie.ai/api/file-base64-upload` path 404s). Body:
    `{"base64Data":"data:image/png;base64,...","uploadPath":"images/refs","fileName":"x.png"}`
    → use `data.downloadUrl` (expires ~3 days).

## Brand logos — faithful redraw (`google/nano-banana-edit`)

Kie's fetcher can't pull Wikimedia directly. Download locally, upload, then edit:

```
ref sources:
  Wikimedia  https://commons.wikimedia.org/wiki/Special:FilePath/<File>.svg?width=600
  GitHub org https://github.com/<Org>.png?size=600     # official logo when not on Commons
```

```json
{ "model": "google/nano-banana-edit",
  "input": { "prompt": "<EDIT_PROMPT>", "image_urls": ["<uploaded downloadUrl>"],
             "output_format": "png", "aspect_ratio": "1:1" } }
```

EDIT_PROMPT: *"Redraw this exact logo as a flat cartoon die-cut sticker. Keep the original
shape, proportions, lettering and brand colors faithful to the reference. Add one thick white
die-cut sticker border with a thin dark outline enclosing the whole logo. Bold clean cartoon
vector look, centered, plain solid white background, no extra elements, no shadows."*

Brands used here: Claude (Wikimedia `Claude AI symbol.svg`), Anthropic (`Anthropic logo.svg`),
DeepSeek (`DeepSeek logo.svg`), MiniMax (`github.com/MiniMax-AI`), Moonshot
(`github.com/MoonshotAI`).

## Situations — multi-character scenes (`google/nano-banana`)

Don't stop at brands. For any action/analogy/example the speaker gives, generate a
**2–3 character cartoon scene** that acts it out. Base style appended to every prompt:

> *Flat cartoon sticker illustration, bold thick dark outlines, thick white die-cut sticker
> border with a thin dark outline, vibrant saturated colors, soft cel shading, expressive cute
> cartoon characters, centered scene, plain solid white background, no shadows, no background
> scenery, no text unless specified.*

Examples that worked: money "scientists shoveling dollar bundles into a robot's open head";
distillation "big robot pouring glowing liquid through a funnel into a small robot's head";
chef "master chef cooking while a sneaky apprentice copies his recipe"; export controls
"suited bald eagle with a USA badge holding a chip crate from a reaching panda with a China
armband". For a wordmark inside a scene, say the icon AND text are "enclosed together inside
one single thick white die-cut border" or the text comes out borderless.

## Background keying (NOT u2net)

u2net is human-tuned and eats the white sticker border. Use corner flood-fill:
`scripts/key_sticker.py <raw.png> <out.png>` — flood-fills from the 4 corners + edge
midpoints (tolerance ~28/channel), softens the alpha (MinFilter 3 + GaussianBlur 1.2), crops
to bbox. Keeps the white die-cut border intact. For scenes with white *inside* enclosed
shapes that should stay, that's fine — flood-fill only removes background-connected white.

**Do not** put a button/CTA with a large white "sticker paper" field through keying — the
enclosed white can't be reached and shows as a box. Build CTAs (e.g. the SÍGUEME button) in
CSS instead.

## Placement

In `build_comp.py`, `stk_geom(brand)` sizes each sticker to ~450×450 visual area scaled by
aspect ratio and centers it at chest height (`top = 1400 - height/2`, floored at 1120). Map
mentions in `build_cut.py`'s `MENTIONS = [(src_word_start, sticker_id)]`. Every pop fires
`assets/sfx/pop-click.mp3` on the same frame.
