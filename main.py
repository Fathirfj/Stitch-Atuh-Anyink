import discord
from discord import option
from PIL import Image
import io
import requests
import os
import zipfile
import re
from flask import Flask
from threading import Thread

# --- KEEP ALIVE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot Vertical Stitch V3 Online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT SETUP ---
bot = discord.Bot()

def bypass_drive_link(url):
    """Mengubah link Google Drive biasa menjadi Direct Download Link"""
    drive_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
    if drive_match:
        file_id = drive_match.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    return url

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
    out_mode = 'RGB' if fmt.upper() == "JPEG" else 'RGBA'
    combined_im = Image.new(out_mode, (base_width, total_height))
    
    y_offset = 0
    for im in resized_images:
        combined_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    
    # Jika user menentukan tinggi khusus (Resize Final)
    if target_height and target_height > 0:
        combined_im = combined_im.resize((base_width, target_height), Image.Resampling.LANCZOS)
        
    return combined_im

@bot.event
async def on_ready():
    print(f"Bot {bot.user} Aktif! Slash commands siap digunakan.")

# --- SLASH COMMAND: STITCH LINK (Direct/Google Drive) ---
@bot.slash_command(description="Stitch gambar dari link (Direct/Drive) secara vertikal")
@option("link1", str, description="Link gambar 1 (Direct atau Google Drive)")
@option("link2", str, description="Link gambar 2 (Direct atau Google Drive)")
@option("format", description="Pilih format hasil", choices=["JPG", "WEBP", "PNG"])
@option("height", int, description="Tinggi total hasil (px)", required=False)
async def stitch_link(ctx, link1: str, link2: str, format: str, height: int = None):
    await ctx.defer()
    try:
        links = [bypass_drive_link(link1), bypass_drive_link(link2)]
        imgs = []
        for url in links:
            resp = requests.get(url, stream=True, timeout=10)
            imgs.append(Image.open(io.BytesIO(resp.content)))
        
        ext = "JPEG" if format == "JPG" else format
        result = process_stitching(imgs, target_height=height, fmt=ext)
        
        with io.BytesIO() as img_bin:
            result.save(img_bin, ext)
            img_bin.seek(0)
            await ctx.respond(file=discord.File(fp=img_bin, filename=f"link_result.{format.lower()}"))
    except Exception as e:
        await ctx.respond(f"Gagal mengambil gambar. Pastikan link publik. Error: {e}")

# --- SLASH COMMAND: STITCH UPLOAD ---
@bot.slash_command(description="Gabungkan upload gambar secara vertikal")
@option("image1", discord.Attachment, description="Gambar 1")
@option("image2", discord.Attachment, description="Gambar 2")
@option("format", description="Pilih format hasil", choices=["JPG", "WEBP", "PNG"])
@option("height", int, description="Tinggi total hasil (px)", required=False)
async def stitch(ctx, image1: discord.Attachment, image2: discord.Attachment, format: str, height: int = None):
    await ctx.defer()
    imgs = []
    for att in [image1, image2]:
        resp = requests.get(att.url)
        imgs.append(Image.open(io.BytesIO(resp.content)))
    
    ext = "JPEG" if format == "
