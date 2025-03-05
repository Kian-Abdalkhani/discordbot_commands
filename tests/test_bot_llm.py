import pytest
from ..bot_llm import bot_response


#TODO: Create a mocker for the ollama API
def test_bot_response_blank():
    with pytest.raises(ValueError):
        bot_response(prompt="")

def test_bot_response_invalid_user():
    with pytest.raises(ValueError):
        bot_response(user="larry",prompt="Tell me a joke")

def test_bot_response_ollama_api_call(mocker):
    mock_client = mocker.patch(bot_response.__module__+ ".Client",
                               autospec=True)

    bot_response(prompt="Why did the chicken cross the road?")
    mock_client.assert_called_once_with(host="http://localhost:11434")

