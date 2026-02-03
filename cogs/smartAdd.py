# cogs/smartAdd.py
import os, io, csv, asyncio, discord, math
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction):  # checks if the user is an admin or the developer
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, (discord.Member,)):
        return interaction.user.guild_permissions.administrator
    return False


def fmt_eta(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class smartAdd(commands.Cog):
    """
    /smartadd role_to_add:<Role> role_required:<Role> [dry_run]
    Adds `role_to_add` to all members who DO NOT have `role_required`.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="smartadd",
        description="Add a role to all users who do NOT have a specific role"
    )
    @app_commands.describe(
        role_to_add="Role to add to each matching user",
        role_required="Users with this role will be skipped (they already qualify)",
        dry_run="If true, no changes are made—just shows what would happen"
    )
    @app_commands.check(permCheck)  # runs permission check (admin or developer)
    @app_commands.guild_only()
    async def smartadd(
        self,
        interaction: discord.Interaction,
        role_to_add: discord.Role,
        role_required: discord.Role,
        dry_run: bool = False
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        if role_to_add == role_required:
            return await interaction.followup.send("`role_to_add` and `role_required` must be different roles.", ephemeral=True)

        # ---- Permission & hierarchy checks ----
        me: discord.Member = guild.me  # the bot as a guild member
        if not me.guild_permissions.manage_roles:
            return await interaction.followup.send("I need **Manage Roles** permission.", ephemeral=True)

        if role_to_add.managed:
            return await interaction.followup.send("That role is **managed** by an application and cannot be assigned by bots.", ephemeral=True)

        if me.top_role <= role_to_add:
            return await interaction.followup.send(
                f"I cannot assign `{role_to_add.name}` because it is higher or equal to my top role.",
                ephemeral=True
            )

        # ---- Warm cache for accurate member lists (requires Members intent) ----
        try:
            async for _ in guild.fetch_members(limit=None):
                pass
        except discord.Forbidden:
            return await interaction.followup.send(
                "Missing permission to view members or **Server Members Intent** not enabled for the bot.",
                ephemeral=True
            )

        # ---- Find targets: members WITHOUT role_required ----
        targets: list[discord.Member] = [m for m in guild.members if role_required not in m.roles]

        # ---- Estimate time (best-effort) ----
        # NOTE: This estimate is for iterating through `targets` only.
        # It does NOT include the initial member fetch above, which can be significant on very large guilds.
        SLEEP_EVERY = 10
        SLEEP_SECONDS = 0.5

        if dry_run:
            # No API calls, just local checks + occasional sleep
            SECONDS_PER_USER = 0.003
        else:
            # One API call per user in the "added" path (plus overhead). Conservative estimate.
            SECONDS_PER_USER = 0.20

        sleep_chunks = len(targets) // SLEEP_EVERY
        est_seconds = (len(targets) * SECONDS_PER_USER) + (sleep_chunks * SLEEP_SECONDS)
        eta_str = fmt_eta(est_seconds)

        await interaction.followup.send(
            content=(
                f"Starting…\n"
                f"**Role to add:** `{role_to_add.name}`\n"
                f"**Role required (skip if present):** `{role_required.name}`\n"
                f"**Dry run:** `{dry_run}`\n"
                f"**Targets (missing required role):** {len(targets)}\n"
                f"⏳ **Estimated time for target processing:** ~{eta_str}\n"
                f"*(Does not include initial member fetch / caching time.)*"
            ),
            ephemeral=True
        )

        # ---- Apply role_to_add (skip if already has it) ----
        results = []  # (user_id, username, display_name, status, note)
        added = already = skipped = failed = 0

        for i, member in enumerate(targets, start=1):
            # If they already have the role_to_add, note it
            if role_to_add in member.roles:
                already += 1
                results.append((member.id, member.name, member.display_name or "", "already_has_role", ""))
                continue

            if dry_run:
                skipped += 1
                results.append((member.id, member.name, member.display_name or "", "dry_run", "would_add"))
                continue

            try:
                await member.add_roles(
                    role_to_add,
                    reason=f"smartAdd by {interaction.user}: missing {role_required.name}"
                )
                added += 1
                results.append((member.id, member.name, member.display_name or "", "added", ""))
            except discord.Forbidden:
                failed += 1
                results.append((member.id, member.name, member.display_name or "", "forbidden", "Missing permissions / hierarchy"))
            except discord.HTTPException as e:
                failed += 1
                results.append((member.id, member.name, member.display_name or "", "error", str(e)))

            # be gentle with rate limits
            if i % SLEEP_EVERY == 0:
                await asyncio.sleep(SLEEP_SECONDS)

        # ---- Build result CSV to return ----
        out = io.StringIO(newline="")
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["user_id", "username", "display_name", "status", "note"])
        for row in results:
            w.writerow(row)

        data = io.BytesIO(out.getvalue().encode("utf-8"))
        fname = f"smartadd_results_{role_to_add.name.replace(' ','_')}_missing_{role_required.name.replace(' ','_')}.csv"

        msg = (
            f"**Role to add:** `{role_to_add.name}`\n"
            f"**Role required (skip if present):** `{role_required.name}`\n"
            f"**Dry run:** `{dry_run}`\n"
            f"**Targets (missing required role):** {len(targets)}\n"
            f"⏳ **Initial ETA (target processing only):** ~{eta_str}\n\n"
            f"✅ **Added:** {added}\n"
            f"➖ **Already had role:** {already}\n"
            f"🧪 **Dry-run would add:** {skipped}\n"
            f"❌ **Failed:** {failed}"
        )

        await interaction.followup.send(
            content=msg,
            file=discord.File(data, filename=fname),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(smartAdd(bot))
