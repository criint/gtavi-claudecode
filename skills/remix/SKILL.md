---
name: remix
description: Turn a finished clip into a payoff-first edit (teaser, white flash and whoosh, one slow-mo or freeze, punchline, ad disclosure) so it counts as original. Use after clip-cutter and before rule-check, or when the user says "remix", "make it original", "add a teaser" or "add the punchline".
---

# Remix (payoff-first edit)

Instagram says subtitles plus a credit do not make a clip original, and YouTube cuts reach for plain reposts. The edit is the product. Every clip gets this treatment before it is posted.

## The formula

[TEASER 2 to 4 s with hook text] -> [WHITE FLASH + WHOOSH] -> [SETUP] -> [PAYOFF with one slow-mo or freeze] -> [REACTION + PUNCHLINE] -> hard cut

1. Teaser: the funniest second first, with the hook text. Tease the END: start the body at the setup so there are 8+ seconds of new footage before the payoff returns. Let the word or action finish.
2. Cut with `clip-cutter` first WITHOUT `--hook` and `--title` (the remix adds its own text). Captions stay.
3. Look at the clip, then write `jobs/<id>/edits/clip_<n>_remix.json`:

```
{
  "clip": "jobs/<id>/edits/clip_1.mp4",
  "teaser": {"start": 11.2, "end": 13.8, "text": "GTA 6 COPS DON'T DO ROLEPLAY"},
  "keep": [[2.0, 15.5]],
  "effect": {"type": "freeze", "at": 12.4, "dur": 0.8},
  "punchline": {"start": 13.0, "end": 15.5, "text": "INSURANCE: DENIED"},
  "disclosure": "Werbung"
}
```

All times are seconds in the input clip. `effect` is `freeze` (0.5 to 1 s) or `slowmo` (`"speed": 0.35` to `0.5`), once per clip, only where it is funny. `disclosure` is required for paid campaign clips (Content Rewards wants it at the start of the video); leave it out only for unpaid posts.

4. Dry run: `python "${CLAUDE_PLUGIN_ROOT}/scripts/remix.py" <spec.json> --dry-run`. Fix every WARN you can (length 12 to 20 s, teaser 2 to 4 s, payoff at 70 to 85 %).
5. Render: same command without `--dry-run`. Output `clip_<n>_remix.mp4` + `.json`.
6. Check the hook frame, the flash, the payoff and the last frame yourself (extract them with ffmpeg and look). Text never covers the face.

## Text rules

- Text adds context, it never describes. Banned pattern: "STREAMER DOES X".
- Hook with a search keyword in frame one: GTA 6, Lucia, Jason, Vice City, or the streamer's name.
- Punchlines are short tags: "GRANDMA DOWN", "INSURANCE: DENIED", "CALL DROPPED".
- No emoji in burned-in text (the script strips them). Never put words in the streamer's mouth.

Then run `rule-check`. It fails a clip that has no remix or, for campaign clips, no disclosure.
