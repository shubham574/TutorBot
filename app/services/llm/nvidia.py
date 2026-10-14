"""NVIDIA NIM LLM Client implementation using OpenAI-compatible API."""
import base64
import json
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from app.config.settings import settings
from app.config.logging_config import logger
from app.services.llm.base import BaseLLMClient

T = TypeVar("T", bound=BaseModel)

DEFAULT_VISION_MODEL = "meta/llama-3.2-11b-vision-instruct"


class NvidiaLLMClient(BaseLLMClient):
    """Client for NVIDIA NIM LLMs supporting text, vision, and structured JSON parsing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.NVIDIA_API_KEY or "dummy_key"
        self.base_url = base_url or settings.NVIDIA_BASE_URL
        self.default_model = default_model or DEFAULT_VISION_MODEL
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        chosen_model = model or self.default_model
        kwargs: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def extract_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> T:
        """
        Extracts structured JSON conforming strictly to schema_class.
        Includes automatic retry if validation fails.
        """
        chosen_model = model or self.default_model

        sys_instruction = system_prompt or (
            "You are an expert academic curriculum parser. "
            "Extract the curriculum data from the user's input and return a valid JSON object.\n"
            "Required top-level keys in your JSON object:\n"
            "- subject: string (e.g. 'Physics')\n"
            "- target_exam: string or null (e.g. 'CBSE Class 12')\n"
            "- exam_date: string (YYYY-MM-DD) or null\n"
            "- units: array of objects with keys 'title' (string), 'marks_weightage' (number or null), "
            "and 'topics' (array of objects with keys 'title', 'estimated_minutes', 'subtopics')\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Do NOT output a JSON schema, $defs, or definitions.\n"
            "2. Output the actual extracted syllabus data filled into the JSON object.\n"
            "3. Return ONLY valid JSON, with no markdown code fences or conversational text."
        )

        messages = [
            {"role": "system", "content": sys_instruction},
            {"role": "user", "content": prompt},
        ]

        # First attempt with json_object format
        raw_output = await self.chat_completion(
            messages=messages,
            model=chosen_model,
            max_tokens=2500,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        try:
            cleaned_json = self._extract_json_string(raw_output)
            return schema_class.model_validate_json(cleaned_json)
        except (json.JSONDecodeError, ValidationError) as err:
            logger.warning(
                "Initial structured extraction failed, attempting 1 retry with error feedback",
                error=str(err),
            )
            # Retry with error feedback
            retry_messages = messages + [
                {"role": "assistant", "content": raw_output},
                {
                    "role": "user",
                    "content": (
                        f"The output failed validation with error: {str(err)}. "
                        "Please correct the output and return ONLY the valid JSON object with the actual extracted data."
                    ),
                },
            ]
            retry_output = await self.chat_completion(
                messages=retry_messages,
                model=chosen_model,
                max_tokens=2500,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            cleaned_json = self._extract_json_string(retry_output)
            return schema_class.model_validate_json(cleaned_json)

    async def extract_from_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        model: Optional[str] = None,
    ) -> str:
        """Uses vision LLM to extract text and details from an image."""
        chosen_model = model or DEFAULT_VISION_MODEL
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:{mime_type};base64,{b64_image}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        response = await self.client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            max_tokens=2000,
            temperature=0.1,
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def _extract_json_string(text: str) -> str:
        """Extracts JSON substring from LLM response, stripping markdown code fences."""
        cleaned = text.strip()
        # Look for ```json ... ```
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            return match.group(1).strip()
        # Look for { ... } or [ ... ]
        first_bracket = cleaned.find("{")
        last_bracket = cleaned.rfind("}")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            return cleaned[first_bracket : last_bracket + 1].strip()
        return cleaned


llm_client = NvidiaLLMClient()
