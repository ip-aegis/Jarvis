import httpx
import json
from typing import List, Dict, Any, AsyncGenerator, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class OllamaService:
    """Service for interacting with Ollama LLM."""

    def __init__(self):
        self.base_url = settings.ollama_url
        self.model = settings.ollama_model
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=lambda retry_state: logger.warning(
            "ollama_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        model: Optional[str] = None,
    ) -> str:
        """Send a chat request and get a complete response."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model or self.model,
                "messages": messages,
                "stream": False,
            }

            if tools:
                payload["tools"] = tools

            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return data.get("message", {}).get("content", "")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Send a chat request and stream the response."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": model or self.model,
                "messages": messages,
                "stream": True,
            }

            if tools:
                payload["tools"] = tools

            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        tool_executor: callable,
    ) -> str:
        """
        Chat with tool calling support.
        Handles tool calls and executes them via the provided executor.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "tools": tools,
            }

            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})

            # Check if there are tool calls
            tool_calls = message.get("tool_calls", [])

            if tool_calls:
                # Execute each tool call
                tool_results = []
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    name = function.get("name")
                    arguments = function.get("arguments", {})

                    # Execute the tool
                    result = await tool_executor(name, arguments)
                    tool_results.append({
                        "role": "tool",
                        "content": json.dumps(result),
                    })

                # Add tool results to messages and get final response
                messages.extend([message, *tool_results])
                return await self.chat(messages, tools)

            return message.get("content", "")

    async def generate(self, prompt: str) -> str:
        """Simple text generation without chat format."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "")

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models on the Ollama server."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json().get("models", [])

    async def health_check(self) -> bool:
        """Check if Ollama server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
