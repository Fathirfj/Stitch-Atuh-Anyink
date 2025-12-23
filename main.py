import discord
from discord import option
from PIL import Image, ImageChops
import io, requests, os, zipfile, re
from flask import Flask
from threading import Thread

# --- KEEP ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "Bot SmartStitch Lite Online!"
def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- BOT SETUP ---
bot = discord.Bot()

def find_smart_split(img, start_y, max_height):
    """Mencari celah kosong terbaik agar tidak memotong teks/gambar"""
    target_y = start_y + max_height
    if target_y >= img.height:
        return img.height

    # Cari area kosong di sekitar target_y (range 100px ke atas)
    search_range = 100 
    best_split = target_y
    min_variance = 1000000

    for y in range(target_y, target_y - search_range, -1):
        if y <= 0: break
        # Ambil satu baris pixel
        row = img.crop((0, y, img.width, y + 1))
        # Cek variasi warna di baris tersebut (semakin kecil = semakin polos/kosong)
        extrema = row.getextrema()
        variance = sum([(e[1] - e[0]) for e in extrema])
        
        if variance < min_variance:
            min_variance = variance
            best_split = y
            if variance == 0: break # Ketemu baris polos sempurna
            
    return best_split

def process_smart_stitch(image_objects, target_width=None, split_height=None, fmt="JPEG"):
    """Menggabungkan lalu membagi secara cerdas (Smart Splitting)"""
    if not image_objects: return []

    # 1. Samakan Lebar
    base_width = target_width or image_objects[0].width
    resized_imgs = []
    for img in image_objects:
        if img.mode != 'RGB' and fmt == "JPEG": img = img.convert('RGB')
        w_ratio = base_width / float(img.width)
        h_size = int(float(img.height) * w_ratio)
        resized_imgs.append(img.resize((base_width, h_size), Image.Resampling.LANCZOS))

    # 2. Gabungkan Jadi Satu Long Strip
    total_h = sum(i.height for i in resized_imgs)
    full_strip = Image.new('RGB', (base_width, total_h))
    curr_y = 0
    for im in resized_imgs:
        full_strip.paste(im, (0, curr_y))
        curr_y += im.height

    # 3. Smart Splitting (Jika split_height ditentukan)
    output_files = []
    if split_height:
        start_y = 0
        while start_y < full_strip.height:
            end_y = find_smart_split(full_strip, start_y, split_height)
            page = full_strip.crop((0, start_y, base_width, end_y))
            output_files.append(page)
            start_y = end_y
    else:
        output_files.append(full_strip)

    return output_files

@bot.slash_command(description="Gabung & Potong Cerdas (SmartStitch Style)")
@option("zip_file", discord.Attachment, description="ZIP berisi potongan manga")
@option("width", int, description="Lebar target (misal 720)", default=720)
@option("split_at", int, description="Potong setiap tinggi X pixel (misal 1500)", default=0)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart_stitch(ctx, zip_file: discord.Attachment, width: int, split_at: int, format: str):
    await ctx.defer()
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
    results = process_smart_stitch(imgs, target_width=width, split_height=split_at if split_at > 0 else None, fmt=ext)

    files = []
    for i, res in enumerate(results):
        buf = io.BytesIO()
        res.save(buf, ext)
        buf.seek(0)
        files.append(discord.File(fp=buf, filename=f"page_{i+1}.{format.lower()}"))

    await ctx.respond(f"Selesai! Berhasil membuat {len(results)} halaman.", files=files[:10]) # Limit 10 file per respond

Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
