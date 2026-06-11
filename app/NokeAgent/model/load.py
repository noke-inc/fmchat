from langchain_aws import ChatBedrock
from config import BEDROCK_MODEL_ID, BEDROCK_REGION


def load_model() -> ChatBedrock:
    """Return a ChatBedrock client using IAM credentials from the runtime environment."""
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=BEDROCK_REGION,
        model_kwargs={"temperature": 0, "max_tokens": 2048},
    )
