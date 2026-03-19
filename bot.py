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

    # Update Help to show !i
    if message.content in ['!help', '!h']:
        embed = discord.Embed(title="💀 Hardstuck | Commands", color=discord.Color.green())
        embed.add_field(name="!s", value="Splash Art Trivia", inline=True)
        embed.add_field(name="!i", value="Blurry Icon Trivia", inline=True)
        embed.add_field(name="!skip", value="Skips the current game (Only the person who started it can skip).", inline=False)
        embed.add_field(name="!stat", value="Check your scores", inline=True)
        embed.add_field(name="!h / !help", value="Show this useless menu.", inline=False)
        await message.channel.send(embed=embed)
        return

    # Update Stats to show both
    if message.content == '!stat':
        guild_id = str(message.guild.id) if message.guild else "DMs"
        user_id = str(message.author.id)
        user_data = scores.get(guild_id, {}).get(user_id, {})
        
        s_score = user_data.get("splash", 0)
        i_score = user_data.get("icon", 0)
        
        await message.channel.send(
            f"📊 {message.author.mention}'s Waste of Time:\n"
            f"🖼️ **Splash Art:** {s_score}\n"
            f"🔍 **Blurry Icons:** {i_score}"
        )
        return

    # --- SHARED GAME HANDLER ---
    # This logic checks if ANY game is running before starting a new one
    if message.content in ['!s', '!i']:
        channel_id = message.channel.id
        game_type = "splash" if message.content == '!s' else "icon"
        current_games = active_games.get(channel_id, set())

        # If ANY game is in the set, and concurrency is off, block it.
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

TOKEN = os.getenv('DISCORD_TOKEN')
client.run(TOKEN)