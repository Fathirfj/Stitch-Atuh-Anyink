import discord
from discord import option
from PIL import Image
import io, requests, os, zipfile, re
from flask import Flask
from threading import Thread

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot SmartStitch V5 (Auto-ZIP Output) Online!"
def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- BOT SETUP ---
bot = discord.Bot()

def bypass_drive_link(url):
    drive_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
    if drive_match:
        file_id = drive_match.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return url

def find_smart_split(img, start_y, max_height):
    target_y = start_y + max_height
    if target_y >= img.height: return img.height
    search_range = 150 
    best_split = target_y
    min_variance = 1000000
    for y in range(target_y, target_y - search_range, -1):
        if y <= start_y: break
        row = img.crop((0, y, img.width, y + 1))
        extrema = row.getextrema()
        variance = sum([(e[1] - e[0]) for e in extrema])
        if variance < min_variance:
            min_variance = variance
            best_split = y
            if variance == 0: break 
    return best_split

def process_smart_stitch(image_objects, target_width=None, split_height=None, fmt="JPEG"):
    if not image_objects: return []
    base_width = target_width or image_objects[0].width
    resized_imgs = []
    for img in image_objects:
        if img.mode != 'RGB' and fmt == "JPEG": img = img.convert('RGB')
        w_ratio = base_width / float(img.width)
        h_size = int(float(img.height) * w_ratio)
        resized_imgs.append(img.resize((base_width, h_size), Image.Resampling.LANCZOS))

    total_h = sum(i.height for i in resized_imgs)
    full_strip = Image.new('RGB', (base_width, total_h))
    curr_y = 0
    for im in resized_imgs:
        full_strip.paste(im, (0, curr_y))
        curr_y += im.height

    output_pages = []
    if split_height and split_height > 0:
        start_y = 0
        while start_y < full_strip.height:
            end_y = find_smart_split(full_strip, start_y, split_height)
            if full_strip.height - end_y < 200: end_y = full_strip.height
            page = full_strip.crop((0, start_y, base_width, end_y))
            output_pages.append(page)
            start_y = end_y
    else:
        output_pages.append(full_strip)
    return output_pages

# --- FUNGSI BARU: MEMBUAT ZIP DARI HASIL POTONGAN ---
def create_zip_result(pages, fmt_name, ext_name):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, page in enumerate(pages):
            img_buf = io.BytesIO()
            page.save(img_buf, fmt_name)
            img_buf.seek(0)
            zip_file.writestr(f"page_{i+1:03d}.{ext_name}", img_buf.read())
    zip_buffer.seek(0)
    return zip_buffer

@bot.event
async def on_ready():
    print(f"Bot {bot.user} Online dengan fitur Auto-ZIP!")

# --- SLASH COMMAND ZIP ---
@bot.slash_command(description="Stitch dari ZIP dan hasilkan ZIP kembali")
@option("zip_file", discord.Attachment, description="File ZIP manga")
@option("width", int, description="Lebar target", default=720)
@option("split_at", int, description="Tinggi per halaman", default=2000)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart_stitch_zip(ctx, zip_file: discord.Attachment, width: int, split_at: int, format: str):
    await ctx.defer()
    try:
        if not zip_file.filename.endswith('.zip'):
            return await ctx.respond("Kirim file .ZIP!")

        resp = requests.get(zip_file.url)
        imgs = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            for name in sorted(archive.namelist()):
                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    with archive.open(name) as f:
                        imgs.append(Image.open(io.BytesIO(f.read())))

        ext = "JPEG" if format == "JPG" else format
        results = process_smart_stitch(imgs, target_width=width, split_height=split_at, fmt=ext)
        
        # Buat ZIP dari hasil
        zip_output = create_zip_result(results, ext, format.lower())
        
        await ctx.respond(
            f"Selesai! {len(results)} halaman telah digabung dan dibungkus dalam ZIP.",
            file=discord.File(fp=zip_output, filename="stitched_manga.zip")
        )
    except Exception as e:
        await ctx.respond(f"Error: {e}")

# --- SLASH COMMAND LINK ---
@bot.slash_command(description="Stitch dari Link dan hasilkan ZIP")
@option("link1", str, description="Link 1")
@option("link2", str, description="Link 2")
@option("width", int, default=720)
@option("split_at", int, default=0)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart_stitch_link(ctx, link1: str, link2: str, width: int, split_at: int, format: str):
    await ctx.defer()
    try:
        links = [bypass_drive_link(link1), bypass_drive_link(link2)]
        imgs = [Image.open(io.BytesIO(requests.get(u).content)) for u in links]
        
        ext = "JPEG" if format == "JPG" else format
        results = process_smart_stitch(imgs, target_width=width, split_height=split_at, fmt=ext)
        
        zip_output = create_zip_result(results, ext, format.lower())
        await ctx.respond(
            f"Selesai! Hasil gabungan link dikirim dalam bentuk ZIP.",
            file=discord.File(fp=zip_output, filename="link_result.zip")
        )
    except Exception as e:
        await ctx.respond(f"Error: {e}")

Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
