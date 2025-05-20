import pytest
import pytest_mock
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot import create_bot


class TestBot:
    @pytest.fixture
    def mock_bot(self, mocker):
        # Mock the discord.ext.commands.Bot class
        bot_mock = mocker.MagicMock(spec=commands.Bot)
        bot_mock.user = mocker.MagicMock(spec=discord.ClientUser)
        bot_mock.user.mentioned_in = mocker.MagicMock(return_value=False)

        # Mock the event registration methods
        events = {}

        def register_event(event_name):
            def decorator(func):
                events[event_name] = func
                return func
            return decorator

        bot_mock.event = register_event
        bot_mock.events = events

        # Mock the process_commands method
        bot_mock.process_commands = AsyncMock()

        # Return the mocked bot
        return bot_mock

    @pytest.fixture
    def mock_commands_bot(self, mocker):
        # Mock the Bot constructor
        bot_mock = mocker.MagicMock()
        mocker.patch('discord.ext.commands.Bot', return_value=bot_mock)
        return bot_mock

    def test_create_bot(self, mock_commands_bot):
        # Test that create_bot creates a bot with the correct parameters
        bot = create_bot()

        # Verify Bot was created with the correct parameters
        discord.ext.commands.Bot.assert_called_once()
        call_args = discord.ext.commands.Bot.call_args

        # Check command prefix
        assert call_args[1]['command_prefix'] == "!"

        # Check intents
        intents = call_args[1]['intents']
        assert isinstance(intents, discord.Intents)
        assert intents.message_content is True
        assert intents.members is True

    def test_on_ready(self, mock_bot):
        # Create a mock for the on_ready event
        on_ready_mock = AsyncMock()

        # Store the decorator function to capture the event handler
        original_event = mock_bot.event
        registered_events = {}

        def event_decorator(func):
            if func.__name__ == 'on_ready':
                registered_events['on_ready'] = func
            return original_event(func)

        # Replace the event decorator with our version
        mock_bot.event = event_decorator

        # Create the bot which registers the event handlers
        bot = create_bot()

        # Verify that on_ready was registered
        assert 'on_ready' in registered_events

        # Call the event handler using the run_async helper
        from conftest import run_async
        run_async(registered_events['on_ready']())

        # No assertions needed as this just logs a message
        # We're just verifying it doesn't raise an exception

    @pytest.mark.asyncio
    async def test_on_connect(self, mock_bot):
        # Create the bot which registers the event handlers
        create_bot.__globals__['commands'] = commands
        create_bot.__globals__['discord'] = discord
        create_bot.__globals__['Bot'] = mock_bot.__class__
        create_bot.__globals__['commands'].Bot = lambda **kwargs: mock_bot

        bot = create_bot()

        # Get the on_connect event handler
        on_connect = mock_bot.events.get('on_connect')
        assert on_connect is not None

        # Call the event handler
        await on_connect()

        # No assertions needed as this just logs a message
        # We're just verifying it doesn't raise an exception

    @pytest.mark.asyncio
    async def test_on_disconnect(self, mock_bot):
        # Create the bot which registers the event handlers
        create_bot.__globals__['commands'] = commands
        create_bot.__globals__['discord'] = discord
        create_bot.__globals__['Bot'] = mock_bot.__class__
        create_bot.__globals__['commands'].Bot = lambda **kwargs: mock_bot

        bot = create_bot()

        # Get the on_disconnect event handler
        on_disconnect = mock_bot.events.get('on_disconnect')
        assert on_disconnect is not None

        # Call the event handler
        await on_disconnect()

        # No assertions needed as this just logs a message
        # We're just verifying it doesn't raise an exception

    @pytest.mark.asyncio
    async def test_on_message_not_mentioned(self, mock_bot, mocker):
        # Create a mock message
        message = mocker.MagicMock()
        message.author = mocker.MagicMock()
        message.channel.send = AsyncMock()

        # Set up the bot to not be mentioned
        mock_bot.user.mentioned_in.return_value = False

        # Create the bot which registers the event handlers
        create_bot.__globals__['commands'] = commands
        create_bot.__globals__['discord'] = discord
        create_bot.__globals__['Bot'] = mock_bot.__class__
        create_bot.__globals__['commands'].Bot = lambda **kwargs: mock_bot

        bot = create_bot()

        # Get the on_message event handler
        on_message = mock_bot.events.get('on_message')
        assert on_message is not None

        # Call the event handler
        await on_message(message)

        # Verify the bot didn't send a message
        message.channel.send.assert_not_called()

        # Verify process_commands was called
        mock_bot.process_commands.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_on_message_mentioned(self, mock_bot, mocker):
        # Create a mock message
        message = mocker.MagicMock()
        message.author = mocker.MagicMock()
        message.channel.send = AsyncMock()

        # Set up the bot to be mentioned
        mock_bot.user.mentioned_in.return_value = True

        # Create the bot which registers the event handlers
        create_bot.__globals__['commands'] = commands
        create_bot.__globals__['discord'] = discord
        create_bot.__globals__['Bot'] = mock_bot.__class__
        create_bot.__globals__['commands'].Bot = lambda **kwargs: mock_bot

        bot = create_bot()

        # Get the on_message event handler
        on_message = mock_bot.events.get('on_message')
        assert on_message is not None

        # Call the event handler
        await on_message(message)

        # Verify the bot sent a message
        message.channel.send.assert_called_once_with("Hello!")

        # Verify process_commands was called
        mock_bot.process_commands.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_on_message_from_bot(self, mock_bot, mocker):
        # Create a mock message from the bot itself
        message = mocker.MagicMock()
        message.author = mock_bot.user
        message.channel.send = AsyncMock()

        # Create the bot which registers the event handlers
        create_bot.__globals__['commands'] = commands
        create_bot.__globals__['discord'] = discord
        create_bot.__globals__['Bot'] = mock_bot.__class__
        create_bot.__globals__['commands'].Bot = lambda **kwargs: mock_bot

        bot = create_bot()

        # Get the on_message event handler
        on_message = mock_bot.events.get('on_message')
        assert on_message is not None

        # Call the event handler
        await on_message(message)

        # Verify the bot didn't send a message
        message.channel.send.assert_not_called()

        # Verify process_commands was not called
        mock_bot.process_commands.assert_not_called()
