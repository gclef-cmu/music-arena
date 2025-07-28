# Music Arena

Music Arena is a platform for comparing text-to-music generation systems in a battle format. Users can generate music from text prompts and vote on their preferences to create leaderboards. See our [paper](https://arxiv.org) for more details.

## Quick Start

1. **Install the package**:

```bash
git clone https://github.com/gclef-cmu/music-arena
cd music-arena
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. **Generate music from a system** (requires [Docker](https://docs.docker.com/get-started)):

```bash
ma-sys musicgen-small:initial generate --prompt "upbeat electronic music" --gpu 0
```

3. **Start a local version of the Arena**:

```bash
ma-deploy dev --tmux | bash
tmux attach-session -t MUSIC-ARENA-DEV
```

## Adding a New Model

To add a new text-to-music model to the arena:

### 1. Update the Registry

Add your model to `systems/registry.yaml`:

```yaml
your-model-name:
  display_name: "Your Model Name"
  description: "Brief description of your model"
  organization: "Your Organization"
  access: "OPEN"  # or "PROPRIETARY"
  supports_lyrics: false  # or true if it supports lyrics
  # Fields below are optional but strongly encouraged
  model_type: "Codec Language Model"  # or "Latent Diffusion", etc.
  training_data:
    type: "Creative Commons"  # or "Licensed Stock", "Commercial", etc.
    sources:
      - "Your training data sources"
    num_tracks: 100000
    num_hours: 5000
  citation: "Doe+ 25"
  links:
    home: "https://www.your-model.com"
    paper: "https://arxiv.org/abs/your-paper"
    code: "https://github.com/your-repo"
  variants:
    "low_temperature": # Name of a "variant" of your mode
      module_name: "your_model"  # Python module name in systems/
      class_name: "YourModelClass"  # Class name to instantiate
      secrets:  # Optional: if your model needs API keys
        - "HUGGINGFACE_READ_TOKEN"
      init_kwargs:  # Optional: if your model needs additional initialization parameters
        temperature: 0.5
```

### 2. Implement the System Class

Create `systems/your_model.py`:

```python
import logging
from music_arena import (
    Audio,
    DetailedTextToMusicPrompt,
    PromptSupport,
    TextToMusicResponse,
)
from music_arena.system import TextToMusicGPUBatchedSystem

LOGGER = logging.getLogger(__name__)

class YourModelClass(TextToMusicGPUBatchedSystem):
    def __init__(self, gpu_mem_gb_per_item: float = 8.0):
        super().__init__(gpu_mem_gb_per_item=gpu_mem_gb_per_item)
        self._model = None

    def _prepare(self):
        # Load your model here
        self._model = load_your_model()

    def _release(self):
        # Clean up resources
        del self._model

    def prompt_support(self, prompt: DetailedTextToMusicPrompt) -> PromptSupport:
        # Check if your model supports this prompt
        if prompt.duration > 60:  # Example constraint
            return PromptSupport.UNSUPPORTED
        return PromptSupport.SUPPORTED

    def _generate_batch(
        self, prompts: list[DetailedTextToMusicPrompt], seed: int
    ) -> list[TextToMusicResponse]:
        # Generate audio for batch of prompts
        responses = []
        for prompt in prompts:
            # Your generation logic here
            audio_samples = your_generation_function(prompt.overall_prompt)
            audio = Audio(samples=audio_samples, sample_rate=32000)
            responses.append(TextToMusicResponse(audio=audio))
        return responses
```

### 3. Test Your System

Build and test your system:

```bash
# Build the system container
ma-sys your-model:initial build

# Test generation
ma-sys your-model:initial generate --prompt "test prompt" --gpu 0
```

## System Commands

### Generating Music

Generate music from any registered system:

```bash
# Generate from a detailed prompt file (no API key required)
ma-sys sao:quick generate -f example.json -g 0

# Basic generation (requires OpenAI API key to convert text prompt to structured prompt)
ma-sys sao:quick generate -p "heavy metal" -g 0
```

### Serving a System

Start a system as a web service:

```bash
# Serve on default port (calculated from system key)
ma-sys musicgen:small serve --gpu 0

# Serve on custom port
ma-sys musicgen:small serve --port 8080 --gpu 0

# Serve with custom batch settings
ma-sys musicgen:medium serve --max_batch_size 4 --max_delay 2.0 --gpu 0
```

The system will be available at `http://localhost:<port>` with endpoints:
- `GET /health` - Health check
- `POST /generate` - Generate music from prompts

### Testing Systems

Test a running system using the curl client:

```bash
# Test system running on default port
./curl_clients/system.sh musicgen:small io/example.json

# Test system on custom port
./curl_clients/system.sh -p 8080 io/example.json

# Test system on remote host
./curl_clients/system.sh -h myserver.com -p 8080 io/example.json
```

### Testing the Gateway

Test the gateway using the curl client:

```bash
# Test gateway health and generate battles
./curl_clients/gateway.sh -p 9000

# Test specific endpoints
./curl_clients/gateway.sh -p 9000 -e generate_battle
./curl_clients/gateway.sh -p 9000 -e record_vote
```

## Deployment

Deploy the complete arena system:

### Development Deployment

```bash
# Print commands to deploy the development environment
ma-deploy dev

# Print commands to deploy specific components only
ma-deploy dev -c frontend
ma-deploy dev -c gateway
ma-deploy dev -c systems
```

### Custom Deployment

Create your own deployment configuration in `deploy/my-config.yaml`:

```yaml
systems:
  "musicgen:small":
    port: 10000
    args:
      max_batch_size: 2
      max_delay: 3.0
  "sao:initial":
    port: 10001
    gpu: 0

weights:
  "musicgen:small/sao:initial": 1.0

components:
  frontend:
    enabled: true
    port: 8080
    vars:
      GATEWAY_URL: "http://localhost:9000"
  gateway:
    enabled: true
    port: 9000
  systems:
    enabled: true
```

Then deploy:

```bash
ma-deploy my-config
```

## Chat Interface

Test routing and lyrics generation:

### Content Moderation

Check if a prompt is appropriate:

```bash
ma-chat moderate --prompt "generate some music"
ma-chat moderate --config 4o-v00 --prompt "inappropriate content"
```

### Prompt Routing

Test how prompts get routed to different systems:

```bash
# Test routing for a simple prompt
ma-chat route --prompt "classical piano music"

# Test with different routing configuration
ma-chat route --config 4o-v00 --prompt "heavy metal with guitar solos"
```

### Lyrics Generation

Generate lyrics for detailed prompts:

```bash
# Generate lyrics from a detailed prompt file
ma-chat lyrics --prompt_path io/example.json

# Generate with different model configuration
ma-chat lyrics --config 4o-v00 --prompt_path io/example.json
```

## TODO

- Move `music_arena/cli/system-*.py` to `components` for consistency
- Move `ResponseMetadata` to `music_arena/dataclass/response.py` and create in serving container than gateway
- Clean up inconsistency between some classes having `TextToMusic*` prefix and some not
- Make the gateway call System.prompt_supported() instead of System.supports_lyrics
- Change supports_lyrics to instrumental_only?