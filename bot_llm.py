from httpx import HTTPError, HTTPStatusError
from ollama import Client
from ollama import ChatResponse

#enter the model from ollama that you would like to use:
OLLAMA_MODEL: str="boug_bot:HC"

#TODO: make this method asynchronous using the asyncio and aiohttp packages
def bot_response(user: str = "user", prompt: str = "") -> str:
  """
  Create a chat response from the Ollama bot.
  :param user: "user" or "system", the source of the prompt.
  :param prompt: question/statement made to the LLM.
  :param client: Ollama bot client host
  :return: LLM's response to the prompt.
  """

  if user not in ["system", "user"]:
    raise ValueError(f"{user} is not a Invalid user, please use 'system' or 'user'")
  if prompt == "":
    raise ValueError("Please enter a prompt.")

  # connect to ollama
  client: Client = Client(host="http://127.0.0.1:11434")

  try:
    response: ChatResponse = client.chat(model=OLLAMA_MODEL,messages=[
      {
        'role': user,
        'content': prompt,
      },
    ])
  except ConnectionError:
    raise ConnectionError("Could not connect to Ollama, please ensure Ollama is running.")

  return response['message']['content']

bot_response(prompt="Hello, I'm Ollama!")