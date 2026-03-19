import discord
import random
import aiohttp
import asyncio

# NEW: Helper to strip spaces and symbols (Dr. Mundo -> drmundo)
def normalize(text):
    return "".join(c for c in text if c.isalnum()).lower()

async def get_random_splash():
    # ... (Keep your existing get_random_splash code here) ...
    # No changes needed in this function!
    pass

# Your exact helper function
async def get_random_splash():
    async with aiohttp.ClientSession() as session:
        async with session.get('https://ddragon.leagueoflegends.com/api/versions.json') as resp:
            versions = await resp.json()
            latest_version = versions[0]
        
        champ_url = f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion.json'
        async with session.get(champ_url) as resp:
            champ_data = await resp.json()
            champions = list(champ_data['data'].keys())
            
        for attempt in range(10):
            random_champ_id = random.choice(champions)
            specific_champ_url = f'https://ddragon.leagueoflegends.com/cdn/{latest_version}/data/en_US/champion/{random_champ_id}.json'
            
            async with session.get(specific_champ_url) as resp:
                specific_champ_data = await resp.json()
                champ_info = specific_champ_data['data'][random_champ_id]
                champ_name = champ_info['name'] 
                
                valid_skins = []
                for s in champ_info['skins']:
                    if "(" not in s['name']:
                        valid_skins.append(s)
                
            random_skin = random.choice(valid_skins)
            skin_num = random_skin['num']
            skin_name = random_skin['name']
            
            if skin_name == 'default':
                skin_name = f"Base {champ_name}"
                
            all_skin_names = []
            for s in valid_skins:
                s_name = s['name']
                if s_name == 'default':
                    all_skin_names.append(f"Base {champ_name}")
                else:
                    all_skin_names.append(s_name)

            image_url = f'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{random_champ_id}_{skin_num}.jpg'
            
            async with session.get(image_url) as img_test:
                if img_test.status == 200:
                    return champ_name, skin_name, all_skin_names, image_url
                else:
                    continue
                    
        return "Teemo", "Base Teemo", ["Base Teemo"], "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Teemo_0.jpg"


# The game logic, moved out of bot.py
async def start_splash_game(client, message, scores, save_scores):
    original_author = message.author 
    champ_name, skin_name, all_skin_names, image_url = await get_random_splash()
    
    # --- EMBED SETUP ---
    embed = discord.Embed(
        title="💀 Hardstuck | Splash Art",
        description="You have **15 seconds** to type the Champion's name.",
        color=discord.Color.dark_grey()
    )
    embed.set_image(url=image_url)
    embed.set_footer(text="Type !skip to stop wasting time (Host only)")
    await message.channel.send(embed=embed)
    
    def check(m):
        return m.author != client.user and m.channel == message.channel
    
    # === SCORING HELPER ===
    # This prevents you from having to copy-paste the dictionary logic 3 times!
    def add_points(user_id, amount):
        guild_id = str(message.guild.id) if message.guild else "DMs"
        uid = str(user_id)
        
        if guild_id not in scores: scores[guild_id] = {}
        if uid not in scores[guild_id]: scores[guild_id][uid] = {}
        if "splash" not in scores[guild_id][uid]: scores[guild_id][uid]["splash"] = 0
        
        scores[guild_id][uid]["splash"] += amount
        save_scores(scores)

    # === PHASE 1: CHAMPION OR DIRECT SKIN ===
    try:
        while True: 
            guess_msg = await client.wait_for('message', check=check, timeout=15.0)
            
            if guess_msg.content.lower() == '!skip':
                if guess_msg.author == original_author:
                    await message.channel.send(f"⏭️ Game skipped! It was **{champ_name}** - **{skin_name}**.")
                    return 
                else:
                    await guess_msg.reply("❌ Only the host can skip.")
                    continue 

            normalized_guess = normalize(guess_msg.content)
            
            # CHECK 1: Did they guess the EXACT skin immediately? (2 Points)
            if normalized_guess == normalize(skin_name):
                add_points(guess_msg.author.id, 2)
                await guess_msg.reply(f"🤯 **ABSOLUTE CINEMA!** You perfectly guessed **{skin_name}** immediately! (+2 Splash Points)")
                return # End the game completely, skipping Phase 2
                
            # CHECK 2: Did they guess the Champion? (1 Point)
            elif normalized_guess == normalize(champ_name):
                add_points(guess_msg.author.id, 1)
                await guess_msg.reply(f"✅ Correct champion! **{champ_name}** (+1 pt). Now for the skin...")
                break # Break the loop to start Phase 2
                
            # CHECK 3: Wrong guess
            else:
                asyncio.create_task(guess_msg.add_reaction("❌"))
                
    except asyncio.TimeoutError:
        # If they timeout in Phase 1, reveal the whole answer and end the game
        await message.channel.send(f"⏰ Time's up! It was **{skin_name}**.")
        return
        
    # === PHASE 2: SKIN ===
    skin_list_str = "\n".join([f"- {s}" for s in all_skin_names])
    await message.channel.send(f"**Guess the exact skin!**\n\n{skin_list_str}\n\nYou have **15 seconds**.")
    
    try:
        while True:
            guess_msg = await client.wait_for('message', check=check, timeout=15.0)
            
            if guess_msg.content.lower() == '!skip':
                if guess_msg.author == original_author:
                    await message.channel.send(f"⏭️ Game skipped! It was **{skin_name}**.")
                    return
                else:
                    await guess_msg.reply("❌ Only the host can skip.")
                    continue
            
            # Note: The guessed_users set is completely GONE. Free-for-all spam is back!
            
            if normalize(guess_msg.content) == normalize(skin_name):
                add_points(guess_msg.author.id, 1)
                await guess_msg.reply(f"🎉 **BULLSEYE!** You guessed **{skin_name}** (+1 pt).")
                break
            else:
                asyncio.create_task(guess_msg.add_reaction("❌"))
                
    except asyncio.TimeoutError:
        await message.channel.send(f"⏰ Time's up! The correct skin was **{skin_name}**.")
        return