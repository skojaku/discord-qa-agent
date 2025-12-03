"""Mock Discord objects for testing bot interactions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock, PropertyMock
import asyncio


@dataclass
class MockUser:
    """Mock Discord user object."""

    id: int = 123456789
    name: str = "TestUser"
    display_name: str = "TestUser"
    discriminator: str = "0001"
    bot: bool = False
    mention: str = field(init=False)

    def __post_init__(self):
        self.mention = f"<@{self.id}>"

    def __eq__(self, other):
        if isinstance(other, MockUser):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


@dataclass
class MockMember(MockUser):
    """Mock Discord guild member object."""

    guild: Optional["MockGuild"] = None
    roles: List[Any] = field(default_factory=list)
    nick: Optional[str] = None

    @property
    def display_name(self) -> str:
        return self.nick or self.name


@dataclass
class MockChannel:
    """Mock Discord channel object."""

    id: int = 987654321
    name: str = "test-channel"
    type: str = "text"
    guild: Optional["MockGuild"] = None

    # Async methods
    send: AsyncMock = field(default_factory=AsyncMock)

    def __post_init__(self):
        self.send = AsyncMock(return_value=create_mock_message(channel=self))
        self.history = self._history

    async def _history(self, limit: int = 100) -> List["MockMessage"]:
        """Mock history method."""
        return []


@dataclass
class MockDMChannel(MockChannel):
    """Mock Discord DM channel."""

    type: str = "private"
    recipient: Optional[MockUser] = None


@dataclass
class MockGuild:
    """Mock Discord guild (server) object."""

    id: int = 111222333
    name: str = "Test Server"
    owner_id: int = 123456789
    members: List[MockMember] = field(default_factory=list)
    channels: List[MockChannel] = field(default_factory=list)

    def get_member(self, user_id: int) -> Optional[MockMember]:
        """Get member by ID."""
        for member in self.members:
            if member.id == user_id:
                return member
        return None


@dataclass
class MockMessage:
    """Mock Discord message object."""

    id: int = 555666777
    content: str = ""
    author: MockUser = field(default_factory=MockUser)
    channel: MockChannel = field(default_factory=MockChannel)
    guild: Optional[MockGuild] = None
    mentions: List[MockUser] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    # Async methods
    reply: AsyncMock = field(default_factory=AsyncMock)
    edit: AsyncMock = field(default_factory=AsyncMock)
    delete: AsyncMock = field(default_factory=AsyncMock)
    add_reaction: AsyncMock = field(default_factory=AsyncMock)

    def __post_init__(self):
        self.reply = AsyncMock()
        self.edit = AsyncMock()
        self.delete = AsyncMock()
        self.add_reaction = AsyncMock()


class MockInteractionResponse:
    """Mock Discord interaction response."""

    def __init__(self):
        self._is_done = False
        self.send_message = AsyncMock()
        self.send_modal = AsyncMock()
        self.defer = AsyncMock()
        self.edit_message = AsyncMock()

    def is_done(self) -> bool:
        return self._is_done

    async def send_message(self, content: str = None, embed: Any = None,
                          view: Any = None, ephemeral: bool = False):
        self._is_done = True

    async def defer(self, thinking: bool = False, ephemeral: bool = False):
        self._is_done = True


class MockFollowup:
    """Mock Discord interaction followup."""

    def __init__(self):
        self.send = AsyncMock()
        self.edit_message = AsyncMock()


@dataclass
class MockInteraction:
    """Mock Discord interaction object for slash commands."""

    id: int = 999888777
    user: MockUser = field(default_factory=MockUser)
    channel: MockChannel = field(default_factory=MockChannel)
    guild: Optional[MockGuild] = None
    data: Dict[str, Any] = field(default_factory=dict)
    message: Optional[MockMessage] = None

    response: MockInteractionResponse = field(default_factory=MockInteractionResponse)
    followup: MockFollowup = field(default_factory=MockFollowup)

    # Track sent embeds and views for assertions
    sent_embeds: List[Any] = field(default_factory=list)
    sent_views: List[Any] = field(default_factory=list)
    sent_modals: List[Any] = field(default_factory=list)

    def __post_init__(self):
        self.response = MockInteractionResponse()
        self.followup = MockFollowup()

        # Capture embeds and views when sent
        original_followup_send = self.followup.send
        async def capture_followup_send(content=None, embed=None, view=None, **kwargs):
            if embed:
                self.sent_embeds.append(embed)
            if view:
                self.sent_views.append(view)
            return await original_followup_send(content=content, embed=embed, view=view, **kwargs)
        self.followup.send = AsyncMock(side_effect=capture_followup_send)

        # Capture modals
        async def capture_modal(modal):
            self.sent_modals.append(modal)
        self.response.send_modal = AsyncMock(side_effect=capture_modal)


class MockBot:
    """Mock Discord bot for testing."""

    def __init__(self, user_id: int = 999999999):
        self.user = MockUser(id=user_id, name="ChibiBot", bot=True)
        self.guilds: List[MockGuild] = []
        self.command_prefix = "!"

        # Async methods
        self.wait_until_ready = AsyncMock()
        self.change_presence = AsyncMock()
        self.close = AsyncMock()
        self.add_cog = AsyncMock()
        self.load_extension = AsyncMock()

        # Command tree
        self.tree = MagicMock()
        self.tree.sync = AsyncMock()


def create_mock_interaction(
    user_id: int = 123456789,
    user_name: str = "TestUser",
    channel_id: int = 987654321,
    channel_name: str = "test-channel",
    guild_id: Optional[int] = 111222333,
    guild_name: str = "Test Server",
) -> MockInteraction:
    """Factory function to create a configured mock interaction."""

    user = MockUser(id=user_id, name=user_name, display_name=user_name)
    channel = MockChannel(id=channel_id, name=channel_name)

    guild = None
    if guild_id:
        guild = MockGuild(id=guild_id, name=guild_name)
        channel.guild = guild

    return MockInteraction(
        user=user,
        channel=channel,
        guild=guild,
    )


def create_mock_message(
    content: str = "",
    user_id: int = 123456789,
    user_name: str = "TestUser",
    channel: Optional[MockChannel] = None,
    guild: Optional[MockGuild] = None,
    mentions: Optional[List[MockUser]] = None,
    is_dm: bool = False,
) -> MockMessage:
    """Factory function to create a configured mock message."""

    author = MockUser(id=user_id, name=user_name, display_name=user_name)

    if channel is None:
        if is_dm:
            channel = MockDMChannel(recipient=author)
        else:
            channel = MockChannel()

    return MockMessage(
        content=content,
        author=author,
        channel=channel,
        guild=guild,
        mentions=mentions or [],
    )


class ScenarioContext:
    """Context for tracking test scenario state."""

    def __init__(self):
        self.interactions: List[MockInteraction] = []
        self.messages: List[MockMessage] = []
        self.user = MockUser()
        self.channel = MockChannel()
        self.guild = MockGuild()
        self.sent_responses: List[Dict[str, Any]] = []

    def new_interaction(self) -> MockInteraction:
        """Create a new interaction in this scenario context."""
        interaction = MockInteraction(
            user=self.user,
            channel=self.channel,
            guild=self.guild,
        )
        self.interactions.append(interaction)
        return interaction

    def new_message(self, content: str, mentions: Optional[List[MockUser]] = None) -> MockMessage:
        """Create a new message in this scenario context."""
        message = MockMessage(
            content=content,
            author=self.user,
            channel=self.channel,
            guild=self.guild,
            mentions=mentions or [],
        )
        self.messages.append(message)
        return message
