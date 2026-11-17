import os, glob, json, random, asyncio, subprocess, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
PAGE_NAME = os.environ.get("PAGE_NAME", "")
W, H = 1080, 1920
VOICES = {"female": "bn-BD-NabanitaNeural", "male": "bn-BD-PradeepNeural"}

PALETTES = [
    ((15, 12, 41), (48, 43, 99)),
    ((10, 25, 47), (0, 120, 160)),
    ((30, 8, 50), (150, 30, 110)),
    ((5, 40, 30), (20, 130, 90)),
    ((40, 10, 10), (180, 60, 40)),
]

with open(os.path.join(os.path.dirname(__file__), "facts.json"), encoding="utf-8") as f:
    FACTS = json.load(f)


def find_font():
    for pat in ["/usr/share/fonts/**/NotoSansBengali-Bold.ttf",
                "/usr/share/fonts/**/NotoSansBengali*.ttf",
                "/usr/share/fonts/**/*Bengali*.ttf"]:
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise RuntimeError("Bangla font paoa jayni")


FONT_PATH = find_font()


def font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(FONT_PATH, size)


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_slide(text, palette, path, size=78, tag=""):
    top, bot = palette
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        px.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    d = ImageDraw.Draw(img)
    fnt = font(size)
    lines = wrap(d, text, fnt, W - 160)
    lh = int(size * 1.6)
    y = (H - lh * len(lines)) // 2
    for ln in lines:
        w = d.textlength(ln, font=fnt)
        d.text(((W - w) / 2 + 3, y + 3), ln, font=fnt, fill=(0, 0, 0))
        d.text(((W - w) / 2, y), ln, font=fnt, fill=(255, 255, 255))
        y += lh
    if tag:
        f2 = font(44)
        w = d.textlength(tag, font=f2)
        d.text(((W - w) / 2, H - 200), tag, font=f2, fill=(220, 220, 220))
    img.save(path)


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


async def tts(text, voice, path):
    await edge_tts.Communicate(text, voice).save(path)


def build_reel(slides, voice_key, out_path):
    voice = VOICES.get(voice_key, VOICES["female"])
    palette = random.choice(PALETTES)
    tmp = tempfile.mkdtemp()
    segs = []
    for i, text in enumerate(slides):
        png, mp3, seg = (os.path.join(tmp, f"{i}{e}") for e in (".png", ".mp3", ".mp4"))
        size = 92 if i == 0 else 74
        make_slide(text, palette, png, size=size, tag=PAGE_NAME)
        asyncio.run(tts(text, voice, mp3))
        dur = duration(mp3) + 0.5
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", png, "-i", mp3,
             "-af", "apad", "-t", f"{dur:.2f}", "-r", "24",
             "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "44100", "-ac", "2", seg],
            check=True, capture_output=True)
        segs.append(seg)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        f.write("\n".join(f"file '{s}'" for s in segs))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", out_path], check=True, capture_output=True)


HELP = (
    "Ami Reel Bot 🎬\n\n"
    "/reel  -> bot nije ekta tech fact reel banabe\n"
    "/reel voice=male  -> purush kontho\n"
    "/reel Title | point 1 | point 2 | point 3  -> tomar nijer fact diye\n\n"
    "Prothom ta title hobe, baki gulo slide."
)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP)


async def reel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    raw = " ".join(ctx.args)
    voice = "female"
    if "voice=male" in raw:
        voice, raw = "male", raw.replace("voice=male", "")
    raw = raw.replace("voice=female", "").strip()

    if "|" in raw:
        slides = [p.strip() for p in raw.split("|") if p.strip()]
    else:
        item = random.choice(FACTS)
        slides = [item["title"]] + item["points"]
    slides.append("Aro tech tips pete follow koro 🔔")

    msg = await update.message.reply_text("Reel baniyechi... 1-2 minute lagte pare ⏳")
    out = os.path.join(tempfile.mkdtemp(), "reel.mp4")
    try:
        await asyncio.to_thread(build_reel, slides, voice, out)
        with open(out, "rb") as v:
            await update.message.reply_document(v, filename="reel.mp4",
                                                caption="Tomar reel ready ✅")
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"Error hoyeche: {e}")


class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


def keepalive():
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), Ping).serve_forever()


if __name__ == "__main__":
    threading.Thread(target=keepalive, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reel", reel))
    app.run_polling()
