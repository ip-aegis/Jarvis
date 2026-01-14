import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
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


@dataclass
class UsageData:
    """Token usage data from OpenAI API response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
        }


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.embedding_model = settings.openai_embedding_model

    def _extract_usage(self, response, model: str) -> UsageData:
        """Extract usage data from API response."""
        usage = response.usage
        return UsageData(
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
            model=response.model or model,
        )

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

    async def chat_with_usage(
        self,
        messages: list[dict[str, str]],
        tools: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> tuple[str, UsageData]:
        """Send a chat request and return response with usage data."""
        kwargs = {
            "model": model or self.model,
            "messages": messages,
        }

        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        usage = self._extract_usage(response, kwargs["model"])

        return content, usage

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

    async def chat_stream_with_usage(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        usage_callback: Optional[callable] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response with usage tracking.

        Usage is passed to callback after streaming completes.
        """
        used_model = model or self.model
        kwargs = {
            "model": used_model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        response = await self.client.chat.completions.create(**kwargs)
        usage_data = None

        async for chunk in response:
            # Check for usage in final chunk
            if hasattr(chunk, "usage") and chunk.usage is not None:
                usage_data = UsageData(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    model=used_model,
                )

            # Yield content chunks
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

        # Call usage callback after streaming completes
        if usage_callback and usage_data:
            usage_callback(usage_data)

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

    async def chat_with_tools_and_usage(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        tool_executor: callable,
        model: Optional[str] = None,
    ) -> tuple[str, UsageData, int]:
        """
        Chat with tool calling support and usage tracking.

        Returns:
            tuple of (content, usage_data, tool_calls_count)
        """
        used_model = model or self.model
        kwargs = {
            "model": used_model,
            "messages": messages,
            "tools": tools,
        }

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Track cumulative usage
        total_prompt = response.usage.prompt_tokens if response.usage else 0
        total_completion = response.usage.completion_tokens if response.usage else 0
        tool_calls_count = 0

        # Check if there are tool calls
        if message.tool_calls:
            tool_calls_count = len(message.tool_calls)

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

            # Get final response after tool execution
            content, final_usage = await self.chat_with_usage(messages, tools, model)

            # Combine usage from both calls
            total_prompt += final_usage.prompt_tokens
            total_completion += final_usage.completion_tokens

            usage = UsageData(
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_tokens=total_prompt + total_completion,
                model=final_usage.model,
            )

            return content, usage, tool_calls_count

        # No tool calls
        usage = UsageData(
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
            model=response.model or used_model,
        )

        return message.content or "", usage, 0

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

    async def chat_with_tools_stream_with_usage(
        self,
        messages: list[dict[str, str]],
        tools: list[dict],
        tool_executor: callable,
        model: Optional[str] = None,
        usage_callback: Optional[callable] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Chat with tool calling support, streaming the final response, with usage tracking.

        Usage is accumulated across tool calls and passed to callback after completion.
        Returns: (tool_calls_count) via the callback's second argument.
        """
        used_model = model or self.model
        kwargs = {
            "model": used_model,
            "messages": messages,
            "tools": tools,
        }

        response = await self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        # Track cumulative usage
        total_prompt = response.usage.prompt_tokens if response.usage else 0
        total_completion = response.usage.completion_tokens if response.usage else 0
        tool_calls_count = 0

        # Check if there are tool calls
        if message.tool_calls:
            tool_calls_count = len(message.tool_calls)

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

            # Track usage from the streaming response
            streaming_usage = None

            def capture_streaming_usage(usage_data: UsageData):
                nonlocal streaming_usage
                streaming_usage = usage_data

            # Stream the final response with usage tracking
            async for chunk in self.chat_stream_with_usage(
                messages, model=model, usage_callback=capture_streaming_usage
            ):
                yield chunk

            # Combine usage
            if streaming_usage:
                total_prompt += streaming_usage.prompt_tokens
                total_completion += streaming_usage.completion_tokens
        else:
            # No tools called, yield the content
            if message.content:
                yield message.content

        # Call usage callback with combined totals
        if usage_callback:
            combined_usage = UsageData(
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_tokens=total_prompt + total_completion,
                model=response.model or used_model,
            )
            usage_callback(combined_usage, tool_calls_count)

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

    async def generate_embedding_with_usage(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> tuple[list[float], UsageData]:
        """Generate an embedding vector with usage tracking."""
        used_model = model or self.embedding_model
        response = await self.client.embeddings.create(
            model=used_model,
            input=text,
        )
        usage = UsageData(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=0,  # Embeddings don't have completion tokens
            total_tokens=response.usage.total_tokens if response.usage else 0,
            model=response.model or used_model,
        )
        return response.data[0].embedding, usage

    async def generate_embeddings_with_usage(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> tuple[list[list[float]], UsageData]:
        """Generate embedding vectors with usage tracking."""
        used_model = model or self.embedding_model
        response = await self.client.embeddings.create(
            model=used_model,
            input=texts,
        )
        usage = UsageData(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=0,
            total_tokens=response.usage.total_tokens if response.usage else 0,
            model=response.model or used_model,
        )
        return [item.embedding for item in response.data], usage

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
