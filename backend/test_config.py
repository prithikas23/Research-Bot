import sys
from app.core.config import settings


def test_configuration():
    # Verify non-secret values
    print(f"Application: {settings.APP_NAME}")
    print(f"Environment: {settings.APP_ENV}")
    print(f"Chroma path: {settings.CHROMA_PATH}")
    print(f"Chroma collection: {settings.CHROMA_COLLECTION}")
    print(f"Embedding provider: {settings.EMBEDDING_PROVIDER}")
    print(f"Embedding model: {settings.HF_EMBEDDING_MODEL}")

    llm_provider = "Groq" if settings.GROQ_API_KEY else "None"
    print(f"LLM provider: {llm_provider}")
    print(f"Frontend URL: {settings.FRONTEND_URL}")

    # Validate that required secrets are present without printing their values
    assert settings.DATABASE_URL, "DATABASE_URL must be configured"
    assert settings.GROQ_API_KEY, "GROQ_API_KEY must be configured"
    assert settings.GROQ_API_KEY.startswith("gsk_"), "GROQ_API_KEY should start with 'gsk_'"
    assert not settings.OPENAI_API_KEY.startswith("gsk_"), "OPENAI_API_KEY must not contain Groq key"


if __name__ == "__main__":
    try:
        test_configuration()
        print("Configuration validation passed.")
    except AssertionError as e:
        print(f"Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)
