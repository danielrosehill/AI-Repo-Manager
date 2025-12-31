"""Model display name mappings for human-readable UI labels."""

# Mapping from API model IDs to human-readable display names
EMBEDDING_MODEL_DISPLAY_NAMES = {
    "google/gemini-embedding-001": "Gemini Embedding",
    "openai/text-embedding-3-small": "OpenAI Embedding Small",
    "openai/text-embedding-3-large": "OpenAI Embedding Large",
    "openai/text-embedding-ada-002": "OpenAI Ada",
    "qwen/qwen3-embedding-8b": "Qwen Embedding",
}

CHAT_MODEL_DISPLAY_NAMES = {
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "google/gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
    "google/gemini-2.0-flash": "Gemini 2.0 Flash",
    "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
    "anthropic/claude-3-haiku": "Claude 3 Haiku",
    "openai/gpt-4o": "GPT-4o",
    "openai/gpt-4o-mini": "GPT-4o Mini",
}


def get_display_name(model_id: str) -> str:
    """Get human-readable display name for a model ID."""
    # Check embedding models first
    if model_id in EMBEDDING_MODEL_DISPLAY_NAMES:
        return EMBEDDING_MODEL_DISPLAY_NAMES[model_id]
    # Check chat models
    if model_id in CHAT_MODEL_DISPLAY_NAMES:
        return CHAT_MODEL_DISPLAY_NAMES[model_id]
    # Fallback: extract last part and clean up
    return model_id.split("/")[-1].replace("-", " ").title()


def get_model_id(display_name: str, model_type: str = "embedding") -> str:
    """Get model ID from display name. Returns display_name if not found."""
    mapping = (
        EMBEDDING_MODEL_DISPLAY_NAMES
        if model_type == "embedding"
        else CHAT_MODEL_DISPLAY_NAMES
    )
    # Reverse lookup
    for model_id, name in mapping.items():
        if name == display_name:
            return model_id
    # Not found, assume it's already a model ID
    return display_name


def get_embedding_models() -> list[tuple[str, str]]:
    """Get list of (model_id, display_name) tuples for embedding models."""
    return list(EMBEDDING_MODEL_DISPLAY_NAMES.items())


def get_chat_models() -> list[tuple[str, str]]:
    """Get list of (model_id, display_name) tuples for chat models."""
    return list(CHAT_MODEL_DISPLAY_NAMES.items())
