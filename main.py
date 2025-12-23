import discord
from discord import option
from PIL import Image
import io, requests, os, zipfile, re, gc
from flask import Flask
from threading import Thread

# --- SERVER FOR RAILWAY ---
app = Flask('')
@app.route('/')
def home(): return "SmartStitch V11 - Drive Bypass Active"
def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

bot = discord.Bot()

def get_drive_direct_link(url):
    """Logika tingkat lanjut untuk menembus proteksi download Google Drive"""
    file_id_match = re.search(r'(?<=/d/|id=)([\w-]+)', url)
    if not file_id_match:
        return url
    
    file_id = file_id_match.group(1)
    # Link untuk mencoba download langsung
    direct_link = f'https://drive.google.com/uc?export=download&id={file_id}'
    
    # Gunakan session untuk menangani cookie 'confirm' dari Google (bypass virus scan warning)
    session = requests.Session()
    response = session.get(direct_link, stream=True)
    
    confirm_token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            confirm_token = value
            break
            
    if confirm_token:
        direct_link += f'&confirm={confirm_token}'
        
    return direct_link

# ... (Fungsi find_smart_split dan process_smart_stitch tetap sama seperti V10) ...
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
    processed_imgs = []
    total_h = 0
    for data in image_data_list:
        try:
            with Image.open(io.BytesIO(data)) as img:
                if fmt == "JPEG" and img.mode != 'RGB': img = img.convert('RGB')
                elif fmt in ["WEBP", "PNG"] and img.mode not in ['RGB', 'RGBA']: img = img.convert('RGBA')
                w_ratio = target_width / float(img.width)
                h_size = int(float(img.height) * w_ratio)
                processed_imgs.append(img.resize((target_width, h_size), Image.Resampling.LANCZOS))
                total_h += h_size
        except: continue
    if not processed_imgs: return []
    mode = 'RGB' if fmt == "JPEG" else 'RGBA'
    full_strip = Image.new(mode, (target_width, total_h))
    curr_y = 0
    for im in processed_imgs:
        full_strip.paste(im, (0, curr_y))
        curr_y += im.height
        im.close() 
    gc.collect()
    output_buffers = []
    start_y = 0
    while start_y < full_strip.height:
        end_y = find_smart_split(full_strip, start_y, split_height) if split_height > 0 else full_strip.height
        if full_strip.height - end_y < 200: end_y = full_strip.height
        page = full_strip.crop((0, start_y, target_width, end_y))
        buf = io.BytesIO()
        if fmt == "JPEG": page.save(buf, fmt, quality=85, optimize=True)
        elif fmt == "WEBP": page.save(buf, fmt, quality=80, lossless=False)
        else: page.save(buf, fmt)
        buf.seek(0)
        output_buffers.append(buf)
        start_y = end_y
    full_strip.close()
    gc.collect()
    return output_buffers

@bot.slash_command(description="SmartStitch: Gabung & Potong Cerdas")
@option("input_url", str, description="Link Google Drive / Direct", required=False)
@option("file_upload", discord.Attachment, description="Upload ZIP", required=False)
@option("width", int, default=720)
@option("split_at", int, default=2000)
@option("format", choices=["JPG", "WEBP", "PNG"], default="JPG")
async def smart(ctx, input_url: str = None, file_upload: discord.Attachment = None, width: int = 720, split_at: int = 2000, format: str = "JPG"):
    await ctx.defer()
    try:
        # Gunakan fungsi bypass baru untuk link
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        if input_url:
            final_url = get_drive_direct_link(input_url)
            resp = requests.get(final_url, headers=headers, stream=True, timeout=60)
        elif file_upload:
            resp = requests.get(file_upload.url, headers=headers, stream=True)
        else:
            return await ctx.respond("Berikan link atau file!")

        img_data_list = []
        content = resp.content
        
        if zipfile.is_zipfile(io.BytesIO(content)):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                for name in sorted(archive.namelist()):
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        img_data_list.append(archive.read(name))
        else:
            img_data_list.append(content)

        fmt_map = {"JPG": "JPEG", "WEBP": "WEBP", "PNG": "PNG"}
        pages_bufs = process_smart_stitch_low_mem(img_data_list, width, split_at, fmt_map[format])
        
        if not pages_bufs:
            return await ctx.respond("Gagal memproses. Cek apakah link Drive sudah 'Anyone with the link'.")

        zip_output = io.BytesIO()
        with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, buf in enumerate(pages_bufs):
                zf.writestr(f"page_{i+1:03d}.{format.lower()}", buf.getvalue())
        
        zip_output.seek(0)
        await ctx.respond(f"✅ Berhasil! Halaman: {len(pages_bufs)}", file=discord.File(fp=zip_output, filename=f"result_{format.lower()}.zip"))
        gc.collect()

    except Exception as e:
        await ctx.respond(f"Error: {e}")

if __name__ == "__main__":
    Thread(target=run_web).start()
    bot.run(os.getenv('DISCORD_TOKEN'))
