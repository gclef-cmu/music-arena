import inspect
import time

import numpy as np
import torch

from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicGPUSystem


class ACEStep15(TextToMusicGPUSystem):
    def __init__(
        self,
        duration: float = 30.0,
        inference_steps: int = 8,
        config_path: str = "acestep-v15-turbo",
        lm_model_path: str | None = "acestep-5Hz-lm-4B",
        lm_backend: str = "pytorch",
        lm_enforce_eager: bool = True,
        create_sample_temperature: float = 0.85,
        create_sample_top_k: int | None = 0,
        create_sample_top_p: float | None = 0.9,
        create_sample_repetition_penalty: float = 1.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._duration = duration
        self._inference_steps = inference_steps
        self._config_path = config_path
        self._lm_model_path = lm_model_path
        self._lm_backend = lm_backend
        self._lm_enforce_eager = lm_enforce_eager
        self._create_sample_temperature = create_sample_temperature
        self._create_sample_top_k = create_sample_top_k
        self._create_sample_top_p = create_sample_top_p
        self._create_sample_repetition_penalty = create_sample_repetition_penalty

        self._dit_handler = None
        self._llm_handler = None
        self._GenerationParams = None
        self._GenerationConfig = None
        self._generate_music = None
        self._create_sample = None

    def _prepare(self):
        from acestep.handler import AceStepHandler
        from acestep.inference import (
            GenerationConfig,
            GenerationParams,
            create_sample,
            generate_music,
        )
        from acestep.llm_inference import LLMHandler
        from acestep.model_downloader import get_checkpoints_dir

        self._GenerationParams = GenerationParams
        self._GenerationConfig = GenerationConfig
        self._generate_music = generate_music
        self._create_sample = create_sample

        self._dit_handler = AceStepHandler()
        status, ok = self._dit_handler.initialize_service(
            project_root="/ace-step-1.5",
            config_path=self._config_path,
            device="cuda",
        )
        if not ok:
            raise RuntimeError(f"ACE-Step 1.5 DiT init failed: {status}")

        self._llm_handler = None
        if self._lm_model_path is not None:
            self._llm_handler = LLMHandler()
            checkpoint_dir = str(get_checkpoints_dir())
            init_kwargs = dict(
                checkpoint_dir=checkpoint_dir,
                lm_model_path=self._lm_model_path,
                backend=self._lm_backend,
                device="cuda",
            )
            # Newer nano-vllm builds may fail CUDA graph capture on some GPUs.
            # If supported by the installed handler, force eager mode to avoid capture.
            if (
                self._lm_backend == "vllm"
                and "enforce_eager"
                in inspect.signature(self._llm_handler.initialize).parameters
            ):
                init_kwargs["enforce_eager"] = self._lm_enforce_eager
            status, ok = self._llm_handler.initialize(**init_kwargs)
            if not ok:
                raise RuntimeError(f"ACE-Step 1.5 LM init failed: {status}")

    def _release(self):
        if self._llm_handler is not None and hasattr(self._llm_handler, "unload"):
            self._llm_handler.unload()
        self._llm_handler = None
        self._dit_handler = None
        torch.cuda.empty_cache()

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        target_duration = prompt.duration if prompt.duration is not None else self._duration
        if target_duration < 10.0 or target_duration > 600.0:
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_single(
        self, prompt: DetailedTextToMusicPrompt, seed: int
    ) -> TextToMusicResponse:
        assert self._dit_handler is not None
        assert self._GenerationParams is not None
        assert self._GenerationConfig is not None
        assert self._generate_music is not None
        assert self._create_sample is not None

        timings: list[tuple[str, float]] = []

        caption = prompt.overall_prompt
        lyrics = prompt.lyrics
        bpm = None
        keyscale = ""
        timesignature = ""
        vocal_language = "unknown"
        sample_duration = None

        if prompt.instrumental:
            lyrics = "[Instrumental]"
        elif lyrics is None:
            if self._llm_handler is None:
                raise RuntimeError(
                    "ACE-Step 1.5 requires the LM to generate lyrics. "
                    "Provide explicit lyrics or initialize with an LM model."
                )
            timings.append(("create_sample", time.time()))
            # Mirror the Gradio Simple mode: convert 0 → None for top_k,
            # and >=1.0 → None for top_p, matching handle_create_sample logic.
            top_k = None if not self._create_sample_top_k else int(self._create_sample_top_k)
            top_p = (
                None
                if not self._create_sample_top_p or self._create_sample_top_p >= 1.0
                else self._create_sample_top_p
            )
            try:
                sample = self._create_sample(
                    llm_handler=self._llm_handler,
                    query=prompt.overall_prompt,
                    instrumental=False,
                    vocal_language='en',
                    temperature=self._create_sample_temperature,
                    top_k=top_k,
                    top_p=top_p,
                    repetition_penalty=self._create_sample_repetition_penalty,
                    use_constrained_decoding=True,
                    constrained_decoding_debug=False,
                )
                if sample.success:
                    caption = sample.caption or caption
                    lyrics = sample.lyrics or ""
                    bpm = sample.bpm
                    keyscale = sample.keyscale or ""
                    timesignature = sample.timesignature or ""
                    vocal_language = sample.language or "unknown"
                    sample_duration = sample.duration
                else:
                    raise RuntimeError(
                        sample.error or "ACE-Step 1.5 create_sample failed"
                    )
            except Exception as exc:  # pragma: no cover - backend/runtime dependent
                raise RuntimeError(
                    f"ACE-Step 1.5 lyric generation failed: {exc}"
                ) from exc

        target_duration = prompt.duration if prompt.duration is not None else self._duration
        if prompt.duration is None and not prompt.instrumental:
            if sample_duration is not None and sample_duration > 0:
                target_duration = sample_duration

        params = self._GenerationParams(
            task_type="text2music",
            caption=caption,
            lyrics=lyrics,
            instrumental=prompt.instrumental,
            bpm=bpm,
            keyscale=keyscale,
            timesignature=timesignature,
            vocal_language=vocal_language,
            duration=target_duration,
            inference_steps=self._inference_steps,
            # Enable CoT thinking whenever the LM is available, matching Simple mode.
            thinking=self._llm_handler is not None,
        )
        config = self._GenerationConfig(
            batch_size=1,
            use_random_seed=False,
            seeds=[seed],
            audio_format="wav",
        )

        timings.append(("generate", time.time()))
        result = self._generate_music(
            self._dit_handler,
            self._llm_handler,
            params,
            config,
            save_dir=None,
        )
        timings.append(("done", time.time()))

        if not result.success or len(result.audios) == 0:
            raise RuntimeError(result.error or "ACE-Step 1.5 generation failed")

        first_audio = result.audios[0]
        sample_rate = int(first_audio.get("sample_rate", 48000))
        samples = first_audio["tensor"]
        if torch.is_tensor(samples):
            samples = samples.detach().cpu().float().numpy()
        samples = np.asarray(samples, dtype=np.float32)

        if samples.ndim == 1:
            samples = samples[:, np.newaxis]
        elif samples.ndim == 2 and samples.shape[0] < samples.shape[1]:
            samples = samples.T
        elif samples.ndim != 2:
            raise ValueError(f"Unexpected audio tensor shape: {samples.shape}")

        audio = Audio(samples=samples, sample_rate=sample_rate)
        if prompt.duration is not None:
            audio = audio.crop(duration=prompt.duration)

        return TextToMusicResponse(
            audio=audio,
            lyrics=None if prompt.instrumental else (lyrics if lyrics else None),
            custom_timings=timings,
        )
