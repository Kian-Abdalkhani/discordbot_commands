import pytest
import pytest_mock
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock, patch
from src.main import MyClient


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

        # Mock the MyClient class to avoid discord connection issues
        with patch('src.main.MyClient') as MockMyClient:
            client = MagicMock(spec=MyClient)
            MockMyClient.return_value = client

            # Set up the mock client
            mock_user = MagicMock()
            mock_user.mentioned_in = MagicMock(return_value=False)
            client.user = mock_user

            client.tree = MagicMock()
            client.tree.sync = AsyncMock()
            client.load_extension = AsyncMock()
            client.process_commands = AsyncMock()

            # Add the actual methods we want to test
            client.on_ready = MyClient.on_ready.__get__(client, MyClient)
            client.on_connect = MyClient.on_connect.__get__(client, MyClient)
            client.on_disconnect = MyClient.on_disconnect.__get__(client, MyClient)
            client.on_message = MyClient.on_message.__get__(client, MyClient)

            return client

    def test_client_initialization(self):
        # Test that MyClient can be initialized with correct parameters
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        client = MyClient()

        # Verify the client was created successfully
        assert isinstance(client, MyClient)
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
            client_instance.load_extension.assert_any_call('src.cogs.utilities')
            client_instance.load_extension.assert_any_call('src.cogs.quotes')
            client_instance.load_extension.assert_any_call('src.cogs.games')
            client_instance.load_extension.assert_any_call('src.cogs.feature_request')
            client_instance.load_extension.assert_any_call('src.cogs.permissions')

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

    @pytest.mark.asyncio
    async def test_interaction_check_restricted_user(self, client_instance, mocker):
        # Test interaction_check with a restricted user
        interaction = mocker.MagicMock()
        interaction.user.id = 12345
        interaction.response.send_message = AsyncMock()
        
        # Mock the permission store to have this user as restricted
        client_instance.ps = mocker.MagicMock()
        client_instance.ps.restricted_members = [12345]
        
        # Call the interaction_check method
        result = await client_instance.interaction_check(interaction)
        
        # Verify the user was denied access
        assert result is False
        interaction.response.send_message.assert_called_once_with("You are still in timeout")

    @pytest.mark.asyncio
    async def test_interaction_check_allowed_user(self, client_instance, mocker):
        # Test interaction_check with an allowed user
        interaction = mocker.MagicMock()
        interaction.user.id = 12345
        
        # Mock the permission store to not have this user as restricted
        client_instance.ps = mocker.MagicMock()
        client_instance.ps.restricted_members = []
        
        # Call the interaction_check method
        result = await client_instance.interaction_check(interaction)
        
        # Verify the user was allowed access
        assert result is True

    @pytest.mark.asyncio
    async def test_on_app_command_completion(self, client_instance, mocker):
        # Test the on_app_command_completion static method
        interaction = mocker.MagicMock()
        interaction.user = mocker.MagicMock()
        interaction.user.id = 12345
        
        command = mocker.MagicMock()
        command.name = "test_command"
        
        with patch('src.main.logger') as mock_logger:
            await MyClient.on_app_command_completion(interaction, command)
            
            # Verify the command usage was logged
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "used command:  /test_command" in call_args

    @pytest.mark.asyncio
    async def test_on_ready_cog_discovery(self, client_instance, mocker):
        # Test the automatic cog discovery functionality
        with patch('src.main.os.listdir') as mock_listdir, \
             patch('src.main.os.path.join') as mock_join, \
             patch('src.main.discord.Object') as mock_object, \
             patch('src.main.GUILD_ID', 12345), \
             patch('src.main.logger') as mock_logger:

            # Mock the cogs directory listing
            mock_listdir.return_value = [
                '__init__.py', 'blackjack.py', 'games.py', 'quotes.py', 
                'utilities.py', 'currency.py', 'permissions.py'
            ]
            mock_join.return_value = '/fake/path/cogs'
            
            mock_guild = MagicMock()
            mock_object.return_value = mock_guild
            
            # Mock the sync result
            client_instance.tree.sync.return_value = [MagicMock(), MagicMock()]
            
            # Call the on_ready method
            await client_instance.on_ready()
            
            # Verify cog discovery was logged
            mock_logger.info.assert_any_call(
                "Discovered extensions: ['src.cogs.blackjack', 'src.cogs.games', 'src.cogs.quotes', 'src.cogs.utilities', 'src.cogs.currency', 'src.cogs.permissions']"
            )
            
            # Verify extensions were loaded
            expected_extensions = [
                'src.cogs.blackjack', 'src.cogs.games', 'src.cogs.quotes', 
                'src.cogs.utilities', 'src.cogs.currency', 'src.cogs.permissions'
            ]
            for extension in expected_extensions:
                client_instance.load_extension.assert_any_call(extension)

    @pytest.mark.asyncio
    async def test_on_ready_extension_load_error(self, client_instance, mocker):
        # Test handling of extension load errors
        with patch('src.main.os.listdir') as mock_listdir, \
             patch('src.main.os.path.join') as mock_join, \
             patch('src.main.discord.Object') as mock_object, \
             patch('src.main.GUILD_ID', 12345), \
             patch('src.main.logger') as mock_logger:

            mock_listdir.return_value = ['games.py']
            mock_join.return_value = '/fake/path/cogs'
            
            mock_guild = MagicMock()
            mock_object.return_value = mock_guild
            
            # Make load_extension raise an exception
            client_instance.load_extension.side_effect = Exception("Load failed")
            client_instance.tree.sync.return_value = []
            
            # Call the on_ready method
            await client_instance.on_ready()
            
            # Verify error was logged
            mock_logger.error.assert_any_call("Failed to load extension src.cogs.games: Load failed")

    def test_main_function_no_token(self, mocker):
        # Test main function when no bot token is provided
        with patch('src.main.os.getenv', return_value=None), \
             patch('src.main.logging.error') as mock_error, \
             patch('src.main.sys.exit') as mock_exit:
            
            from src.main import main
            main()
            
            # Verify error was logged and program exited
            mock_error.assert_called_once_with("No bot token found in environment variables")
            mock_exit.assert_called_once_with(1)

    def test_main_function_with_token(self, mocker):
        # Test main function with valid bot token
        mock_client = mocker.MagicMock()
        
        with patch('src.main.os.getenv', return_value='fake_token'), \
             patch('src.main.MyClient', return_value=mock_client) as mock_client_class:
            
            from src.main import main
            main()
            
            # Verify client was created and run was called
            mock_client_class.assert_called_once()
            mock_client.run.assert_called_once_with('fake_token')
