
import discord
from discord.ext import commands
from PIL import Image
import io
import requests

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def stitch(ctx):
    # Cek apakah ada 2 lampiran gambar
    if len(ctx.message.attachments) < 2:
        await ctx.send("Kirimkan minimal 2 gambar sekaligus dengan perintah !stitch")
        return

    images = []
    for attachment in ctx.message.attachments:
        # Download gambar ke memori
        response = requests.get(attachment.url)
        img = Image.open(io.BytesIO(response.content))
        images.append(img)

    # Logika penggabungan horizontal
    widths, heights = zip(*(i.size for i in images))
    total_width = sum(widths)
    max_height = max(heights)

    # Buat gambar baru (kanvas kosong)
    new_im = Image.new('RGB', (total_width, max_height))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset, 0))
        x_offset += im.size[0]

    # Simpan hasil ke buffer untuk dikirim balik
    with io.BytesIO() as image_binary:
        new_im.save(image_binary, 'PNG')
        image_binary.seek(0)
        await ctx.send(file=discord.File(fp=image_binary, filename='stitched.png'))

bot.run(MTQ1Mjg5NjUxOTA2MDU4NjU0Ng.GTyu7e.8hyIiVAhEBX6wNMM9aCKts0gwaYVlIxSDSN-yM)
