"""Join The Coalition cog for new member onboarding."""

import os

import discord
import logfire
from discord.ext import commands


class JoinCoalitionModal(discord.ui.DesignerModal):
    """Modal for joining The Coalition using Components V2."""

    def __init__(self, user_nickname: str, welcome_channel_id: str | None = None, *args, **kwargs):
        self.user_nickname = user_nickname
        self.welcome_channel_id = welcome_channel_id

        # Welcome message at the top
        welcome_text = discord.ui.TextDisplay(
            "**TEST COMMAND DO NOT USE** We look forward to you joining our community.\n"
            "[THE COALITION](https://coalitionracing.com/)\n"
            "Please complete this form to apply for membership.\n\n"
            f"**Your current server nickname is:** {user_nickname}\n\n"
        )

        # Text input for full name
        full_name_input = discord.ui.Label(
            "What is your full name?",
            discord.ui.InputText(
                placeholder="Enter your full name",
                required=True,
            ),
        )

        # Text input for how they heard about the team
        how_heard_input = discord.ui.Label(
            "How did you hear about THE COALITION team?",
            discord.ui.InputText(
                placeholder="e.g., Zwift race, friend, social media, etc.",
                required=True,
            ),
        )

        # Multi-select for reasons to join
        reason_select = discord.ui.Label(
            "Why would you like to join The Coalition?",
            discord.ui.Select(
                placeholder="Select one or more reasons",
                min_values=1,
                max_values=3,
                options=[
                    discord.SelectOption(label="Virtual Racing", value="Virtual Racing"),
                    discord.SelectOption(label="Fitness and Training", value="Fitness and Training"),
                    discord.SelectOption(label="Community", value="Community"),
                ],
            ),
            description="You can select multiple options.",
        )

        # Multi-select for platforms
        platform_select = discord.ui.Label(
            "Which virtual cycling platforms do you use?",
            discord.ui.Select(
                placeholder="Select one or more platforms",
                min_values=1,
                max_values=5,
                options=[
                    discord.SelectOption(label="Zwift", value="Zwift"),
                    discord.SelectOption(label="Rouvy", value="Rouvy"),
                    discord.SelectOption(label="MyWhoosh", value="MyWhoosh"),
                    discord.SelectOption(label="TrainingPeaks Virtual", value="TrainingPeaks Virtual"),
                    discord.SelectOption(label="Other", value="Other"),
                ],
            ),
            description="You can select multiple options.",
        )

        # Multi-select for Zwift race series (optional)
        race_series_select = discord.ui.Label(
            "Which Zwift race series are you interested in?",
            discord.ui.Select(
                placeholder="Select all that apply (optional)",
                min_values=0,
                max_values=5,
                required=False,
                options=[
                    discord.SelectOption(label="ZRL", value="ZRL"),
                    discord.SelectOption(label="TTT", value="TTT"),
                    discord.SelectOption(label="ClubLadder", value="ClubLadder"),
                    discord.SelectOption(label="FRR", value="FRR"),
                    discord.SelectOption(label="Other", value="Other"),
                ],
            ),
            description="Optional - select all that apply.",
        )

        # Text input for ZwiftPower URL
        zwiftpower_input = discord.ui.Label(
            "ZwiftPower Profile URL",
            discord.ui.InputText(
                placeholder="https://zwiftpower.com/profile.php?z=...",
                required=False,
            ),
            description="If you use Zwift, please make sure you have a zwiftpower.com profile.",
        )

        super().__init__(
            welcome_text,
            full_name_input,
            how_heard_input,
            reason_select,
            platform_select,
            race_series_select,
            zwiftpower_input,
            *args,
            **kwargs,
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission and send DM to user."""
        # Extract values from the modal children
        # children[0] = welcome_text (TextDisplay - no value)
        # children[1] = full_name (Label -> InputText)
        # children[2] = how_heard (Label -> InputText)
        # children[3] = reasons (Label -> Select)
        # children[4] = platforms (Label -> Select)
        # children[5] = race_series (Label -> Select)
        # children[6] = zwiftpower_url (Label -> InputText)
        full_name = self.children[1].item.value
        how_heard = self.children[2].item.value
        reasons = self.children[3].item.values
        platforms = self.children[4].item.values
        race_series = self.children[5].item.values
        zwiftpower_url = self.children[6].item.value

        # Build the response message
        response_message = (
            "**Thank you for your interest in joining The Coalition!**\n\n"
            "Here is a summary of your submission:\n\n"
            f"**Server Nickname:** {self.user_nickname}\n"
            f"**Full Name:** {full_name}\n"
            f"**How did you hear about us:** {how_heard}\n"
            f"**Reasons for Joining:** {', '.join(reasons)}\n"
            f"**Virtual Cycling Platforms:** {', '.join(platforms)}\n"
            f"**Zwift Race Series Interest:** {', '.join(race_series) if race_series else 'None selected'}\n"
            f"**ZwiftPower Profile:** {zwiftpower_url or 'Not provided'}\n\n"
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
            full_name=full_name,
            how_heard=how_heard,
            reasons=reasons,
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
                    embed.add_field(name="Full Name", value=full_name, inline=True)
                    embed.add_field(name="How They Heard About Us", value=how_heard, inline=False)
                    embed.add_field(name="Reasons for Joining", value=", ".join(reasons), inline=False)
                    embed.add_field(name="Virtual Cycling Platforms", value=", ".join(platforms), inline=False)
                    embed.add_field(
                        name="Zwift Race Series Interest",
                        value=", ".join(race_series) if race_series else "None selected",
                        inline=False,
                    )
                    embed.add_field(name="ZwiftPower Profile", value=zwiftpower_url or "Not provided", inline=False)
                    embed.set_footer(text=f"User ID: {interaction.user.id}")
                    await channel.send(embed=embed)
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

        # Create and send the modal
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
