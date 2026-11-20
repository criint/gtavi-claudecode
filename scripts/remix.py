"""Payoff-first remix of a finished vertical clip (the edit that makes a clip "yours").

Takes a clip made by cut.py (1080x1920, captions already burned in) and a small JSON spec, and renders:

  [TEASER 2-4 s + hook text] -> [WHITE FLASH + WHOOSH] -> [SETUP ... PAYOFF with one slow-mo or freeze]
  -> [REACTION + PUNCHLINE text] -> hard cut

Optional: an ad disclosure ("Werbung" / "#ad") in the first seconds, which paid campaigns require at the start.

usage: python remix.py spec.json [--dry-run]

spec.json (all times are seconds in the INPUT clip; the script maps them onto the output timeline):
{
  "clip": "jobs/<id>/edits/clip_1.mp4",
  "out": "jobs/<id>/edits/clip_1_remix.mp4",          optional, default <clip>_remix.mp4
  "teaser": {"start": 11.2, "end": 13.8, "text": "GTA 6 COPS DON'T DO ROLEPLAY"},
  "keep": [[2.0, 15.5]],                                optional, default the whole clip
  "effect": {"type": "freeze", "at": 12.4, "dur": 0.8},  or {"type": "slowmo", "at": 12.0, "dur": 1.2, "speed": 0.5}
  "punchline": {"start": 13.0, "end": 15.5, "text": "INSURANCE: DENIED"},
  "disclosure": "Werbung",                               optional, shown 0 to 2.5 s at the top
  "flash": true, "whoosh": true,                         optional, default true
  "text_y": 820                                          optional, y of hook/punchline (top of the game panel)
}
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, run, save_json, load_json, tool
from cut import esc, ts, W, H

EMOJI = re.compile("[\U00010000-\U0010FFFF☀-➿️]")


def clean_text(s):
    """Burned-in text: no emoji (libass draws them as boxes), upper case, single spaces."""
    return " ".join(EMOJI.sub("", s or "").upper().split())


def plan(spec, dur):
    """Return (segments, teaser_len). Segment = dict(kind, a, b, rate|hold, out0, out1)."""
    t = spec["teaser"]
    if not 0 <= t["start"] < t["end"] <= dur:
        sys.exit(f"teaser {t['start']}-{t['end']} is outside the clip (0-{dur:.2f})")
    segs = [{"kind": "teaser", "a": t["start"], "b": t["end"], "rate": 1.0}]
    eff = spec.get("effect") or {}
    for a, b in spec.get("keep") or [[0, dur]]:
        a, b = max(0.0, float(a)), min(dur, float(b))
        if b <= a:
            continue
        at = eff.get("at")
        if eff and a < at < b:
            if eff["type"] == "freeze":
                segs += [{"kind": "body", "a": a, "b": at, "rate": 1.0},
                         {"kind": "freeze", "a": at, "b": at, "hold": float(eff.get("dur", 0.8))},
                         {"kind": "body", "a": at, "b": b, "rate": 1.0}]
            elif eff["type"] == "slowmo":
                e = min(b, at + float(eff.get("dur", 1.0)))
                sp = float(eff.get("speed", 0.5))
                if not 0.25 <= sp < 1:
                    sys.exit("slowmo speed must be between 0.25 and 0.99 (0.35 to 0.5 works best)")
                segs += [{"kind": "body", "a": a, "b": at, "rate": 1.0},
                         {"kind": "slow", "a": at, "b": e, "rate": sp},
                         {"kind": "body", "a": e, "b": b, "rate": 1.0}]
            else:
                sys.exit("effect type must be freeze or slowmo")
            eff = {}  # only once per clip
        else:
            segs.append({"kind": "body", "a": a, "b": b, "rate": 1.0})
    segs = [s for s in segs if s["kind"] == "freeze" or s["b"] - s["a"] > 0.05]
    o = 0.0
    for s in segs:
        s["out0"] = o
        o += s["hold"] if s["kind"] == "freeze" else (s["b"] - s["a"]) / s["rate"]
        s["out1"] = o
    return segs, segs[0]["out1"]


def map_t(segs, t):
    """Input time -> output time, body only (never the teaser)."""
    for s in segs[1:]:
        if s["kind"] == "freeze":
            if abs(t - s["a"]) < 1e-6:
                return s["out0"]
            continue
        if s["a"] <= t <= s["b"]:
            return s["out0"] + (t - s["a"]) / s["rate"]
    return None


def atempo(rate):
    chain, r = [], rate
    while r < 0.5:
        chain.append("atempo=0.5"); r /= 0.5
    chain.append(f"atempo={r:.4f}")
    return ",".join(chain)


def build_ass(spec, segs, T, total):
    y = int(spec.get("text_y", 820))
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Punch,Arial Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,8,2,8,60,60,0,1
Style: Ad,Arial,52,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,10,0,8,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pop = "{\\fscx112\\fscy112\\t(0,100,\\fscx100\\fscy100)}"
    tt = clean_text(spec["teaser"].get("text", ""))
    if tt:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(T)},Punch,,0,0,0,,{{\\pos({W // 2},{y})}}{pop}{esc(tt)}")
    p = spec.get("punchline") or {}
    pt = clean_text(p.get("text", ""))
    if pt:
        a, b = map_t(segs, p["start"]), map_t(segs, p["end"])
        if a is None:
            sys.exit("punchline start is not inside the kept body of the clip")
        b = total if b is None else b
        ev.append(f"Dialogue: 1,{ts(a)},{ts(b)},Punch,,0,0,0,,{{\\pos({W // 2},{y})}}{pop}{esc(pt)}")
    if spec.get("disclosure"):
        ev.append(f"Dialogue: 2,{ts(0)},{ts(min(2.5, total))},Ad,,0,0,0,,{{\\pos({W // 2},50)}}{esc(spec['disclosure'])}")
    return hdr + "\n".join(ev) + "\n"


def warnings(spec, segs, T, total):
    w = []
    if not 12 <= total <= 20:
        w.append(f"length {total:.1f}s: the guide's sweet spot is 12 to 20 s (12 to 16 preferred)")
    if not 2 <= T <= 4.5:
        w.append(f"teaser is {T:.1f}s: aim for 2 to 4 s and let the word or action finish")
    back = map_t(segs, spec["teaser"]["start"])
    if back is not None and back - T < 8:
        w.append(f"the teased moment comes back after only {back - T:.1f}s of new footage; aim for 8+ s "
                 "(tease the END, start the body at the setup)")
    p = spec.get("punchline")
    if p and map_t(segs, p["start"]) is not None:
        pos = map_t(segs, p["start"]) / total
        if not 0.6 <= pos <= 0.95:
            w.append(f"punchline starts at {pos:.0%} of the runtime; the payoff usually sits at 70 to 85 %")
    if not p:
        w.append("no punchline: one short joke on the reaction is what makes the edit yours")
    if not spec.get("effect"):
        w.append("no slow-mo or freeze on the payoff")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--dry-run", action="store_true", help="print the plan, render nothing")
    a = ap.parse_args()
    sp = Path(a.spec)
    spec = json.loads(sp.read_text(encoding="utf-8"))
    clip = Path(spec["clip"])
    if not clip.exists():
        sys.exit(f"clip not found: {clip}")
    out = Path(spec.get("out") or clip.with_name(clip.stem + "_remix.mp4"))
    p = ffprobe(clip)
    dur = float(p["format"]["duration"])
    has_audio = any(s.get("codec_type") == "audio" for s in p["streams"])
    segs, T = plan(spec, dur)
    total = segs[-1]["out1"]
    for s in segs:
        what = f"hold {s['hold']:.2f}s" if s["kind"] == "freeze" else f"in {s['a']:.2f}-{s['b']:.2f}" + (f" x{s['rate']}" if s["rate"] != 1 else "")
        print(f"{s['kind']:7s} {what:24s} -> out {s['out0']:.2f}-{s['out1']:.2f}")
    for w in warnings(spec, segs, T, total):
        print("WARN  " + w)
    if a.dry_run:
        return

    ass = out.with_suffix(".ass")
    ass.write_text(build_ass(spec, segs, T, total), encoding="utf-8")
    AF = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    f, labels = [], []
    for i, s in enumerate(segs):
        if s["kind"] == "freeze":
            f.append(f"[0:v]trim=start={s['a']:.3f}:duration=0.034,setpts=PTS-STARTPTS,"
                     f"tpad=stop_mode=clone:stop_duration={s['hold']:.3f},trim=duration={s['hold']:.3f},setpts=PTS-STARTPTS[v{i}]")
            f.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={s['hold']:.3f},{AF}[a{i}]")
        else:
            vs = "setpts=PTS-STARTPTS" if s["rate"] == 1 else f"setpts=(PTS-STARTPTS)/{s['rate']}"
            f.append(f"[0:v]trim=start={s['a']:.3f}:end={s['b']:.3f},{vs},fps=30[v{i}]")
            if has_audio:
                at = "" if s["rate"] == 1 else "," + atempo(s["rate"])
                f.append(f"[0:a]atrim=start={s['a']:.3f}:end={s['b']:.3f},asetpts=PTS-STARTPTS{at},{AF}[a{i}]")
            else:
                d = (s["b"] - s["a"]) / s["rate"]
                f.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f},{AF}[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    f.append("".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][ac]")
    v_last, a_last = "vc", "ac"
    if spec.get("flash", True):
        f.append(f"color=c=white:s={W}x{H}:r=30:d=0.35,format=rgba,fade=t=out:st=0.05:d=0.30:alpha=1,"
                 f"setpts=PTS+{T:.3f}/TB[fl]")
        f.append(f"[{v_last}][fl]overlay=eof_action=pass:format=auto[vf]")
        v_last = "vf"
    if spec.get("whoosh", True):
        st = max(0.0, T - 0.25)
        f.append("anoisesrc=d=0.5:c=pink:r=48000:a=0.5,highpass=f=500,lowpass=f=7000,"
                 "afade=t=in:d=0.25:curve=exp,afade=t=out:st=0.25:d=0.25," + AF +
                 f",adelay={int(st * 1000)}|{int(st * 1000)}[wh]")
        f.append(f"[{a_last}][wh]amix=inputs=2:duration=first:normalize=0[am]")
        a_last = "am"
    sub = str(ass).replace("\\", "/").replace(":", "\\:")
    f.append(f"[{v_last}]subtitles='{sub}',format=yuv420p[vo]")
    f.append(f"[{a_last}]loudnorm=I=-14:TP=-1.5:LRA=11,{AF}[ao]")
    run([tool("ffmpeg"), "-y", "-v", "error", "-i", str(clip), "-filter_complex", ";".join(f),
         "-map", "[vo]", "-map", "[ao]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out)])

    side = clip.with_suffix(".json")
    meta = load_json(side) if side.exists() else {}
    meta.update({"file": str(out), "hook": " / ".join(x for x in [clean_text(spec["teaser"].get("text", "")),
                                                                   clean_text((spec.get("punchline") or {}).get("text", ""))] if x),
                 "remix": {"spec": str(sp), "teaser_len": round(T, 2), "length": round(total, 2),
                           "effect": (spec.get("effect") or {}).get("type"), "disclosure": spec.get("disclosure")}})
    save_json(out.with_suffix(".json"), meta)
    print(out)


if __name__ == "__main__":
    main()
