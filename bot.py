import os
import logging
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

PLATFORMS = {
    "youtube": {"name": "🎬 YouTube Thumbnail", "size": (1280, 720), "bg": "#FF0000", "text_color": "white"},
    "fiverr": {"name": "🛒 Fiverr Gig Image", "size": (1280, 768), "bg": "#1DBF73", "text_color": "white"},
    "upwork": {"name": "💼 Upwork Gig Cover", "size": (960, 640), "bg": "#6FDA44", "text_color": "#2C2C2C"},
    "social": {"name": "📱 Social Media Graphic", "size": (1080, 1080), "bg": "#3B82F6", "text_color": "white"}
}

def generate_image(platform_key, description, custom_size=None):
    preset = PLATFORMS[platform_key]
    width, height = custom_size if custom_size else preset["size"]
    
    img = Image.new("RGB", (width, height), color=preset["bg"])
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=int(height/12))
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=int(height/20))
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    platform_title = preset["name"]
    bbox = draw.textbbox((0, 0), platform_title, font=font_large)
    title_w = bbox[2] - bbox[0]
    draw.text(((width - title_w)/2, height*0.2), platform_title, fill=preset["text_color"], font=font_large)
    
    max_chars_per_line = 35
    lines = [description[i:i+max_chars_per_line] for i in range(0, len(description), max_chars_per_line)]
    y_offset = height * 0.45
    for line in lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=font_small)
        line_w = bbox[2] - bbox[0]
        draw.text(((width - line_w)/2, y_offset), line, fill=preset["text_color"], font=font_small)
        y_offset += height * 0.08
    
    watermark = "@PixelGigBot"
    bbox = draw.textbbox((0, 0), watermark, font=font_small)
    wm_w = bbox[2] - bbox[0]
    draw.text((width - wm_w - 10, height - 30), watermark, fill=preset["text_color"], font=font_small)
    
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

async def start(update, context):
    keyboard = [[InlineKeyboardButton(p['name'], callback_data=key)] for key, p in PLATFORMS.items()]
    await update.message.reply_text(
        "🎨 *Welcome to PixelGig Bot!*\n\nSelect a platform to create an image for:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def platform_selected(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data['platform'] = query.data
    preset = PLATFORMS[query.data]
    await query.edit_message_text(
        f"✅ Platform selected: {preset['name']}\n📏 Default size: {preset['size'][0]}x{preset['size'][1]}\n\nSend me image description (optionally with custom size like '800x600')"
    )

async def handle_message(update, context):
    if 'platform' not in context.user_data:
        await update.message.reply_text("Please use /start first")
        return
    
    platform = context.user_data['platform']
    text = update.message.text.strip()
    
    import re
    match = re.search(r'(\d+)\s*[x×]\s*(\d+)', text)
    custom_size = (int(match.group(1)), int(match.group(2))) if match else None
    description = re.sub(r'\d+\s*[x×]\s*\d+', '', text).strip() if match else text
    
    if not description:
        description = f"Design for {PLATFORMS[platform]['name']}"
    
    await update.message.reply_text(f"🎨 Generating... Please wait")
    
    try:
        img_bytes = generate_image(platform, description, custom_size)
        await update.message.reply_photo(photo=img_bytes, caption=f"✅ Done!\nPlatform: {PLATFORMS[platform]['name']}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)}")
    
    del context.user_data['platform']

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(platform_selected))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Use polling (more reliable on Render free tier)
    print("🤖 Bot started in polling mode...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
