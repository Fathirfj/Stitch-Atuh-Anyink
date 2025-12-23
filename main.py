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
def home(): return "Bot Vertical Stitch Online!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT SETUP (Slash Commands) ---
bot = discord.Bot()

def process_stitching(image_objects):
    """Logika Gabung Vertikal"""
    if not image_objects:
        return None
    
    # Samakan lebar ke gambar pertama agar rapi
    base_width = image_objects[0].size[0]
    resized_images = []
    for img in image_objects:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        # Resize proporsional berdasarkan lebar
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        resized_images.append(img.resize((base_width, h_size), Image.Resampling.LANCZOS))

    # Hitung total tinggi
    total_height = sum(img.size[1] for img in resized_images)
    
    # Buat kanvas vertikal
    new_im = Image.new('RGB', (base_width, total_height))
    y_offset = 0
    for im in resized_images:
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    
    return new_im

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

# --- SLASH COMMAND: STITCH DARI ATTACHMENT ---
@bot.slash_command(description="Gabungkan gambar secara vertikal")
@option("image1", discord.Attachment, description="Gambar pertama")
@option("image2", discord.Attachment, description="Gambar kedua")
@option("image3", discord.Attachment, description="Gambar ketiga (opsional)", required=False)
async def stitch(ctx, image1: discord.Attachment, image2: discord.Attachment, image3: discord.Attachment = None):
    await ctx.defer() # Memberi waktu bot memproses
    
    attachments = [image1, image2]
    if image3: attachments.append(image3)
    
    imgs = []
    for att in attachments:
        resp = requests.get(att.url)
        imgs.append(Image.open(io.BytesIO(resp.content)))
    
    result = process_stitching(imgs)
    
    with io.BytesIO() as img_bin:
        result.save(img_bin, 'PNG')
        img_bin.seek(0)
        await ctx.respond(file=discord.File(fp=img_bin, filename='vertical_stitched.png'))

# --- SLASH COMMAND: STITCH DARI ZIP (Google Drive/Local) ---
@bot.slash_command(description="Stitch semua gambar di dalam file .ZIP")
@option("zip_file", discord.Attachment, description="Unggah file ZIP berisi gambar")
async def stitch_zip(ctx, zip_file: discord.Attachment):
    if not zip_file.filename.endswith('.zip'):
        return await ctx.respond("Mohon unggah file format .ZIP!")

    await ctx.defer()
    resp = requests.get(zip_file.url)
    
    imgs = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        for file_name in sorted(archive.namelist()):
            if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                with archive.open(file_name) as file:
                    imgs.append(Image.open(io.BytesIO(file.read())))

    if len(imgs) < 2:
        return await ctx.respond("Isi ZIP minimal harus ada 2 gambar!")

    result = process_stitching(imgs)
    with io.BytesIO() as img_bin:
        result.save(img_bin, 'PNG')
        img_bin.seek(0)
        await ctx.respond(file=discord.File(fp=img_bin, filename='zip_stitched.png'))

# Jalankan
Thread(target=run_web).start()
bot.run(os.getenv('DISCORD_TOKEN'))
