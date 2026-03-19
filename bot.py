import discord
import json
import os
from dotenv import load_dotenv
import games.icon as icon

# NEW: Import the splash file we just made!
import games.splash as splash 

load_dotenv()

# Tell it to look in the data folder
SCORE_FILE = "data/scores.json"

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
            key=lambda x: x[1], 
            reverse=True
        )[:5] # Grabs the top 5
        
        icon_top = sorted(
            [(uid, data.get('icon', 0)) for uid, data in guild_scores.items() if data.get('icon', 0) > 0],
            key=lambda x: x[1], 
            reverse=True
        )[:5] # Grabs the top 5
        
        embed = discord.Embed(title=f"🏆 {message.guild.name} | Leaderboards", color=discord.Color.gold())
        
        # Format the text (using <@id> tags them without actually sending a ping notification)
        splash_text = "\n".join([f"**{i+1}.** <@{uid}> - {score}" for i, (uid, score) in enumerate(splash_top)])
        icon_text = "\n".join([f"**{i+1}.** <@{uid}> - {score}" for i, (uid, score) in enumerate(icon_top)])
        
        embed.add_field(name="🖼️ Top Splashers", value=splash_text if splash_text else "No points yet.", inline=True)
        embed.add_field(name="🔍 Top Blurry Icons", value=icon_text if icon_text else "No points yet.", inline=True)
        
        await message.channel.send(embed=embed)
        return

    # --- FEATURE 2: TARGETED STATS ---
    # Change == to .startswith() so it catches "!stat @username"
    if user_command.startswith('!stat'):
        guild_id = str(message.guild.id) if message.guild else "DMs"
        
        # If they mentioned someone, check that person. Otherwise, check themselves.
        if message.mentions:
            target_user = message.mentions[0]
        else:
            target_user = message.author
            
        user_id = str(target_user.id)
        user_data = scores.get(guild_id, {}).get(user_id, {})
        
        s_score = user_data.get("splash", 0)
        i_score = user_data.get("icon", 0)
        
        await message.channel.send(
            f"📊 {target_user.mention}'s Waste of Time:\n"
            f"🖼️ **Splash Art:** {s_score}\n"
            f"🔍 **Blurry Icons:** {i_score}"
        )
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
TOKEN = os.getenv('DISCORD_TOKEN')
client.run(TOKEN)