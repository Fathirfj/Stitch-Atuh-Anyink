import discord
from discord import option
from PIL import Image
import io
import requests
import os
import zipfile
from flask import Flask
from threading import Thread

# --- KEEP ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot Vertical Stitch V2 Online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT SETUP ---
bot = discord.Bot()

def process_stitching(image_objects, target_height=None, fmt="PNG"):
    """Logika Gabung Vertikal dengan Custom Height & Format"""
    if not image_objects:
        return None
    
    base_width = image_objects[0].size[0]
    resized_images = []
    
    for img in image_objects:
        if img.mode != 'RGB' and fmt.upper() == "JPEG":
            img = img.convert('RGB')
        
        # Resize proporsional berdasarkan lebar gambar pertama
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        resized_images.append(img.resize((base_width, h_size), Image.Resampling.LANCZOS))

    total_height = sum(img.size[1] for img in resized_images)
    
    # Gabungkan ke kanvas sementara
    combined_im = Image.new('RGB' if fmt.upper() == "JPEG" else 'RGBA', (base_width, total_height))
    y_offset = 0
    for im in resized_images:
        combined_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    
    # Jika user menentukan tinggi khusus, lakukan resize final
    if target_height and target_height > 0:
        # Menghitung ratio agar tidak gepeng (optional) atau paksa sesuai target_height
        combined_im = combined_im.resize((base_width, target_height), Image.Resampling.LANCZOS)
        
    return combined_im

@bot.event
async def on_ready():
    print(f"{bot.user} Siap! Gunakan /stitch atau /stitch_zip")

# --- SLASH COMMAND: STITCH ---
@bot.slash_command(description="Gabungkan gambar secara vertikal dengan setting tinggi & format")
@option("image1", discord.Attachment, description="Gambar 1")
@option("image2", discord.Attachment, description="Gambar 2")
@option("format", description="Pilih format hasil", choices=["JPG", "WEBP", "PNG"])
@option("height", int, description="Tinggi total hasil (kosongkan untuk otomatis)", required=False)
async def stitch(ctx, image1: discord.Attachment, image2: discord.Attachment, format: str, height: int = None):
    await ctx.defer()
    
    imgs = []
    for att in [image1, image2]:
        resp = requests.get(att.url)
        imgs.append(Image.open(io.BytesIO(resp.content)))
    
    ext = "JPEG" if format == "JPG" else format
    result = process_stitching(imgs, target_height=height, fmt=ext)
    
    with io.BytesIO() as img_bin:
        result.save(img_bin, ext)
        img_bin.seek(0)
        file_name = f"result.{format.lower()}"
        await ctx.respond(file=discord.File(fp=img_bin, filename=file_name))

# --- SLASH COMMAND: ZIP ---
@bot.slash_command(description="Stitch semua gambar dari ZIP dengan setting tinggi & format")
@option("zip_file", discord.Attachment, description="File ZIP berisi gambar")
@option("format", description="Pilih format hasil", choices=["JPG", "WEBP", "PNG"])
@option("height", int, description="Tinggi total hasil (kosongkan untuk otomatis)", required=False)
async def stitch_zip(ctx, zip_file: discord.Attachment, format: str, height: int = None):
    if not zip_file.filename.endswith('.zip'):
        return await ctx.respond("Gunakan file .ZIP!")

    await ctx.defer()
    resp = requests.get(zip_file.url)
    
    imgs = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        for name in sorted(archive.namelist()):
            if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                with archive.open(name) as f:
                    imgs.append(Image.open(io.BytesIO(f.read())))

    if len(imgs) < 2:
        return await ctx.respond("Minimal 2 gambar dalam ZIP!")

    ext = "JPEG" if format == "JPG" else format
    result = process_stitching(imgs, target_height=height, fmt=ext)
    
    with io.BytesIO() as img_bin:
        result.save(img_bin, ext)
        img_bin.seek(0)
        await ctx.respond(file=discord.File(fp=img_bin, filename=f"zip_result.{format.lower()}"))

# Jalankan
Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
