import discord
import json
import os
from dotenv import load_dotenv
import games.icon as icon
import games.stats as stats
# NEW: Import the splash file we just made!
import games.splash as splash 
import asyncio
from games.players import RIOT_PLAYERS

load_dotenv()

# Tell it to look in the data folder
SCORE_FILE = "data/scores.json"

TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

def load_scores():
    # This automatically creates the 'data' folder if it doesn't exist yet!
    if not os.path.exists("data"):
        os.makedirs("data")
        
    if os.path.exists(SCORE_FILE):
        with open(SCORE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_scores(scores_to_save):
    with open(SCORE_FILE, "w") as f:
        json.dump(scores_to_save, f, indent=4)

scores = load_scores()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# --- CONCURRENCY SETUP ---
# Tracks what games are running in which channel: { channel_id: {"splash", "icon"} }
active_games = {} 

# Toggle this to True later if you want people to play Splash and Icon at the exact same time
ALLOW_CONCURRENT_GAMES = False 


@client.event
async def on_ready():
    print(f'Logged in successfully as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user: return

    user_command = message.content.lower()

    # Update Help to show !i and !l
    if user_command in ['!help', '!h']:
        embed = discord.Embed(title="💀 Hardstuck | Commands", color=discord.Color.green())
        embed.add_field(name="!s", value="Splash Art Trivia", inline=True)
        embed.add_field(name="!i", value="Blurry Icon Trivia", inline=True)
        embed.add_field(name="!g", value="Player Roulette Trivia (Guess by Name or Team/Role)", inline=False) # <--- Added here
        embed.add_field(name="!stat [@user]", value="Check your (or someone else's) scores", inline=False)
        embed.add_field(name="!l", value="Server Leaderboard", inline=True)
        embed.add_field(name="!skip", value="Skips the current game (Host only).", inline=False)
        await message.channel.send(embed=embed)
        return

    # --- FEATURE 1: LEADERBOARD ---
    if user_command == '!l':
        if not message.guild:
            await message.channel.send("Leaderboards are only available in servers!")
            return
            
        guild_id = str(message.guild.id)
        guild_scores = scores.get(guild_id, {})
        
        # Sort users, filtering out people with 0 points
        splash_top = sorted(
            [(uid, data.get('splash', 0)) for uid, data in guild_scores.items() if data.get('splash', 0) > 0],
            key=lambda x: x[1], reverse=True)[:5]
            
        icon_top = sorted(
            [(uid, data.get('icon', 0)) for uid, data in guild_scores.items() if data.get('icon', 0) > 0],
            key=lambda x: x[1], reverse=True)[:5]
            
        # NEW: Sort the roulette points!
        roulette_top = sorted(
            [(uid, data.get('roulette', 0)) for uid, data in guild_scores.items() if data.get('roulette', 0) > 0],
            key=lambda x: x[1], reverse=True)[:5]
        
        embed = discord.Embed(title=f"🏆 {message.guild.name} | Leaderboards", color=discord.Color.gold())
        
        splash_text = "\n".join([f"**{i+1}.** <@{uid}> - {score}" for i, (uid, score) in enumerate(splash_top)])
        icon_text = "\n".join([f"**{i+1}.** <@{uid}> - {score}" for i, (uid, score) in enumerate(icon_top)])
        roulette_text = "\n".join([f"**{i+1}.** <@{uid}> - {score}" for i, (uid, score) in enumerate(roulette_top)])
        
        embed.add_field(name="🖼️ Top Splashers", value=splash_text if splash_text else "No points yet.", inline=True)
        embed.add_field(name="🔍 Top Icons", value=icon_text if icon_text else "No points yet.", inline=True)
        # NEW: Add the Roulette column!
        embed.add_field(name="🎲 Top Roulette", value=roulette_text if roulette_text else "No points yet.", inline=True)
        
        await message.channel.send(embed=embed)
        return

    # --- FEATURE 2: TARGETED STATS ---
    if user_command.startswith('!stat'):
        guild_id = str(message.guild.id) if message.guild else "DMs"
        
        if message.mentions:
            target_user = message.mentions[0]
        else:
            target_user = message.author
            
        user_id = str(target_user.id)
        user_data = scores.get(guild_id, {}).get(user_id, {})
        
        s_score = user_data.get("splash", 0)
        i_score = user_data.get("icon", 0)
        r_score = user_data.get("roulette", 0) # NEW: Get roulette score
        
        await message.channel.send(
            f"📊 {target_user.mention}'s Waste of Time:\n"
            f"🖼️ **Splash Art:** {s_score}\n"
            f"🔍 **Blurry Icons:** {i_score}\n"
            f"🎲 **Roulette:** {r_score}"  # NEW: Display roulette score
        )
        return
    
    # === OP.GG ROULETTE GUESSING GAME ===
    if user_command == '!g':
        loading_msg = await message.reply("🎲 Fetching 3 random Ranked games from a mystery player...")
        
        # Get the packed dictionary from stats.py
        data = await stats.get_random_player_stats(RIOT_PLAYERS, RIOT_API_KEY)
        
        # If it failed to find anyone, print the error and stop
        if not data["success"]:
            await loading_msg.edit(content=data["error_msg"])
            return
            
        # Display the prompt using the dictionary data
        await loading_msg.edit(content=f"**Who is this player?**\n{data['games_text']}\n\n*Guess their name or team/role (e.g., `Team 5 Sup`)*")
        
        def check(m):
            return m.channel == message.channel and not m.author.bot
            
        loop = asyncio.get_event_loop()
        end_time = loop.time() + 20.0 
        
        try:
            while True:
                time_left = end_time - loop.time()
                if time_left <= 0:
                    raise asyncio.TimeoutError
                    
                guess_msg = await client.wait_for('message', check=check, timeout=time_left)
                
                # --- NEW: SKIP LOGIC ---
                if guess_msg.content.lower() == '!skip':
                    if guess_msg.author == message.author: # Check if it's the host
                        await message.channel.send(f"⏭️ **Game skipped!** The player was **{data['target_name']}** (`Team {data['team_num']} {data['role_display']}`).")
                        return # Instantly kills the game
                    else:
                        asyncio.create_task(guess_msg.reply("❌ Only the person who started the game can skip it!", delete_after=5.0))
                        continue # Ignore this message and keep the timer running
                # -----------------------

                # Crush the spaces in the user's guess
                guess = guess_msg.content.lower().replace(" ", "")
                
                # Compare it against the clean data we got from stats.py
                is_name_correct = (guess == data['clean_target_name'])
                is_team_correct = (guess in data['valid_team_guesses'])
                
                if is_name_correct or is_team_correct:
                    # --- ADD SCORE TRACKING ---
                    guild_id = str(message.guild.id) if message.guild else "DMs"
                    winner_id = str(guess_msg.author.id)
                    
                    if guild_id not in scores:
                        scores[guild_id] = {}
                    if winner_id not in scores[guild_id]:
                        scores[guild_id][winner_id] = {}
                        
                    scores[guild_id][winner_id]["roulette"] = scores[guild_id][winner_id].get("roulette", 0) + 1
                    save_scores(scores)
                    # --------------------------

                    await guess_msg.reply(f"🎉 **Correct!** The player was **{data['target_name']}** (`Team {data['team_num']} {data['role_display']}`).")
                    break
                else:
                    asyncio.create_task(guess_msg.add_reaction("❌"))
                    
        except asyncio.TimeoutError:
            await message.channel.send(f"⏰ Time's up! The player was **{data['target_name']}** (`Team {data['team_num']} {data['role_display']}`).")
            
        return

    # --- SHARED GAME HANDLER ---
    if user_command in ['!s', '!i']:
        channel_id = message.channel.id
        # FIXED: Use user_command here so case-insensitivity actually works!
        game_type = "splash" if user_command == '!s' else "icon"
        current_games = active_games.get(channel_id, set())

        if not ALLOW_CONCURRENT_GAMES and len(current_games) > 0:
            await message.channel.send("⏳ A game is already running! Finish it first.")
            return
        
        if game_type in current_games:
            await message.channel.send(f"⏳ A {game_type} game is already running!")
            return

        if channel_id not in active_games: active_games[channel_id] = set()
        active_games[channel_id].add(game_type)

        try:
            if game_type == "splash":
                await splash.start_splash_game(client, message, scores, save_scores)
            else:
                await icon.start_icon_game(client, message, scores, save_scores)
        finally:
            active_games[channel_id].discard(game_type)

# --- RUN BOT ---
client.run(TOKEN)