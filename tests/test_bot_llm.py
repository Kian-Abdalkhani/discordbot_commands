import pytest
from ..bot_llm import bot_response

#TODO: Create a mocker for the ollama API
class TestBotLLM:

    def test_bot_response_blank(self):
        with pytest.raises(ValueError):
            bot_response(prompt="")

    def test_bot_response_empty(self):
        with pytest.raises(ValueError):
            bot_response(user="larry",prompt="Tell me a joke")

    # def test_returned_values(self,mocker):
    #     mock_get = mocker.patch("ollama.Client")
    #     mock_get.return_value.generate.return_value ={
    #
    #
    #     } "To get to the other side"
    #
    #     result = bot_response(prompt="Tell me a joke")
    #     assert result == "To get to the other side"
    #     mock_get.assert_called_once_with("https://ollama-services:11434/Tell me a joke")