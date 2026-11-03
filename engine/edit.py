"""The editing-quality layer: turns the raw talking-avatar clip into a finished, branded reel.

  1. cut plan    split the video at sentence boundaries; alternate wide shots and punch-in zooms
                 (jump-cut feel), and swap some sentences for stock b-roll while the voice continues
  2. timeline    render each piece at exactly 25 fps and join them
  3. audio       voice clean-up + background music that ducks under the voice, then two-pass
                 loudness normalisation to -14 LUFS (Instagram/YouTube/TikTok level)
  4. graphics    animated word-by-word captions in brand font/colours inside the Reels/Shorts safe zone,
                 hook text for the first 2 s, CTA at the end, logo
  5. extras      optional brand intro/outro clips, and a cover/thumbnail image
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import FPS, H, W
from .media import ffmpeg, loudness, probe

# Reels/Shorts cover the top ~220 px (header) and bottom ~420 px (caption, buttons) and the right
# ~140 px of the lower half (like/comment/share). Everything important stays inside this box.
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT = 230, H - 440, W - 150


# ---------------------------------------------------------------- helpers

def ass_color(hex_color, alpha=0):
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass_escape(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", r"\N")


def frames(t):
    return int(round(t * FPS))


def clean_words(words, script=""):
    """Whisper sometimes splits words ("b", "-roll"); glue fragments back and keep the script's spelling."""
    out = []
    for w in words:
        if out and re.match(r"^[-'’]", w["w"]):
            out[-1] = {"w": out[-1]["w"] + w["w"], "s": out[-1]["s"], "e": w["e"]}
        else:
            out.append(dict(w))
    tokens = script.split()
    if len(tokens) == len(out):
        for w, t in zip(out, tokens):
            w["w"] = t
    return out


def sentences(words):
    """Group word timings into sentences: [(start, end, [words])]."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?।]$", w["w"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    # Long sentences get one extra cut in the middle so no shot lasts much more than ~5 s.
    split = []
    for s in out:
        if s[-1]["e"] - s[0]["s"] > 5.5 and len(s) >= 8:
            mid = len(s) // 2
            split += [s[:mid], s[mid:]]
        else:
            split.append(s)
    return [(s[0]["s"], s[-1]["e"], s) for s in split]


# ---------------------------------------------------------------- 1. cut plan

def cut_plan(words, duration, brand, broll_clips):
    sents = sentences(words)
    bounds = [0.0] + [sents[i][0] - 0.04 for i in range(1, len(sents))] + [duration]
    bounds = [frames(b) / FPS for b in bounds]
    punch = brand.get("punch_ins", True)
    pieces = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a < 1 / FPS:
            continue
        zoom = 1.0
        if punch:
            zoom = 1.16 if i % 2 == 0 else 1.0  # hook (first sentence) starts tight, then alternate
        pieces.append({"start": a, "end": b, "kind": "talk", "zoom": zoom})

    # B-roll on evenly spaced middle sentences (never the hook or the last line with the CTA).
    clips = list(broll_clips)
    cand = list(range(1, len(pieces) - 1))
    if clips and cand:
        step = max(1, len(cand) // len(clips))
        chosen = cand[::step][:len(clips)]
        seconds = float(brand.get("broll", {}).get("seconds", 2.4))
        for idx, clip in zip(sorted(chosen, reverse=True), clips):
            p = pieces[idx]
            length = p["end"] - p["start"]
            b_end = p["start"] + min(seconds, length)
            b_end = frames(b_end) / FPS
            new = [{"start": p["start"], "end": b_end, "kind": "broll", "clip": clip["path"], "zoom": 1.0}]
            if p["end"] - b_end >= 0.5:
                new.append({"start": b_end, "end": p["end"], "kind": "talk", "zoom": 1.0 if p["zoom"] > 1 else 1.16})
            else:
                new[0]["end"] = p["end"]
            pieces[idx:idx + 1] = new
    if punch:  # two talking shots back to back must differ, otherwise the cut is invisible
        for prev, cur in zip(pieces, pieces[1:]):
            if prev["kind"] == cur["kind"] == "talk" and prev["zoom"] == cur["zoom"]:
                cur["zoom"] = 1.0 if prev["zoom"] > 1 else 1.16
    return pieces


# ---------------------------------------------------------------- 2. timeline

def render_piece(piece, talking, out):
    n = frames(piece["end"]) - frames(piece["start"])
    if piece["kind"] == "broll":
        src_dur = probe(piece["clip"])["duration"]
        ss = 0.5 if src_dur > (n / FPS) + 1 else 0
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},"
              # slow push-in so stock footage never looks static
              f"zoompan=z='min(1+0.0022*on,1.08)':d=1:s={W}x{H}:fps={FPS}:"
              "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
              f"tpad=stop_mode=clone:stop_duration=5,setsar=1,format=yuv420p")
        ffmpeg("-ss", f"{ss:.2f}", "-i", piece["clip"], "-an", "-vf", vf, "-frames:v", n,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-r", FPS, out)
        return
    z = piece["zoom"]
    vf = f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if z > 1.0:
        zw, zh = int(W * z) // 2 * 2, int(H * z) // 2 * 2
        # Zoom toward the face (upper-middle of the frame), not the chest.
        vf += f",scale={zw}:{zh},crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.30"
    vf += ",tpad=stop_mode=clone:stop_duration=5,setsar=1,format=yuv420p"
    ffmpeg("-ss", f"{piece['start']:.3f}", "-i", talking, "-an", "-vf", vf, "-frames:v", n,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "15", "-r", FPS, out)


def build_timeline(pieces, talking, work):
    pdir = work / "pieces"
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    lines = []
    for i, p in enumerate(pieces):
        out = pdir / f"{i:03d}_{p['kind']}.mp4"
        render_piece(p, talking, out)
        lines.append(f"file '{out.name}'")
    (pdir / "list.txt").write_text("\n".join(lines) + "\n")
    timeline = work / "timeline.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", pdir / "list.txt", "-c", "copy", timeline)
    return timeline


# ---------------------------------------------------------------- 3. audio

def build_audio(voice, duration, client, seed, work, log):
    music = client.music_files()
    vol = float(client.brand.get("music_volume", 0.16))
    mix = work / "mix.wav"
    # Voice: remove rumble, gentle compression so quiet words stay audible.
    vchain = "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2"
    if music:
        track = music[int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(music)]
        log(f"music: {track.name}")
        fade_out = max(0.0, duration - 1.2)
        graph = (f"[0:a]aresample=48000,{vchain},apad=pad_dur=0.6,asplit=2[v][key];"
                 f"[1:a]aresample=48000,volume={vol},afade=t=in:d=0.6,afade=t=out:st={fade_out:.2f}:d=1.2[m];"
                 # Ducking: music dips ~8-10 dB whenever the voice is talking.
                 f"[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[duck];"
                 f"[v][duck]amix=inputs=2:duration=first:normalize=0[a]")
        ffmpeg("-i", voice, "-stream_loop", "-1", "-i", track, "-filter_complex", graph, "-map", "[a]",
               "-t", f"{duration:.3f}", "-ac", "2", "-c:a", "pcm_s16le", mix)
    else:
        ffmpeg("-i", voice, "-af", f"aresample=48000,{vchain},apad", "-t", f"{duration:.3f}",
               "-ac", "2", "-c:a", "pcm_s16le", mix)
    # Two-pass loudness normalisation: measure, then correct precisely to -14 LUFS / -1.5 dBTP.
    m = loudness(mix)
    final = work / "audio_final.wav"
    if m and m["lufs"] > -70:
        ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['lufs']}:measured_TP={m['true_peak']}:"
              f"measured_LRA={m['lra']}:measured_thresh=-70:linear=true")
    else:
        ln = "loudnorm=I=-14:TP=-1.5:LRA=11"
    ffmpeg("-i", mix, "-af", f"{ln},aresample=48000", "-c:a", "pcm_s16le", final)
    return final, bool(music)


# ---------------------------------------------------------------- 4. graphics

def write_ass(words, duration, brand, on_screen_text, path):
    st = brand["style"]
    font = st.get("font", "Arial Black")
    size = int(st.get("caption_size", 84))
    primary, accent, outline = ass_color(st["primary"]), ass_color(st["accent"]), ass_color(st["outline"])
    hook_bg = ass_color(st.get("hook_bg", "#000000"), alpha=0x30)
    cy = int(H * float(st.get("caption_y", 0.64)))
    cy = min(max(cy, SAFE_TOP + 200), SAFE_BOTTOM - 60)
    per_line = int(st.get("words_per_line", 3))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{primary},{primary},{outline},&H80000000,-1,0,0,0,100,100,1,0,1,7,4,5,90,170,0,1
Style: Hook,{font},74,{primary},{primary},{hook_bg},{hook_bg},-1,0,0,0,100,100,0,0,3,18,0,8,90,90,{SAFE_TOP + 190},1
Style: CTA,{font},62,{ass_color(st.get('hook_bg', '#000000'))},{primary},{accent},{accent},-1,0,0,0,100,100,0,0,3,16,0,8,110,110,{SAFE_TOP + 190},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pos = rf"\pos({(90 + SAFE_RIGHT) // 2},{cy})"
    for i in range(0, len(words), per_line):
        group = words[i:i + per_line]
        group_end = words[i + per_line]["s"] if i + per_line < len(words) else min(duration, group[-1]["e"] + 0.4)
        for j, cur in enumerate(group):
            start = cur["s"]
            end = group[j + 1]["s"] if j + 1 < len(group) else group_end
            if end <= start:
                continue
            parts = []
            for w in group:
                t = ass_escape(w["w"].upper())
                if w is cur:
                    # Active word: brand accent colour and a quick "pop".
                    t = rf"{{\c{accent}\fscx88\fscy88\t(0,90,\fscx106\fscy106)}}{t}{{\r}}"
                parts.append(t)
            intro = r"\fscx92\fscy92\t(0,80,\fscx100\fscy100)" if j == 0 else ""
            ev.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{{{pos}{intro}}}{' '.join(parts)}")
    if on_screen_text:
        first_end = sentences(words)[0][1] if words else 2.0
        hook_end = min(max(2.2, first_end + 0.3), 4.0, duration)
        ev.append(f"Dialogue: 2,{ass_time(0)},{ass_time(hook_end)},Hook,,0,0,0,,"
                  rf"{{\fad(80,180)\fscx85\fscy85\t(0,140,\fscx100\fscy100)}}{ass_escape(on_screen_text.upper())}")
    cta = brand.get("cta")
    if cta and duration > 8:
        ev.append(f"Dialogue: 2,{ass_time(duration - 2.4)},{ass_time(duration)},CTA,,0,0,0,,"
                  rf"{{\fad(150,0)\fscx85\fscy85\t(0,160,\fscx100\fscy100)}}{ass_escape(cta.upper())}")
    path.write_text(head + "\n".join(ev) + "\n", encoding="utf-8")
    return path


def finish(timeline, audio, ass, client, duration, out):
    logo = client.file(client.brand.get("logo"))
    fontsdir = client.font_dir()
    subs = f"subtitles={ass.name}" + (f":fontsdir={fontsdir}" if fontsdir else "")
    inputs = ["-i", timeline, "-i", audio]
    if logo:
        inputs += ["-i", logo]
        graph = (f"[0:v]{subs}[s];[2:v]scale=150:-1,format=rgba,colorchannelmixer=aa=0.9[lg];"
                 f"[s][lg]overlay=x={W - 150 - 70}:y={SAFE_TOP + 10}:format=auto[v]")
    else:
        graph = f"[0:v]{subs}[v]"
    ffmpeg(*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "1:a", "-t", f"{duration:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
           Path(out).resolve(), cwd=ass.parent)


def add_bumpers(main, client, work, out):
    """Brand intro/outro clips, if the client has them."""
    intro, outro = client.file(client.brand.get("intro")), client.file(client.brand.get("outro"))
    if not intro and not outro:
        shutil.move(main, out)
        return
    clips = [c for c in (intro, main, outro) if c]
    inputs, chains, labels = [], [], ""
    for i, c in enumerate(clips):
        inputs += ["-i", c]
        has_audio = probe(c)["has_audio"]
        chains.append(f"[{i}:v]fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[v{i}]")
        if has_audio:
            chains.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        else:
            d = probe(c)["duration"]
            chains.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{d:.3f}[a{i}]")
        labels += f"[v{i}][a{i}]"
    graph = ";".join(chains) + f";{labels}concat=n={len(clips)}:v=1:a=1[v][a]"
    ffmpeg(*inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
           "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out)


# ---------------------------------------------------------------- 5. cover

def find_font(brand, size):
    cands = [brand["style"].get("font_file"), "/System/Library/Fonts/Supplemental/Arial Black.ttf",
             "/System/Library/Fonts/Supplemental/Impact.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    for c in cands:
        if c and Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def make_cover(timeline, at, text, brand, out):
    frame = out.with_suffix(".frame.png")
    ffmpeg("-ss", f"{at:.2f}", "-i", timeline, "-frames:v", 1, frame)
    img = Image.open(frame).convert("RGB")
    frame.unlink()
    if text:
        st = brand["style"]
        draw = ImageDraw.Draw(img)
        font = find_font(brand, 108)
        words, lines, cur = text.upper().split(), [], ""
        for w in words:  # wrap to the safe width
            trial = f"{cur} {w}".strip()
            if draw.textlength(trial, font=font) > W - 200 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        lines.append(cur)
        y = int(H * 0.36) - len(lines) * 62
        for i, line in enumerate(lines):
            tw = draw.textlength(line, font=font)
            color = st["accent"] if i == len(lines) - 1 else st["primary"]
            draw.text(((W - tw) / 2, y), line, font=font, fill=color, stroke_width=9, stroke_fill=st["outline"])
            y += 124
    img.save(out, quality=92)
    return out


# ---------------------------------------------------------------- entry point

def edit_reel(manifest, client, row, broll_clips, work, out, log):
    work, out = Path(work).resolve(), Path(out).resolve()
    words = clean_words(json.loads(Path(manifest["words"]).read_text()), row.get("script", ""))
    (work / "words_clean.json").write_text(json.dumps(words, indent=1, ensure_ascii=False))
    voice_dur = float(manifest["duration"])
    duration = round(voice_dur + 0.35, 2)  # a short breath after the last word
    pieces = cut_plan(words, duration, client.brand, broll_clips)
    (work / "cut_plan.json").write_text(json.dumps(pieces, indent=1))
    log(f"cut plan: {len(pieces)} shots ({sum(p['kind'] == 'broll' for p in pieces)} b-roll, "
        f"{sum(p['kind'] == 'talk' and p['zoom'] > 1 for p in pieces)} punch-ins)")
    timeline = build_timeline(pieces, manifest["video"], work)
    audio, has_music = build_audio(manifest["voice"], duration, client, str(row.get("id")), work, log)
    ass = write_ass(words, duration, client.brand, row.get("on_screen_text", ""), work / "captions.ass")
    main = work / "main.mp4"
    finish(timeline, audio, ass, client, duration, main)
    add_bumpers(main, client, work, out)
    cover = make_cover(timeline, min(0.6, duration / 2), row.get("on_screen_text", ""), client.brand,
                       out.with_name("cover.jpg"))
    return {"pieces": pieces, "music": has_music, "cover": str(cover), "duration": duration}
