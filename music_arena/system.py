import abc
import asyncio
import enum
import logging
import random
from typing import AsyncIterator, Generic, Optional, TypeVar

from .dataclass.prompt import BasePrompt, DetailedTextToMusicPrompt
from .dataclass.response import BaseResponse, TextToMusicResponse
from .env import check_gpu_memory_gb

PromptT = TypeVar("PromptT", bound=BasePrompt)
ResponseT = TypeVar("ResponseT", bound=BaseResponse)


class PromptSupport(enum.Enum):
    UNSUPPORTED = "UNSUPPORTED"
    PARTIAL = "PARTIAL"
    SUPPORTED = "SUPPORTED"


class BaseAudioGenerationSystem(Generic[PromptT, ResponseT], abc.ABC):
    def __init__(self):
        self._ready = False

    @property
    def ready(self):
        return self._ready

    def prepare(self):
        if not self._ready:
            self._prepare()
        self._ready = True

    def release(self):
        if self._ready:
            self._release()
        self._ready = False

    def _prepare(self):
        pass

    def _release(self):
        pass

    def prompt_support(self, prompt: PromptT) -> PromptSupport:
        """Check if the prompt is supported by the system."""
        return PromptSupport.SUPPORTED

    @abc.abstractmethod
    async def generate_stream(
        self, prompts: list[PromptT], seed: Optional[int] = None
    ) -> AsyncIterator[ResponseT]:
        """Stream responses as they become available."""
        pass

    def generate(
        self, prompts: list[PromptT] | PromptT, seed: Optional[int] = None
    ) -> list[ResponseT] | ResponseT:
        """User-friendly synchronous interface that collects all responses."""
        self.prepare()
        prompt_list: list[PromptT] = prompts if isinstance(prompts, list) else [prompts]
        if seed is None:
            seed = random.randint(0, 2**32)

        # Collect all responses from the stream
        async def _collect_responses():
            result_list = []
            async for response in self.generate_stream(prompt_list, seed):
                result_list.append(response)
            return result_list

        result_list = asyncio.run(_collect_responses())

        if len(result_list) != len(prompt_list):
            raise AssertionError("Expected same number of results as prompts")
        return result_list if isinstance(prompts, list) else result_list[0]


class TextToMusicSystem(
    BaseAudioGenerationSystem[DetailedTextToMusicPrompt, TextToMusicResponse]
):
    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        """Check if the prompt is supported by the system."""
        return PromptSupport.SUPPORTED


class TextToMusicAPISystem(TextToMusicSystem):
    """System for external API providers."""

    def __init__(self, *args, max_parallelism: Optional[int] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_parallelism = max_parallelism

    @abc.abstractmethod
    async def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        """Generate a single response asynchronously."""
        pass

    async def generate_stream(
        self, prompts: list[DetailedTextToMusicPrompt], seed: Optional[int] = None
    ) -> AsyncIterator[TextToMusicResponse]:
        """Fire off all requests concurrently and yield responses as they complete."""
        if seed is None:
            seed = random.randint(0, 2**32)

        if self.max_parallelism is None:
            # No limit - create tasks for all prompts
            tasks = [
                self._generate_single(prompt, seed + i)
                for i, prompt in enumerate(prompts)
            ]

            # Yield responses as they complete (not necessarily in order)
            for coro in asyncio.as_completed(tasks):
                response = await coro
                yield response
        else:
            # Limit parallelism using semaphore
            semaphore = asyncio.Semaphore(self.max_parallelism)

            async def _generate_with_semaphore(
                prompt: DetailedTextToMusicPrompt, prompt_seed: int
            ):
                async with semaphore:
                    return await self._generate_single(prompt, prompt_seed)

            # Create tasks for all prompts with semaphore
            tasks = [
                _generate_with_semaphore(prompt, seed + i)
                for i, prompt in enumerate(prompts)
            ]

            # Yield responses as they complete (not necessarily in order)
            for coro in asyncio.as_completed(tasks):
                response = await coro
                yield response


class TextToMusicLocalSystem(TextToMusicSystem):
    """System for local batch processing (e.g., GPU-based models)."""

    def __init__(self, max_batch_size: Optional[int] = None):
        super().__init__()
        if max_batch_size is not None and max_batch_size < 1:
            raise ValueError("max_batch_size must be at least 1")
        self.max_batch_size = max_batch_size

    @abc.abstractmethod
    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        """Generate a batch of responses synchronously."""
        pass

    async def generate_stream(
        self, prompts: list[DetailedTextToMusicPrompt], seed: Optional[int] = None
    ) -> AsyncIterator[TextToMusicResponse]:
        """Process in batches and yield responses as each batch completes."""
        if seed is None:
            seed = random.randint(0, 2**32)

        batch_size = self.max_batch_size or len(prompts)

        for i in range(0, len(prompts), batch_size):
            batch_prompts = prompts[i : i + batch_size]
            batch_responses = self._generate_batch(batch_prompts, seed + i)

            # Yield each response in the batch
            for response in batch_responses:
                yield response


class TextToMusicGPUSystem(TextToMusicLocalSystem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, max_batch_size=1, **kwargs)

    @abc.abstractmethod
    def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        pass

    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        assert len(prompts) == 1, "max_batch_size must be 1 for GPU systems"
        return [
            self._generate_single(prompt, seed + i) for i, prompt in enumerate(prompts)
        ]


class TextToMusicGPUBatchedSystem(TextToMusicLocalSystem):
    def __init__(self, *args, gpu_mem_gb_per_item: float = 8.0, **kwargs):
        available_memory = check_gpu_memory_gb()["available"]
        max_batch_size = int(available_memory / gpu_mem_gb_per_item)
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.INFO)
        logger.info(
            f"Available GPU memory: {available_memory} GB, max batch size: {max_batch_size}"
        )
        super().__init__(
            *args,
            max_batch_size=max_batch_size,
            **kwargs,
        )
