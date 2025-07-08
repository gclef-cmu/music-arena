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

# Page Titles and Headers
GR_TITLE = "Music Arena"
TITLE_MD = "# 🎵 Music Arena: Free Music Generation - Vote for the Best Model!"

# Tab Names
TAB_ARENA = "⚔️ Arena"
TAB_DIRECT = "🗡️ Specific Model"
TAB_LEADERBOARD = "📊 Leaderboard"
TAB_ABOUT = "📜 About & Terms"

# UI Elements
MAIN_MD = """
**Music Arena** is a free platform for evaluating and comparing AI music generation models. We are currently in **private beta**. Please email any feedback to chrisdonahue@cmu.edu.
""".strip()
EXPAND_INFO_ACCORDION_TEXT = (
    "🔍 Expand for instructions and more information for Music Arena"
)

# Links
FEEDBACK_FORM = "https://forms.gle/AevMiHGwBFRJ44Gz8"

# =============================================================================
# UI String Constants - Buttons and Labels
# =============================================================================

# Button Labels
GENERATE_BUTTON_LABEL = "🎵 Generate"
PREBAKE_BUTTON_LABEL = "🔮 Surprise me"
NEW_ROUND_BUTTON = "🎲 New Round"
REGENERATE_BUTTON = "🔄 Regenerate"
BUTTON_A_BETTER = "👈  A is better"
BUTTON_B_BETTER = "B is better 👉"
BUTTON_TIE = "🤝  Tie"
BUTTON_BOTH_BAD = "👎  Both are bad"
TOS_ACCEPT_BUTTON_LABEL = "✅ I accept"
TOS_REJECT_BUTTON_LABEL = "❌ I do not accept"

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
LYRICS_A_LABEL = "**Lyrics A**:\n\n"
LYRICS_B_LABEL = "**Lyrics B**:\n\n"

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
GATEWAY_UNAVAILABLE_MSG = "Our backend is either offline or experiencing high traffic. Please try again later."
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

Music Arena is primarily operated by the [Generative Creativity Lab (G-CLef)](https://chrisdonahue.com/#group) at Carnegie Mellon University, with support from [Sony AI](https://ai.sony) and assistance from [LMArena](https://lmarena.ai). See {TAB_ABOUT} for more details.

**How to participate**:

1. ✍️ Enter a prompt and click "{GENERATE_BUTTON_LABEL}" to generate two different songs.
1. 🎧 Listen to both songs.
1. 🗳️ Vote on which you prefer.
1. 💾 After voting, you may download the generated music that you voted for.
1. 📊 Your votes will be used to compile a _leaderboard_ of the best models.

**Known issues**:

1. Limited number of models available supporting vocal generation.
1. Slow (~60s) generation times for open weights models.

**Feedback**:

Aside from the known issues above, please direct any feedback to chrisdonahue@cmu.edu. Alternatively, you can [submit a bug report](https://forms.gle/DxUii6ys7Rj7jbR7A).

**Models**. Two of the following models are randomly selected for each round:
""".strip()

DIRECT_MD = """
## 🗡️ Specific Model

### Coming soon!

Stop by later to test out a specific model.
""".strip()

NEEDS_ACK_TOS_MD = """
You need to acknowledge our terms of service before using Music Arena.
""".strip()

LEADERBOARD_COMING_SOON_MD = """
## 📊 Model Leaderboard

### Coming soon!

We're working hard to bring you comprehensive leaderboard data. Check back soon to see how different music AI models stack up against each other based on community votes!
""".strip()

TERMS_MD = """
1.  **Research Preview:** This service is a research preview intended for evaluating and comparing AI music generation models. It is provided "as is" without warranties of any kind.
2.  **Prohibited Uses:** The service must not be used for any illegal, harmful, defamatory, or infringing purposes. Do not use prompts intended to generate such content.
3.  **Privacy:** Please do not submit any private or sensitive personal information in your text prompts.
4.  **Data Collection and Use:** The service collects data including your text prompts, your preferences (votes) regarding generated audio, and _fully anonymized_ user tracking data (salted and hashed IP addresses and browser fingerprints). This data is crucial for research to advance music generation technology and to improve this platform.
5.  **Demographics:** By accepting our terms, you acknowledge that you are 18 years or older and living in the United States.
6.  **Data Distribution:** By accepting our terms, you agree that we may release your anonymized interaction data including anonymized identifiers, text prompts, listening, and voting data under a Creative Commons Attribution (CC-BY) license or a similar open license.
7.  **Feedback:** Your feedback is valuable. Please [report any bugs, issues, or surprising outputs](https://forms.gle/DxUii6ys7Rj7jbR7A).
""".strip()
TERMS_CHECKSUM = hashlib.md5(TERMS_MD.encode()).hexdigest()

TERMS_OF_SERVICE_MODAL_MD = f"""
By clicking {TOS_ACCEPT_BUTTON_LABEL} below, you agree to the following **terms of service**:

{TERMS_MD}
""".strip()

ABOUT_MD = f"""
## About Us
Welcome to Music Arena! This platform ranks Text-to-Music AI models based on crowdsourced human preferences. Models are evaluated in head-to-head battles, and their Elo ratings are updated dynamically. Explore the top models, their performance metrics, and learn more about their capabilities. Powered by insights from CMU [Generative Creativity Lab (G-CLef)](https://chrisdonahue.com/#group), Georgia Tech [Music Informatics Group](https://musicinformatics.gatech.edu/), and [LM Arena](https://blog.lmarena.ai/about/).

Links:

- [Codebase](https://github.com/gclef-cmu/music-arena)
- [Feedback Form](https://forms.gle/DxUii6ys7Rj7jbR7A)

## Contributors

The development of Music Arena has so far been led by the following contributors [Chris Donahue](https://chrisdonahue.com/), [Yonghyun Kim](https://yonghyunk1m.com), [Wayne Chi](https://www.waynechi.com/). Additional assistance provided by [Anastasios Angelopolus](https://people.eecs.berkeley.edu/~angelopoulos/) and [Wei-Lin Chiang](https://infwinston.github.io/).

We invite community contributions to our [codebase](https://github.com/gclef-cmu/music-arena)

## Terms of Service

Music Arena is approved by CMU's Institutional Review Board under Protocol `STUDY2024_00000489`. By using Music Arena, you agree to the following terms of service:

{TERMS_MD}

## Acknowledgments

Music Arena is supported by [Sony AI](https://ai.sony) and was developed with assistance from the [LMArena](https://lmarena.ai) team.
""".strip()
