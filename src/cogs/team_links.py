"""Team links cog for fetching team link magic URLs."""

import os

import discord
import httpx
from discord.ext import commands


class TeamLinks(commands.Cog):
    """Cog for team link commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")

    @discord.slash_command(name="team_links", description="Get a link to the team links page")
    async def team_links(self, ctx: discord.ApplicationContext):
        """Generate a magic link to the team links page."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        headers = {
            "X-API-Key": self.api_key,
            "X-Guild-Id": str(guild.id),
            "X-Discord-User-Id": str(member.id),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/team_links",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    magic_link = data.get("magic_link_url", "")
                    expires_in = data.get("expires_in_seconds", 300)

                    await ctx.respond(
                        f"Here's your personal link to the Team Links page:\n\n"
                        f"{magic_link}\n\n"
                        f"This link expires in {expires_in // 60} minutes and can only be used once.",
                        ephemeral=True,
                    )
                elif response.status_code == 404:
                    data = response.json()
                    message = data.get("message", "User not found")
                    await ctx.respond(
                        f"Could not generate link: {message}\n\n"
                        "Please make sure you have an account on the team website.",
                        ephemeral=True,
                    )
                else:
                    await ctx.respond(
                        f"Failed to generate link. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )


def setup(bot: commands.Bot):
    bot.add_cog(TeamLinks(bot))
