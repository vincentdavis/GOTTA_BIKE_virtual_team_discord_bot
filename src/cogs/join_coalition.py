"""Join The Coalition cog for new member onboarding."""

import os
from typing import ClassVar

import discord
import httpx
import logfire
from discord.ext import commands


async def create_membership_application(
    api_url: str,
    api_key: str,
    guild_id: str,
    user: discord.User,
    member: discord.Member,
    modal_form_data: dict,
) -> dict | None:
    """Create a membership application via the Django API.

    Args:
        api_url: Base URL for the API.
        api_key: API authentication key.
        guild_id: Discord guild ID.
        user: Discord user object.
        member: Discord member object.
        modal_form_data: Data from the modal form.

    Returns:
        API response dict or None if failed.

    """
    headers = {
        "X-API-Key": api_key,
        "X-Guild-Id": guild_id,
        "X-Discord-User-Id": str(user.id),
    }

    payload = {
        "discord_id": str(user.id),
        "discord_username": user.name,
        "server_nickname": member.nick or member.display_name,
        "avatar_url": user.display_avatar.url if user.display_avatar else "",
        "guild_avatar_url": member.guild_avatar.url if member.guild_avatar else "",
        "discord_user_data": {
            "id": str(user.id),
            "name": user.name,
            "display_name": user.display_name,
            "discriminator": user.discriminator,
            "bot": user.bot,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "discord_member_data": {
            "id": str(member.id),
            "nick": member.nick,
            "display_name": member.display_name,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "roles": [{"id": str(r.id), "name": r.name} for r in member.roles],
        },
        "modal_form_data": modal_form_data,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_url}/membership_application",
                json=payload,
                headers=headers,
                timeout=15.0,
            )

            if response.status_code == 200:
                result = response.json()
                logfire.info(
                    "Membership application created/retrieved",
                    discord_id=str(user.id),
                    application_id=result.get("id"),
                    already_exists=result.get("already_exists", False),
                )
                return result
            else:
                logfire.error(
                    "Failed to create membership application",
                    status_code=response.status_code,
                    response=response.text,
                )
                return None

    except httpx.TimeoutException:
        logfire.error("Membership application API request timed out")
        return None
    except httpx.RequestError as e:
        logfire.error("Membership application API request failed", error=str(e))
        return None


class JoinCoalitionModal(discord.ui.DesignerModal):
    """Modal for collecting new member application information."""

    REASON_OPTIONS: ClassVar[list[str]] = ["Virtual Racing", "Fitness and Training", "Community"]
    PLATFORM_OPTIONS: ClassVar[list[str]] = ["Zwift", "Rouvy", "MyWhoosh", "TrainingPeaks Virtual", "Other"]
    RACE_SERIES_OPTIONS: ClassVar[list[str]] = ["ZRL", "TTT", "ClubLadder", "FRR", "Women's Racing", "Other"]

    def __init__(
        self,
        user_nickname: str,
        welcome_channel_id: str | None,
        api_url: str,
        api_key: str,
        guild_id: str,
        *args,
        **kwargs,
    ):
        self.user_nickname = user_nickname
        self.welcome_channel_id = welcome_channel_id
        self.api_url = api_url
        self.api_key = api_key
        self.guild_id = guild_id

        # 1. How did you hear about us? (text input)
        how_heard_input = discord.ui.Label(
            "How did you hear about THE COALITION?",
            discord.ui.InputText(
                placeholder="e.g., Zwift race, friend, social media, etc.",
                required=True,
            ),
        )

        # 2. Why do you want to join? (select menu)
        reason_select = discord.ui.Label(
            "Why would you like to join The Coalition?",
            discord.ui.Select(
                placeholder="Select your reasons",
                min_values=1,
                max_values=3,
                options=[discord.SelectOption(label=opt, value=opt) for opt in self.REASON_OPTIONS],
            ),
        )

        # 3. Do you know someone on the team? (text input, optional)
        know_someone_input = discord.ui.Label(
            "Do you know someone on the team?",
            discord.ui.InputText(
                placeholder="Who? (leave blank if no)",
                required=False,
            ),
        )

        # 4. Which platforms do you use? (select menu)
        platform_select = discord.ui.Label(
            "Which virtual cycling platforms do you use?",
            discord.ui.Select(
                placeholder="Select your platforms",
                min_values=1,
                max_values=5,
                options=[discord.SelectOption(label=opt, value=opt) for opt in self.PLATFORM_OPTIONS],
            ),
        )

        # 5. Zwift race series interest (select menu, optional)
        race_series_select = discord.ui.Label(
            "Zwift race series interest (optional)",
            discord.ui.Select(
                placeholder="Select race series",
                min_values=0,
                max_values=5,
                options=[discord.SelectOption(label=opt, value=opt) for opt in self.RACE_SERIES_OPTIONS],
                required=False,
            ),
        )

        super().__init__(
            how_heard_input,
            reason_select,
            know_someone_input,
            platform_select,
            race_series_select,
            *args,
            **kwargs,
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission."""
        # Extract values from children
        # children[0] = how_heard (Label -> InputText)
        # children[1] = reasons (Label -> Select)
        # children[2] = know_someone (Label -> InputText)
        # children[3] = platforms (Label -> Select)
        # children[4] = race_series (Label -> Select)
        how_heard = self.children[0].item.value
        reasons = self.children[1].item.values
        know_someone = self.children[2].item.value
        platforms = self.children[3].item.values
        race_series = self.children[4].item.values

        # Build modal form data for API
        modal_form_data = {
            "how_heard": how_heard,
            "reasons": reasons,
            "know_someone": know_someone,
            "platforms": platforms,
            "race_series": race_series,
        }

        # Create membership application via API
        application_url = None
        if isinstance(interaction.user, discord.Member) and interaction.guild:
            api_result = await create_membership_application(
                api_url=self.api_url,
                api_key=self.api_key,
                guild_id=self.guild_id,
                user=interaction.user,
                member=interaction.user,
                modal_form_data=modal_form_data,
            )
            if api_result:
                # Get application URL - API returns absolute URL, use as-is
                application_url = api_result.get("application_url", "")

        logfire.info(
            "Join Coalition application submitted",
            user_id=str(interaction.user.id),
            user_name=interaction.user.name,
            how_heard=how_heard,
            reasons=reasons,
            know_someone=know_someone,
            platforms=platforms,
            race_series=race_series,
            application_url=application_url,
        )

        # Post form data to welcome team channel (without the public link)
        if self.welcome_channel_id and interaction.guild:
            try:
                channel = interaction.guild.get_channel(int(self.welcome_channel_id))
                if channel and isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(
                        title="New Coalition Application",
                        description="A new member has applied to join The Coalition!",
                        color=discord.Color.green(),
                    )
                    embed.add_field(name="Discord User", value=f"{interaction.user.mention}", inline=True)
                    embed.add_field(name="Server Nickname", value=self.user_nickname, inline=True)
                    embed.add_field(name="How They Heard About Us", value=how_heard, inline=False)
                    embed.add_field(name="Reasons for Joining", value=", ".join(reasons), inline=False)
                    embed.add_field(
                        name="Knows Someone on Team", value=know_someone if know_someone else "No", inline=False
                    )
                    embed.add_field(name="Virtual Cycling Platforms", value=", ".join(platforms), inline=False)
                    embed.add_field(
                        name="Zwift Race Series Interest",
                        value=", ".join(race_series) if race_series else "None selected",
                        inline=False,
                    )
                    embed.set_footer(text=f"User ID: {interaction.user.id}")
                    await channel.send(embed=embed)
                    logfire.info("Successfully posted application to welcome channel")
                else:
                    logfire.warning(
                        "Channel not found or not a TextChannel",
                        channel_id=self.welcome_channel_id,
                    )
            except Exception as e:
                logfire.error(
                    "Failed to post to welcome team channel",
                    error=str(e),
                    channel_id=self.welcome_channel_id,
                )

        # Send ephemeral message to user with their application link
        if application_url:
            await interaction.response.send_message(
                f"{self.user_nickname} please complete your application here. {application_url}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Your application has been submitted! A team administrator will review it soon.",
                ephemeral=True,
            )


class JoinCoalition(commands.Cog):
    """Cog for new member onboarding."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id = os.getenv("WELCOME_TEAM_CHANNEL", "")
        self.api_url = os.getenv("DBOT_API_URL", "http://localhost:8000/api/dbot")
        self.api_key = os.getenv("DBOT_AUTH_KEY", "")
        self.guild_id = os.getenv("DISCORD_GUILD_ID", "")

    @discord.slash_command(name="join_the_coalition", description="Apply to join The Coalition team")
    async def join_the_coalition(self, ctx: discord.ApplicationContext):
        """Start the application process to join The Coalition."""
        if not isinstance(ctx.author, discord.Member):
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return

        # Get user's nickname or display name
        user_nickname = ctx.author.nick or ctx.author.display_name

        modal = JoinCoalitionModal(
            user_nickname=user_nickname,
            welcome_channel_id=self.welcome_channel_id,
            api_url=self.api_url,
            api_key=self.api_key,
            guild_id=self.guild_id,
            title="Join The Coalition",
        )
        await ctx.send_modal(modal)

    async def cog_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle errors for commands in this cog."""
        if isinstance(error, commands.CheckFailure):
            await ctx.respond("You don't have permission to use this command.", ephemeral=True)
        else:
            logfire.error(
                "Command error in JoinCoalition cog",
                error=str(error),
                command=ctx.command.name if ctx.command else "unknown",
            )
            raise error


def setup(bot: commands.Bot):
    """Load the JoinCoalition cog."""
    bot.add_cog(JoinCoalition(bot))
