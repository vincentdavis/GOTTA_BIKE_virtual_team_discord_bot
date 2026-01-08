"""Join The Coalition cog for new member onboarding."""

import discord
import logfire
from discord.ext import commands


class JoinCoalitionModal(discord.ui.DesignerModal):
    """Modal for joining The Coalition using Components V2."""

    def __init__(self, user_nickname: str, *args, **kwargs):
        self.user_nickname = user_nickname

        # Text input for full name
        full_name_input = discord.ui.Label(
            "What is your full name?",
            discord.ui.InputText(
                placeholder="Enter your full name",
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
            full_name_input,
            reason_select,
            platform_select,
            zwiftpower_input,
            *args,
            **kwargs,
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission and send DM to user."""
        # Extract values from the modal children
        # children[0] = full_name (Label -> InputText)
        # children[1] = reasons (Label -> Select)
        # children[2] = platforms (Label -> Select)
        # children[3] = zwiftpower_url (Label -> InputText)
        full_name = self.children[0].item.value
        reasons = self.children[1].item.values
        platforms = self.children[2].item.values
        zwiftpower_url = self.children[3].item.value

        # Build the response message
        response_message = (
            "**Thank you for your interest in joining The Coalition!**\n\n"
            "Here is a summary of your submission:\n\n"
            f"**Server Nickname:** {self.user_nickname}\n"
            f"**Full Name:** {full_name}\n"
            f"**Reasons for Joining:** {', '.join(reasons)}\n"
            f"**Virtual Cycling Platforms:** {', '.join(platforms)}\n"
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
            reasons=reasons,
            platforms=platforms,
        )


class JoinCoalition(commands.Cog):
    """Cog for new member onboarding."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
