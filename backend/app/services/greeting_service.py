import re
from datetime import datetime
from typing import Optional


class GreetingService:
    """
    Independent service for detecting pure greetings and casual conversational messages.
    Ensures greeting-only messages receive friendly predefined responses without
    invoking ChromaDB, embeddings, or LLM RAG pipelines.
    """

    MORNING_PATTERNS = {
        "good morning",
        "good morning to you",
        "happy morning",
        "morning",
        "very good morning",
        "gm",
    }

    AFTERNOON_PATTERNS = {
        "good afternoon",
        "good afternoon to you",
        "happy afternoon",
        "afternoon",
        "very good afternoon",
        "good day",
    }

    EVENING_PATTERNS = {
        "good evening",
        "good evening to you",
        "happy evening",
        "evening",
        "very good evening",
    }

    NIGHT_PATTERNS = {
        "good night",
        "good night to you",
        "have a good night",
        "night",
        "night night",
        "sweet dreams",
        "gn",
    }

    GENERAL_GREETING_WORDS = {
        "hi",
        "hii",
        "hiii",
        "hiiii",
        "hello",
        "helloo",
        "hellooo",
        "hey",
        "heyy",
        "heyyy",
        "greetings",
        "hi there",
        "hello there",
        "hey there",
        "hola",
        "namaste",
    }

    CASUAL_STATUS_PATTERNS = {
        "how are you",
        "how are you doing",
        "how are you today",
        "how r u",
        "how are u",
        "hows it going",
        "how is it going",
        "how do you do",
        "hope you are doing well",
        "hows your day",
        "how is your day",
        "hows your day going",
        "how is your day going",
        "how have you been",
    }

    IDENTITY_PATTERNS = {
        "who are you",
        "who are u",
        "who r u",
        "what are you",
        "what is your name",
        "whats your name",
        "what do you do",
        "what can you do",
        "tell me about yourself",
        "introduce yourself",
        "who created you",
        "who made you",
    }

    # -------------------------------------------------------------------
    # Time helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _get_current_period() -> str:
        """
        Return the time-of-day period based on the current local hour.
        Periods:
            'morning'   -> 05:00 – 11:59
            'afternoon' -> 12:00 – 16:59
            'evening'   -> 17:00 – 20:59
            'night'     -> 21:00 – 04:59
        """
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    @staticmethod
    def _period_response(period: str) -> str:
        """Return the canonical greeting response for a given period."""
        mapping = {
            "morning": "Good morning! How can I help you today?",
            "afternoon": "Good afternoon! How can I help you today?",
            "evening": "Good evening! How can I help you today?",
            "night": "Good night! Take care and have a restful night.",
        }
        return mapping[period]

    @staticmethod
    def _period_prefix(period: str) -> str:
        """Return the short greeting prefix for a given period."""
        mapping = {
            "morning": "Good morning!",
            "afternoon": "Good afternoon!",
            "evening": "Good evening!",
            "night": "Good night!",
        }
        return mapping[period]

    def _validate_timed_greeting(
        self, intended_period: str, full_response: str, prefix: str | None = None
    ) -> str | tuple[str, str] | None:
        """
        Validate a time-specific greeting the user sent.

        If the intended period matches the current time → return `full_response` as-is.
        If it does NOT match → gently correct the user with the right greeting.

        When `prefix` is supplied (for detect_greeting_prefix), returns a corrected prefix.
        """
        current = self._get_current_period()
        if intended_period == current:
            if prefix is not None:
                return prefix
            return full_response

        # Build a polite correction message
        correct_response = self._period_response(current)
        correction = (
            f"It's actually {current} now! {correct_response}"
        )
        if prefix is not None:
            # For prefix mode, return corrected prefix string
            return self._period_prefix(current)
        return correction

    # -------------------------------------------------------------------

    @staticmethod
    def normalize_message(text: str) -> str:
        """
        Normalize text:
        - Lowercase
        - Remove emojis, punctuation, and symbols
        - Collapse multiple spaces
        - Strip whitespace
        """
        if not text:
            return ""
        # Lowercase
        lower = text.lower().strip()
        # Remove punctuation and special characters, keep alphanumeric and spaces
        cleaned = re.sub(r"[^\w\s]", " ", lower)
        # Collapse multiple spaces into single space
        normalized = re.sub(r"\s+", " ", cleaned).strip()
        return normalized

    def detect_greeting(self, message: str) -> Optional[str]:
        """
        Detect if a message is ONLY a greeting or casual conversational message.
        If it contains a question or topic (e.g. 'Good morning, what is diabetes?'),
        returns None so it proceeds to the full RAG retrieval pipeline.
        """
        norm = self.normalize_message(message)
        if not norm:
            return None

        # Check Night first (since 'good night' contains 'night' and is distinct)
        if norm in self.NIGHT_PATTERNS:
            return self._validate_timed_greeting(
                "night", "Good night! Take care and have a restful night."
            )

        # Check Morning
        if norm in self.MORNING_PATTERNS:
            return self._validate_timed_greeting(
                "morning", "Good morning! How can I help you today?"
            )

        # Check Afternoon
        if norm in self.AFTERNOON_PATTERNS:
            return self._validate_timed_greeting(
                "afternoon", "Good afternoon! How can I help you today?"
            )

        # Check Evening
        if norm in self.EVENING_PATTERNS:
            return self._validate_timed_greeting(
                "evening", "Good evening! How can I help you today?"
            )

        # Check General Greetings (Hi, Hello, Hey, Hii, etc.)
        if norm in self.GENERAL_GREETING_WORDS:
            return "Hello! How can I help you today?"

        # Regex check for variations like 'hiiiii' or 'heyyyy'
        if re.fullmatch(r"^h+[ie]+y*$", norm) or re.fullmatch(r"^h+e+l+o+$", norm):
            return "Hello! How can I help you today?"

        # Check Casual Status ("How are you?", "How are you doing?")
        if norm in self.CASUAL_STATUS_PATTERNS:
            return "I'm doing well, thank you! How can I help you today?"

        # Check Identity ("Who are you?", "What is your name?")
        if norm in self.IDENTITY_PATTERNS:
            return (
                "I am Research Bot, your AI research assistant. "
                "I can help you search, analyze, and answer questions from your uploaded research papers. "
                "How can I assist you today?"
            )

        # If it's a combination (e.g. 'Hi how are you'), check if it only consists of greetings/status
        tokens = norm.split()
        if len(tokens) <= 6:
            # Check combinations like "hi good morning", "hello good afternoon", "hi how are you"
            rest = " ".join(tokens[1:])
            if tokens[0] in self.GENERAL_GREETING_WORDS and (
                rest in self.MORNING_PATTERNS
                or rest in self.AFTERNOON_PATTERNS
                or rest in self.EVENING_PATTERNS
                or rest in self.NIGHT_PATTERNS
                or rest in self.CASUAL_STATUS_PATTERNS
                or rest in self.IDENTITY_PATTERNS
                or rest in self.GENERAL_GREETING_WORDS
            ):
                if "morning" in norm:
                    return self._validate_timed_greeting(
                        "morning", "Good morning! How can I help you today?"
                    )
                if "afternoon" in norm or "day" in norm:
                    return self._validate_timed_greeting(
                        "afternoon", "Good afternoon! How can I help you today?"
                    )
                if "evening" in norm:
                    return self._validate_timed_greeting(
                        "evening", "Good evening! How can I help you today?"
                    )
                if "night" in norm:
                    return self._validate_timed_greeting(
                        "night", "Good night! Take care and have a restful night."
                    )
                return "Hello! I'm doing well, thank you! How can I help you today?"

        return None

    def detect_greeting_prefix(self, message: str) -> tuple[str | None, str]:
        """
        For mixed messages like "Good morning, what is diabetes?",
        detect if the message *starts* with a greeting followed by actual content.

        Returns:
            (prefix, cleaned_question) where prefix is e.g. "Good morning!"
            and cleaned_question is the remainder (the actual query).
            If no greeting prefix is detected, prefix is None and cleaned_question
            is the original message.
        """
        norm = self.normalize_message(message)
        if not norm:
            return None, message

        # Map of greeting pattern sets to their canonical prefix responses
        timed_sets = [
            (self.NIGHT_PATTERNS, "Good night!", "night"),
            (self.MORNING_PATTERNS, "Good morning!", "morning"),
            (self.AFTERNOON_PATTERNS, "Good afternoon!", "afternoon"),
            (self.EVENING_PATTERNS, "Good evening!", "evening"),
            (self.GENERAL_GREETING_WORDS, "Hello!", None),
        ]

        for pattern_set, prefix, period in timed_sets:
            for pattern in sorted(pattern_set, key=len, reverse=True):
                if norm.startswith(pattern):
                    remainder = norm[len(pattern):].strip(" ,;:-")
                    # Only treat as a prefix if there's meaningful content after
                    if remainder and len(remainder.split()) >= 2:
                        if period is not None:
                            prefix = self._validate_timed_greeting(period, prefix, prefix)
                        return prefix, remainder

        return None, message


greeting_service = GreetingService()
detect_greeting = greeting_service.detect_greeting
detect_greeting_prefix = greeting_service.detect_greeting_prefix
