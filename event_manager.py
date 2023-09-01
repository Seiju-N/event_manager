import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.environ["GUILD_ID"])
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
ROLE_NAME_ADMIN = os.environ["ROLE_NAME_ADMIN"]
ROLE_NAME_JOIN = os.environ["ROLE_NAME_JOIN"]
ROLE_NAME_SPEC = os.environ["ROLE_NAME_SPEC"]

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(intents=intents)
bot.event_message_ids = []


def get_role_id_by_name(guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    return role.id if role else None


def has_role(member: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in member.roles)


class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_message_id = None
        self.emoji_to_role = {}

    @commands.slash_command(name="create", description="Create an event")
    async def create(self, ctx, *, event_name: str):
        if not has_role(
            ctx.author,
        ):
            await ctx.send("You don't have permission to create an event!")
            return
        embed = discord.Embed(
            title=event_name, description="React to join or spectate!"
        )
        message = await ctx.send(embed=embed)
        self.role_message_id = message.id
        self.bot.event_message_ids.append(message.id)

        # Add reactions
        await message.add_reaction("✋")
        await message.add_reaction("👀")
        await message.add_reaction("❌")

        # Setup role mapping
        self.emoji_to_role = {
            "✋": self.get_role_id_by_name(ctx.guild, ROLE_NAME_JOIN),
            "👀": self.get_role_id_by_name(ctx.guild, ROLE_NAME_SPEC),
        }

    def get_role_id_by_name(self, guild, role_name):
        role = discord.utils.get(guild.roles, name=role_name)
        return role.id if role else None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.bot.event_message_ids:
            return
        if (
            payload.message_id != self.role_message_id
            or payload.user_id == self.bot.user.id
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        role_id = self.emoji_to_role.get(str(payload.emoji))
        if not role_id:
            return

        role = guild.get_role(role_id)
        member = guild.get_member(payload.user_id)
        await member.add_roles(role)

        # Remove the user's reaction
        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.TextChannel):
            message = await channel.fetch_message(payload.message_id)
            user = self.bot.get_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)


class ReactionRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_message_id = 0
        self.bot.loop.create_task(self.setup_roles())

    @commands.Cog.listener()
    async def on_ready(self):
        print("Successfully loaded : ReactionRoleCog")
        await self.bot.tree.sync(guild=discord.Object(GUILD_ID))
        print("sync")

    async def setup_roles(self):
        await self.bot.wait_until_ready()
        guild = self.bot.get_guild(GUILD_ID)

        self.emoji_to_role = {
            discord.PartialEmoji(name="✋"): self.get_role_id_by_name(
                guild, ROLE_NAME_JOIN
            ),
            discord.PartialEmoji(name="👀"): self.get_role_id_by_name(
                guild, ROLE_NAME_SPEC
            ),
        }

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if payload.message_id != self.role_message_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        try:
            role_id = self.emoji_to_role[payload.emoji]
        except KeyError:
            return

        role = guild.get_role(role_id)
        if role is None:
            return
        member = guild.get_member(payload.user_id)
        if role == self.emoji_to_role[discord.PartialEmoji(name="❌")]:
            await member.remove_roles(role)
        else:
            try:
                await payload.member.add_roles(role)
            except discord.HTTPException:
                pass
        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.TextChannel):
            message = await channel.fetch_message(payload.message_id)
            user = self.bot.get_user(payload.user_id)
            await message.remove_reaction(payload.emoji, user)


bot.add_cog(EventCog(bot))
bot.add_cog(ReactionRoleCog(bot))
bot.run(BOT_TOKEN)
