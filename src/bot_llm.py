from httpx import HTTPError, HTTPStatusError
from ollama import Client
from ollama import ChatResponse
import os

#enter the model from ollama that you would like to use and connect to Ollama:
OLLAMA_MODEL: str="boug_bot:HC"

# Only create the client when needed, not at import time
def get_client():
    return Client(host=os.getenv("OLLAMA_API_URL"))

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

  try:
    client = get_client()
    response: ChatResponse = client.chat(model=OLLAMA_MODEL,messages=[
      {
        'role': user,
        'content': prompt,
      },
    ])
  except ConnectionError:
    raise ConnectionError("Could not connect to Ollama, please ensure Ollama is running.")

  return response['message']['content']

# Only make the API call if this file is run directly, not when imported
if __name__ == "__main__":
    bot_response(prompt="Hello, I'm Ollama!")
