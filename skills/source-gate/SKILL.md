---
name: source-gate
description: Check a source before cutting - real GTA 6 proof frame, fresh (under 24 h), not already posted by 3+ pages, subtitles proofread, send test. Use after moment-finder or live-mode and before clip-cutter, or when the user asks "is this clip usable".
---

# Source gate

Most candidates should fail here. Expect to reject 9 out of 10. All commands: `python "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" <cmd> jobs/<id> ...`. Results go to `jobs/<id>/gate.json`; `rule-check` fails any clip whose gate is missing or failed.

1. **Look, don't trust titles.** `sheet jobs/<id> --start S --end E` builds a contact sheet (one frame every 2 s). Open the image and look. Reject: no real facecam or a tiny cam, VTuber/PNGtuber, sexual content, animal harm, slurs, story spoilers, cutscenes, leaks.
2. **Prove it is GTA 6.** Many streamers play GTA V under the GTA 6 category. `proof jobs/<id> --at T --cue "<what only GTA 6 has>"` saves the frame. Valid cues: Lucia or Jason, the Leonida/Vice City skyline, the new HUD or police livery. Open the saved frame and confirm; if unsure, it fails.
3. **Fresh.** `fresh jobs/<id>` reads the creation time (needs under 24 h, after launch). If the time is missing, pass `--created` from the clip page.
4. **Dedupe.** `dupes jobs/<id> --query "<streamer> gta 6 <moment>"` prints search links. Ask the human to check them (or use the browser tools), then `dupes jobs/<id> --found N`. 3 or more pages = skip or find a clearly new angle.
5. **Subtitles.** `subs jobs/<id> export --start S --end E` writes `words.txt`. Proofread against the audio with the human: fix wrong words, delete what you cannot hear clearly, check in-game subtitles so an NPC line is not given to the streamer. `subs jobs/<id> apply jobs/<id>/words.txt`, then re-run `clip-cutter`.
6. **Send test.** `send jobs/<id> --to "<who a viewer would send it to>" --text "<what they would type>"`. No obvious friend means no post.
7. `status jobs/<id>` must say GATE: PASS before cutting.

Prefer mid-size streamers with real facecams over the biggest names: big-streamer moments are on 20 pages within hours. Only streamers inside a campaign you joined, or who gave permission.
