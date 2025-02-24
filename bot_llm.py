from ollama import Client
from ollama import ChatResponse


def bot_response(user: str = "user", prompt: str = None) -> str:

  client: Client = Client(host="ollama-services:11434")

  response: ChatResponse = client.chat(model="deepseek-r1:1.5b",messages=[
    {
      'role': user,
      'content': prompt,
    },
  ])

  return response['message']['content']