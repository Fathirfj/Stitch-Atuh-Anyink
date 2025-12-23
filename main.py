import discord
from discord.ext import commands
from PIL import Image
import io
import requests
import os
from flask import Flask
from threading import Thread

# --- BAGIAN KEEP ALIVE (Agar Railway Tidak Mati) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    # Mengambil port dari environment variable Railway (default 8080)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- BAGIAN BOT DISCORD ---
intents = discord.Intents.default()
intents.message_content = True # Pastikan Message Content Intent aktif di Dev Portal
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot berhasil login sebagai {bot.user}')

@bot.command()
async def stitch(ctx):
    """Menggabungkan minimal 2 gambar secara horizontal"""
    if len(ctx.message.attachments) < 2:
        await ctx.send("Kirimkan minimal 2 gambar sekaligus dengan perintah !stitch")
        return

    await ctx.send("Sedang memproses gambar...")

    images = []
    try:
        for attachment in ctx.message.attachments:
            # Unduh gambar
            response = requests.get(attachment.url)
            img = Image.open(io.BytesIO(response.content))
            # Pastikan gambar dalam mode RGB (untuk menghindari error PNG transparan)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        # Logika penggabungan horizontal
        widths, heights = zip(*(i.size for i in images))
        total_width = sum(widths)
        max_height = max(heights)

        # Buat kanvas kosong baru
        new_im = Image.new('RGB', (total_width, max_height))

        x_offset = 0
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]

        # Simpan hasil ke buffer memori
        with io.BytesIO() as image_binary:
            new_im.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=discord.File(fp=image_binary, filename='stitched.png'))

    except Exception as e:
        await ctx.send(f"Terjadi kesalahan saat mengolah gambar: {e}")

# Jalankan server web sebelum bot dimulai
keep_alive()

# Jalankan bot dengan Token dari Environment Variable Railway
token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("Error: Variabel DISCORD_TOKEN belum diatur di Railway!")
