import os
import sqlite3
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from constant import OW2_CHARACTOR_NAMES, ADD_COMMAND_DESCRIPTION, VIEW_COMMAND_DESCRIPTION

# ================================
# DB 초기화 함수
# ================================
DB_PATH = "builds.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_build(name: str, code: str, description: str, user_id: str, username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO builds (name, code, description, user_id, username) VALUES (?, ?, ?, ?, ?)",
            (name, code, description, user_id, username)
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, str(e)
    finally:
        conn.close()

def get_builds_by_name(name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT code, description, username, created_at
        FROM builds
        WHERE name = ?
        ORDER BY created_at DESC
    """, (name,))
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_build_by_code(code: str, user_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM builds WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "❌ 해당 코드가 존재하지 않습니다."
    if row[0] != str(user_id):
        conn.close()
        return False, "⚠️ 이 빌드는 본인만 삭제할 수 있습니다."
    cur.execute("DELETE FROM builds WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    return True, f"✅ 코드 `{code}` 가 삭제되었습니다."

# ================================
# Discord Bot 초기화
# ================================
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================================
# 봇 준비 이벤트
# ================================
@bot.event
async def on_ready():
    init_db()
    print(f"✅ 로그인 성공: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🔧 Slash 명령어 동기화 완료: {len(synced)}개")
    except Exception as e:
        print(e)

# ================================
# Slash Command 구현
# ================================

@bot.tree.command(name="조회", description=VIEW_COMMAND_DESCRIPTION)
@app_commands.describe(name="영웅 이름")
async def view_command(interaction: discord.Interaction, name: str):
    name = name.strip()
    builds = get_builds_by_name(name)
    if not builds:
        await interaction.response.send_message(f"❌ '{name}' 영웅에 등록된 빌드가 없습니다.", ephemeral=True)
    else:
        response = f"📖 '{name}' 등록된 빌드 목록:\n"
        for i, (code, desc, username, created_at) in enumerate(builds, start=1):
            response += f"\n{i}. 코드: `{code}` | 설명: {desc} | 등록자: {username} | 등록일: {created_at}"
        await interaction.response.send_message(response, ephemeral=True)

@bot.tree.command(name="추가", description=ADD_COMMAND_DESCRIPTION)
@app_commands.describe(name="영웅 이름", code="빌드 코드", description="간단한 설명")
async def add_command(interaction: discord.Interaction, name: str, code: str, description: str):
    name = name.strip()
    code = code.strip().upper()
    description = description.strip()
    if not(name in OW2_CHARACTOR_NAMES and len(code) == 5):
        await interaction.response.send_message(
            f"⚠️ 형식 오류 발생: 정확한 영웅 이름과 빌드 코드 형식(영문 숫자 5자)을 입력하세요.\n"
            f"{OW2_CHARACTOR_NAMES}",
            ephemeral=True
        )
        return
    success, err = add_build(name, code, description, str(interaction.user.id), interaction.user.name)
    if success:
        await interaction.response.send_message(
            f"📌 영웅 '{name}' 에 빌드가 추가되었습니다!\n"
            f"코드: `{code}` | 설명: {description} | 등록자: {interaction.user.name}",
            ephemeral=True
        )
    else:
        if "UNIQUE constraint failed" in err:
            await interaction.response.send_message(f"⚠️ 코드 `{code}` 는 이미 등록되어 있습니다.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ 등록 중 오류 발생: {err}", ephemeral=True)

@bot.tree.command(name="삭제", description="등록한 빌드를 삭제합니다.")
@app_commands.describe(code="빌드 코드")
async def delete_command(interaction: discord.Interaction, code: str):
    code = code.strip().upper()
    success, message = delete_build_by_code(code, str(interaction.user.id))
    await interaction.response.send_message(message, ephemeral=True)

# ================================
# 실행
# ================================
bot.run(DISCORD_TOKEN)
