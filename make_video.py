#!/usr/bin/env python3
"""Build the GraphMem demo video from REAL demo output only (streaming writer).

Every on-screen word comes from /tmp/demo_data.json (produced by
graphmem.demo.run_comparison) or the build's own source strings.
No fabricated dialogue, no fake UI, no invented metrics.
Claims: multi-hop traversal ranked by token overlap (per memory.py) -
never embeddings/vector search.
"""
import json
import math
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 30
FRAMES = "/tmp/graphmem_frames"
OUT = os.path.expanduser("~/workspace/earning/graph-hacks/graphmem-build/demo_video.mp4")

F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
F_MONOB = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
F_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
F_SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG = (13, 17, 23)
WHITE = (235, 238, 243)
DIM = (150, 160, 175)
GREEN = (6, 214, 160)
RED = (239, 71, 111)
BLUE = (17, 138, 178)
YELLOW = (255, 209, 102)
PURPLE = (157, 78, 221)
ORANGE = (244, 162, 97)

PALETTE = {"User": YELLOW, "Fact": GREEN, "Event": BLUE,
           "Session": PURPLE, "Procedure": RED, "Agent": ORANGE}

data = json.load(open("/tmp/demo_data.json"))
GRAPH = data["graph"]
N_NODES, N_EDGES = len(GRAPH["nodes"]), len(GRAPH["edges"])

_counter = [0]

def emit(img):
    img.save(f"{FRAMES}/f{_counter[0]:05d}.png")
    _counter[0] += 1
    return img  # return so caller may keep the last frame

def fade_last(last, n=6):
    blk = Image.new("RGB", (W, H), (0, 0, 0))
    for i in range(n):
        emit(Image.blend(last, blk, (i + 1) / n))

def font(path, size):
    return ImageFont.truetype(path, size)

def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def header_bar(d, title, color):
    d.rectangle([0, 0, W, 78], fill=(18, 23, 30))
    d.rectangle([0, 78, W, 80], fill=color)
    d.text((36, 22), title, font=font(F_SANSB, 30), fill=WHITE)

def typewriter_panel(title, bar_color, prompt_line, body_text,
                     secs, body_size=25, body_color=WHITE, hold_secs=1.2,
                     mono=True):
    fnt = font(F_MONO if mono else F_SANS, body_size)
    base = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(base)
    header_bar(d, title, bar_color)
    y = 110
    if prompt_line:
        d.text((60, y), prompt_line, font=font(F_MONOB, 22), fill=YELLOW)
        y += 46
    lh = int(body_size * 1.45)
    n = int(secs * FPS)
    last = None
    for i in range(n):
        frac = (i + 1) / n
        shown = body_text[:int(len(body_text) * frac)]
        img = base.copy()
        dd = ImageDraw.Draw(img)
        shown_lines = wrap(dd, shown, fnt, W - 140)
        yy = y
        for ln in shown_lines:
            dd.text((60, yy), ln, font=fnt, fill=body_color)
            yy += lh
        if i < n - 1 and shown_lines:
            cx = 60 + dd.textlength(shown_lines[-1], font=fnt)
            dd.rectangle([cx + 4, yy - lh, cx + 16, yy - 8], fill=GREEN)
        last = emit(img)
    for _ in range(int(hold_secs * FPS)):
        last = emit(last.copy())
    fade_last(last)

def static_title_panel(secs):
    n = int(secs * FPS)
    texts = [
        ("GraphMem", 84, WHITE, F_SANSB, 190),
        ("graph memory for agents", 40, GREEN, F_SANS, 300),
        ("Recall via multi-hop traversal \u2014 not flat lookup", 28, DIM, F_SANS, 368),
        ("Graph Hacks \u00b7 WeMakeDevs \u00d7 FalkorDB", 30, YELLOW, F_SANSB, 470),
        ("Track 02: Agent Memory and Coordination", 26, DIM, F_SANS, 518),
        ("Habib Ur Rehman \u00b7 github.com/habib-analyst", 24, DIM, F_SANS, 600),
    ]
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    last = None
    for i in range(n):
        img = Image.new("RGB", (W, H), BG)
        dd = ImageDraw.Draw(img)
        k = min(1.0, i / (FPS * 1.2))
        for (txt, size, col, fp, y) in texts:
            tw = probe.textlength(txt, font=font(fp, size))
            dd.text(((W - tw) / 2, y), txt, font=font(fp, size),
                    fill=tuple(int(c * k) for c in col))
        last = emit(img)
    fade_last(last)

def graph_panel(secs):
    nodes, edges = GRAPH["nodes"], GRAPH["edges"]
    n = len(nodes)
    cx, cy, R, NR = W / 2, 348, 200, 40
    pos = {}
    for i, nd in enumerate(nodes):
        a = 2 * math.pi * i / max(n, 1) - math.pi / 2
        pos[nd["id"]] = (cx + R * math.cos(a), cy + R * math.sin(a))
    short = {}
    for nd in nodes:
        t = " ".join((nd.get("text", "") or nd.get("name", "")).split())
        short[nd["id"]] = (t[:30] + "\u2026") if len(t) > 30 else t
    node_idx = {nd["id"]: i for i, nd in enumerate(nodes)}
    nfr = int(secs * FPS)
    stagger = 6
    last = None
    for fi in range(nfr):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        header_bar(d, "MEMORY GRAPH \u2014 what the demo run learned", GREEN)
        for e in edges:
            a, b = pos.get(e["src"]), pos.get(e["dst"])
            if not a or not b:
                continue
            t0 = max(node_idx[e["src"]], node_idx[e["dst"]]) * stagger + 12
            if fi < t0:
                continue
            is_handoff = e["type"] == "HANDOFF"
            d.line([a, b], fill=RED if is_handoff else (120, 130, 145),
                   width=4 if is_handoff else 2)
            if is_handoff:
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                tag = "HANDOFF"
                tw = d.textlength(tag, font=font(F_SANSB, 18))
                d.rectangle([mx - tw / 2 - 8, my - 36, mx + tw / 2 + 8, my - 10],
                            fill=RED)
                d.text((mx - tw / 2, my - 34), tag, font=font(F_SANSB, 18),
                       fill=(13, 17, 23))
        for i, nd in enumerate(nodes):
            t0 = i * stagger
            if fi < t0:
                continue
            al = min(1.0, (fi - t0) / 10)
            x, y = pos[nd["id"]]
            col = PALETTE.get(nd["label"], DIM)
            col = tuple(int(c * al + BG[j] * (1 - al)) for j, c in enumerate(col))
            d.ellipse([x - NR, y - NR, x + NR, y + NR], fill=col,
                      outline=(255, 255, 255), width=2)
            lbl = nd["label"]
            lsize = 15
            while lsize > 8 and d.textlength(lbl, font=font(F_SANSB, lsize)) > 2 * NR - 12:
                lsize -= 1
            tw = d.textlength(lbl, font=font(F_SANSB, lsize))
            d.text((x - tw / 2, y - lsize), lbl, font=font(F_SANSB, lsize),
                   fill=(13, 17, 23))
            st = short[nd["id"]]
            tw2 = d.textlength(st, font=font(F_SANS, 13))
            d.text((x - tw2 / 2, y + NR + 8), st, font=font(F_SANS, 13), fill=DIM)
        leg = [("Fact", GREEN, "semantic"), ("Event", BLUE, "episodic"),
               ("Procedure", RED, "procedural"), ("Agent", ORANGE, ""),
               ("Session", PURPLE, ""), ("User", YELLOW, "")]
        lx = 60
        for lab, col, kind in leg:
            d.ellipse([lx, 620, lx + 18, 638], fill=col)
            txt = lab + (f" ({kind})" if kind else "")
            d.text((lx + 24, 618), txt, font=font(F_SANS, 16), fill=DIM)
            lx += d.textlength(txt + "    ", font=font(F_SANS, 16)) + 40
        d.text((60, 668),
               f"{N_NODES} nodes \u00b7 {N_EDGES} edges \u2014 HANDOFF edges in red",
               font=font(F_SANS, 20), fill=WHITE)
        last = emit(img)
    fade_last(last)

def takeaway_panel(secs):
    lines = [
        ("Amnesiac agent: re-debugs the same Safari 500 ticket every time.", WHITE, False),
        ("Memory agent: recalls the cause from the graph, applies", WHITE, False),
        ("the known fix, and hands context to a second agent.", WHITE, False),
        ("", WHITE, False),
        ("Recall = 2-hop traversal, ranked by token overlap.", GREEN, True),
        ("No embeddings. No vector index. Just the graph.", GREEN, True),
        ("", WHITE, False),
        ("Track 02: Agent Memory and Coordination \u2014 Graph Hacks (WeMakeDevs \u00d7 FalkorDB)", YELLOW, False),
        ("Habib Ur Rehman (Pakistan) \u00b7 github.com/habib-analyst", DIM, False),
    ]
    n = int(secs * FPS)
    last = None
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    wrapped = []
    for (txt, col, bold) in lines:
        fnt = font(F_SANSB if bold else F_SANS, 30)
        if not txt:
            wrapped.append(("", col, fnt))
        else:
            for wln in wrap(probe, txt, fnt, W - 180):
                wrapped.append((wln, col, fnt))
    for i in range(n):
        img = Image.new("RGB", (W, H), BG)
        dd = ImageDraw.Draw(img)
        header_bar(dd, "TAKEAWAY", YELLOW)
        k = min(1.0, i / (FPS * 1.0))
        yy = 130
        for (txt, col, fnt) in wrapped:
            if txt:
                dd.text((90, yy), txt, font=fnt,
                        fill=tuple(int(c * k) for c in col))
            yy += 50
        last = emit(img)
    fade_last(last)

def main():
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    TASK = data["task"]
    amn = data["amnesiac"]
    mem = data["with_memory"]
    r1 = mem[0]

    static_title_panel(7)
    typewriter_panel("THE TASK", BLUE, "$ python demo_compare.py", TASK,
                     8, body_size=30)

    typewriter_panel("RUN A \u2014 MEMORY OFF  (amnesiac agent, fresh graph each time)",
                     RED, "ticket #1 arrives \u2014 same report as always:",
                     "Agent: " + amn[0]["reply"], 10, body_size=27)
    typewriter_panel("RUN A \u2014 MEMORY OFF  (amnesiac agent, fresh graph each time)",
                     RED, "ticket #2 arrives \u2014 identical report:",
                     "Agent: " + amn[1]["reply"], 9, body_size=27)
    typewriter_panel("RUN A \u2014 MEMORY OFF", RED, "",
                     "Same ticket \u2192 same answer: the agent starts from scratch. Every. Single. Time.",
                     5, body_size=30, body_color=RED, mono=False)

    typewriter_panel("RUN B \u2014 MEMORY ON  (shared graph \u00b7 planner \u2192 coder team)",
                     GREEN, "ticket #1 (first sighting) \u2014 researcher investigates:",
                     "Researcher: " + r1["research"], 12, body_size=24)
    typewriter_panel("RUN B \u2014 MEMORY ON", GREEN,
                     "planner recalls the learned fact from the graph:",
                     "Planner: " + r1["plan"], 9, body_size=24)
    typewriter_panel("RUN B \u2014 MEMORY ON", GREEN,
                     "HANDOFF planner \u2192 coder (written to the graph):",
                     r1["handoff_summary"], 9, body_size=24, body_color=ORANGE)
    typewriter_panel("RUN B \u2014 MEMORY ON", GREEN,
                     "coder implements with the handed-off context:",
                     "Coder: " + r1["implementation"], 9, body_size=24)
    typewriter_panel("RUN B \u2014 MEMORY ON", GREEN,
                     "ticket #2 (same report, repeat):",
                     "Researcher, planner and coder all recall the cause instantly "
                     "from the graph \u2014 no re-debugging, known fix applied, "
                     "context handed off again.", 7, body_size=28,
                     body_color=GREEN, mono=False)

    graph_panel(16)
    takeaway_panel(9)

    print(f"frames: {_counter[0]}  ({_counter[0] / FPS:.1f}s)")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS),
        "-i", f"{FRAMES}/f%05d.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
        "-movflags", "+faststart", OUT,
    ], check=True, capture_output=True, text=True)
    print("wrote", OUT)

if __name__ == "__main__":
    main()
