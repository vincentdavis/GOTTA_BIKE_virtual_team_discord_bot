"""ZwiftPower cog for ZwiftPower-related commands."""

import os
from typing import ClassVar

import discord
import httpx
import logfire
from discord.ext import commands


class ZwiftPower(commands.Cog):
    """Cog for ZwiftPower commands."""

    # ZwiftPower division to category mapping (matches apps/team/services.py)
    DIV_TO_CAT: ClassVar[dict[int, str]] = {
        5: "A+",
        10: "A",
        20: "B",
        30: "C",
        40: "D",
        50: "E",
    }

    def __init__(self, bot: commands.Bot):
        """Initialize the ZwiftPower cog.

        Args:
            bot: The Discord bot instance.

        """
        self.bot = bot
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

    def _get_headers(self, user_id: str) -> dict:
        """Get headers for API requests.

        Args:
            user_id: Discord user ID for the request.

        Returns:
            Headers dict for the API request.

        """
        return {
            "X-API-Key": self.api_key,
            "X-Guild-Id": self.guild_id,
            "X-Discord-User-Id": user_id,
        }

    @discord.slash_command(name="update_zp_team", description="Update team roster from ZwiftPower")
    @commands.has_permissions(administrator=True)
    async def update_zp_team(self, ctx: discord.ApplicationContext):
        """Trigger ZwiftPower team roster update (admin only)."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        headers = self._get_headers(str(member.id))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/update_zp_team",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    logfire.info("ZwiftPower team update triggered", status=data.get("status"))
                    await ctx.respond(
                        "ZwiftPower team update has been queued.\n"
                        "The team roster will be updated in the background.",
                        ephemeral=True,
                    )
                else:
                    logfire.error(
                        "Failed to trigger ZP team update",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    await ctx.respond(
                        f"Failed to trigger update. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            logfire.error("ZP team update request timed out")
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            logfire.error("ZP team update request failed", error=str(e))
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )

    @discord.slash_command(name="update_zp_results", description="Update team results from ZwiftPower")
    @commands.has_permissions(administrator=True)
    async def update_zp_results(self, ctx: discord.ApplicationContext):
        """Trigger ZwiftPower team results update (admin only)."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        headers = self._get_headers(str(member.id))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/update_zp_results",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    logfire.info("ZwiftPower results update triggered", status=data.get("status"))
                    await ctx.respond(
                        "ZwiftPower results update has been queued.\n"
                        "Team results will be updated in the background.",
                        ephemeral=True,
                    )
                else:
                    logfire.error(
                        "Failed to trigger ZP results update",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    await ctx.respond(
                        f"Failed to trigger update. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            logfire.error("ZP results update request timed out")
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            logfire.error("ZP results update request failed", error=str(e))
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )

    @discord.slash_command(name="my_profile", description="View your Zwift racing profile")
    async def my_profile(self, ctx: discord.ApplicationContext):
        """Display the user's combined ZwiftPower and Zwift Racing profile."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        headers = self._get_headers(str(member.id))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/my_profile",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    embed = self._build_profile_embed(data, member)
                    await ctx.respond(embed=embed, ephemeral=True)
                elif response.status_code == 404:
                    error_data = response.json()
                    await ctx.respond(
                        error_data.get("message", "Profile not found."),
                        ephemeral=True,
                    )
                else:
                    logfire.error(
                        "Failed to fetch profile",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    await ctx.respond(
                        f"Failed to fetch profile. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            logfire.error("Profile request timed out")
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            logfire.error("Profile request failed", error=str(e))
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )

    def _build_profile_embed(self, data: dict, member: discord.Member) -> discord.Embed:
        """Build a Discord embed for the profile data.

        Args:
            data: Profile data from the API.
            member: Discord member who requested the profile.

        Returns:
            Discord Embed with formatted profile information.

        """
        zp = data.get("zwiftpower")
        zr = data.get("zwiftracing")

        # Use name from whichever source is available
        name = (zp or {}).get("name") or (zr or {}).get("name") or member.display_name

        zwid = data.get("zwid")

        embed = discord.Embed(
            title=f"Profile: {name}",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Zwift ID: {zwid}")

        # Account section (if they have a linked account)
        account = data.get("account")
        if account:
            discord_name = account.get("discord_nickname") or account.get("discord_username") or ""
            verified = "✓" if account.get("zwid_verified") else ""
            if discord_name:
                embed.description = f"Discord: **{discord_name}** {verified}"

        # ZwiftPower section
        if zp:
            zp_lines = []
            if zp.get("div"):
                cat = self.DIV_TO_CAT.get(zp["div"], str(zp["div"]))
                zp_lines.append(f"**Cat:** {cat}")
            if zp.get("r"):
                zp_lines.append(f"**Rank:** {zp['r']}")
            if zp.get("ftp"):
                zp_lines.append(f"**FTP:** {zp['ftp']}W")
            if zp.get("weight"):
                zp_lines.append(f"**Weight:** {zp['weight']}kg")

            # Power metrics
            power_parts = []
            if zp.get("h_15_watts"):
                wkg = f" ({zp['h_15_wkg']}w/kg)" if zp.get("h_15_wkg") else ""
                power_parts.append(f"15s: {zp['h_15_watts']}W{wkg}")
            if zp.get("h_1200_watts"):
                wkg = f" ({zp['h_1200_wkg']}w/kg)" if zp.get("h_1200_wkg") else ""
                power_parts.append(f"20m: {zp['h_1200_watts']}W{wkg}")
            if power_parts:
                zp_lines.append(f"**Power:** {', '.join(power_parts)}")

            # Stats
            stats_parts = []
            if zp.get("distance_km"):
                stats_parts.append(f"{zp['distance_km']:,.0f}km")
            if zp.get("climbed_m"):
                stats_parts.append(f"{zp['climbed_m']:,}m climbed")
            if zp.get("time_hours"):
                stats_parts.append(f"{zp['time_hours']:,.0f}hrs")
            if stats_parts:
                zp_lines.append(f"**Totals:** {', '.join(stats_parts)}")

            if zp_lines:
                zp_link = f"[View on ZwiftPower ↗](https://zwiftpower.com/profile.php?z={zwid})"
                embed.add_field(
                    name="ZwiftPower",
                    value="\n".join(zp_lines) + f"\n{zp_link}",
                    inline=False,
                )

        # Zwift Racing section
        if zr:
            zr_lines = []

            # Category and rating
            if zr.get("race_current_category"):
                rating = f" ({zr['race_current_rating']:.0f})" if zr.get("race_current_rating") else ""
                zr_lines.append(f"**Category:** {zr['race_current_category']}{rating}")

            if zr.get("power_cp"):
                zr_lines.append(f"**Critical Power:** {zr['power_cp']:.0f}W")

            # Max ratings
            if zr.get("race_max30_rating"):
                zr_lines.append(f"**Max 30d:** {zr['race_max30_rating']:.0f} ({zr.get('race_max30_category', '')})")
            if zr.get("race_max90_rating"):
                zr_lines.append(f"**Max 90d:** {zr['race_max90_rating']:.0f} ({zr.get('race_max90_category', '')})")

            # Race stats
            race_parts = []
            if zr.get("race_finishes"):
                race_parts.append(f"{zr['race_finishes']} races")
            if zr.get("race_wins"):
                race_parts.append(f"{zr['race_wins']} wins")
            if zr.get("race_podiums"):
                race_parts.append(f"{zr['race_podiums']} podiums")
            if race_parts:
                zr_lines.append(f"**Stats:** {', '.join(race_parts)}")

            # Phenotype
            if zr.get("phenotype_value"):
                zr_lines.append(f"**Phenotype:** {zr['phenotype_value']}")

            if zr_lines:
                zr_link = f"[View on ZwiftRacing ↗](https://www.zwiftracing.app/riders/{zwid})"
                embed.add_field(
                    name="ZwiftRacing",
                    value="\n".join(zr_lines) + f"\n{zr_link}",
                    inline=False,
                )

        # Power curve section (from ZR data)
        if zr:
            power_curve = []
            if zr.get("power_wkg5"):
                power_curve.append(f"5s: {zr['power_wkg5']:.2f}")
            if zr.get("power_wkg15"):
                power_curve.append(f"15s: {zr['power_wkg15']:.2f}")
            if zr.get("power_wkg60"):
                power_curve.append(f"1m: {zr['power_wkg60']:.2f}")
            if zr.get("power_wkg300"):
                power_curve.append(f"5m: {zr['power_wkg300']:.2f}")
            if zr.get("power_wkg1200"):
                power_curve.append(f"20m: {zr['power_wkg1200']:.2f}")

            if power_curve:
                embed.add_field(
                    name="Power Curve (w/kg)",
                    value=" | ".join(power_curve),
                    inline=False,
                )

        # Verification status section
        verification = data.get("verification")
        if verification:
            verify_lines = []
            verify_labels = {
                "weight_full": "Weight (Full)",
                "weight_light": "Weight (Light)",
                "height": "Height",
                "power": "Power",
            }
            for key, label in verify_labels.items():
                v = verification.get(key, {})
                if not v.get("verified"):
                    verify_lines.append(f"**{label}:** No record")
                elif v.get("is_expired"):
                    verify_lines.append(f"**{label}:** ❌ Expired")
                elif v.get("days_remaining") is not None:
                    days = v["days_remaining"]
                    verify_lines.append(f"**{label}:** ✅ {days} days")
                else:
                    verify_lines.append(f"**{label}:** ✅ Never expires")

            if verify_lines:
                embed.add_field(
                    name="Race Ready Status",
                    value="\n".join(verify_lines),
                    inline=False,
                )

        return embed

    async def teammate_autocomplete(self, ctx: discord.AutocompleteContext) -> list[discord.OptionChoice]:
        """Autocomplete function for teammate search.

        Args:
            ctx: The autocomplete context.

        Returns:
            List of OptionChoice with matching teammate names.

        """
        query = ctx.value or ""
        if len(query) < 2:
            return []

        # Use a dummy user ID for the autocomplete request (auth still required)
        headers = self._get_headers(str(ctx.interaction.user.id))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/search_teammates",
                    params={"q": query},
                    headers=headers,
                    timeout=5.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    return [
                        discord.OptionChoice(
                            name=f"{r['name']} ({r.get('flag', '')})",
                            value=str(r["zwid"]),
                        )
                        for r in results
                    ]
        except (httpx.TimeoutException, httpx.RequestError):
            pass

        return []

    @discord.slash_command(name="teammate_profile", description="View a teammate's Zwift racing profile")
    async def teammate_profile(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str,
            description="Search for a teammate by name",
            autocomplete=teammate_autocomplete,
            required=True,
        ),
    ):
        """Display a teammate's combined ZwiftPower and Zwift Racing profile."""
        await ctx.defer(ephemeral=True)

        guild = ctx.guild
        member = ctx.author

        if not guild:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        if str(guild.id) != self.guild_id:
            await ctx.respond("This command can only be used in the configured guild.", ephemeral=True)
            return

        # The 'name' parameter contains the zwid from autocomplete selection
        try:
            zwid = int(name)
        except ValueError:
            await ctx.respond(
                "Please select a teammate from the autocomplete suggestions.",
                ephemeral=True,
            )
            return

        headers = self._get_headers(str(member.id))

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/teammate_profile/{zwid}",
                    headers=headers,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    embed = self._build_profile_embed(data, member)
                    await ctx.respond(embed=embed, ephemeral=True)
                elif response.status_code == 404:
                    error_data = response.json()
                    await ctx.respond(
                        error_data.get("message", "Teammate not found."),
                        ephemeral=True,
                    )
                else:
                    logfire.error(
                        "Failed to fetch teammate profile",
                        status_code=response.status_code,
                        response=response.text,
                    )
                    await ctx.respond(
                        f"Failed to fetch profile. Server returned status {response.status_code}.",
                        ephemeral=True,
                    )

        except httpx.TimeoutException:
            logfire.error("Teammate profile request timed out")
            await ctx.respond(
                "Request timed out. Please try again later.",
                ephemeral=True,
            )
        except httpx.RequestError as e:
            logfire.error("Teammate profile request failed", error=str(e))
            await ctx.respond(
                f"Failed to connect to the API: {e}",
                ephemeral=True,
            )


def setup(bot: commands.Bot):
    """Set up the ZwiftPower cog.

    Args:
        bot: The Discord bot instance.

    """
    bot.add_cog(ZwiftPower(bot))
