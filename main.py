import discord
from discord import option
from PIL import Image
import io, requests, os, zipfile, re, gc
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home(): return "Bot SmartStitch V8 - Memory Optimized!"
def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

bot = discord.Bot()

def bypass_drive_link(url):
    drive_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
    if drive_match:
        return f'https://drive.google.com/uc?export=download&id={drive_match.group(1)}'
    return url

def find_smart_split(full_strip, start_y, max_height):
    target_y = start_y + max_height
    if target_y >= full_strip.height: return full_strip.height
    search_range = 150 
    best_split = target_y
    min_variance = 1000000
    for y in range(target_y, target_y - search_range, -1):
        if y <= start_y: break
        row = full_strip.crop((0, y, full_strip.width, y + 1))
        extrema = row.getextrema()
        variance = sum([(e[1] - e[0]) for e in extrema])
        if variance < min_variance:
            min_variance = variance
            best_split = y
            if variance == 0: break 
    return best_split

def process_smart_stitch_low_mem(image_data_list, target_width=720, split_height=2000, fmt="JPEG"):
    """Versi hemat memori: Memproses gambar tanpa menahan semuanya di RAM"""
    processed_imgs = []
    total_h = 0
    
    # 1. Hitung total tinggi & resize awal
    for data in image_data_list:
        with Image.open(io.BytesIO(data)) as img:
            if img.mode != 'RGB' and fmt == "JPEG": img = img.convert('RGB')
            w_ratio = target_width / float(img.width)
            h_size = int(float(img.height) * w_ratio)
            temp_img = img.resize((target_width, h_size), Image.Resampling.LANCZOS)
            processed_imgs.append(temp_img)
            total_h += h_size

    # 2. Gabungkan ke satu strip
    full_strip = Image.new('RGB', (target_width, total_h))
    curr_y = 0
    for im in processed_imgs:
        full_strip.paste(im, (0, curr_y))
        curr_y += im.height
        im.close() # Langsung tutup untuk hemat RAM
    
    processed_imgs.clear()
    gc.collect() # Paksa pembersihan RAM

    # 3. Potong Cerdas
    output_pages = []
    ext = "JPEG" if fmt == "JPG" else fmt
    start_y = 0
    while start_y < full_strip.height:
        end_y = find_smart_split(full_strip, start_y, split_height) if split_height > 0 else full_strip.height
        if full_strip.height - end_y < 200: end_y = full_strip.height
        
        page = full_strip.crop((0, start_y, target_width, end_y))
        img_buf = io.BytesIO()
        page.save(img_buf, ext, quality=85) # Quality 85 untuk kurangi ukuran file
        img_buf.seek(0)
        output_pages.append(img_buf)
        start_y = end_y
        
    full_strip.close()
    gc.collect()
    return output_pages

@bot.slash_command(description="SmartStitch Hemat RAM (ZIP/Link)")
@option("input", str, description="Link atau unggah ZIP", required=False)
@option("file", discord.Attachment, description="Unggah ZIP langsung", required=False)
@option("width", int, default=720)
@option("split_at", int, default=2000)
async def smart(ctx, input: str = None, file: discord.Attachment = None, width: int = 720, split_at: int = 2000):
    await ctx.defer()
    try:
        source_url = bypass_drive_link(input) if input else (file.url if file else None)
        if not source_url: return await ctx.respond("Kirim link atau unggah file!")

        resp = requests.get(source_url, stream=True, timeout=60)
        img_data_list = []
        
        # Jika ZIP
        if zipfile.is_zipfile(io.BytesIO(resp.content)):
            with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
                for name in sorted(archive.namelist()):
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        img_data_list.append(archive.read(name))
        else:
            img_data_list.append(resp.content)

        # Proses dengan mode Low Mem
        pages_bufs = process_smart_stitch_low_mem(img_data_list, width, split_at)
        
        # Buat ZIP hasil
        zip_output = io.BytesIO()
        with zipfile.ZipFile(zip_output, "a", zipfile.ZIP_DEFLATED) as zf:
            for i, buf in enumerate(pages_bufs):
                zf.writestr(f"page_{i+1:03d}.jpg", buf.read())
        
        zip_output.seek(0)
        await ctx.respond(file=discord.File(fp=zip_output, filename="result.zip"))
        
        # Bersihkan memori terakhir
        img_data_list.clear()
        gc.collect()

    except Exception as e:
        await ctx.respond(f"Error OOM/System: {e}")

if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run(os.getenv('DISCORD_TOKEN'))
