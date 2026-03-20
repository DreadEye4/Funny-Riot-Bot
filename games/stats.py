import aiohttp
import random

EPOCH_2026 = 1767225600 

async def get_random_player_stats(player_list, api_key):
    headers = {"X-Riot-Token": api_key}
    shuffled_indices = random.sample(range(len(player_list)), len(player_list))
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for i in shuffled_indices:
            player = player_list[i]
            game_name, tag_line = player.split('#')
            
            # 1. Get PUUID
            account_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
            async with session.get(account_url) as resp:
                if resp.status != 200: continue
                account_data = await resp.json()
                puuid = account_data['puuid']

            # 2. Get Matches
            matchlist_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?startTime={EPOCH_2026}&queue=420&count=100"
            async with session.get(matchlist_url) as resp:
                if resp.status != 200: continue
                match_ids = await resp.json()
                
            # 3. Skip if under 3 games
            if len(match_ids) < 3: continue 
                
            # 4. Pick 3 random games
            chosen_matches = random.sample(match_ids, 3)
            
            # --- QOL UPDATE: FETCH CHAMPION MASTERY ---
            # Match IDs look like "NA1_123456". We split it to get "na1" for the mastery URL!
            region = chosen_matches[0].split('_')[0].lower()
            mastery_url = f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}"
            
            mastery_dict = {}
            async with session.get(mastery_url) as resp:
                if resp.status == 200:
                    mastery_data = await resp.json()
                    # Create a fast lookup dictionary: { championId: championPoints }
                    mastery_dict = {m['championId']: m['championPoints'] for m in mastery_data}

            # 5. Get Match Details
            results = []
            for match_id in chosen_matches:
                match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
                async with session.get(match_url) as resp:
                    if resp.status != 200: continue
                    match_data = await resp.json()
                    
                    for p in match_data['info']['participants']:
                        if p['puuid'] == puuid:
                            k, d, a = p['kills'], p['deaths'], p['assists']
                            champ = p['championName']
                            champ_id = p['championId']
                            win = "Victory" if p['win'] else "Defeat"
                            
                            # Lookup points and format with commas (e.g., 1,500,000)
                            pts = mastery_dict.get(champ_id, 0)
                            pts_formatted = f"{pts:,}"
                            
                            # Added the mastery points right next to the champ!
                            results.append(f"- **{champ}** ({pts_formatted} pts) | {win}: {k}/{d}/{a}")
                            break
            
            if len(results) == 3:
                games_text = "\n".join(results)
                
                # Math logic stays exactly the same
                pos = i + 1 
                team_num = (i // 5) + 1
                role_mod = pos % 5
                
                valid_roles = ['top'] if role_mod == 1 else ['jg', 'jungle'] if role_mod == 2 else ['mid', 'middle'] if role_mod == 3 else ['adc', 'bot'] if role_mod == 4 else ['sup', 'support']
                
                clean_target_name = game_name.lower().replace(" ", "")
                valid_team_guesses = [f"team{team_num}{r}" for r in valid_roles]
                
                return {
                    "success": True,
                    "games_text": games_text,
                    "target_name": game_name,
                    "clean_target_name": clean_target_name,
                    "valid_team_guesses": valid_team_guesses,
                    "team_num": team_num,
                    "role_display": valid_roles[0].title()
                }
                
        return {"success": False, "error_msg": "❌ Nobody has played 3 Ranked Solo/Duo games in 2026 yet!"}