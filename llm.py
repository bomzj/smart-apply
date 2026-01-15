from typing import Literal
from openai import AzureOpenAI
from smolagents import tool, CodeAgent, AzureOpenAIServerModel
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from langfuse import Langfuse, get_client, observe
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Models costs per 1M tokens input/output:
# gpt 5: 1.25/10
# gpt 5 mini: 0.25/2
# gpt 5 nano: 0.05/0.4

# Available models
type Model = Literal["fast", "smart"]

@observe
def ask_llm(message: str, model: Model = "fast") -> str:
    model = getenv("AZURE_OPENAI_MODEL_" + model.upper())
    response = llm.chat.completions.create(
        messages=[
            { "role": "system", "content": "Do not include any reasoning in your response." },
            { "role": "user", "content": message }
        ],
        model=model
    )

    return response.choices[0].message.content

# Configure telemetry to debug model behavior and monitor usage
if getenv("LANGFUSE_ENABLED").lower() == "true":
    langfuse = Langfuse(
        public_key=getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=getenv("LANGFUSE_SECRET_KEY"),
        host=getenv("LANGFUSE_HOST")
    )

    langfuse = get_client()

    # Verify connection
    if langfuse.auth_check():
        print("Langfuse client is authenticated and ready!")
    else:
        print("Authentication failed. Please check your credentials and host.")

    # for langfuse to work with smolagents and azure open ai
    SmolagentsInstrumentor().instrument()


model = AzureOpenAIServerModel(
      model_id=getenv("AZURE_OPENAI_MODEL_FAST"),
      azure_endpoint=getenv("AZURE_OPENAI_ENDPOINT"),
      api_key=getenv("AZURE_OPENAI_API_KEY"),
      api_version=getenv("OPENAI_API_VERSION")
)

llm = model.create_client()