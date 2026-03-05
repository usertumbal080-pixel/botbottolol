"""
Cog: Like Commands
Slash command /like untuk kirim like ke profil Free Fire.
Webhook 1: notif tiap ada yang berhasil kirim like
Webhook 2: notif error/log API
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL              = os.environ.get("API_URL", "http://localhost:5000")
API_KEY              = os.environ.get("API_KEY", "")
COOLDOWN_S           = int(os.environ.get("COOLDOWN", "30"))
WEBHOOK_LIKE_URL     = os.environ.get("WEBHOOK_LIKE_URL", "")    # notif tiap ada like masuk
WEBHOOK_LOG_URL      = os.environ.get("WEBHOOK_LOG_URL", "")     # notif error / log API

VALID_REGIONS = ["ID", "IND", "ME", "VN", "TH", "BD", "PK", "BR", "CIS", "SAC", "TW", "SG"]

COLOR_SUCCESS = 0x00FF88
COLOR_ERROR   = 0xFF4444
COLOR_LOADING = 0xFFAA00
COLOR_LOG     = 0x5865F2


class LikeCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot       = bot
        self.cooldowns: dict[int, float] = {}

    # ── Cooldown ──────────────────────────────────────────────────────────────

    def _check_cooldown(self, user_id: int) -> float:
        last      = self.cooldowns.get(user_id, 0)
        remaining = COOLDOWN_S - (time.time() - last)
        return max(0.0, remaining)

    def _set_cooldown(self, user_id: int):
        self.cooldowns[user_id] = time.time()

    # ── Webhook senders ───────────────────────────────────────────────────────

    async def _send_webhook_like(
        self,
        session: aiohttp.ClientSession,
        uid: str,
        nickname: str,
        region: str,
        likes_before: int,
        likes_after: int,
        likes_added: int,
        requested_by: str,
        guild_name: str,
    ):
        """Kirim notif ke webhook LIKE setiap ada like berhasil."""
        if not WEBHOOK_LIKE_URL:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "username":   "💖 FF Like Logger",
            "embeds": [{
                "title":  "💖 Like Berhasil Dikirim",
                "color":  COLOR_SUCCESS,
                "fields": [
                    {"name": "👤 Nickname",     "value": f"`{nickname}`",       "inline": True},
                    {"name": "🆔 UID",          "value": f"`{uid}`",            "inline": True},
                    {"name": "🌍 Region",       "value": f"`{region}`",         "inline": True},
                    {"name": "❤️ Like Sebelum", "value": f"`{likes_before:,}`", "inline": True},
                    {"name": "💖 Like Sesudah", "value": f"`{likes_after:,}`",  "inline": True},
                    {"name": "➕ Ditambahkan",  "value": f"`+{likes_added}`",   "inline": True},
                    {"name": "👮 Diminta oleh", "value": f"`{requested_by}`",   "inline": True},
                    {"name": "🏠 Server",       "value": f"`{guild_name}`",     "inline": True},
                ],
                "footer": {"text": f"FF Like Bot • {now}"}
            }]
        }
        try:
            await session.post(WEBHOOK_LIKE_URL, json=payload, timeout=aiohttp.ClientTimeout(total=10))
        except Exception:
            pass

    async def _send_webhook_log(
        self,
        session: aiohttp.ClientSession,
        level: str,
        title: str,
        detail: str,
        uid: str = "",
        region: str = "",
        requested_by: str = "",
    ):
        """Kirim log/error ke webhook LOG."""
        if not WEBHOOK_LOG_URL:
            return
        color_map = {"ERROR": COLOR_ERROR, "WARN": COLOR_LOADING, "INFO": COLOR_LOG}
        icon_map  = {"ERROR": "🚨", "WARN": "⚠️", "INFO": "ℹ️"}
        now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = [{"name": "📋 Detail", "value": f"```{detail[:1000]}```", "inline": False}]
        if uid:
            fields.insert(0, {"name": "🆔 UID",    "value": f"`{uid}`",    "inline": True})
        if region:
            fields.insert(1, {"name": "🌍 Region", "value": f"`{region}`", "inline": True})
        if requested_by:
            fields.append({"name": "👮 User", "value": f"`{requested_by}`", "inline": True})

        payload = {
            "username": "🔧 FF API Logger",
            "embeds": [{
                "title":  f"{icon_map.get(level, 'ℹ️')} [{level}] {title}",
                "color":  color_map.get(level, COLOR_LOG),
                "fields": fields,
                "footer": {"text": f"FF Like Bot • {now}"}
            }]
        }
        try:
            await session.post(WEBHOOK_LOG_URL, json=payload, timeout=aiohttp.ClientTimeout(total=10))
        except Exception:
            pass

    # ── API request ───────────────────────────────────────────────────────────

    async def _send_like(self, uid: str, region: str) -> dict:
        headers = {}
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
        requested_by = str(interaction.user)
        guild_name   = interaction.guild.name if interaction.guild else "DM"
        region_val   = region.value if region else "ID"

        # Validasi UID — bisa langsung respond karena belum defer
        if not uid.isdigit():
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ UID Tidak Valid",
                    description="UID harus berupa angka. Contoh: `/like uid:123456789`",
                    color=COLOR_ERROR
                ),
                ephemeral=True
            )
            async with aiohttp.ClientSession() as s:
                await self._send_webhook_log(s, "WARN", "UID Tidak Valid",
                    f"User {requested_by} input UID tidak valid: '{uid}'",
                    uid=uid, region=region_val, requested_by=requested_by)
            return

        # Cek cooldown — bisa langsung respond karena belum defer
        remaining = self._check_cooldown(interaction.user.id)
        if remaining > 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="⏳ Cooldown Aktif",
                    description=f"Tunggu **{remaining:.1f} detik** lagi.",
                    color=COLOR_LOADING
                ),
                ephemeral=True
            )
            return

        # ── DEFER dulu sebelum proses yang lama ──
        # Ini memberitahu Discord "bot sedang proses" sehingga tidak timeout 3 detik
        await interaction.response.defer()
        self._set_cooldown(interaction.user.id)

        # Kirim like
        result = await self._send_like(uid, region_val)

        # ── Gagal ──
        if not result or result.get("_status") != 200 or not result.get("success"):
            err_msg = result.get("error", "Tidak dapat menghubungi server API") if result else "Timeout"

            error_embed = discord.Embed(title="❌ Gagal Mengirim Like", color=COLOR_ERROR)
            error_embed.add_field(name="UID",    value=f"`{uid}`",        inline=True)
            error_embed.add_field(name="Region", value=f"`{region_val}`", inline=True)
            error_embed.add_field(name="Error",  value=f"`{err_msg}`",    inline=False)
            error_embed.set_footer(text=f"Diminta oleh {interaction.user.display_name}")
            await interaction.followup.send(embed=error_embed)

            async with aiohttp.ClientSession() as s:
                await self._send_webhook_log(
                    s, "ERROR", "Gagal Kirim Like", err_msg,
                    uid=uid, region=region_val, requested_by=requested_by
                )
            return

        # ── Sukses ──
        likes_before = result.get("likes_before", 0)
        likes_after  = result.get("likes_after",  0)
        likes_added  = result.get("likes_added",  likes_after - likes_before)
        nickname     = result.get("nickname", "Unknown")

        bar_len = 10
        pct     = min(likes_after / max(likes_after + 100, 1), 1.0)
        bar     = "█" * int(bar_len * pct) + "░" * (bar_len - int(bar_len * pct))

        success_embed = discord.Embed(title="✅ Like Berhasil Dikirim!", color=COLOR_SUCCESS)
        success_embed.add_field(name="👤 Nickname",     value=f"`{nickname}`",       inline=True)
        success_embed.add_field(name="🆔 UID",          value=f"`{uid}`",            inline=True)
        success_embed.add_field(name="🌍 Region",       value=f"`{region_val}`",     inline=True)
        success_embed.add_field(name="❤️ Like Sebelum", value=f"`{likes_before:,}`", inline=True)
        success_embed.add_field(name="💖 Like Sesudah", value=f"`{likes_after:,}`",  inline=True)
        success_embed.add_field(name="➕ Ditambahkan",  value=f"`+{likes_added}`",   inline=True)
        success_embed.add_field(name="📊 Like Bar",     value=f"`[{bar}]` {likes_after:,} likes", inline=False)
        success_embed.set_footer(text=f"Diminta oleh {interaction.user.display_name} • Cooldown {COOLDOWN_S}s")
        await interaction.followup.send(embed=success_embed)

        # Kirim ke kedua webhook
        async with aiohttp.ClientSession() as s:
            await self._send_webhook_like(
                s, uid, nickname, region_val,
                likes_before, likes_after, likes_added,
                requested_by, guild_name
            )
            await self._send_webhook_log(
                s, "INFO", "Like Berhasil",
                f"Nickname: {nickname} | {likes_before} → {likes_after} (+{likes_added})",
                uid=uid, region=region_val, requested_by=requested_by
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(LikeCommands(bot))
