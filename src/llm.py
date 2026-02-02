from typing import Literal
from openai import AzureOpenAI
from smolagents import tool, CodeAgent, AzureOpenAIServerModel
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from langfuse import Langfuse, get_client, observe
from config import settings

LANGFUSE_ENABLED = settings.langfuse_enabled

# Models costs per 1M tokens input/output:
# gpt 5: 1.25/10
# gpt 5 mini: 0.25/2
# gpt 5 nano: 0.05/0.4


def apply_if(decorator, condition):
    """Apply decorator only if condition is True"""
    return decorator if condition else lambda f: f


# Available models
type Model = Literal["fast", "smart"]

@apply_if(observe, LANGFUSE_ENABLED)
def ask_llm(message: str, model: Model = "fast") -> str:
    model_id = settings.azure_openai_model_fast if model == "fast" else settings.azure_openai_model_smart
    response = llm.chat.completions.create(
        messages=[
            { "role": "system", "content": "Do not include any reasoning in your response." },
            { "role": "user", "content": message }
        ],
        model=model_id
    )

    return response.choices[0].message.content

# Configure telemetry to debug model behavior and monitor usage
if LANGFUSE_ENABLED:
    langfuse = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host
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
      model_id=settings.azure_openai_model_fast,
      azure_endpoint=settings.azure_openai_endpoint,
      api_key=settings.azure_openai_api_key,
      api_version=settings.azure_openai_api_version
)

llm = model.create_client()