# AetherLab Cloud Rendering

AetherLab can render Manim scenes locally, or send a single sanitized Manim
scene file to a GitHub Actions render repo and download the MP4 artifact.
Cloud rendering is optional and always fails soft to local rendering.

## Recommended Setup

1. Create a GitHub repository for render jobs.
   - Private is safest.
   - Public is supported, but generated scene code may be visible.
2. Add `.github/workflows/render.yml` from this project to that repository.
3. In AetherLab Settings, choose:
   - Render mode: `Cloud` or `Auto`
   - GitHub render repo: `owner/name`
   - Workflow file: `render.yml`
   - Render branch: `renders`
4. Authenticate.
   - Preferred: GitHub device login, when an AetherLab OAuth client id is
     configured via `AETHERLAB_GITHUB_CLIENT_ID`.
   - Fallback: paste a fine-grained GitHub token.

## Token Permissions

For a fine-grained token, restrict it to the render repository and grant:

- Actions: read/write
- Contents: read/write

The app uses Contents write to commit `jobs/<job_id>.py` to the render branch,
Actions write to dispatch the workflow, and Actions read to poll runs and
download artifacts.

## Privacy Rules

AetherLab never intentionally uploads:

- API keys or tokens
- `.env` files
- app config files
- textbook cache files
- user prompt metadata

Only the generated scene code is committed. Public render repos are allowed, but
the generated scene code may contain visible labels derived from the lesson or
problem. Use a private repo if that matters.

Before cloud dispatch, AetherLab scans the scene payload for common secret
patterns. If it sees one, it refuses cloud rendering and renders locally.

## Modes

- `Local`: current behavior. Render with the local Manim install.
- `Cloud`: try GitHub Actions first; fall back to local if unavailable.
- `Auto`: use cloud only for heavy scenes. The default threshold is `3.0`,
  matching AetherLab's existing heavy-scene render-cost heuristic.

## Cache Behavior

Cloud job ids are derived from:

- scene code
- scene class
- quality
- fps
- `manim==0.20.1`
- workflow contract version

Identical scenes reuse an existing GitHub artifact when available. Downloaded
MP4s are stored under the same local isolated render-run directory shape used by
local rendering, so missing local videos still trigger a re-render.

## Runner Parity

The workflow pins:

- `ubuntu-24.04`
- Python `3.14`
- `manim==0.20.1`
- ffmpeg, cairo, pango

LaTeX is installed only when the app marks a scene as needing `Tex`/`MathTex`.
AetherLab's default generated and fallback scenes remain Text-first to avoid a
hard LaTeX dependency.

## Failure Behavior

Cloud failures map back to the normal render contract:

- timeout -> `render-timeout`, `failure_kind="timeout"`
- Manim crash -> `render-error`, classified as latex/ffmpeg/oom/hallucinated-api/unknown
- no network/token/repo/workflow -> local fallback

The existing render repair, visual critique, and narration loops operate on the
returned `SceneBundle` exactly as they do for local renders.
