"""Standalone Discord bot runner (spec 164).

Run with: python -m app.services.discord_bot_runner

Requires DISCORD_BOT_TOKEN env var and the `discord.py` package.
This module is NOT imported by the API — it runs as a separate process.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

# Guard import — discord.py is optional; the API works without it.
try:
    import discord
    from discord import app_commands
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False

API_BASE_URL = os.getenv("COHERENCE_API_URL", "https://api.coherencycoin.com")


def _build_bot():
    """Construct the Discord bot with slash commands."""
    if not HAS_DISCORD:
        raise RuntimeError("discord.py is not installed. Run: pip install discord.py")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True

    bot = discord.Client(intents=intents)
    tree = app_commands.CommandTree(bot)

    @tree.command(name="cc-idea", description="Look up a Coherence Network idea")
    @app_commands.describe(idea_id="The idea ID to look up")
    async def cc_idea(interaction: discord.Interaction, idea_id: str):
        """Fetch idea details and display as a rich embed."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/api/ideas/{idea_id}/embed"
            async with session.get(url) as resp:
                if resp.status == 404:
                    await interaction.response.send_message(
                        f"Idea `{idea_id}` not found.", ephemeral=True,
                    )
                    return
                if resp.status != 200:
                    await interaction.response.send_message(
                        "Failed to fetch idea.", ephemeral=True,
                    )
                    return
                data = await resp.json()

        embed = discord.Embed(
            title=data.get("title", "Idea"),
            description=data.get("description", ""),
            color=data.get("color", 0x5865F2),
        )
        for field in data.get("fields", []):
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", True),
            )
        footer = data.get("footer", {})
        if footer:
            embed.set_footer(text=footer.get("text", ""))

        await interaction.response.send_message(embed=embed)

    @tree.command(name="cc-status", description="Show Coherence Network portfolio summary")
    async def cc_status(interaction: discord.Interaction):
        """Display portfolio summary as a rich embed."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/api/portfolio/status-embed"
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.response.send_message(
                        "Failed to fetch portfolio status.", ephemeral=True,
                    )
                    return
                data = await resp.json()

        embed = discord.Embed(
            title=data.get("title", "Portfolio"),
            color=data.get("color", 0x5865F2),
        )
        for field in data.get("fields", []):
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", True),
            )
        await interaction.response.send_message(embed=embed)

    @tree.command(name="cc-stake", description="Stake CC on an idea")
    @app_commands.describe(idea_id="The idea to stake on", amount="Amount of CC to stake")
    async def cc_stake(interaction: discord.Interaction, idea_id: str, amount: float):
        """Stake CC on an idea via the API."""
        import aiohttp

        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be positive.", ephemeral=True,
            )
            return

        discord_user_id = str(interaction.user.id)
        payload = {
            "provider": "discord",
            "provider_id": discord_user_id,
            "amount_cc": amount,
            "rationale": f"Staked via Discord by {interaction.user.display_name}",
        }

        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}/api/ideas/{idea_id}/stake"
            async with session.post(url, json=payload) as resp:
                if resp.status == 404:
                    await interaction.response.send_message(
                        f"Idea `{idea_id}` not found.", ephemeral=True,
                    )
                    return
                if resp.status not in (200, 201):
                    await interaction.response.send_message(
                        "Failed to stake.", ephemeral=True,
                    )
                    return
                data = await resp.json()

        embed = discord.Embed(
            title="✅ Stake Recorded",
            description=f"Staked **{amount} CC** on idea `{idea_id}`",
            color=0x2ECC71,
        )
        embed.add_field(name="Total Staked", value=f"{data.get('total_staked', amount):.2f} CC")
        await interaction.response.send_message(embed=embed)

    @bot.event
    async def on_ready():
        logger.info(f"Discord bot connected as {bot.user} (id={bot.user.id})")
        await tree.sync()
        logger.info("Slash commands synced")

    @bot.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
        """Map 👍/👎 reactions on idea embeds to vote API calls."""
        if payload.user_id == bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in ("👍", "👎"):
            return

        channel = bot.get_channel(payload.channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Only process reactions on bot embeds that have an idea footer
        if message.author.id != bot.user.id or not message.embeds:
            return

        embed = message.embeds[0]
        if not embed.footer or not embed.footer.text:
            return

        footer_text = embed.footer.text
        if not footer_text.startswith("Idea ID: "):
            return

        idea_id = footer_text.replace("Idea ID: ", "").strip()
        direction = "up" if emoji == "👍" else "down"

        import aiohttp
        async with aiohttp.ClientSession() as session:
            # Vote on question index 0 by default for reaction votes
            url = f"{API_BASE_URL}/api/ideas/{idea_id}/questions/0/vote"
            vote_payload = {
                "voter_id": f"discord:{payload.user_id}",
                "direction": direction,
            }
            async with session.post(url, json=vote_payload) as resp:
                if resp.status == 200:
                    logger.info(f"Vote recorded: {idea_id} q0 {direction} by {payload.user_id}")
                else:
                    logger.warning(f"Vote failed: {resp.status} for {idea_id}")

    return bot


def main():
    """Entry point for the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN env var is required", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    bot = _build_bot()
    bot.run(token)


if __name__ == "__main__":
    main()
