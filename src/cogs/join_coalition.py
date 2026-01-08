"""Join The Coalition cog for new member onboarding."""

import os

import discord
import logfire
from discord.ext import commands


class JoinCoalitionModal(discord.ui.DesignerModal):
    """Modal for collecting text inputs (Part 2 of the join form)."""

    def __init__(
        self,
        user_nickname: str,
        welcome_channel_id: str | None,
        reasons: list[str],
        platforms: list[str],
        race_series: list[str],
        *args,
        **kwargs,
    ):
        self.user_nickname = user_nickname
        self.welcome_channel_id = welcome_channel_id
        self.reasons = reasons
        self.platforms = platforms
        self.race_series = race_series

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
        # children[3] = zwiftpower_url (Label -> InputText)
        full_name = self.children[1].item.value
        how_heard = self.children[2].item.value
        zwiftpower_url = self.children[3].item.value

        # Build the response message
        response_message = (
            "**Thank you for your interest in joining The Coalition!**\n\n"
            "Here is a summary of your submission:\n\n"
            f"**Server Nickname:** {self.user_nickname}\n"
            f"**Full Name:** {full_name}\n"
            f"**How did you hear about us:** {how_heard}\n"
            f"**Reasons for Joining:** {', '.join(self.reasons)}\n"
            f"**Virtual Cycling Platforms:** {', '.join(self.platforms)}\n"
            f"**Zwift Race Series Interest:** {', '.join(self.race_series) if self.race_series else 'None selected'}\n"
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
            reasons=self.reasons,
            platforms=self.platforms,
            race_series=self.race_series,
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
                    embed.add_field(name="Reasons for Joining", value=", ".join(self.reasons), inline=False)
                    embed.add_field(name="Virtual Cycling Platforms", value=", ".join(self.platforms), inline=False)
                    embed.add_field(
                        name="Zwift Race Series Interest",
                        value=", ".join(self.race_series) if self.race_series else "None selected",
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


class JoinCoalitionView(discord.ui.View):
    """View with select menus (Part 1 of the join form)."""

    REASON_OPTIONS = ["Virtual Racing", "Fitness and Training", "Community"]
    PLATFORM_OPTIONS = ["Zwift", "Rouvy", "MyWhoosh", "TrainingPeaks Virtual", "Other"]
    RACE_SERIES_OPTIONS = ["ZRL", "TTT", "ClubLadder", "FRR", "Other"]

    def __init__(self, user_nickname: str, welcome_channel_id: str | None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_nickname = user_nickname
        self.welcome_channel_id = welcome_channel_id
        self.selected_reasons: list[str] = []
        self.selected_platforms: list[str] = []
        self.selected_race_series: list[str] = []

        # Create select menus programmatically
        self.reason_select = discord.ui.Select(
            placeholder="Why would you like to join The Coalition?",
            min_values=1,
            max_values=3,
            options=[discord.SelectOption(label=opt, value=opt) for opt in self.REASON_OPTIONS],
            row=0,
        )
        self.reason_select.callback = self.on_reason_select  # ty: ignore[invalid-assignment]
        self.add_item(self.reason_select)

        self.platform_select = discord.ui.Select(
            placeholder="Which virtual cycling platforms do you use?",
            min_values=1,
            max_values=5,
            options=[discord.SelectOption(label=opt, value=opt) for opt in self.PLATFORM_OPTIONS],
            row=1,
        )
        self.platform_select.callback = self.on_platform_select  # ty: ignore[invalid-assignment]
        self.add_item(self.platform_select)

        self.race_series_select = discord.ui.Select(
            placeholder="Zwift race series interest (optional)",
            min_values=0,
            max_values=5,
            options=[discord.SelectOption(label=opt, value=opt) for opt in self.RACE_SERIES_OPTIONS],
            row=2,
        )
        self.race_series_select.callback = self.on_race_series_select  # ty: ignore[invalid-assignment]
        self.add_item(self.race_series_select)

        self.continue_button = discord.ui.Button(
            label="Continue",
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=3,
        )
        self.continue_button.callback = self.on_continue  # ty: ignore[invalid-assignment]
        self.add_item(self.continue_button)

    async def on_reason_select(self, interaction: discord.Interaction):
        """Handle reason selection."""
        self.selected_reasons = interaction.data.get("values", [])
        self._update_select_options()
        self._update_button_state()
        await interaction.response.edit_message(view=self)

    async def on_platform_select(self, interaction: discord.Interaction):
        """Handle platform selection."""
        self.selected_platforms = interaction.data.get("values", [])
        self._update_select_options()
        self._update_button_state()
        await interaction.response.edit_message(view=self)

    async def on_race_series_select(self, interaction: discord.Interaction):
        """Handle race series selection."""
        self.selected_race_series = interaction.data.get("values", [])
        self._update_select_options()
        await interaction.response.edit_message(view=self)

    async def on_continue(self, interaction: discord.Interaction):
        """Open the modal for text inputs."""
        modal = JoinCoalitionModal(
            user_nickname=self.user_nickname,
            welcome_channel_id=self.welcome_channel_id,
            reasons=self.selected_reasons,
            platforms=self.selected_platforms,
            race_series=self.selected_race_series,
            title="Join The Coalition",
        )
        await interaction.response.send_modal(modal)
        self.stop()

    def _update_select_options(self):
        """Update select options to show selected state."""
        self.reason_select.options = [
            discord.SelectOption(label=opt, value=opt, default=(opt in self.selected_reasons))
            for opt in self.REASON_OPTIONS
        ]
        self.platform_select.options = [
            discord.SelectOption(label=opt, value=opt, default=(opt in self.selected_platforms))
            for opt in self.PLATFORM_OPTIONS
        ]
        self.race_series_select.options = [
            discord.SelectOption(label=opt, value=opt, default=(opt in self.selected_race_series))
            for opt in self.RACE_SERIES_OPTIONS
        ]

    def _update_button_state(self):
        """Enable the continue button if required selections are made."""
        self.continue_button.disabled = not (self.selected_reasons and self.selected_platforms)


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

        # Create the welcome embed for Part 1
        embed = discord.Embed(
            title="Welcome to The COALITION!",
            description=(
                "**TEST COMMAND DO NOT USE**\n\n"
                "We look forward to you joining our community.\n"
                "[THE COALITION](https://coalitionracing.com/)\n\n"
                "Please complete this form to apply for membership.\n\n"
                f"**Your current server nickname is:** {user_nickname}\n\n"
                "**Step 1 of 2:** Select your answers from the dropdowns below, "
                "then click **Continue** to complete the application."
            ),
            color=discord.Color.blue(),
        )

        view = JoinCoalitionView(
            user_nickname=user_nickname,
            welcome_channel_id=self.welcome_channel_id,
        )
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
