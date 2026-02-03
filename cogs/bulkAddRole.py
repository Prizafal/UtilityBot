# cogs/bulk_add_role.py
import os, io, csv, re, asyncio, discord
from discord import app_commands
from discord.ext import commands

DEV_ID = int(os.getenv("DEV_ID", "0"))

def permCheck(interaction: discord.Interaction):  # checks if the user is an admin or the developer
    if interaction.user and interaction.user.id == DEV_ID:
        return True
    if interaction.guild and isinstance(interaction.user, (discord.Member,)):
        return interaction.user.guild_permissions.administrator
    return False

_ID_RE = re.compile(r"^\d{15,22}$")  # snowflake-ish

class bulkAddRole(commands.Cog):
    """
    /bulkaddrole role:<Role> file:<CSV or TXT>
    CSV format: one identifier per row (ID or name).
    With header, use any of: user_id, id, discord_id, username, name, display_name, nick
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="bulkaddrole",
        description="Add a role to many users from a CSV/TXT of user IDs or usernames"
    )
    @app_commands.describe(
        role="Role to add to each user",
        file="CSV/TXT file of IDs or names (one per line or header column)"
    )
    @app_commands.check(permCheck)  # runs permission check (admin or developer)
    @app_commands.guild_only()
    async def bulkaddrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        file: discord.Attachment
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send("Use this in a server.", ephemeral=True)

        # ---- Permission & hierarchy checks ----
        me: discord.Member = guild.me  # the bot as a guild member
        if not me.guild_permissions.manage_roles:
            return await interaction.followup.send("I need **Manage Roles** permission.", ephemeral=True)

        if role.managed:
            return await interaction.followup.send("That role is **managed** by an application and cannot be assigned by bots.", ephemeral=True)

        if me.top_role <= role:
            return await interaction.followup.send(
                f"I cannot assign `{role.name}` because it is higher or equal to my top role.",
                ephemeral=True
            )

        # ---- Validate attachment ----
        if not file.content_type or all(k not in file.content_type for k in ("csv", "text", "plain")):
            return await interaction.followup.send("Please attach a **.csv** or **.txt** file.", ephemeral=True)

        # ---- Read & decode ----
        try:
            raw = await file.read()
        except Exception as e:
            return await interaction.followup.send(f"Failed to read file: {e}", ephemeral=True)

        text = None
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue
        if text is None:
            return await interaction.followup.send("Could not decode file (try UTF-8).", ephemeral=True)

        # ---- Parse CSV robustly (no Sniffer; handle 1-value-per-line) ----
        sample = text[:4096]
        # choose a delimiter if present; else treat as newline-separated
        chosen = None
        for d in (",", ";", "\t", "|"):
            if d in sample:
                chosen = d
                break

        if chosen:
            dialect = csv.excel
            dialect.delimiter = chosen
            reader = csv.reader(io.StringIO(text), dialect)
        else:
            # no delimiter → assume one identifier per line
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            # emulate CSV rows: each row is a single-cell list
            reader = ([ln] for ln in lines)

        # ---- Extract identifiers (ID or name) ----
        idents: list[str] = []
        valid_cols = {"user_id", "id", "discord_id", "username", "name", "display_name", "nick"}

        try:
            it = iter(reader)
            first = next(it, None)
            if first is None:
                return await interaction.followup.send("File is empty.", ephemeral=True)

            # Ensure row is list-like
            if not isinstance(first, (list, tuple)):
                first = [str(first)]

            # Header mode ?
            if any(str(c).strip().lower() in valid_cols for c in first):
                header = [str(c).strip().lower() for c in first]
                col_idx = None
                for cand in ("user_id", "id", "discord_id", "username", "name", "display_name", "nick"):
                    if cand in header:
                        col_idx = header.index(cand)
                        break
                if col_idx is None:
                    return await interaction.followup.send(
                        "No supported column found. Use one of: user_id, id, discord_id, username, name, display_name, nick.",
                        ephemeral=True,
                    )
                for row in it:
                    if not row or col_idx >= len(row):
                        continue
                    val = str(row[col_idx]).strip()
                    if val:
                        idents.append(val)
            else:
                # no header → first column only, include the first row too
                def first_col(row):
                    if not isinstance(row, (list, tuple)):
                        row = [str(row)]
                    return str(row[0]).strip() if row and len(row) > 0 else ""

                first_val = first_col(first)
                if first_val:
                    idents.append(first_val)
                for row in it:
                    val = first_col(row)
                    if val:
                        idents.append(val)
        except Exception as e:
            return await interaction.followup.send(f"Failed to read rows: {e}", ephemeral=True)

        # Deduplicate while preserving order
        seen = set()
        tokens: list[str] = []
        for s in idents:
            if s not in seen:
                seen.add(s)
                tokens.append(s)

        if not tokens:
            return await interaction.followup.send("No valid identifiers found in file.", ephemeral=True)

        # ---- Warm cache for name lookups (requires Members intent) ----
        try:
            async for _ in guild.fetch_members(limit=None):
                pass
        except discord.Forbidden:
            return await interaction.followup.send(
                "Missing permission to view members or **Server Members Intent** not enabled for the bot.",
                ephemeral=True
            )

        # Build indices for quick exact (case-insensitive) name resolution
        members: list[discord.Member] = list(guild.members)
        by_username: dict[str, list[discord.Member]] = {}
        by_display: dict[str, list[discord.Member]] = {}
        by_nick: dict[str, list[discord.Member]] = {}

        for m in members:
            by_username.setdefault(m.name.lower(), []).append(m)
            by_display.setdefault((m.display_name or "").lower(), []).append(m)
            by_nick.setdefault((m.nick or "").lower(), []).append(m)

        async def resolve_member(identifier: str) -> tuple[discord.Member | None, str]:
            """
            Returns (member, status_reason)
            status_reason in {"id_ok","name_ok","ambiguous","not_found","error"}
            """
            s = identifier.strip()

            # Prefer numeric ID
            if _ID_RE.match(s):
                uid = int(s)
                member = guild.get_member(uid)
                if member is not None:
                    return member, "id_ok"
                try:
                    member = await guild.fetch_member(uid)
                    return member, "id_ok"
                except discord.NotFound:
                    return None, "not_found"
                except discord.HTTPException:
                    return None, "error"

            # Exact name matches across nick/display/username (case-insensitive)
            key = s.lower()
            candidates = []
            candidates.extend(by_nick.get(key, []))
            candidates.extend(by_display.get(key, []))
            candidates.extend(by_username.get(key, []))

            # Dedup in case the same member appears in multiple buckets
            unique = list({m.id: m for m in candidates}.values())

            if len(unique) == 1:
                return unique[0], "name_ok"
            if len(unique) > 1:
                return None, "ambiguous"
            return None, "not_found"

        # ---- Process assignments ----
        results = []  # (input, user_id|blank, status, note)
        success = already = not_found = failed = ambiguous = 0
        missing_list: list[str] = []   # not_found + ambiguous (for error attachment)

        for i, token in enumerate(tokens, start=1):
            member, reason = await resolve_member(token)

            if member is None:
                if reason == "ambiguous":
                    ambiguous += 1
                    results.append((token, "", "ambiguous", "Multiple users match this name"))
                    missing_list.append(f"{token}  <-- ambiguous")
                elif reason == "not_found":
                    not_found += 1
                    results.append((token, "", "not_found", "No member matched"))
                    missing_list.append(token)
                else:
                    failed += 1
                    results.append((token, "", "error", reason))
                if i % 10 == 0:
                    await asyncio.sleep(0.5)
                continue

            # Already has role?
            if role in member.roles:
                already += 1
                results.append((token, str(member.id), "already_has_role", ""))
                if i % 10 == 0:
                    await asyncio.sleep(0.5)
                continue

            # Try to add role
            try:
                await member.add_roles(role, reason=f"Bulk add by {interaction.user} via CSV")
                success += 1
                results.append((token, str(member.id), "added", ""))
            except discord.Forbidden:
                failed += 1
                results.append((token, str(member.id), "forbidden", "Missing permissions or role hierarchy"))
            except discord.HTTPException as e:
                failed += 1
                results.append((token, str(member.id), "error", f"{e}"))

            if i % 10 == 0:
                await asyncio.sleep(0.5)

        # ---- Build result CSV to return ----
        out = io.StringIO(newline="")
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["input", "user_id", "status", "note"])
        for row in results:
            w.writerow(row)
        data = io.BytesIO(out.getvalue().encode("utf-8"))

        msg = (
            f"**Role:** `{role.name}`\n"
            f"**Processed:** {len(tokens)}\n"
            f"✅ **Added:** {success}\n"
            f"➖ **Already had:** {already}\n"
            f"❓ **Ambiguous:** {ambiguous}\n"
            f"❔ **Not found:** {not_found}\n"
            f"❌ **Failed:** {failed}"
        )
        await interaction.followup.send(
            content=msg,
            file=discord.File(data, filename=f"bulk_add_role_results_{role.name.replace(' ','_')}.csv"),
            ephemeral=True
        )

        # ---- Unresolved identifiers attachment (names not found or ambiguous) ----
        if missing_list:
            print(f"[BULK ADD ROLE] Unresolved in guild {guild.id}: {missing_list}")
            miss_txt = io.StringIO("\n".join(missing_list))
            miss_bytes = io.BytesIO(miss_txt.getvalue().encode("utf-8"))
            await interaction.followup.send(
                content=f"❌ Some identifiers could not be resolved in **{guild.name}** (`{guild.id}`): **{len(missing_list)}**",
                file=discord.File(miss_bytes, filename="unresolved_identifiers.txt"),
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(bulkAddRole(bot))
