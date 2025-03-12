import pytest
from ..bot_llm import bot_response

#tests blank prompts
def test_bot_response_blank():
    with pytest.raises(ValueError):
        bot_response(prompt="")

#tests if invalid user is input into bot_response
def test_bot_response_invalid_user():
    with pytest.raises(ValueError):
        bot_response(user="larry",prompt="Tell me a joke")

#tests if api is called
def test_bot_response_ollama_api_call(mocker):
    mock_client = mocker.patch(bot_response.__module__+ ".Client",
                               autospec=True)

    bot_response(prompt="Why did the chicken cross the road?")
    mock_client.assert_called_once_with(host="http://127.0.0.1:11434")

#tests if ollama api is able to connect
def test_ollama_connection():
    try:
        bot_response(prompt="Are you on?")
    except ConnectionError:
        assert False
    else:
        assert True


