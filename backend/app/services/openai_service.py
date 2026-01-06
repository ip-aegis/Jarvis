import json
from collections.abc import AsyncGenerator
from typing import Any, Optional

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.embedding_model = settings.openai_embedding_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            "openai_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> str:
        """Send a chat request and get a complete response."""
        kwargs = {
            "model": model or self.model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Send a chat request and stream the response."""
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "stream": True,
        }

        # Note: When streaming with tools, we don't include tools
        # as the response handling becomes complex

        response = await self.client.chat.completions.create(**kwargs)

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        tool_executor: callable,
        model: Optional[str] = None,
    ) -> str:
        """
        Chat with tool calling support.
        Handles tool calls and executes them via the provided executor.
        """
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "tools": tools,
        }

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Check if there are tool calls
        if message.tool_calls:
            # Add assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            # Execute each tool call
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # Execute the tool
                result = await tool_executor(name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            # Get final response after tool execution
            return await self.chat(messages, tools, model)

        return message.content or ""

    async def chat_with_tools_stream(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        tool_executor: callable,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Chat with tool calling support, streaming the final response.
        Handles tool calls first, then streams the final answer.
        """
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "tools": tools,
        }

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Check if there are tool calls
        if message.tool_calls:
            # Add assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            # Execute each tool call
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                result = await tool_executor(name, arguments)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            # Stream the final response
            async for chunk in self.chat_stream(messages, model=model):
                yield chunk
        else:
            # No tools called, yield the content
            if message.content:
                yield message.content

    async def generate_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> list[float]:
        """Generate an embedding vector for the given text."""
        response = await self.client.embeddings.create(
            model=model or self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def generate_embeddings(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""
        response = await self.client.embeddings.create(
            model=model or self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def health_check(self) -> bool:
        """Check if OpenAI API is reachable."""
        try:
            # Simple model list call to verify API key works
            await self.client.models.list()
            return True
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """List available models."""
        try:
            models = await self.client.models.list()
            return [
                {
                    "name": m.id,
                    "created": m.created,
                    "owned_by": m.owned_by,
                }
                for m in models.data
                if "gpt" in m.id or "text-embedding" in m.id
            ]
        except Exception as e:
            logger.error("list_models_failed", error=str(e))
            return []
