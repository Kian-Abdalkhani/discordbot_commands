import pytest
import pytest_mock
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import Client


class TestClient:
    @pytest.fixture
    def mock_client(self, mocker):
        # Mock the discord.ext.commands.Bot class that Client inherits from
        bot_mock = mocker.MagicMock(spec=commands.Bot)
        bot_mock.user = mocker.MagicMock(spec=discord.ClientUser)
        bot_mock.user.mentioned_in = mocker.MagicMock(return_value=False)
        bot_mock.tree = mocker.MagicMock()
        bot_mock.tree.sync = AsyncMock()
        bot_mock.load_extension = AsyncMock()
        bot_mock.process_commands = AsyncMock()

        return bot_mock

    @pytest.fixture
    def client_instance(self, mocker):
        # Create a Client instance with real intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        # Mock the Client class to avoid discord connection issues
        with patch('src.main.Client') as MockClient:
            client = MagicMock(spec=Client)
            MockClient.return_value = client

            # Set up the mock client
            mock_user = MagicMock()
            mock_user.mentioned_in = MagicMock(return_value=False)
            client.user = mock_user

            client.tree = MagicMock()
            client.tree.sync = AsyncMock()
            client.load_extension = AsyncMock()
            client.process_commands = AsyncMock()

            # Add the actual methods we want to test
            client.on_ready = Client.on_ready.__get__(client, Client)
            client.on_connect = Client.on_connect.__get__(client, Client)
            client.on_disconnect = Client.on_disconnect.__get__(client, Client)
            client.on_message = Client.on_message.__get__(client, Client)

            return client

    def test_client_initialization(self):
        # Test that Client can be initialized with correct parameters
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        client = Client(command_prefix="!", intents=intents)

        # Verify the client was created successfully
        assert isinstance(client, Client)
        assert isinstance(client, commands.Bot)

    @pytest.mark.asyncio
    async def test_on_ready(self, client_instance, mocker):
        # Mock the dependencies for on_ready
        with patch('src.main.discord.Object') as mock_object, \
             patch('src.main.GUILD_ID', 12345):

            mock_guild = MagicMock()
            mock_object.return_value = mock_guild

            # Mock the sync result
            client_instance.tree.sync.return_value = [MagicMock(), MagicMock()]  # 2 synced commands

            # Call the on_ready method
            await client_instance.on_ready()

            # Verify extensions were loaded
            client_instance.load_extension.assert_any_call('cogs.utilities')
            client_instance.load_extension.assert_any_call('cogs.quotes')
            client_instance.load_extension.assert_any_call('cogs.games')

            # Verify tree sync was called
            client_instance.tree.sync.assert_called_once_with(guild=mock_guild)

    @pytest.mark.asyncio
    async def test_on_ready_sync_error(self, client_instance, mocker):
        # Mock the dependencies and make sync raise an exception
        with patch('src.main.discord.Object') as mock_object, \
             patch('src.main.GUILD_ID', 12345), \
             patch('src.main.logger') as mock_logger:

            mock_guild = MagicMock()
            mock_object.return_value = mock_guild

            # Make tree.sync raise an exception
            client_instance.tree.sync.side_effect = Exception("Sync failed")

            # Call the on_ready method
            await client_instance.on_ready()

            # Verify error was logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_connect(self, client_instance):
        # Test the on_connect event handler
        with patch('src.main.logger') as mock_logger:
            await client_instance.on_connect()
            # Verify it logs the connection message
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_disconnect(self, client_instance):
        # Test the on_disconnect event handler
        with patch('src.main.logger') as mock_logger:
            await client_instance.on_disconnect()
            # Verify it logs the disconnection message
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_message_from_bot(self, client_instance, mocker):
        # Create a mock message from the bot itself
        message = mocker.MagicMock()
        message.author = client_instance.user
        message.channel.send = AsyncMock()

        # Call the on_message event handler
        await client_instance.on_message(message)

        # Verify the bot didn't send a message
        message.channel.send.assert_not_called()
        # Verify process_commands was not called
        client_instance.process_commands.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_not_mentioned(self, client_instance, mocker):
        # Create a mock message from another user
        message = mocker.MagicMock()
        message.author = mocker.MagicMock()
        message.channel.send = AsyncMock()

        # Set up the bot to not be mentioned
        client_instance.user.mentioned_in.return_value = False

        # Call the on_message event handler
        await client_instance.on_message(message)

        # Verify the bot didn't send a greeting message
        message.channel.send.assert_not_called()
        # Verify process_commands was called
        client_instance.process_commands.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_on_message_mentioned(self, client_instance, mocker):
        # Create a mock message from another user
        message = mocker.MagicMock()
        message.author = mocker.MagicMock()
        message.author.mention = "@TestUser"
        message.channel.send = AsyncMock()

        # Set up the bot to be mentioned
        client_instance.user.mentioned_in.return_value = True

        # Call the on_message event handler
        await client_instance.on_message(message)

        # Verify the bot sent a greeting message
        expected_message = f"Hello {message.author.mention}, I am the server's minigame bot!"
        message.channel.send.assert_called_once_with(expected_message)

        # Verify process_commands was not called (since we return early when mentioned)
        client_instance.process_commands.assert_not_called()
