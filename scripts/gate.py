"""Source gate: the checks a clip must pass BEFORE it is cut and posted.

Writes jobs/<id>/gate.json. check.py reads it and fails the clip if a check is missing or failed.

  python gate.py sheet  jobs/<id> [--start S --end E] [--every 2]   contact sheet to look at (never trust titles)
  python gate.py proof  jobs/<id> --at 12.5 --cue "new police livery, Lucia on screen"
                                                                     save a proof frame with a GTA 6-only cue
  python gate.py fresh  jobs/<id> [--max-hours 24] [--launch 2026-11-19]
                                                                     source younger than 24 h and after launch
  python gate.py dupes  jobs/<id> --query "speed gta 6 cops"         print search links (TikTok, X, YouTube)
  python gate.py dupes  jobs/<id> --found 2                          record how many pages already posted it (3+ = skip)
  python gate.py subs   jobs/<id> export --start S --end E           words.txt to proofread (one "start end word" per line)
  python gate.py subs   jobs/<id> apply words.txt                    write the corrected words back, then re-run cut.py
  python gate.py send   jobs/<id> --to "my friend who always crashes" --text "bro this is you"
  python gate.py status jobs/<id>                                    PASS/FAIL per check, exit 1 on any FAIL
"""
import argparse, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
sys.path.insert(0, str(Path(__file__).parent))
from common import load_json, run, save_json, tool

CHECKS = ["proof", "fresh", "dupes", "subs", "send"]
MAX_DUPES = 3


def gate_path(job):
    return Path(job) / "gate.json"


def load_gate(job):
    p = gate_path(job)
    return load_json(p) if p.exists() else {}


def put(job, key, value):
    g = load_gate(job)
    value["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    g[key] = value
    save_json(gate_path(job), g)


def source_of(job):
    c = load_json(Path(job) / "candidates.json")
    return c["source"], c


def cmd_sheet(a):
    src, c = source_of(a.job)
    s = a.start if a.start is not None else 0
    e = a.end if a.end is not None else s + 60
    out = Path(a.job) / "proof"; out.mkdir(exist_ok=True)
    n = max(1, int((e - s) / a.every))
    cols = 4; rows = (n + cols - 1) // cols
    img = out / f"sheet_{int(s)}-{int(e)}.jpg"
    run([tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s:.2f}", "-to", f"{e:.2f}", "-i", src,
         "-vf", f"fps=1/{a.every},scale=480:-2,tile={cols}x{rows}:padding=4", "-frames:v", "1", "-q:v", "3", str(img)])
    print(img)
    print(f"tiles left to right, top to bottom: tile k shows second {s:g} + k * {a.every:g}")


def cmd_proof(a):
    src, _ = source_of(a.job)
    out = Path(a.job) / "proof"; out.mkdir(exist_ok=True)
    img = out / f"proof_{a.at:.1f}.jpg"
    run([tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{a.at:.2f}", "-i", src, "-frames:v", "1", "-q:v", "2", str(img)])
    ok = bool(a.cue.strip())
    put(a.job, "proof", {"ok": ok, "frame": str(img), "time": a.at, "cue": a.cue})
    print(img)
    print("Look at the frame yourself: the cue must be something only GTA 6 has (Leonida/Vice City skyline, "
          "Lucia or Jason, the new HUD or police livery). The Twitch category and the title are not proof.")


def cmd_fresh(a):
    info_p = Path(a.job) / "info.json"
    info = load_json(info_p) if info_p.exists() else {}
    ts_ = info.get("timestamp") or info.get("release_timestamp")
    if ts_:
        made = datetime.fromtimestamp(float(ts_), timezone.utc)
        exact = True
    elif info.get("upload_date"):
        made = datetime.strptime(info["upload_date"], "%Y%m%d").replace(tzinfo=timezone.utc)
        exact = False
    elif a.created:
        made = datetime.fromisoformat(a.created).astimezone(timezone.utc); exact = True
    else:
        sys.exit("no creation time in info.json; pass --created 2026-11-20T08:15 (from the clip page)")
    age_h = (datetime.now(timezone.utc) - made).total_seconds() / 3600
    launch = datetime.fromisoformat(a.launch).replace(tzinfo=timezone.utc)
    # a date without a time can be up to 24 h older than it looks
    limit = a.max_hours if exact else a.max_hours + 24
    ok = age_h <= limit and made >= launch - timedelta(days=1)
    put(a.job, "fresh", {"ok": ok, "created": made.isoformat(), "age_hours": round(age_h, 1), "exact_time": exact,
                         "launch": a.launch})
    print(f"{'PASS' if ok else 'FAIL'}  created {made:%Y-%m-%d %H:%M} UTC, {age_h:.1f} h old"
          + ("" if exact else " (date only, time unknown)"))


def cmd_dupes(a):
    if a.query:
        q = quote_plus(a.query)
        print("Search these and count pages that already posted this exact moment:")
        print(f"  TikTok:  https://www.tiktok.com/search?q={q}")
        print(f"  X:       https://x.com/search?q={q}&f=live")
        print(f"  YouTube: https://www.youtube.com/results?search_query={q}&sp=EgIIAg%253D%253D")
        print("Then: python gate.py dupes <job> --found N")
    if a.found is not None:
        ok = a.found < MAX_DUPES
        put(a.job, "dupes", {"ok": ok, "found": a.found, "query": a.query})
        print(f"{'PASS' if ok else 'FAIL'}  {a.found} pages already have it" + ("" if ok else " (skip it or find a clearly new angle)"))


def cmd_subs(a):
    tp = Path(a.job) / "transcript.json"
    words = load_json(tp)
    if a.action == "export":
        if a.start is None or a.end is None:
            sys.exit("export needs --start and --end (the clip window in source seconds)")
        out = Path(a.job) / "words.txt"
        lines = [f"{w['s']:.2f} {w['e']:.2f} {w['w']}" for w in words if a.start <= w["s"] < a.end]
        out.write_text("# start end word  -- fix wrong words, delete words you cannot hear clearly, keep the times\n"
                       + "\n".join(lines) + "\n", encoding="utf-8")
        put(a.job, "subs", {"ok": False, "window": [a.start, a.end], "note": "exported, not reviewed yet"})
        print(out)
        print("Listen to the clip and correct this file. Never guess a word: delete it instead. "
              "Check in-game subtitles first so an NPC line is not put in the streamer's mouth.")
    else:
        g = load_gate(a.job).get("subs", {})
        win = g.get("window")
        if not win:
            sys.exit("run 'subs export' first")
        new = []
        for ln in Path(a.file).read_text(encoding="utf-8").splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            s, e, w = ln.split(None, 2)
            new.append({"w": w.strip(), "s": float(s), "e": float(e)})
        backup = tp.with_name(f"transcript.{int(time.time())}.bak.json")
        save_json(backup, words)
        merged = [w for w in words if not (win[0] <= w["s"] < win[1])] + new
        merged.sort(key=lambda w: w["s"])
        save_json(tp, merged)
        put(a.job, "subs", {"ok": True, "window": win, "words": len(new), "backup": str(backup)})
        print(f"PASS  {len(new)} proofread words written ({backup.name} kept). Re-run cut.py to burn them in.")


def cmd_send(a):
    ok = bool(a.to.strip())
    put(a.job, "send", {"ok": ok, "to": a.to, "text": a.text})
    print(f"{'PASS' if ok else 'FAIL'}  send test: {a.to} -> \"{a.text}\"")


def evaluate(job):
    g = load_gate(job)
    res = []
    for k in CHECKS:
        v = g.get(k)
        if not v:
            res.append((k, False, "missing"))
        else:
            res.append((k, bool(v.get("ok")), v.get("cue") or v.get("note") or v.get("created") or
                        (f"{v['found']} pages" if "found" in v else "") or v.get("to", "")))
    return res


def cmd_status(a):
    res = evaluate(a.job)
    for k, ok, d in res:
        print(f"{'PASS' if ok else 'FAIL'}  gate {k}" + (f"  [{d}]" if d else ""))
    bad = [r for r in res if not r[1]]
    print("GATE: " + ("FAIL" if bad else "PASS"))
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sheet"); p.add_argument("job"); p.add_argument("--start", type=float); p.add_argument("--end", type=float)
    p.add_argument("--every", type=float, default=2.0)
    p = sub.add_parser("proof"); p.add_argument("job"); p.add_argument("--at", type=float, required=True); p.add_argument("--cue", required=True)
    p = sub.add_parser("fresh"); p.add_argument("job"); p.add_argument("--max-hours", type=float, default=24)
    p.add_argument("--launch", default="2026-11-19"); p.add_argument("--created")
    p = sub.add_parser("dupes"); p.add_argument("job"); p.add_argument("--query"); p.add_argument("--found", type=int)
    p = sub.add_parser("subs"); p.add_argument("job"); p.add_argument("action", choices=["export", "apply"])
    p.add_argument("file", nargs="?"); p.add_argument("--start", type=float); p.add_argument("--end", type=float)
    p = sub.add_parser("send"); p.add_argument("job"); p.add_argument("--to", required=True); p.add_argument("--text", default="")
    p = sub.add_parser("status"); p.add_argument("job")
    a = ap.parse_args()
    if a.cmd == "subs" and a.action == "apply" and not a.file:
        sys.exit("subs apply needs the corrected words.txt")
    {"sheet": cmd_sheet, "proof": cmd_proof, "fresh": cmd_fresh, "dupes": cmd_dupes,
     "subs": cmd_subs, "send": cmd_send, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
