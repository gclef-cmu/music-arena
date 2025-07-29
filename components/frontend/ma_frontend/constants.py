"""Global constants for Music Arena application."""

import hashlib
import os

from music_arena.dataclass import Preference

# =============================================================================
# Configuration Constants
# =============================================================================

MINIMUM_LISTEN_TIME = float(os.getenv("MINIMUM_LISTEN_TIME", 5.0))
TOS_EXPIRY_HOURS = int(os.getenv("TOS_EXPIRY_HOURS", 24 * 7))
PROMPT_MAX_CHAR_LENGTH = 8192
LYRICS_MAX_CHAR_LENGTH = 8192
CONVERSATION_TURN_LIMIT = 50
SESSION_EXPIRATION_TIME = 3600
GATEWAY_GET_TIMEOUT = 10.0
GATEWAY_GENERATE_TIMEOUT = 180.0
GATEWAY_VOTE_TIMEOUT = 10.0
LOGDIR = "logs"

# =============================================================================
# UI String Constants - Titles and Headers
# =============================================================================

# URLS
ARXIV_IDENTIFIER = "2507.20900"
PAPER_URL = f"https://arxiv.org/abs/{ARXIV_IDENTIFIER}"
CODE_URL = "https://github.com/gclef-cmu/music-arena"
FEEDBACK_FORM_URL = "https://forms.gle/DxUii6ys7Rj7jbR7A"
CONTACT_EMAIL = "musicarena@cmu.edu"

# Page Titles and Headers
GR_TITLE = "Music Arena"
TITLE_MD = "# 🎵 Music Arena ⚔️: Free Music Generation - Vote for the Best Model!"

# Tab Names
TAB_ARENA = "⚔️ Arena"
TAB_LEADERBOARD = "📊 Leaderboard"
TAB_ABOUT = "📜 About & Terms"

# UI Elements
MAIN_MD = f"""
**Music Arena** is a free platform for evaluating and comparing AI music generation models. We are currently in **open beta** as of July 28, 2025.

Please forgive issues or slow generation times as we work to improve and scale the platform, and [report any issues]({FEEDBACK_FORM_URL}) that you encounter!
""".strip()
EXPAND_INFO_ACCORDION_TEXT = (
    "🔍 Expand for instructions and more information for Music Arena"
)

# =============================================================================
# UI String Constants - Buttons and Labels
# =============================================================================

# Button Labels
GENERATE_BUTTON_LABEL = "🎵 Generate"
PREBAKE_BUTTON_LABEL = "🎲 Random Prompt"
NEW_ROUND_BUTTON = "🧽 Start Over"
REGENERATE_BUTTON = "🔄 Regenerate w/ Same Prompt"
BUTTON_A_BETTER = "👈  A is better"
BUTTON_B_BETTER = "B is better 👉"
BUTTON_TIE = "🤝  Tie"
BUTTON_BOTH_BAD = "👎  Both are bad"
TOS_ACCEPT_BUTTON_LABEL = "✅ I accept"
TOS_REJECT_BUTTON_LABEL = "❌ I do not accept"
FEEDBACK_SUBMIT_BUTTON_LABEL = "Submit feedback"
FEEDBACK_SUBMITTED_BUTTON_LABEL = "Feedback submitted!"

# Input Labels and Placeholders
LYRICS_CHECKBOX_LABEL = "Lyrics"
LYRICS_INPUT_LABEL = "Lyrics Input"
LYRICS_INPUT_PLACEHOLDER = (
    "🖋️ Enter lyrics here, or leave blank to automatically generate lyrics"
)
INPUT_PLACEHOLDER = f"👉 Enter your prompt and press {GENERATE_BUTTON_LABEL}"

# Audio Player Labels
AUDIO_PLAYER_A_LABEL = "Generated Music A"
AUDIO_PLAYER_B_LABEL = "Generated Music B"
DOWNLOAD_FILE_LABEL = "💾 Download your preferred music!"

# System and Battle Labels
BATTLE_UUID_LABEL = "**Battle ID**: "
HIDDEN_TAG_LABEL = "Model identity hidden until vote"
SYSTEM_A_LABEL = "**Model A**: "
SYSTEM_B_LABEL = "**Model B**: "
SYSTEM_UNKNOWN_NAME = "Unknown"
SYSTEM_NAME_TEMPLATE = "{name} (`{tag}`)"
SYSTEM_LABEL_TEMPLATE = "{label} {name} (`{tag}`)"
STATS_LABEL_TEMPLATE = "**Stats**: Generated {duration:.1f}s of music in {generation_duration:.1f}s ({rtf:.1f}x real time{rtf_emoji}{queued_str})\n\n"
EMOJI_THRESHOLDS = [
    (float("-inf"), " 🐌"),
    (0.9, ""),
    (2.0, " 🏎️"),
    (8.0, " 🏎️💨"),
]
STATS_QUEUED_LABEL = ", queued for {queued:.1f}s"
DISPLAY_QUEUE_THRESHOLD = 10.0
LYRICS_A_LABEL = "**Lyrics A**:\n\n"
LYRICS_B_LABEL = "**Lyrics B**:\n\n"

# Feedback Labels
FEEDBACK_HEADER_LABEL = (
    "_(Optional)_ Please share more feedback on this battle and your vote!"
)
FEEDBACK_WINNER_LABEL = (
    "What did you *like* about 🥇 Generated Music {a_or_b} (from {model_name})?"
)
FEEDBACK_LOSER_LABEL = (
    "What did you *dislike* about 🥈 Generated Music {a_or_b} (from {model_name})?"
)
FEEDBACK_BOTH_BAD_LABEL = (
    "What did you dislike about Generated Music {a_or_b} (from {model_name})?"
)
FEEDBACK_TIE_LABEL = (
    "What did you like or dislike about Generated Music {a_or_b} (from {model_name})?"
)
FEEDBACK_ADDITIONAL_LABEL = (
    "Any additional feedback on this battle or Music Arena in general?"
)

# =============================================================================
# UI String Constants - Messages and Status
# =============================================================================

# Vote Messages
VOTE_ALLOWED_MSG = "✅ You can now vote!"
# VOTE_NOT_ALLOWED_MSG = f"⚠️ You must listen to at least {round(MINIMUM_LISTEN_TIME)} seconds of each audio before voting is enabled."
VOTE_NOT_ALLOWED_MSG = (
    "⚠️ You must listen to at least a bit of each audio before voting is enabled."
)
VOTE_NOT_ALLOWED_A_TEMPLATE = (
    f"You need to **listen to {AUDIO_PLAYER_A_LABEL} for more time**."
)
VOTE_NOT_ALLOWED_B_TEMPLATE = (
    f"You need to **listen to {AUDIO_PLAYER_B_LABEL} for more time**."
)
VOTE_NOT_ALLOWED_BOTH_TEMPLATE = f"You need to **listen to both {AUDIO_PLAYER_A_LABEL} and {AUDIO_PLAYER_B_LABEL} for more time**."
PREFERENCE_TO_VOTE_CAST_MSG = {
    Preference.A: "🫶 Thank you for voting! You voted for 🥇 **{a_name}** in favor of 🥈 **{b_name}**.",
    Preference.B: "🫶 Thank you for voting! You voted for 🥇 **{b_name}** in favor of 🥈 **{a_name}**.",
    Preference.TIE: f"🫶 Thank you for voting! Looks like **{{a_name}}** and **{{b_name}}** were too close to call. Please **try again by pressing {REGENERATE_BUTTON} below**.",
    Preference.BOTH_BAD: f"🫶 Thank you for voting! We are sorry neither **{{a_name}}** nor **{{b_name}}** produced satisfactory output. Please **try again by pressing {REGENERATE_BUTTON} below**.",
}

# Error Messages
GATEWAY_UNAVAILABLE_MSG = "Our backend is either offline for maintenance or experiencing high traffic. Please try again later."
MODERATION_MSG = "Your message contains content that violates our content policy. Please revise your message and try again."
RATE_LIMIT_MSG = "You have reached the rate limit. Please try again later."
RATIONALE_TO_ERROR_MSG = {
    "Music Reference": "Your prompt contains a reference to a real music artist, song, or album. Please revise your prompt and try again.",
    "Copyrighted": "Your prompt contains lyrics that are from a well-known copyrighted song. Please revise your prompt and try again.",
    "Insensitive": "Your prompt contains culturally insensitive content. Please revise your prompt and try again.",
    "Explicit": "Your prompt contains explicit content. Please revise your prompt and try again.",
    "Profanity": "Your prompt contains inappropriate profanity. Please revise your prompt and try again.",
}
UNKNOWN_RATIONALE_ERROR_MSG = "Your prompt contains content that violates our content policy. Please revise your prompt and try again."

# Model Description Constants
MODEL_DESCRIPTION_UNAVAILABLE_MD = "Model descriptions temporarily unavailable."
MODEL_DESCRIPTION_NO_AVAILABLE = "No description available"

# =============================================================================
# Markdown Content
# =============================================================================

GATEWAY_UNAVAILABLE_MD = GATEWAY_UNAVAILABLE_MSG

ARENA_MD = """
""".strip()

ARENA_ABOUT_MD = f"""
**Music Arena** is a free platform for evaluating and comparing AI music generation models. Type a text prompt for any music you can imagine and press "{GENERATE_BUTTON_LABEL}"! Music Arena will even generate lyrics for you if your prompt implies that you want them.

Music Arena is an _academic research project_ operated by the [Generative Creativity Lab (G-CLef)](https://chrisdonahue.com/#group) at Carnegie Mellon University. Our primary goals are to provide rigorous evaluation for music generation models, and to provide an open and renewable source of music generation preference data for the research community. See our [paper]({PAPER_URL}) for more details.

**How to participate**:

1. ✍️ Enter a prompt and click "{GENERATE_BUTTON_LABEL}" to generate two different songs.
1. 🎧 Listen to both songs.
1. 🗳️ Vote on which you prefer.
1. 💾 After voting, you may download the generated music that you voted for.
1. 📊 Your votes will be used to compile a _leaderboard_ of the best models.

**Known issues**:

1. Limited number of models available supporting vocal and lyrics generation.
1. Some models will generate vocals even for instrumental prompts.
1. Slow (~60s) generation times for open weights models.

**Feedback**:

Please submit any feedback using [this form]({FEEDBACK_FORM_URL}).

**Models**. Two of the following models are randomly selected for each round:
""".strip()

NEEDS_ACK_TOS_MD = """
You need to accept our terms of service before using Music Arena. Please refresh this page if you wish to accept the terms.
""".strip()

LEADERBOARD_COMING_SOON_MD = """
## 📊 Model Leaderboard

### Coming soon!

We're working hard to bring you comprehensive leaderboard data. Check back soon to see how different music AI models stack up against each other based on community votes!
""".strip()

TERMS_OF_SERVICE_MODAL_INSTRUCTIONS = f"""
By clicking "{TOS_ACCEPT_BUTTON_LABEL}" below, you agree to the **terms of service** below.
""".strip()

TERMS_MD = f"""
## Terms of Service - Music Arena

**Effective Date:** July 28, 2025

By accessing or using Music Arena ("Service"), you agree to be bound by these Terms of Service ("Terms"). If you do not agree to these Terms, do not use the Service.

### 1. Service Description and Research Preview Status

Music Arena is a research platform designed for evaluating and comparing AI music generation models. The Service is provided on an experimental, "research preview" basis. We make no representations or warranties regarding the Service's availability, reliability, accuracy, or fitness for any particular purpose. The Service is provided "AS IS" and "AS AVAILABLE" without warranties of any kind, either express or implied.

### 2. Eligibility and Account Requirements

By using this Service, you represent and warrant that:
- You are at least 18 years of age
- You are a legal resident of the United States
- You have the legal capacity to enter into these Terms
- Your use of the Service complies with all applicable laws and regulations

### 3. Prohibited Uses and Conduct

You agree not to use the Service to:
- Submit prompts designed to imitate specific recording artists or copyrighted material or infringe in any other manner on intellectual property rights
- Submit prompts designed to generate hate speech, sexually explicit content, or content promoting violence
- Generate, distribute, or promote content that is illegal, harmful, threatening, abusive, defamatory, libelous, or otherwise objectionable
- Use automated means (bots, scrapers, etc.) to access or manipulate the Service without express written permission
- Interfere with or disrupt the Service's operation or security
- Violate any applicable local, state, national, or international law or regulation

### 4. Privacy and Data Protection

**Information Collection:** We collect and process your interactions with the Service, including but not limited to:
- Text prompts and queries you submit
- Audio listening behavior and interaction patterns  
- User preferences and voting data
- Natural language feedback on generated audio
- Anonymized user tracking identifiers, e.g. your IP address anonymized with cryptographic hashing with salt

**Sensitive Information:** You must not submit personal identifying information, private data, confidential information, or any sensitive personal data through the Service, e.g., in your text prompts or natural language feedback.

### 5. Data Use and Research Purposes

By using the Service, you acknowledge and consent that your interaction data may be:
- Used for research and development purposes to advance AI music generation technology
- Analyzed to improve the Service's functionality and user experience
- Aggregated with other user data for academic research and publication
- Shared publicly with the research community under appropriate data use agreements

### 6. Data Distribution and Licensing

**Open Data Release:** You expressly agree and consent that we may release your anonymized interaction data, including but not limited to:
- Anonymized user identifiers
- Text prompts and queries
- Listening behavior and engagement metrics
- Preference and voting data

**License Grant:** Such data may be distributed under Creative Commons Attribution 4.0 International (CC BY 4.0) license or similar open-source licenses. You hereby grant us a perpetual, irrevocable, worldwide, royalty-free license to use, reproduce, distribute, and create derivative works from your contributions to the Service for any purpose, including but not limited to research and educational purposes.

### 7. Intellectual Property

**Open Source Software:** The Music Arena platform software is made available under the MIT License and can be found at {CODE_URL}. Users may use, modify, and distribute the software in accordance with the terms of the MIT License.

**Service Trademarks:** The "Music Arena" name, logo, and associated trademarks remain the property of Music Arena and are not covered by the open source license.

**Third-Party Components:** The Service may incorporate third-party software, AI models, and other components that are subject to their respective licenses and terms of use.

**Generated Content:** AI-generated musical content created through the Service may not be subject to copyright protection under current U.S. law. Users should not assume exclusive rights to generated content, and such content may be freely used by others.

### 8. Termination

We reserve the right to terminate or suspend your access to the Service immediately, without prior notice, for any reason, including but not limited to breach of these Terms.

### 9. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, IN NO EVENT SHALL MUSIC ARENA, ITS AFFILIATES, OR THEIR RESPECTIVE OFFICERS, DIRECTORS, EMPLOYEES, OR AGENTS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF DATA, LOSS OF PROFITS, OR BUSINESS INTERRUPTION, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE SERVICE.

### 10. Indemnification

You agree to indemnify, defend, and hold harmless Music Arena and its affiliates from and against any claims, liabilities, damages, losses, costs, or expenses arising out of or in connection with your use of the Service or violation of these Terms.

### 11. Modification of Terms

We reserve the right to modify these Terms at any time. Changes will be effective immediately upon posting to the Service. Your continued use constitutes acceptance of the modified Terms.

### 12. Severability

If any provision of these Terms is found to be unenforceable or invalid, that provision will be limited or eliminated to the minimum extent necessary so that these Terms will otherwise remain in full force and effect.

### 13. Contact Information

For questions about these Terms, please contact us at: {CONTACT_EMAIL}

**Last Updated:** July 28, 2025
""".strip()
TERMS_CHECKSUM = hashlib.md5(TERMS_MD.encode()).hexdigest()


ABOUT_MD = f"""
## About Us

Welcome to Music Arena! This platform ranks Text-to-Music AI models based on crowdsourced human preferences. Models are evaluated in head-to-head battles, and their Elo ratings are updated dynamically. Explore the top models, their performance metrics, and learn more about their capabilities.

Music Arena is an _academic research project_ operated by the [Generative Creativity Lab (G-CLef)](https://chrisdonahue.com/#group) at Carnegie Mellon University. Our primary goals are to provide rigorous evaluation for music generation models, and to provide an open and renewable source of music generation preference data for the research community. See our [paper]({PAPER_URL}) for more details.

Music Arena is approved by CMU's Institutional Review Board under Protocol `STUDY2024_00000489`.

Links:

- [Paper]({PAPER_URL})
- [Codebase]({CODE_URL})
- [Feedback Form]({FEEDBACK_FORM_URL})

## Contributors

The development of Music Arena has so far been led by the following contributors: [Chris Donahue](https://chrisdonahue.com/), [Yonghyun Kim](https://yonghyunk1m.com) of the Georgia Tech [Music Informatics Group](https://musicinformatics.gatech.edu/), and [Wayne Chi](https://www.waynechi.com/). Additional assistance provided by [Anastasios Angelopolus](https://people.eecs.berkeley.edu/~angelopoulos/) and [Wei-Lin Chiang](https://infwinston.github.io/).

We invite community contributions to our [codebase]({CODE_URL}).

## Acknowledgments

Music Arena is supported by funding from [Sony AI](https://ai.sony), with informal and pro-bono assistance provided by [LMArena](https://lmarena.ai).

## Citation

If you use Music Arena in your research, please cite our preprint:

```bibtex
@article{{kim2025musicarena,
  title={{Music Arena: Live Evaluation for Text-to-Music}},
  author={{Kim, Yonghyun and Chi, Wayne and Angelopoulos, Anastasios and Chiang, Wei-Lin and Saito, Koichi and Watanabe, Shinji and Mitsufuji, Yuki and Donahue, Chris}},
  journal={{arXiv:{ARXIV_IDENTIFIER}}},
  year={{2025}}
}}
```

{TERMS_MD}
""".strip()
