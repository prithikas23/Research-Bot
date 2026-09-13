import logging
from abc import ABC, abstractmethod
import httpx
from app.core.config import settings
from app.services.greeting_service import detect_greeting

logger = logging.getLogger(__name__)

GROUNDED_SYSTEM_PROMPT = (
    "You are Research Bot, a dedicated AI research paper assistant.\n\n"
    "IDENTITY & CONVERSATIONAL RULES:\n"
    "- Your name is always Research Bot. Never assume the identity of any author, student, researcher, or person mentioned in the uploaded documents.\n"
    "- If the user asks who you are or what your name is, introduce yourself as Research Bot.\n"
    "- If the user's message begins with a greeting followed by a research question (e.g., 'Good morning, what is diabetes?' or 'Hi, explain cardiovascular disease.'), acknowledge the greeting naturally (e.g., 'Good morning! ...' or 'Hello! ...') and then answer the research question strictly using the supplied research context.\n\n"
    "GROUNDED ANSWERING RULES:\n"
    "- Answer the user's research questions using only the supplied research-paper context.\n"
    "- Do not invent facts, citations, paper titles, page numbers, or sources.\n"
    "- If the supplied context does not contain enough information to answer a research question, say:\n"
    "\"I could not find sufficient information about this in the uploaded research papers.\"\n"
    "- Be concise, clear, and informative.\n"
    "- Use the conversation history only to understand the user's question.\n"
    "- Do not use unsupported external knowledge."
)


def check_greeting_or_identity(query: str) -> str | None:
    """Delegate to modular greeting_service."""
    return detect_greeting(query)


class BaseLLMService(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_answer(
        self,
        query: str,
        context_chunks: list[str],
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a grounded answer given query, context, and conversation history."""
        pass


class GroqLLMService(BaseLLMService):
    """
    Groq LLM provider implementation with conversation history and grounded prompting.
    Includes automated fallback to working models if the configured model is decommissioned.
    """

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.primary_model = settings.GROQ_CHAT_MODEL
        self.fallback_models = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "groq/compound-mini"]
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def build_messages(
        self,
        query: str,
        context_chunks: list[str],
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        messages = [{"role": "system", "content": GROUNDED_SYSTEM_PROMPT}]

        # Append recent conversation history if provided (e.g. prior turns)
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = turn.get("role")
                content = turn.get("content")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # Format retrieved research context
        if context_chunks:
            formatted_context = "\n\n---\n\n".join(
                f"[Source Chunk {i + 1}]:\n{chunk}"
                for i, chunk in enumerate(context_chunks)
            )
            user_content = (
                f"Supplied Research-Paper Context:\n{formatted_context}\n\n"
                f"User Question: {query}\n\n"
                f"Answer strictly using only the above research-paper context:"
            )
        else:
            user_content = (
                f"No research-paper context was found for this query.\n\n"
                f"User Question: {query}"
            )

        messages.append({"role": "user", "content": user_content})
        return messages

    def check_greeting_or_identity(self, query: str) -> str | None:
        return detect_greeting(query)

    def generate_answer(
        self,
        query: str,
        context_chunks: list[str],
        conversation_history: list[dict] | None = None,
    ) -> str:
        # Check greetings and identity questions first
        preset = self.check_greeting_or_identity(query)
        if preset:
            return preset

        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        # If no research context is retrieved at all, return the prompt's mandated refusal directly
        if not context_chunks:
            return "I could not find sufficient information about this in the uploaded research papers."

        messages = self.build_messages(query, context_chunks, conversation_history)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Attempt with active/working model first, fall back if model_not_found
        preferred_model = getattr(self, "_active_model", self.primary_model)
        models_to_try = [preferred_model] + [m for m in self.fallback_models if m != preferred_model]

        with httpx.Client(timeout=45.0) as client:
            last_error = None
            for model in models_to_try:
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.1,
                }
                try:
                    response = client.post(self.base_url, headers=headers, json=payload)
                    if response.status_code == 200:
                        self._active_model = model
                        data = response.json()
                        raw_answer = data["choices"][0]["message"]["content"]
                        # Strip thinking tags if generated by reasoning models
                        if "</think>" in raw_answer:
                            raw_answer = raw_answer.split("</think>")[-1].strip()
                        return raw_answer.strip()
                    elif response.status_code in (400, 404):
                        err_text = response.text
                        logger.warning(f"Groq model '{model}' unavailable ({response.status_code}): {err_text}. Trying fallback...")
                        last_error = Exception(f"Model {model} failed: {err_text}")
                        continue
                    else:
                        response.raise_for_status()
                except Exception as e:
                    last_error = e
                    logger.warning(f"Error calling Groq with model {model}: {e}")
                    continue

            if last_error:
                raise last_error
            raise RuntimeError("All Groq model attempts failed.")


def get_llm_service() -> BaseLLMService:
    return GroqLLMService()


llm_service = get_llm_service()
