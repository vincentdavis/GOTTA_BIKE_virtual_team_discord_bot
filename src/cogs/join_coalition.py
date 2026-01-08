"""Join The Coalition cog for new member onboarding."""

import discord
import logfire
from discord.ext import commands


class JoinCoalitionModal(discord.ui.Modal):
    """Modal for collecting text inputs for joining The Coalition."""

    def __init__(self, user_nickname: str, reasons: list[str], platforms: list[str]):
        super().__init__(title="Join The Coalition")
        self.reasons = reasons
        self.platforms = platforms

        # Add a label-like text at the top (using a disabled text input as workaround)
        self.full_name = discord.ui.InputText(
            label="What is your full name?",
            placeholder="Enter your full name",
            required=True,
            style=discord.InputTextStyle.short,
        )
        self.add_item(self.full_name)

        self.zwiftpower_url = discord.ui.InputText(
            label="ZwiftPower Profile URL (if you use Zwift)",
            placeholder="https://zwiftpower.com/profile.php?z=...",
            required=False,
            style=discord.InputTextStyle.short,
        )
        self.add_item(self.zwiftpower_url)

        self.user_nickname = user_nickname

    async def callback(self, interaction: discord.Interaction):
        """Handle modal submission and send DM to user."""
        # Build the response message
        response_message = (
            "**Thank you for your interest in joining The Coalition!**\n\n"
            "Here is a summary of your submission:\n\n"
            f"**Server Nickname:** {self.user_nickname}\n"
            f"**Full Name:** {self.full_name.value}\n"
            f"**Reasons for Joining:** {', '.join(self.reasons)}\n"
            f"**Virtual Cycling Platforms:** {', '.join(self.platforms)}\n"
            f"**ZwiftPower Profile:** {self.zwiftpower_url.value or 'Not provided'}\n\n"
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
            full_name=self.full_name.value,
            reasons=self.reasons,
            platforms=self.platforms,
        )


class JoinCoalitionView(discord.ui.View):
    """View with select menus for joining The Coalition."""

    def __init__(self, user_nickname: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_nickname = user_nickname
        self.selected_reasons: list[str] = []
        self.selected_platforms: list[str] = []

    @discord.ui.select(
        placeholder="Why would you like to join The Coalition?",
        min_values=1,
        max_values=3,
        options=[
            discord.SelectOption(label="Virtual Racing", value="Virtual Racing"),
            discord.SelectOption(label="Fitness and Training", value="Fitness and Training"),
            discord.SelectOption(label="Community", value="Community"),
        ],
    )
    async def reason_select(self, select: discord.ui.Select, interaction: discord.Interaction):
        """Handle reason selection."""
        self.selected_reasons = select.values
        await interaction.response.defer()
        await self._check_completion(interaction)

    @discord.ui.select(
        placeholder="Which virtual cycling platforms do you use?",
        min_values=1,
        max_values=5,
        options=[
            discord.SelectOption(label="Zwift", value="Zwift"),
            discord.SelectOption(label="Rouvy", value="Rouvy"),
            discord.SelectOption(label="MyWhoosh", value="MyWhoosh"),
            discord.SelectOption(label="TrainingPeaks Virtual", value="TrainingPeaks Virtual"),
            discord.SelectOption(label="Other", value="Other"),
        ],
    )
    async def platform_select(self, select: discord.ui.Select, interaction: discord.Interaction):
        """Handle platform selection."""
        self.selected_platforms = select.values
        await interaction.response.defer()
        await self._check_completion(interaction)

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary, disabled=True)
    async def continue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open the modal for text inputs."""
        modal = JoinCoalitionModal(
            user_nickname=self.user_nickname,
            reasons=self.selected_reasons,
            platforms=self.selected_platforms,
        )
        await interaction.response.send_modal(modal)
        self.stop()

    async def _check_completion(self, interaction: discord.Interaction):
        """Enable the continue button if both selections are made."""
        if self.selected_reasons and self.selected_platforms:
            self.continue_button.disabled = False
            await interaction.message.edit(view=self)


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

        # Create the welcome embed
        embed = discord.Embed(
            title="Welcome to The COALITION!",
            description=(
                "**TEST COMMAND DO NOT USE** We look forward to you joining our community.\n"
                "[THE COALITION](https://coalitionracing.com/)\n"
                "Please complete this form to apply for membership.\n\n"
                f"**Your current server nickname is:** {user_nickname}\n\n"
                "Please select your answers from the dropdowns below, then click **Continue** "
                "to complete the application."
            ),
            color=discord.Color.blue(),
        )

        view = JoinCoalitionView(user_nickname=user_nickname)
        await ctx.respond(embed=embed, view=view, ephemeral=True)

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
