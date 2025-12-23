import discord
from discord import option
from PIL import Image
import io, requests, os, zipfile, re
from flask import Flask
from threading import Thread

# --- SERVER UNTUK RAILWAY HEALTHCHECK ---
app = Flask('')
@app.route('/')
def home(): return "Bot SmartStitch V7 - Full System Online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- KONFIGURASI BOT ---
bot = discord.Bot()

def bypass_drive_link(url):
    """Mengonversi link Google Drive biasa ke link unduhan langsung"""
    drive_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
    if drive_match:
        file_id = drive_match.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return url

def find_smart_split(img, start_y, max_height):
    """Logika SmartStitch: Mencari celah kosong (putih/hitam) untuk memotong halaman"""
    target_y = start_y + max_height
    if target_y >= img.height: return img.height
    
    search_range = 150 # Jarak pencarian baris kosong (dalam pixel)
    best_split = target_y
    min_variance = 1000000
    
    for y in range(target_y, target_y - search_range, -1):
        if y <= start_y: break
        row = img.crop((0, y, img.width, y + 1))
        extrema = row.getextrema()
        # Menghitung variasi warna baris
        variance = sum([(e[1] - e[0]) for e in extrema])
        if variance < min_variance:
            min_variance = variance
            best_split = y
            if variance == 0: break # Celah polos sempurna ditemukan
    return best_split

def process_smart_stitch(image_objects, target_width=None, split_height=None, fmt="JPEG"):
    """Menggabungkan semua gambar lalu membaginya secara cerdas"""
    if not image_objects: return []
    
    # 1. Resize semua gambar ke lebar yang sama
    base_width = target_width or image_objects[0].width
    resized_imgs = []
    for img in image_objects:
        if img.mode != 'RGB' and fmt == "JPEG": 
            img = img.convert('RGB')
        w_ratio = base_width / float(img.width)
        h_size = int(float(img.height) * w_ratio)
        resized_imgs.append(img.resize((base_width, h_size), Image.Resampling.LANCZOS))

    # 2. Gabungkan menjadi satu strip panjang
    total_h = sum(i.height for i in resized_imgs)
    full_strip = Image.new('RGB', (base_width, total_h))
    curr_y = 0
    for im in resized_imgs:
        full_strip.paste(im, (0, curr_y))
        curr_y += im.height

    # 3. Smart Splitting
    output_pages = []
    if split_height and split_height > 0:
        start_y = 0
        while start_y < full_strip.height:
            end_y = find_smart_split(full_strip, start_y, split_height)
            # Jangan biarkan potongan terakhir terlalu kecil (kurang dari 200px)
            if full_strip.height - end_y < 200: end_y = full_strip.height
            page = full_strip.crop((0, start_y, base_width, end_y))
            output_pages.append(page)
            start_y = end_y
    else:
        output_pages.append(full_strip)
    return output_pages

def create_zip_result(pages, fmt_name, ext_name):
    """Membungkus hasil akhir ke dalam file ZIP"""
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
    print(f"Bot Berhasil Login: {bot.user}")

# --- COMMAND: SMART STITCH DARI LINK ---
@bot.slash_command(description="Ambil file (ZIP/Gambar) dari link dan potong cerdas")
@option("url", str, description="Link Google Drive atau Direct Link")
@option("width", int, description="Lebar target (px)", default=720)
@option("split_at", int, description="Tinggi per halaman (px)", default=2000)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart_stitch_link(ctx, url: str, width: int, split_at: int, format: str):
    await ctx.defer()
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        final_url = bypass_drive_link(url)
        resp = requests.get(final_url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            return await ctx.respond(f"Gagal unduh. Server merespon: {resp.status_code}")

        imgs = []
        data = io.BytesIO(resp.content)
        
        # Cek apakah ZIP atau Gambar Tunggal
        if zipfile.is_zipfile(data):
            with zipfile.ZipFile(data) as archive:
                for name in sorted(archive.namelist()):
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        with archive.open(name) as f:
                            imgs.append(Image.open(io.BytesIO(f.read())))
        else:
            try:
                imgs.append(Image.open(data))
            except:
                return await ctx.respond("Link bukan gambar/ZIP valid. Pastikan link publik.")

        if not imgs:
            return await ctx.respond("Tidak ada gambar ditemukan.")

        ext = "JPEG" if format == "JPG" else format
        results = process_smart_stitch(imgs, target_width=width, split_height=split_at, fmt=ext)
        zip_output = create_zip_result(results, ext, format.lower())
        
        await ctx.respond(
            f"Selesai! {len(results)} halaman diproses.",
            file=discord.File(fp=zip_output, filename="stitched_result.zip")
        )
    except Exception as e:
        await ctx.respond(f"Error: {str(e)}")

# --- COMMAND: SMART STITCH DARI UPLOAD ---
@bot.slash_command(description="Unggah ZIP dan potong secara cerdas")
@option("zip_file", discord.Attachment, description="File ZIP berisi manga")
@option("width", int, default=720)
@option("split_at", int, default=2000)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart_stitch_upload(ctx, zip_file: discord.Attachment, width: int, split_at: int, format: str):
    await ctx.defer()
    try:
        if not zip_file.filename.endswith('.zip'):
            return await ctx.respond("Harap unggah file .ZIP")
        
        resp = requests.get(zip_file.url)
        imgs = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            for name in sorted(archive.namelist()):
                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    with archive.open(name) as f:
                        imgs.append(Image.open(io.BytesIO(f.read())))

        ext = "JPEG" if format == "JPG" else format
        results = process_smart_stitch(imgs, target_width=width, split_height=split_at, fmt=ext)
        zip_output = create_zip_result(results, ext, format.lower())
        
        await ctx.respond(f"Berhasil! {len(results)} halaman dalam ZIP.", file=discord.File(fp=zip_output, filename="manga_stitch.zip"))
    except Exception as e:
        await ctx.respond(f"Error: {str(e)}")

# JALANKAN SEMUA
if __name__ == "__main__":
    Thread(target=run_web).start()
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
