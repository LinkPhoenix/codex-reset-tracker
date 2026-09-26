from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlsplit

import discord
from discord import app_commands
from discord.ext import commands

from .config import AppConfig
from .models import TweetMatch
from .notifiers import AlertMessage, NotificationError, format_alert
from .runner import LAST_SCAN_AT_KEY, QuotaResetTracker
from .state import StateStore
from .time_window import parse_created_at

LOGGER = logging.getLogger(__name__)
BOT_TOKEN_ENV = "CODQ_DISCORD_BOT_TOKEN"
TEST_GUILD_ID_ENV = "CODQ_DISCORD_TEST_GUILD_ID"
ALLOWED_SOURCE_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}


class CodexResetBot(commands.Bot):
    def __init__(self, state: StateStore):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.state = state

    async def setup_hook(self) -> None:
        await self.add_cog(ResetBotCommands(self))
        test_guild_id = os.getenv(TEST_GUILD_ID_ENV, "").strip()
        if not test_guild_id:
            await self.tree.sync()
            return
        try:
            guild_id = int(test_guild_id)
        except ValueError as exc:
            raise NotificationError(f"{TEST_GUILD_ID_ENV} must be a numeric Discord server ID") from exc
        if guild_id <= 0:
            raise NotificationError(f"{TEST_GUILD_ID_ENV} must be a positive Discord server ID")

        test_guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=test_guild)
        await self.tree.sync(guild=test_guild)
        LOGGER.info("synced slash commands to the test guild %s", guild_id)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.state.remove_discord_channel(guild.id)
        LOGGER.info("removed Discord alert subscription for departed guild %s", guild.id)

    async def send_match(self, match: TweetMatch) -> dict[str, dict[str, object]]:
        destinations = self.state.discord_channels()
        if not destinations:
            LOGGER.info("no Discord servers are subscribed; skipping this alert")
            return {"discord": {"ok": True, "delivered": 0, "reason": "no_subscribers"}}

        message = format_alert("Potential AI quota reset", match)
        results: dict[str, dict[str, object]] = {}
        delivered_guilds = self.state.discord_delivered_guilds(match.alert_key)
        for guild_id, channel_id in destinations:
            key = str(guild_id)
            if guild_id in delivered_guilds:
                results[key] = {"ok": True, "skipped": "already_delivered"}
                continue
            try:
                channel = self.get_channel(channel_id)
                if channel is None:
                    channel = await self.fetch_channel(channel_id)
                if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                    raise NotificationError("Configured destination is not a text channel")
                await channel.send(
                    embed=_alert_embed(message),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                self.state.mark_discord_delivered(
                    match.alert_key, guild_id, channel_id
                )
            except (discord.HTTPException, NotificationError) as exc:
                LOGGER.warning("Discord delivery failed for guild %s: %s", guild_id, exc)
                results[key] = {"ok": False, "error": str(exc)}
            else:
                results[key] = {"ok": True}

        failed_guilds = [
            guild_id for guild_id, result in results.items() if not result["ok"]
        ]
        if failed_guilds:
            raise NotificationError(
                f"Discord delivery is incomplete for guilds {failed_guilds}; "
                "successful guild deliveries are saved for retry"
            )
        return results


class ResetBotCommands(commands.Cog):
    def __init__(self, bot: CodexResetBot):
        self.bot = bot

    @app_commands.command(
        name="set-alert-channel",
        description="Use this channel for Codex and Claude reset alerts",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(channel="Text channel that should receive reset alerts")
    async def set_alert_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild = interaction.guild
        target = channel or interaction.channel
        if guild is None or target is None:
            await interaction.response.send_message(
                "This command can only be used in a server channel.", ephemeral=True
            )
            return
        if not isinstance(target, discord.TextChannel) or target.guild.id != guild.id:
            await interaction.response.send_message(
                "Choose a text channel in this server.", ephemeral=True
            )
            return

        missing = _missing_channel_permissions(guild, target)
        if missing:
            await interaction.response.send_message(
                "I cannot post embeds in that channel. Grant me: "
                + ", ".join(missing)
                + ".",
                ephemeral=True,
            )
            return

        self.bot.state.set_discord_channel(guild.id, target.id)
        await interaction.response.send_message(
            f"Reset alerts will be posted in {target.mention}.", ephemeral=True
        )

    @app_commands.command(
        name="stop-alerts", description="Disable reset alerts for this server"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def stop_alerts(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        removed = self.bot.state.remove_discord_channel(interaction.guild_id)
        message = (
            "Reset alerts are disabled for this server."
            if removed
            else "This server had no alert channel configured."
        )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name="reset-bot-status", description="Show this server's reset alert setup"
    )
    async def reset_bot_status(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        configured = dict(self.bot.state.discord_channels()).get(interaction.guild.id)
        if configured is None:
            response = (
                "Alerts are not configured for this server. A server manager can run "
                "`/set-alert-channel` here or choose a channel with its option."
            )
        else:
            channel = self.bot.get_channel(configured)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(configured)
                except discord.HTTPException:
                    channel = None
            if not isinstance(channel, discord.TextChannel):
                response = (
                    f"Alerts point to <#{configured}>, but that text channel is "
                    "unavailable. A server manager can select a new one with "
                    "`/set-alert-channel`."
                )
            else:
                missing = _missing_channel_permissions(interaction.guild, channel)
                response = f"Alerts are configured for {channel.mention}."
                if missing:
                    response += " I still need: " + ", ".join(missing) + "."
                else:
                    response += " The channel is ready to receive embeds."
        response += f"\nBot latency: {round(self.bot.latency * 1000)} ms."
        last_scan = parse_created_at(self.bot.state.get_metadata(LAST_SCAN_AT_KEY))
        if last_scan is None:
            response += "\nThe tracker has not completed its first scan yet."
        else:
            response += f"\nLast completed tracker scan: <t:{int(last_scan.timestamp())}:R>."
        await interaction.followup.send(response, ephemeral=True)

    @app_commands.command(
        name="test-reset-alert",
        description="Post one clearly labeled synthetic alert to the configured channel",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def test_reset_alert(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return

        configured = dict(self.bot.state.discord_channels()).get(guild.id)
        if configured is None:
            await interaction.response.send_message(
                "No alert channel is configured. Run `/set-alert-channel` first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = self.bot.get_channel(configured)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(configured)
            except discord.HTTPException:
                channel = None
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != guild.id:
            await interaction.followup.send(
                "The configured alert channel is unavailable. Choose another with `/set-alert-channel`.",
                ephemeral=True,
            )
            return

        missing = _missing_channel_permissions(guild, channel)
        if missing:
            await interaction.followup.send(
                "I cannot send the test alert there. Grant me: "
                + ", ".join(missing)
                + ".",
                ephemeral=True,
            )
            return

        try:
            await channel.send(
                embed=_alert_embed(_test_alert_message()),
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            LOGGER.warning(
                "Discord test-alert delivery failed for guild %s: %s",
                guild.id,
                type(exc).__name__,
            )
            await interaction.followup.send(
                "Discord rejected the test alert. Check channel permissions and try again.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"A clearly labeled test alert was posted in {channel.mention}. It contains no real reset signal.",
            ephemeral=True,
        )

    @app_commands.command(
        name="preview-reset-alert",
        description="Preview the reset alert privately without posting to the alert channel",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def preview_reset_alert(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "Private preview only; no alert was posted.",
            embed=_alert_embed(_preview_alert_message()),
            ephemeral=True,
        )

    @app_commands.command(
        name="reset-bot-help", description="Show setup steps and available bot commands"
    )
    async def reset_bot_help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Codex Reset Tracker",
            description=(
                "This bot relays possible Codex and Claude reset signals from "
                "tracked public X accounts. A signal is an estimate, not a guarantee."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Server managers",
            value=(
                "`/set-alert-channel [channel]` — choose where alerts appear\n"
                "`/test-reset-alert` — post a clearly labeled test message\n"
                "`/preview-reset-alert` — preview the embed privately\n"
                "`/stop-alerts` — disable alerts for this server"
            ),
            inline=False,
        )
        embed.add_field(
            name="Everyone",
            value="`/reset-bot-status` checks this server's setup and `/reset-bot-help` shows this guide.",
            inline=False,
        )
        embed.set_footer(text="For push alerts, check your Discord channel and device notification settings.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Only a server manager with Manage Server permission can do that."
        else:
            original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
            LOGGER.error(
                "Discord application command failed: %s",
                type(original).__name__,
                exc_info=(type(original), original, original.__traceback__),
            )
            message = "That command failed. Check the bot's channel permissions and try again."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def _alert_embed(message: AlertMessage) -> discord.Embed:
    payload = message.payload
    product = message.title.lower()
    if "claude" in product:
        color = 0xD97757
    elif "codex" in product:
        color = 0x10A37F
    else:
        color = 0x5865F2
    embed = discord.Embed(
        title=message.title[:256],
        url=_safe_source_url(message.url),
        description=discord.utils.escape_markdown(
            discord.utils.escape_mentions(str(payload.get("excerpt", message.body)))
        )[:4096],
        color=discord.Color(color),
    )
    embed.set_author(
        name=discord.utils.escape_markdown(
            f"@{payload.get('author_username', 'unknown')} · {payload.get('source', 'X')}"
        )[:256]
    )
    created_at = payload.get("created_at")
    if created_at:
        timestamp = parse_created_at(str(created_at))
        if timestamp is not None:
            embed.timestamp = timestamp
    embed.add_field(
        name="Signal",
        value=str(
            payload.get("signal_label", "Reset-related post from a tracked public account")
        )[:1024],
        inline=True,
    )
    window = payload.get("reset_window")
    if isinstance(window, dict):
        embed.add_field(
            name="Estimated reset window",
            value=(
                f"{window.get('user_start_at')} – {window.get('user_end_at')}\n"
                f"Timezone: {window.get('user_timezone')} · "
                f"Confidence: {window.get('confidence')}"
            )[:1024],
            inline=False,
        )
    if payload.get("source") == "Test":
        embed.set_footer(text="Synthetic test alert · No real reset was detected")
    else:
        embed.set_footer(text="Unofficial signal · Verify the source before acting")
    return embed


def _safe_source_url(value: str | None) -> str | None:
    if not value or any(
        character.isspace() or ord(character) < 0x20 for character in value
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_SOURCE_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
        ):
            return None
    except ValueError:
        return None
    return value


def _test_alert_message() -> AlertMessage:
    return AlertMessage(
        title="TEST · Codex Reset Tracker",
        body="Synthetic delivery test; this is not a real reset signal.",
        url="",
        payload={
            "author_username": "CodexResetTracker",
            "source": "Test",
            "excerpt": "This is a test alert. No Codex or Claude quota reset was detected.",
            "signal_label": "Test delivery check",
        },
    )


def _preview_alert_message() -> AlertMessage:
    return AlertMessage(
        title="Potential Codex quota reset",
        body="Private preview of a reset signal.",
        url="https://x.com/OpenAI",
        payload={
            "author_username": "OpenAI",
            "source": "X",
            "excerpt": "Example: Codex limits may reset later today.",
            "signal_label": "Reset-related post from a tracked public account",
            "reset_window": {
                "user_start_at": "Today, 4:00 PM",
                "user_end_at": "Today, 6:00 PM",
                "user_timezone": "your local timezone",
                "confidence": "low",
            },
        },
    )


def _missing_channel_permissions(
    guild: discord.Guild, channel: discord.TextChannel
) -> list[str]:
    bot_member = guild.me
    if bot_member is None:
        return ["View Channel", "Send Messages", "Embed Links"]
    permissions = channel.permissions_for(bot_member)
    required = (
        ("view_channel", "View Channel"),
        ("send_messages", "Send Messages"),
        ("embed_links", "Embed Links"),
    )
    return [label for attribute, label in required if not getattr(permissions, attribute)]


async def run_discord_tracker(config: AppConfig) -> None:
    token = os.getenv(BOT_TOKEN_ENV)
    if not token:
        raise NotificationError(f"Set {BOT_TOKEN_ENV} before starting the Discord bot")

    state = StateStore(config.state_path)
    bot = CodexResetBot(state)
    tracker = QuotaResetTracker(config, notifier=bot, state=state)
    bot_task = asyncio.create_task(bot.start(token), name="discord-bot")
    ready_task = asyncio.create_task(bot.wait_until_ready(), name="discord-ready")
    tracker_task: asyncio.Task[None] | None = None
    try:
        done, _ = await asyncio.wait(
            {bot_task, ready_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if bot_task in done:
            await bot_task
            raise NotificationError("Discord bot stopped before becoming ready")
        ready_task.result()
        LOGGER.info("Discord bot is ready; starting the X reset tracker")
        tracker_task = asyncio.create_task(tracker.run_forever(), name="reset-tracker")
        done, _ = await asyncio.wait(
            {bot_task, tracker_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            task.result()
    finally:
        if tracker_task is not None and not tracker_task.done():
            tracker_task.cancel()
        if not bot.is_closed():
            await bot.close()
        for task in (ready_task, bot_task, tracker_task):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (ready_task, bot_task, tracker_task) if task is not None),
            return_exceptions=True,
        )
        state.close()
