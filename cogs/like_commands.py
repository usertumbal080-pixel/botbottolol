"""
Cog: Like Commands
Slash command /like untuk kirim like ke profil Free Fire.
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import time
from dotenv import load_dotenv

load_dotenv()

API_URL     = os.environ.get("API_URL", "http://localhost:5000")
API_KEY     = os.environ.get("API_KEY", "")
COOLDOWN_S  = int(os.environ.get("COOLDOWN", "30"))   # detik antar request per user

VALID_REGIONS = ["ID", "IND", "ME", "VN", "TH", "BD", "PK", "BR", "CIS", "SAC", "TW", "SG"]

# Warna embed
COLOR_SUCCESS = 0x00FF88
COLOR_ERROR   = 0xFF4444
COLOR_LOADING = 0xFFAA00


class LikeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot       = bot
        self.cooldowns: dict[int, float] = {}   # user_id → last_used timestamp

    # ── Helper: cek cooldown ──────────────────────────────────────────────────

    def _check_cooldown(self, user_id: int) -> float:
        """Return sisa cooldown dalam detik. 0 = boleh jalan."""
        last = self.cooldowns.get(user_id, 0)
        elapsed = time.time() - last
        remaining = COOLDOWN_S - elapsed
        return max(0.0, remaining)

    def _set_cooldown(self, user_id: int):
        self.cooldowns[user_id] = time.time()

    # ── Helper: API request ───────────────────────────────────────────────────

    async def _get_player_info(self, uid: str, region: str) -> dict | None:
        headers = {}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        url = f"{API_URL}/playerinfo?uid={uid}&region={region}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            pass
        return None

    async def _send_like(self, uid: str, region: str) -> dict | None:
        headers = {"Content-Type": "application/json"}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        url = f"{API_URL}/like?uid={uid}&region={region}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    data["_status"] = resp.status
                    return data
        except Exception as e:
            return {"error": str(e), "_status": 0}

    # ── /like command ─────────────────────────────────────────────────────────

    @app_commands.command(name="like", description="Kirim like ke profil Free Fire")
    @app_commands.describe(
        uid    = "UID / Player ID Free Fire",
        region = "Region akun (ID, IND, ME, VN, dll)"
    )
    @app_commands.choices(region=[
        app_commands.Choice(name=r, value=r) for r in VALID_REGIONS
    ])
    async def like_command(
        self,
        interaction: discord.Interaction,
        uid: str,
        region: app_commands.Choice[str] = None
    ):
        # Validasi UID
        if not uid.isdigit():
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ UID Tidak Valid",
                    description="UID harus berupa angka. Contoh: `/like uid:123456789`",
                    color=COLOR_ERROR
                ),
                ephemeral=True
            )
            return

        region_val = region.value if region else "ID"

        # Cek cooldown
        remaining = self._check_cooldown(interaction.user.id)
        if remaining > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⏳ Cooldown Aktif",
                    description=f"Tunggu **{remaining:.1f} detik** lagi sebelum kirim like.",
                    color=COLOR_LOADING
                ),
                ephemeral=True
            )
            return

        # Loading embed
        loading_embed = discord.Embed(
            title="🔄 Memproses Like...",
            description=(
                f"**UID:** `{uid}`\n"
                f"**Region:** `{region_val}`\n\n"
                f"⏳ Mengirim like, harap tunggu..."
            ),
            color=COLOR_LOADING
        )
        loading_embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
        await interaction.response.send_message(embed=loading_embed)

        # Set cooldown sebelum proses (agar tidak spam saat loading)
        self._set_cooldown(interaction.user.id)

        # Kirim like (sudah include before & after di API)
        result = await self._send_like(uid, region_val)

        if not result or result.get("_status", 0) not in (200,) or not result.get("success"):
            err_msg = result.get("error", "Tidak dapat menghubungi server API") if result else "Timeout"
            error_embed = discord.Embed(
                title="❌ Gagal Mengirim Like",
                color=COLOR_ERROR
            )
            error_embed.add_field(name="UID",    value=f"`{uid}`",        inline=True)
            error_embed.add_field(name="Region", value=f"`{region_val}`", inline=True)
            error_embed.add_field(name="Error",  value=f"`{err_msg}`",    inline=False)
            error_embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
            await interaction.edit_original_response(embed=error_embed)
            return

        # Sukses
        likes_before = result.get("likes_before", 0)
        likes_after  = result.get("likes_after",  0)
        likes_added  = result.get("likes_added",  likes_after - likes_before)
        nickname     = result.get("nickname", "Unknown")

        # Bar progress visual likes
        bar_len  = 10
        pct      = min(likes_after / max(likes_after + 100, 1), 1.0)
        filled   = int(bar_len * pct)
        bar      = "█" * filled + "░" * (bar_len - filled)

        success_embed = discord.Embed(
            title="✅ Like Berhasil Dikirim!",
            color=COLOR_SUCCESS
        )
        success_embed.add_field(name="👤 Nickname", value=f"`{nickname}`",   inline=True)
        success_embed.add_field(name="🆔 UID",      value=f"`{uid}`",        inline=True)
        success_embed.add_field(name="🌍 Region",   value=f"`{region_val}`", inline=True)
        success_embed.add_field(
            name="❤️ Like Sebelum",
            value=f"`{likes_before:,}`",
            inline=True
        )
        success_embed.add_field(
            name="💖 Like Sesudah",
            value=f"`{likes_after:,}`",
            inline=True
        )
        success_embed.add_field(
            name="➕ Ditambahkan",
            value=f"`+{likes_added}`",
            inline=True
        )
        success_embed.add_field(
            name="📊 Like Bar",
            value=f"`[{bar}]` {likes_after:,} likes",
            inline=False
        )
        success_embed.set_footer(
            text=f"Diminta oleh {interaction.user.display_name} • Cooldown {COOLDOWN_S}s"
        )
        await interaction.edit_original_response(embed=success_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LikeCommands(bot))
