import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import Guild
import os
from dotenv import load_dotenv

load_dotenv()

GUILD_ID = int(os.environ["GUILD_ID"])
BOT_TOKEN = os.environ["BOT_TOKEN"]
ROLE_NAME_ADMIN = os.environ["ROLE_NAME_ADMIN"]
ROLE_NAME_JOIN = os.environ["ROLE_NAME_JOIN"]
ROLE_NAME_SPEC = os.environ["ROLE_NAME_SPEC"]

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(intents=intents)
bot.event_message_ids = []


def get_role_id_by_name(guild: Guild, role_name):
    role = discord.utils.get(guild.roles, name=role_name)
    return role.id if role else None


def has_role(member: discord.Member, role_name: str) -> bool:
    return any(role.name == role_name for role in member.roles)


def create_event_embed(event_name, participants, spectators):
    participants_str = " ".join(participants) if participants else "なし"
    spectators_str = " ".join(spectators) if spectators else "なし"
    embed = discord.Embed(
        title=event_name,
        description=f"🤚 参加者: {participants_str}\n"
        f"👀 観戦者: {spectators_str}\n"
        "リアクションで参加・観戦を選択してください。",
    )
    return embed


class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.emoji_to_role = {}

    @commands.slash_command(name="create", description="Create an event")
    async def create(self, ctx: Context, *, event_name: str):
        if not has_role(
            ctx.author,
            ROLE_NAME_ADMIN,
        ):
            await ctx.send("You don't have permission to create an event!")
            return
        embed = create_event_embed(event_name, 0, 0)
        message = await ctx.send(embed=embed)
        self.bot.event_message_ids.append(message.id)

        # Add reactions
        await message.add_reaction("✋")
        await message.add_reaction("👀")
        await message.add_reaction("❌")

        # Setup role mapping
        self.emoji_to_role = {
            "✋": get_role_id_by_name(ctx.guild, ROLE_NAME_JOIN),
            "👀": get_role_id_by_name(ctx.guild, ROLE_NAME_SPEC),
        }


class ReactionRoleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
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
            discord.PartialEmoji(name="✋"): get_role_id_by_name(guild, ROLE_NAME_JOIN),
            discord.PartialEmoji(name="👀"): get_role_id_by_name(guild, ROLE_NAME_SPEC),
        }

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if payload.message_id not in self.bot.event_message_ids:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role_id = self.emoji_to_role.get(payload.emoji, None)
        if not role_id:
            return

        role = guild.get_role(role_id)
        if role is None:
            return
        member = guild.get_member(payload.user_id)
        if role.name == ROLE_NAME_JOIN and has_role(member, ROLE_NAME_SPEC):
            spec_role = guild.get_role(get_role_id_by_name(guild, ROLE_NAME_SPEC))
            await member.remove_roles(spec_role)
        elif role.name == ROLE_NAME_SPEC and has_role(member, ROLE_NAME_JOIN):
            join_role = guild.get_role(get_role_id_by_name(guild, ROLE_NAME_JOIN))
            await member.remove_roles(join_role)

        await member.add_roles(role)

        channel = self.bot.get_channel(payload.channel_id)
        if isinstance(channel, discord.TextChannel):
            message = await channel.fetch_message(payload.message_id)
            user = self.bot.get_user(payload.user_id)

            # 参加者と観戦者の名前のリストを取得
            participants = await self.get_users_with_reaction(message, "✋")
            spectators = await self.get_users_with_reaction(message, "👀")
            new_embed = create_event_embed(
                message.embeds[0].title, participants, spectators
            )

            # メッセージのEmbedを更新
            await message.edit(embed=new_embed)
            await message.remove_reaction(payload.emoji, user)

    async def get_users_with_reaction(self, message, emoji_name):
        """メッセージから指定された絵文字を持つユーザーの名前のリストを取得"""
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji_name:
                users = await reaction.users().flatten()
                return [f"<@{user.id}>" for user in users if not user.bot]
        return []


bot.add_cog(EventCog(bot))
bot.add_cog(ReactionRoleCog(bot))
bot.run(BOT_TOKEN)
