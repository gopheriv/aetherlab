# Manim-Bot Settings Compatibility

AetherLab can reuse the safe, portable environment setting names from
`manim-bot`. During migration it can also read a legacy `.env` as a fallback,
without mutating your process environment or printing secret values.

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
5. A legacy `.env` fills only still-unset compatible fields.
6. Defaults keep the app usable without secrets.

Notes:

- `CLOUD_RENDER_ENABLED=true` maps to AetherLab `auto` render mode unless
  `AETHERLAB_RENDER_MODE` is explicitly set.
- AetherLab first checks `AETHERLAB_LEGACY_ENV_PATH` / `MANIM_BOT_ENV_PATH`.
  If unset, it looks for `.env` in this project and then a sibling
  `../manim-bot/.env`. Set `AETHERLAB_DISABLE_LEGACY_ENV=1` to disable this
  fallback, which the test harness does by default.
- GitHub cloud tokens can come from AetherLab Settings, `GITHUB_TOKEN` /
  `GH_TOKEN`, or an existing `gh auth login` session (`gh auth token`). Tokens
  are used at runtime only; they are not copied into render job files.
- Telegram-only settings, Cloudflare D1 settings, and bot admin settings are not
  used by AetherLab.
