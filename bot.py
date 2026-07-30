import discord
from discord.ext import commands
import random
import asyncio
import json
import os
from dotenv import load_dotenv

# .env 파일에서 토큰을 불러옵니다.
load_dotenv()

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'{bot.user.name} 봇이 성공적으로 켜졌습니다! 암시장 통신망 연결 완료.')

# ==========================================
# 💾 데이터 저장 기능 (JSON 장부 시스템)
# ==========================================
DATA_FILE = 'survival_data.json'

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        user_balances = json.load(f)
else:
    user_balances = {}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_balances, f, ensure_ascii=False, indent=4)

def is_registered(user_id):
    return str(user_id) in user_balances

def add_balance(user_id, amount):
    user_id = str(user_id)
    user_balances[user_id] += amount
    save_data()

# ==========================================
# 📜 0. 생존자 등록 시스템 (!생존신고)
# ==========================================
@bot.command()
async def 생존신고(ctx):
    user_id = str(ctx.author.id)
    
    if is_registered(user_id):
        await ctx.send("⚠️ 이미 암시장 명부에 등록된 생존자입니다. 통신망을 자유롭게 이용하십시오.")
    else:
        user_balances[user_id] = 1000
        save_data()
        await ctx.send(f"📜 **[등록 완료]** {ctx.author.name}님, 암시장에 오신 것을 환영합니다.\n초기 정착 지원금으로 생존 식량 **1000개**가 지급되었습니다.")

# ==========================================
# 1. 지갑 및 송금 기능
# ==========================================
@bot.command()
async def 지갑(ctx):
    if not is_registered(ctx.author.id):
        await ctx.send("⚠️ 미등록 생존자입니다. 먼저 `!생존신고`를 입력해 암시장에 등록해 주세요.")
        return
        
    잔액 = user_balances[str(ctx.author.id)]
    await ctx.send(f"🎒 **{ctx.author.name}**님의 남은 생존 식량: **{잔액}개**")

@bot.command()
async def 송금(ctx, 대상: discord.Member, 금액: int):
    if not is_registered(ctx.author.id) or not is_registered(대상.id):
        await ctx.send("⚠️ 본인 또는 상대방이 미등록 생존자입니다. 등록 후 이용해 주세요.")
        return
        
    if 금액 <= 0:
        await ctx.send("⚠️ 암시장에서는 1개 이상의 식량만 거래할 수 있습니다.")
        return
        
    내잔고 = user_balances[str(ctx.author.id)]
    if 금액 > 내잔고:
        await ctx.send(f"⚠️ 식량이 부족합니다! (현재 보유량: {내잔고}개)")
        return
    
    add_balance(ctx.author.id, -금액)
    add_balance(대상.id, 금액)
    await ctx.send(f"🤝 **{ctx.author.name}**님이 **{대상.name}**님에게 생존 식량 **{금액}개**를 건네주었습니다.")

# ==========================================
# 2. 도박 기능들 (탐색, 주파수, 룰렛)
# ==========================================
@bot.command()
async def 탐색(ctx, 방향: str, 배팅액: int):
    if not is_registered(ctx.author.id):
        await ctx.send("⚠️ 미등록 생존자입니다. 먼저 `!생존신고`를 입력해 암시장에 등록해 주세요.")
        return
        
    내잔고 = user_balances[str(ctx.author.id)]
    if 배팅액 <= 0 or 배팅액 > 내잔고:
        await ctx.send(f"⚠️ 식량이 부족하거나 잘못된 수량입니다. (현재: {내잔고}개)")
        return
        
    if 방향 not in ['왼쪽', '오른쪽']:
        await ctx.send("⚠️ `!탐색 왼쪽 [수량]` 또는 `!탐색 오른쪽 [수량]`으로 입력해 주세요!")
        return

    await ctx.send(f"🔦 {ctx.author.name}님이 어두운 폐허의 **{방향}** 골목으로 진입합니다...")
    await asyncio.sleep(1.5)

    if random.choice(['성공', '실패']) == '성공':
        add_balance(ctx.author.id, 배팅액)
        await ctx.send(f"📦 **[탐색 성공]** 무사히 물자를 구했습니다! 식량 **{배팅액}개** 추가 획득. (현재: {user_balances[str(ctx.author.id)]}개)")
    else:
        add_balance(ctx.author.id, -배팅액)
        await ctx.send(f"🩸 **[탐색 실패]** 감염자에게 쫓겨 식량을 떨어뜨렸습니다... 식량 **{배팅액}개** 상실. (현재: {user_balances[str(ctx.author.id)]}개)")

@bot.command()
async def 주파수(ctx, 배팅액: int):
    if not is_registered(ctx.author.id):
        await ctx.send("⚠️ 미등록 생존자입니다. 먼저 `!생존신고`를 입력해 암시장에 등록해 주세요.")
        return
        
    내잔고 = user_balances[str(ctx.author.id)]
    if 배팅액 <= 0 or 배팅액 > 내잔고:
        await ctx.send(f"⚠️ 식량이 부족합니다. (현재: {내잔고}개)")
        return

    await ctx.send("📻 낡은 무전기의 주파수 다이얼을 돌립니다. `[ 찌직... 삐빅... ]`")
    await asyncio.sleep(1)

    신호목록 = ['🔴', '🟢', '🔵', '⚡', '💀']
    신호1, 신호2, 신호3 = random.choice(신호목록), random.choice(신호목록), random.choice(신호목록)
    결과화면 = f"**[ {신호1} | {신호2} | {신호3} ]**\n"
    
    if 신호1 == 신호2 == 신호3:
        if 신호1 == '💀':
            잃을돈 = 배팅액 * 3
            add_balance(ctx.author.id, -잃을돈)
            await ctx.send(결과화면 + f"🚫 **[저주받은 주파수]** 비명소리! 식량 **{잃을돈}개** 상실. (현재: {user_balances[str(ctx.author.id)]}개)")
        else:
            얻을돈 = 배팅액 * 5
            add_balance(ctx.author.id, 얻을돈)
            await ctx.send(결과화면 + f"📡 **[통신 동기화 100%]** 잭팟! 식량 **{얻을돈}개** 획득! (현재: {user_balances[str(ctx.author.id)]}개)")
    elif 신호1 == 신호2 or 신호2 == 신호3 or 신호1 == 신호3:
        얻을돈 = int(배팅액 * 0.5)
        add_balance(ctx.author.id, 얻을돈)
        await ctx.send(결과화면 + f"안전한 신호를 잡았습니다. 식량 **{얻을돈}개** 추가 획득. (현재: {user_balances[str(ctx.author.id)]}개)")
    else:
        add_balance(ctx.author.id, -배팅액)
        await ctx.send(결과화면 + f"잡음만 들립니다. 통신 실패로 식량 **{배팅액}개** 상실. (현재: {user_balances[str(ctx.author.id)]}개)")

roulette_state = {} 

@bot.command()
async def 룰렛(ctx, 배팅액: int):
    if not is_registered(ctx.author.id):
        await ctx.send("⚠️ 미등록 생존자입니다. 먼저 `!생존신고`를 입력해 암시장에 등록해 주세요.")
        return
        
    내잔고 = user_balances[str(ctx.author.id)]
    if 배팅액 <= 0 or 배팅액 > 내잔고:
        await ctx.send(f"⚠️ 식량이 부족합니다. (현재: {내잔고}개)")
        return

    server_id = ctx.guild.id
    if server_id not in roulette_state:
        roulette_state[server_id] = {
            'bullet_position': random.randint(1, 6),
            'current_chamber': 1
        }
        await ctx.send("🔄 **[재장전]** 누군가 실린더를 맹렬히 돌렸습니다. 6개의 실린더 중 1발 장전. `[ 촤르르륵- 탁! ]`")
        await asyncio.sleep(2)

    state = roulette_state[server_id]
    current_chamber = state['current_chamber']
    bullet_position = state['bullet_position']
    남은확률 = 7 - current_chamber
    
    await ctx.send(f"🔫 방아쇠를 당깁니다... (현재 격발 확률: 1/{남은확률}) `[ 찰칵... ]`")
    await asyncio.sleep(2)
    
    if current_chamber == bullet_position:
        add_balance(ctx.author.id, -배팅액)
        await ctx.send(f"💥 **[탕!]** {ctx.author.name}님 쓰러짐. 식량 **{배팅액}개** 상실. (현재: {user_balances[str(ctx.author.id)]}개)")
        del roulette_state[server_id]
    else:
        state['current_chamber'] += 1
        얻을돈 = 배팅액 * 남은확률 
        add_balance(ctx.author.id, 얻을돈)
        await ctx.send(f"💨 **[빈 약실]** 생존 보상으로 식량 **{얻을돈}개** 획득. (현재: {user_balances[str(ctx.author.id)]}개)\n⚠️ *다음 사람은 더 위험해집니다...*")

# ==========================================
# 3. 봇 구동 (토큰 보안 처리)
# ==========================================
token = os.environ.get('DISCORD_TOKEN')