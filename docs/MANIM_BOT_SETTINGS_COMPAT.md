# Manim-Bot Settings Compatibility

AetherLab can reuse the safe, portable environment setting names from
`manim-bot` without copying `manim-bot/.env` or any secret-bearing files.

Supported aliases:

| AetherLab setting | Native env | manim-bot-compatible env |
|---|---|---|
| Code/chat model | `AETHERLAB_LLM_MODEL` | `MANIM_MODEL`, `GPT_MODEL`, `CHAT_MODEL` |
| API key | `AETHERLAB_OPENAI_API_KEY`, `OPENAI_API_KEY` | `GPT_API_KEY`, `DASHSCOPE_API_KEY` |
| OpenAI-compatible base URL | `AETHERLAB_OPENAI_BASE_URL`, `OPENAI_BASE_URL` | `GPT_BASE_URL`, `LLM_BASE_URL` |
| LLM timeout | `AETHERLAB_LLM_TIMEOUT` | `LLM_TIMEOUT` |
| Render tier | `AETHERLAB_RENDER_TIER` | `RENDER_TIER` |
| Render FPS | `AETHERLAB_MANIM_FPS` | `MANIM_FPS` |
| Vision critic model | `AETHERLAB_VISION_MODEL` | `VISION_MODEL` |
| Vision critic passes | `AETHERLAB_VISUAL_CRITIC_MAX_PASSES` | `VISUAL_CRITIC_MAX_PASSES` |
| Vision critic frame count | `AETHERLAB_VISUAL_CRITIC_KEYFRAMES` | `VISUAL_CRITIC_KEYFRAMES` |
| Narration enabled | `AETHERLAB_NARRATION` | `VOICEOVER_ENABLED`, `TTS_ENABLED` |
| Narration voice/rate | `AETHERLAB_TTS_VOICE`, `AETHERLAB_TTS_RATE` | `TTS_VOICE`, `TTS_RATE` |
| Cloud render enable | `AETHERLAB_RENDER_MODE=auto` | `CLOUD_RENDER_ENABLED=true` |
| Cloud render repo/workflow/branch | `AETHERLAB_RENDER_REPO`, `AETHERLAB_GITHUB_WORKFLOW`, `AETHERLAB_GITHUB_BRANCH` | `CLOUD_RENDER_REPO`, `CLOUD_RENDER_WORKFLOW`, `CLOUD_RENDER_BRANCH` |
| Cloud render timing | `AETHERLAB_CLOUD_RENDER_TIMEOUT`, `AETHERLAB_CLOUD_POLL_SECONDS` | `CLOUD_RENDER_TIMEOUT`, `CLOUD_RENDER_POLL` |

Precedence remains conservative:

1. AetherLab-specific env vars win.
2. Existing OpenAI-compatible env vars win next.
3. manim-bot-compatible aliases fill only unset compatible fields.
4. Saved AetherLab app config fills after env.
5. Defaults keep the app usable without secrets.

Notes:

- `CLOUD_RENDER_ENABLED=true` maps to AetherLab `auto` render mode unless
  `AETHERLAB_RENDER_MODE` is explicitly set.
- `manim-bot/.env` is intentionally not read by AetherLab. Keep credentials in
  your shell environment, AetherLab Settings, or a deployment secret store.
- Telegram-only settings, Cloudflare D1 settings, and bot admin settings are not
  used by AetherLab.
