import discord
import random
import aiohttp
import asyncio
import io
from PIL import Image, ImageFilter

# Helper to strip spaces and symbols (same as splash)
def normalize(text):
    return "".join(c for c in text if c.isalnum()).lower()

async def get_blurred_icon():
    async with aiohttp.ClientSession() as session:
        # 1. Get latest version and champion list
        async with session.get('https://ddragon.leagueoflegends.com/api/versions.json') as resp:
            versions = await resp.json()
            latest_version = versions[0]
        
        champ_url = f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json'
        async with session.get(champ_url) as resp:
            champ_data = await resp.json()
            champions = list(champ_data['data'].keys())
            
        random_champ_id = random.choice(champions)
        champ_name = champ_data['data'][random_champ_id]['name']
        
        # 2. Get the icon image URL
        icon_url = f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/img/champion/{random_champ_id}.png'
        
        # 3. Download the image and blur it using Pillow
        async with session.get(icon_url) as img_resp:
            img_bytes = await img_resp.read()
            
            with Image.open(io.BytesIO(img_bytes)) as img:
                img = img.convert("RGB")
                
                # Get original dimensions (usually 120x120)
                original_size = img.size
                
                # --- PIXELATION MAGIC ---
                # Shrink to 10x10 pixels (lower = harder)
                pixel_size = (4, 4) 
                small_img = img.resize(pixel_size, resample=Image.BILINEAR)
                
                # Scale it back up to look blocky
                # We use NEAREST so it doesn't try to "smooth" the blocks
                pixelated_img = small_img.resize(original_size, Image.NEAREST)
                
                # Save to buffer
                final_buffer = io.BytesIO()
                pixelated_img.save(final_buffer, format="PNG")
                final_buffer.seek(0)
                
                return champ_name, final_buffer

async def start_icon_game(client, message, scores, save_scores):
    original_author = message.author
    champ_name, image_buffer = await get_blurred_icon()
    
    # Send the blurred image as a file
    file = discord.File(fp=image_buffer, filename="blurred.png")
    
    embed = discord.Embed(
        title="💀 Hardstuck | Blurry Icon",
        description="Who's this champion? You have **15 seconds**.",
        color=discord.Color.dark_grey()
    )
    embed.set_image(url="attachment://blurred.png")
    embed.set_footer(text="Type !skip to give up (Host only)")
    
    await message.channel.send(file=file, embed=embed)
    
    def check(m):
        return m.author != client.user and m.channel == message.channel

    try:
        # We completely removed the user_cooldowns dictionary!
        while True:
            # This pulls the next message directly from Discord's chronological queue
            guess_msg = await client.wait_for('message', check=check, timeout=15.0)
            
            # 1. Check for Skip
            if guess_msg.content.lower() == '!skip':
                if guess_msg.author == original_author:
                    await message.channel.send(f"⏭️ Game skipped! It was **{champ_name}**.")
                    return
                else:
                    await guess_msg.reply("❌ Only the host can skip.")
                    continue

            # 2. Check for the Winner
            if normalize(guess_msg.content) == normalize(champ_name):
                guild_id = str(message.guild.id) if message.guild else "DMs"
                user_id = str(guess_msg.author.id)
                
                # Scoring
                if guild_id not in scores: scores[guild_id] = {}
                if user_id not in scores[guild_id]: scores[guild_id][user_id] = {}
                if "icon" not in scores[guild_id][user_id]: scores[guild_id][user_id]["icon"] = 0
                
                scores[guild_id][user_id]["icon"] += 1
                save_scores(scores)
                
                await guess_msg.reply(f"🎉 **Correct!** It was **{champ_name}**. +1 Icon point.")
                break # This stops the loop, ignoring any remaining spam in the queue
                
            # 3. Handle Wrong Guesses
            else:
                # FIRE AND FORGET! The loop instantly moves to the next queued message.
                asyncio.create_task(guess_msg.add_reaction("❌"))
                
    except asyncio.TimeoutError:
        await message.channel.send(f"⏰ Time's up! The champion was **{champ_name}**.")