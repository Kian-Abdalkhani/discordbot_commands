from ollama import Client
from ollama import ChatResponse

#FIXME: need to remove deepseek's '<think>' portions of it's response
def bot_response(user: str = "user", prompt: str = None) -> str:
  """
  Create a chat response from the Ollama bot.
  :param user: "user" or "system", the source of the prompt.
  :param prompt: question/statement made to the LLM.
  :return: LLM's response to the prompt.
  """

  if user not in ["system", "user"]:
    raise ValueError(f"{user} is not a Invalid user, please use 'system' or 'user'")
  if prompt is None:
    raise ValueError("Please enter a prompt.")

  #connect to ollama
  client: Client = Client(host="ollama-services:11434")

  #send prompt to desired LLM model
  response: ChatResponse = client.chat(model="deepseek-r1:1.5b",messages=[
    {
      'role': user,
      'content': prompt,
    },
  ])

  return response['message']['content']