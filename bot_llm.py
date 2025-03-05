from ollama import Client
from ollama import ChatResponse

#FIXME: need to remove deepseek's '<think>' portions of it's response
def bot_response(user: str = "user", prompt: str = "", client: Client = None) -> str:
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
  if client is None:
    client: Client = Client(host="http://localhost:11434")
  response: ChatResponse = client.chat(model="artifish/llama3.2-uncensored:latest",messages=[
    {
      'role': user,
      'content': prompt,
    },
  ])

  return response['message']['content']

if __name__ == "__main__":
  print(bot_response(prompt=""))