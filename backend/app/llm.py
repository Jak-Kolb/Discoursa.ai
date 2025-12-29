from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Dict
import json

from google import genai
from google.genai.types import HarmCategory, HarmBlockThreshold, Content, Part, GenerateContentConfig

from .retrieval import RetrievedContext, formatContext

PROMPT_DIR = Path(__file__).parent / "prompts"
DEFAULT_MODEL = "gemini-2.0-flash-exp"
logger = logging.getLogger(__name__)


def _loadPrompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


@dataclass
class LLMMessage:
    role: str
    content: str


class DebateLLM:
    """Abstraction for Google Gemini LLM interaction using google-genai SDK."""

    def __init__(self, *, model_name: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.antisycophancy_prompt = _loadPrompt("system_antisycophancy.txt")
        self.guardrails_prompt = _loadPrompt("system_factuality_guardrails.txt")
        self.model_name = model_name or os.getenv("MODEL_NAME") or DEFAULT_MODEL
        
        # Configure the API key
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        if not self.api_key:
            logger.warning("No Gemini API key found. LLM features disabled.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def _get_config(self, system_instruction: Optional[str] = None) -> GenerateContentConfig:
        """Returns a configuration object."""
        # Safety settings
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]
        
        return GenerateContentConfig(
            system_instruction=system_instruction,
            safety_settings=safety_settings,
            temperature=1.0, # Default temperature
        )

    def generate_tweet_reply(self, history: List[LLMMessage], topic: str) -> str:
        if not self.client:
            return "I'm ready to debate! (Mock response - API key missing)"

        system_prompt = (
            "You are Discoursa, a sharp, witty debate bot. "
            "Your goal is to politely but effectively dismantle the user's argument. "
            "CONSTRAINT: Your response MUST be under 280 characters. "
            "Do not use hashtags. Be direct."
        )

        gemini_history = self._map_history_to_gemini(history)
        
        # If history is empty, use topic as prompt
        current_message = f"Debate this topic: {topic}"
        
        # If history exists, the last user message needs to be extracted as the prompt
        if gemini_history and gemini_history[-1]["role"] == "user":
            current_message = gemini_history.pop()["parts"][0]["text"]

        try:
            config = self._get_config(system_instruction=system_prompt)
            # Create a chat session with the previous history (excluding current message)
            chat = self.client.chats.create(
                model=self.model_name,
                config=config,
                history=gemini_history
            )
            
            response = chat.send_message(current_message)
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "I have nothing to say right now."

    def buildSystemPrompt(self) -> str:
        prompts = [self.antisycophancy_prompt, self.guardrails_prompt]
        return "\n\n".join([p for p in prompts if p])

    def generateSubtopics(self, topic: str) -> List[str]:
        if not self.client:
            return []

        try:
            prompt = (
                f"List 5 relevant subtopics for a debate on '{topic}'. "
                "Return only the subtopics as a numbered list."
            )
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            content = response.text
            if content:
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                subtopics = []
                for line in lines:
                    parts = line.split(".", 1)
                    if len(parts) > 1:
                        subtopics.append(parts[1].strip())
                    else:
                        subtopics.append(line)
                return subtopics[:5]
        except Exception as exc:
            logger.exception("LLM subtopic generation failed: %s", exc)

        return []

    def generateReply(
        self,
        *,
        topic: str,
        user_stance: str,
        user_message: str,
        context: Iterable[RetrievedContext],
        history: List[LLMMessage],
        context_bundle: Optional[str] = None,
        temperature: float = 1,
    ) -> str:
        if not self.client:
             return "Failed to get an answer from API: Gemini API key not found."

        context_items = list(context)
        if context_bundle is None:
            context_bundle, _ = formatContext(context_items)

        # Build System Instructions
        system_instruction = self.buildSystemPrompt()
        
        # Add dynamic instructions
        dynamic_instruction = (
            "You are a professional debater tasked with arguing against the user. "
            f"The topic is '{topic}'. The user's stance is: '{user_stance}'. "
            "Your goal is to adopt and maintain the OPPOSITE stance throughout the entire conversation. "
            "Never agree with the user. "
            "Construct compelling counter-arguments using the provided evidence where relevant. "
            "In your opening statement, clearly define the opposing position you will be defending. "
            "Integrate evidence naturally into your argument without explicitly citing filenames or chunk IDs. "
            "Review the conversation history to avoid repeating arguments or evidence. "
            "Directly address the user's latest point. "
            "Open the debate naturally by countering the user's stance."
            "Be concise yet persuasive in your responses. Your response length is somewhat up to your discretion based on what the user prompts you with."
            "While length is somewhat up to your discretion, you MUST keep responses between around 25 and 150 words."
        )
        
        if context_bundle:
            dynamic_instruction += f"\n\nRetrieved evidence you can use:\n{context_bundle}"
        else:
            dynamic_instruction += "\n\nNo supporting documents were retrieved. Flag uncertainty when making claims that are not grounded."

        full_system_instruction = f"{system_instruction}\n\n{dynamic_instruction}"

        # Setup Chat History
        gemini_history = self._map_history_to_gemini(history)
        
        # Extract the current message from history if it's there
        current_message = user_message
        if gemini_history and gemini_history[-1]["role"] == "user":
            # Check overlap to avoid duplication or missed context
            last_text = gemini_history[-1]["parts"][0]["text"]
            if last_text == user_message:
                gemini_history.pop()

        try:
            config = self._get_config(system_instruction=full_system_instruction)
            config.temperature = temperature
            
            chat = self.client.chats.create(
                model=self.model_name,
                config=config,
                history=gemini_history
            )
            
            response = chat.send_message(current_message)
            return response.text.strip()

        except Exception as exc:
            logger.exception("LLM request failed: %s", exc)
            return f"Failed to get an answer from API: {exc}"

    def _map_history_to_gemini(self, history: List[LLMMessage]) -> List[Dict]:
        """Maps LLMMessage history to google-genai history format."""
        gemini_history = []
        for msg in history:
            role = "model" if msg.role == "assistant" else "user"
            gemini_history.append({
                "role": role, 
                "parts": [{"text": msg.content}]
            })
        return gemini_history

    def oppositionConsistent(self, reply: str, user_stance: str) -> bool:
        stance_tokens = set(user_stance.lower().split())
        matches = sum(1 for token in stance_tokens if token in reply.lower())
        return matches < max(1, len(stance_tokens))

    def detectHallucinations(self, reply: str, context: Iterable[RetrievedContext]) -> List[str]:
        if any(context):
            return []
        return ["No supporting documents found; treat claims as ungrounded."]
