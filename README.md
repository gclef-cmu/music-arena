# Music Arena

Music Arena is a platform for comparing text-to-music generation systems in a battle format. Users can generate music from text prompts and vote on their preferences to create leaderboards.

## Quick Start

1. **Install the package**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Generate music from a system**:
   ```bash
   ma-sys musicgen:small generate --prompt "upbeat electronic music"
   ```

3. **Start the full arena**:
   ```bash
   ma-deploy dev
   ```

## Adding a New Model

To add a new text-to-music model to the arena:

### 1. Update the Registry

Add your model to `music_arena/registry.yaml`:

```yaml
your-model-name:
  display_name: "Your Model Name"
  description: "Brief description of your model"
  organization: "Your Organization"
  access: "OPEN"  # or "CLOSED", "GATED"
  supports_lyrics: false  # or true if it supports lyrics
  model_type: "Codec Language Model"  # or "Latent Diffusion", etc.
  training_data:
    type: "Creative Commons"  # or "Licensed Stock", "Commercial", etc.
    sources:
      - "Your training data sources"
    num_tracks: 100000
    num_hours: 5000
  citation: "Your Citation"
  links:
    paper: "https://arxiv.org/abs/your-paper"
    code: "https://github.com/your-repo"
  variants:
    "initial":
      module_name: "your_model"  # Python module name in systems/
      class_name: "YourModelClass"  # Class name to instantiate
      secrets:  # Optional: if your model needs API keys
        - "HUGGINGFACE_READ_TOKEN"
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
ma-sys your-model:initial generate --prompt "test prompt"
```

## System Commands

### Generating Music

Generate music from any registered system:

```bash
# Basic generation
ma-sys system_tag:variant_tag generate --prompt "your text prompt here"

# With additional options
ma-sys musicgen:small generate --prompt "upbeat jazz" --duration 15 --seed 42

# Generate from a detailed prompt file
ma-sys sao:initial generate --prompt_path prompt.json
```

### Serving a System

Start a system as a web service:

```bash
# Serve on default port (calculated from system key)
ma-sys musicgen:small serve

# Serve on custom port
ma-sys musicgen:small serve --port 8080

# Serve with custom batch settings
ma-sys musicgen:medium serve --max_batch_size 4 --max_delay 2.0
```

The system will be available at `http://localhost:<port>` with endpoints:
- `GET /health` - Health check
- `POST /generate` - Generate music from prompts

### Testing Systems

Test a running system using the curl client:

```bash
# Test system running on default port
./curl_clients/system.sh musicgen:small prompt.json

# Test system on custom port
./curl_clients/system.sh -p 8080 prompt.json

# Test system on remote host
./curl_clients/system.sh -h myserver.com -p 8080 prompt.json
```

Create a test prompt file (`prompt.json`):

```json
{
  "overall_prompt": "upbeat electronic dance music",
  "duration": 10,
  "seed": 42
}
```

## Component Management

Run individual components of the arena:

### Frontend

```bash
# Run frontend component
ma-comp frontend --port 8080

# Frontend with custom gateway URL
ma-comp frontend --port 8080 -e "GATEWAY_URL=http://localhost:9000"
```

### Gateway

```bash
# Run gateway with systems
ma-comp gateway --systems "musicgen:small,sao:initial" --port 9000

# Gateway with weights for A/B testing
ma-comp gateway --systems "musicgen:small,musicgen:medium" --weights "musicgen:small/musicgen:medium/0.7"
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
# Deploy development environment
ma-deploy dev

# Deploy specific components only
ma-deploy dev -c frontend
ma-deploy dev -c gateway
ma-deploy dev -c systems
```

### Production Deployment

```bash
# Deploy production environment
ma-deploy prod

# Generate deployment script without running
ma-deploy prod > deploy_script.sh
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
  "musicgen:small/sao:initial": 0.5

components:
  frontend:
    enabled: true
    port: 8080
    vars:
      GATEWAY_URL: "http://localhost:9000"
  gateway:
    enabled: true
    port: 9000
    args:
      flakiness: 0.1
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
ma-chat lyrics --prompt_path detailed_prompt.json

# Generate with different model configuration
ma-chat lyrics --config 4o-v00 --prompt_path detailed_prompt.json
```

Example detailed prompt file (`detailed_prompt.json`):

```json
{
  "overall_prompt": "upbeat pop song about summer",
  "duration": 30,
  "instrumental": false,
  "generate_lyrics": true,
  "lyrics_theme": "summer vacation, friendship, good times",
  "lyrics_style": "catchy pop verses and chorus"
}
```

## Development

### Building Containers

```bash
# Build base container
docker build -t music-arena-base .

# Build system container
ma-sys musicgen:small build

# Build component containers
ma-comp frontend --skip_build
ma-comp gateway --skip_build
```

### Environment Variables

Key environment variables:
- `HUGGINGFACE_READ_TOKEN` - For models requiring HuggingFace access
- `OPENAI_API_KEY` - For lyrics generation and routing
- `GATEWAY_URL` - Frontend gateway connection
- `MINIMUM_LISTEN_TIME` - Required listening time before voting

### Logs and Debugging

```bash
# View system logs
docker logs music-arena-system-musicgen-small

# View component logs  
docker logs music-arena-component-gateway

# Debug mode
ma-sys musicgen:small generate --prompt "test" --debug
```

## TODO

- Move `music_arena/cli/system-*.py` to `components` for consistency
- Move `ResponseMetadata` to `music_arena/dataclass/response.py` and create in serving container than gateway
- Clean up inconsistency between some classes having `TextToMusic*` prefix and some not
- Make the gateway call System.prompt_supported() instead of System.supports_lyrics