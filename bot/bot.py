"""
Animal Company Discord Bot
Slash commands: /get-auth, /get-api
Calls the Railway-hosted backend API.
"""

import os
import asyncio
import aiohttp
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_BASE      = os.getenv("API_BASE_URL", "http://localhost:8000")   # your Railway backend URL
INTERNAL_KEY  = os.getenv("INTERNAL_KEY", "change-this-secret")      # must match backend

# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)


def api_headers() -> dict:
    return {
        "x-internal-key": INTERNAL_KEY,
        "Content-Type": "application/json",
    }


# ── /get-auth ─────────────────────────────────────────────────────────────────
@tree.command(
    name="get-auth",
    description="Register your Animal Company in-game pairing code and get your API key.",
)
@app_commands.describe(
    pairing_code="The code shown on the in-game computer's Pair screen (e.g. AB12CD34)."
)
async def get_auth(interaction: discord.Interaction, pairing_code: str):
    await interaction.response.defer(ephemeral=True)

    payload = {
        "discord_id":   str(interaction.user.id),
        "discord_name": interaction.user.display_name,
        "pairing_code": pairing_code.strip().upper(),
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/auth",
                json=payload,
                headers=api_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

                if resp.status == 200:
                    embed = discord.Embed(
                        title="✅ Authenticated!",
                        color=discord.Color.green(),
                        description="Your pairing code has been registered. Here's your API key — keep it safe!",
                    )
                    embed.add_field(name="🐾 Pairing Code",  value=f"`{data['pairing_code']}`",  inline=True)
                    embed.add_field(name="🔑 API Key",       value=f"||`{data['api_key']}`||",   inline=False)
                    embed.add_field(name="📅 Registered At", value=data["registered_at"][:19].replace("T", " ") + " UTC", inline=False)
                    embed.set_footer(text=f"Discord: {interaction.user.display_name}")

                    await interaction.followup.send(embed=embed, ephemeral=True)

                elif resp.status == 422:
                    await interaction.followup.send(
                        f"❌ **Invalid pairing code.**\n"
                        f"{data.get('detail', 'Make sure you copy it exactly from the in-game computer.')}",
                        ephemeral=True,
                    )
                elif resp.status == 409:
                    await interaction.followup.send(
                        f"❌ **Code already taken.**\n"
                        f"{data.get('detail', 'That pairing code is already linked to another account.')}",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Something went wrong (`{resp.status}`): `{data.get('detail', 'unknown error')}`",
                        ephemeral=True,
                    )

    except aiohttp.ClientConnectorError:
        await interaction.followup.send(
            "❌ Can't reach the backend API. Make sure it's running on Railway.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Unexpected error: `{e}`", ephemeral=True)


# ── /get-api ──────────────────────────────────────────────────────────────────
@tree.command(
    name="get-api",
    description="Fetch your Animal Company account data and API key.",
)
async def get_api(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/api/{interaction.user.id}",
                headers=api_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()

                if resp.status == 200:
                    last_used = data.get("last_used")
                    last_used_str = (
                        last_used[:19].replace("T", " ") + " UTC"
                        if last_used else "Never"
                    )

                    embed = discord.Embed(
                        title="🐾 Your Animal Company Account",
                        color=discord.Color.blurple(),
                    )
                    embed.add_field(name="Discord",       value=data["discord_name"],                                          inline=True)
                    embed.add_field(name="Pairing Code",  value=f"`{data['pairing_code']}`",                                   inline=True)
                    embed.add_field(name="API Key",       value=f"||`{data['api_key']}`||",                                    inline=False)
                    embed.add_field(name="Registered",    value=data["registered_at"][:19].replace("T", " ") + " UTC",         inline=True)
                    embed.add_field(name="Last Fetched",  value=last_used_str,                                                  inline=True)
                    embed.set_footer(text="Use /get-auth to update your pairing code at any time.")

                    await interaction.followup.send(embed=embed, ephemeral=True)

                elif resp.status == 404:
                    await interaction.followup.send(
                        "⚠️ No account found for you yet.\n"
                        "Run `/get-auth <pairing_code>` to register your in-game pairing code first!",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error (`{resp.status}`): `{data.get('detail', 'unknown')}`",
                        ephemeral=True,
                    )

    except aiohttp.ClientConnectorError:
        await interaction.followup.send(
            "❌ Can't reach the backend API. Make sure it's running on Railway.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Unexpected error: `{e}`", ephemeral=True)


# ── Startup ───────────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot online: {client.user} | Backend: {API_BASE}")


client.run(DISCORD_TOKEN)
