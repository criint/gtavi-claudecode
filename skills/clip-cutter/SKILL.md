---
name: clip-cutter
description: Cut a picked moment into a finished 1080x1920 vertical clip with word-by-word captions, and a hook box. Use after moment-finder, or when the user says "cut it", "make the clip", "make it vertical".
---

# Clip cutter

Run:

`python "${CLAUDE_PLUGIN_ROOT}/scripts/cut.py" jobs/<id> --pick <n> --layout fill|blur|facecam --hook "TEXT"`

- `fill`: crop the game video to fill the frame. Default for gameplay.
- `blur`: full video centered over a blurred copy. Use when cropping would cut off the action.
- `facecam`: gameplay with the streamer's camera shown. Use for reactions.

Before running:

1. The source must pass `source-gate` (proof frame, fresh, dupes, subtitles, send test).
2. If the clip will be remixed (the default), cut WITHOUT `--hook`/`--title`; `remix` adds the teaser and punchline text. Otherwise get 3 hook options from `hook-writer`.

After running:

1. Output is an mp4 in `media/edits`. Check it is 1080x1920, the hook shows in the first 2 seconds, captions are readable. No credit text is burned into the video; the poster credits the creator in the post.
2. Run `remix` on it (payoff-first edit), then `rule-check` on the remix. Fix and re-cut until it passes.
3. Trim 7 to 30 seconds for most clips. End on the payoff.
4. Show the human the file, and the caption text, and ask for "yes". Do not upload anything.
