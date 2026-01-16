"""Join The Coalition cog for new member onboarding."""

import os
from typing import ClassVar

import discord
import logfire
from discord.ext import commands


class JoinCoalitionModal(discord.ui.DesignerModal):
    """Modal for collecting new member application information."""

    REASON_OPTIONS: ClassVar[list[str]] = ["Virtual Racing", "Fitness and Training", "Community"]
    PLATFORM_OPTIONS: ClassVar[list[str]] = ["Zwift", "Rouvy", "MyWhoosh", "TrainingPeaks Virtual", "Other"]
    RACE_SERIES_OPTIONS: ClassVar[list[str]] = ["ZRL", "TTT", "ClubLadder", "FRR", "Other"]

    def __init__(self, user_nickname: str, welcome_channel_id: str | None, *args, **kwargs):
        self.user_nickname = user_nickname
        self.welcome_channel_id = welcome_channel_id

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

        # Build the response message
        response_message = (
            "**Thank you for your interest in joining The Coalition!**\n\n"
            "Here is a summary of your submission:\n\n"
            f"**Server Nickname:** {self.user_nickname}\n"
            f"**How did you hear about us:** {how_heard}\n"
            f"**Reasons for Joining:** {', '.join(reasons)}\n"
            f"**Know someone on the team:** {know_someone or 'No'}\n"
            f"**Virtual Cycling Platforms:** {', '.join(platforms)}\n"
            f"**Zwift Race Series Interest:** {', '.join(race_series) if race_series else 'None selected'}\n\n"
            "A team administrator will review your application soon!"
        )

        # Try to send DM to the user
        try:
            await interaction.user.send(response_message)
            await interaction.response.send_message(
                "Your application has been submitted! Check your DMs for a confirmation.",
                ephemeral=True,
            )
        except discord.Forbidden:
            # User has DMs disabled
            await interaction.response.send_message(
                "Your application has been submitted, but I couldn't send you a DM. "
                "Please enable DMs from server members to receive confirmations.\n\n"
                f"Here's your submission summary:\n{response_message}",
                ephemeral=True,
            )

        logfire.info(
            "Join Coalition application submitted",
            user_id=str(interaction.user.id),
            user_name=interaction.user.name,
            how_heard=how_heard,
            reasons=reasons,
            know_someone=know_someone,
            platforms=platforms,
            race_series=race_series,
        )

        # Post to welcome team channel if configured
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
                    logfire.info("Successfully posted to welcome channel")
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


class JoinCoalition(commands.Cog):
    """Cog for new member onboarding."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id = os.getenv("WELCOME_TEAM_CHANNEL", "")

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
