from ollama import chat
from ollama import ChatResponse

response: ChatResponse = chat(model='mistral', messages=[
  {
    'role': 'user',
    'content': 'Suggest me songs of male freedom with title and artist only similar to Young Lust by Pink Floyd. Without any comments.',
  },
])
print(response['message']['content'])