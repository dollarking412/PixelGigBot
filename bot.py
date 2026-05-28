import os
import logging
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8443))

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Platform presets (size, style hint)
PLATFORMS = {
    "youtube": {"name": "🎬 YouTube Thumbnail", "size": (1280, 720), "bg": "#FF0000", "text_color": "white"},
    "fiverr": {"name": "🛒 Fiverr Gig Image", "size": (1280, 768), "bg": "#1DBF73", "text_color": "white"},
    "upwork": {"name": "💼 Upwork Gig Cover", "size": (960, 640), "bg": "#6FDA44", "text_color": "#2C2C2C"},
    "social": {"name": "📱 Social Media Graphic", "size": (1080, 1080), "bg": "#3B82F6", "text_color": "white"}
}

# --- Helper: Generate image from description ---
def generate_image(platform_key: str, description: str, custom_size=None):
    """Creates a simple but clean design. For real AI art, integrate DALL·E or Stable Diffusion."""
    preset = PLATFORMS[platform_key]
    width, height = custom_size if custom_size else preset["size"]
    
    # Create background
    img = Image.new("RGB", (width, height), color=preset["bg"])
    draw = ImageDraw.Draw(img)
    
    # Try to use a default font; fallback to default if not found
    try:
        font_large = ImageFont.truetype("arial.ttf", size=int(height/12))
        font_small = ImageFont.truetype("arial.ttf", size=int(height/20))
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw platform title
    platform_title = preset["name"]
    bbox = draw.textbbox((0, 0), platform_title, font=font_large)
    title_w = bbox[2] - bbox[0]
    draw.text(((width - title_w)/2, height*0.2), platform_title, fill=preset["text_color"], font=font_large)
    
    # Draw user description (wrap if too long)
    max_chars_per_line = 35
    lines = [description[i:i+max_chars_per_line] for i in range(0, len(description), max_chars_per_line)]
    y_offset = height * 0.45
    for line in lines[:3]:  # max 3 lines
        bbox = draw.textbbox((0, 0), line, font=font_small)
        line_w = bbox[2] - bbox[0]
        draw.text(((width - line_w)/2, y_offset), line, fill=preset["text_color"], font=font_small)
        y_offset += height * 0.08
    
    # Add PixelGig watermark
    watermark = "@PixelGigBot"
    bbox = draw.textbbox((0, 0), watermark, font=font_small)
    wm_w = bbox[2] - bbox[0]
    draw.text((width - wm_w - 10, height - 30), watermark, fill=preset["text_color"], font=font_small)
    
    # Save to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(p['name'], callback_data=key)] for key, p in PLATFORMS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎨 *Welcome to PixelGig Bot!*\n\nSelect a platform to create an image for:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def platform_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data
    context.user_data['platform'] = platform
    preset = PLATFORMS[platform]
    await query.edit_message_text(
        f"✅ Platform selected: {preset['name']}\n"
        f"📏 Default size: {preset['size'][0]}x{preset['size'][1]}\n\n"
        "Now send me:\n"
        "1️⃣ *Image description* (e.g., 'modern coding workspace with laptop')\n"
        "2️⃣ *Custom size* (optional, like `800x600`)\n\n"
        "Example:\n`Futuristic AI brain, neon colors, 1024x768`",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'platform' not in context.user_data:
        await update.message.reply_text("Please start over with /start and select a platform first.")
        return
    
    platform = context.user_data['platform']
    text = update.message.text.strip()
    
    # Check for custom size in the message
    custom_size = None
    import re
    match = re.search(r'(\d+)\s*[x×]\s*(\d+)', text)
    if match:
        custom_size = (int(match.group(1)), int(match.group(2)))
        description = re.sub(r'\d+\s*[x×]\s*\d+', '', text).strip()
    else:
        description = text
    
    if not description:
        description = f"Design for {PLATFORMS[platform]['name']}"
    
    await update.message.reply_text(f"🎨 Generating your image for **{PLATFORMS[platform]['name']}**...\n⏳ Please wait.", parse_mode="Markdown")
    
    try:
        img_bytes = generate_image(platform, description, custom_size)
        await update.message.reply_photo(photo=img_bytes, caption=f"✅ Here's your design!\nPlatform: {PLATFORMS[platform]['name']}\nDescription: {description}")
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        await update.message.reply_text("❌ Image generation failed. Please try again with simpler text.")
    
    # Reset to allow new platform choice
    del context.user_data['platform']
    await update.message.reply_text("To create another design, type /start")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Cancelled. Use /start to begin again.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(platform_selected, pattern="^(youtube|fiverr|upwork|social)$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # For Render webhook (production) or polling (local)
    if os.environ.get("RENDER"):
        app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/{TOKEN}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
