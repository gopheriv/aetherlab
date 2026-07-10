# AetherLab Cloud Rendering

AetherLab can render Manim scenes locally, or send a single sanitized Manim
scene file to a GitHub Actions render repo and download the MP4 artifact.
Cloud rendering is optional and always fails soft to local rendering.

## Recommended Setup

1. Create a GitHub repository for render jobs.
   - Private is safest.
   - Public is supported, but generated scene code may be visible.
2. In AetherLab Settings, choose:
   - Render mode: `Cloud` or `Auto`
   - GitHub render repo: `owner/name`
   - Workflow file: `render.yml`
   - Render branch: `renders`
3. Authenticate.
   - Preferred: GitHub device login, when an AetherLab OAuth client id is
     configured via `AETHERLAB_GITHUB_CLIENT_ID`.
   - Fallback: paste a fine-grained GitHub token (needs the `workflow` scope,
     see below).
   - If you already use the GitHub CLI, `gh auth login` is also enough:
     AetherLab can read `gh auth token` at runtime without saving the token in
     app config.
4. Click **Test cloud render**. AetherLab now **installs the render workflow for
   you** — it commits `.github/workflows/render.yml` to the repository's default
   branch and to the render branch (GitHub only dispatches a workflow that
   exists on the default branch). This also happens automatically before the
   first cloud render, so no manual copying is required.
   - Manual alternative: copy `.github/workflows/render.yml` from this project
     into the repository yourself.

## Token Permissions

For a fine-grained token, restrict it to the render repository and grant:

- Actions: read/write
- Contents: read/write
- Workflows: read/write  (required to install `.github/workflows/render.yml`;
  a classic token needs the `workflow` scope. The in-app device login already
  requests `repo workflow`.)

The app uses Contents write to commit `jobs/<job_id>.py` to the render branch,
Actions write to dispatch the workflow, and Actions read to poll runs and
download artifacts. Candidate writes are serialized per repository/branch and
HTTP 409 conflicts receive a short bounded retry; distinct job files still
share one branch tip, so names alone are not concurrency control.

## manim-bot Migration

If you already configured `manim-bot/.env`, AetherLab can reuse compatible keys
as a fallback, including `CLOUD_RENDER_ENABLED`, `CLOUD_RENDER_REPO`,
`CLOUD_RENDER_WORKFLOW`, `CLOUD_RENDER_BRANCH`, `CLOUD_RENDER_TIMEOUT`, and
`CLOUD_RENDER_POLL`. AetherLab-specific env vars and saved Settings still win.
Set `AETHERLAB_DISABLE_LEGACY_ENV=1` to turn this migration fallback off.

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

- poll timeout -> cancel the remote run best-effort and immediately fall back local
- Manim crash -> `render-error`, classified as latex/ffmpeg/oom/hallucinated-api/unknown
- no network/token/repo/workflow -> local fallback

The configured cloud timeout is a ceiling. AetherLab derives a smaller
quality/cost-aware budget (a light draft is capped at 420 seconds even when an
old config still says 1800); the default ceiling is 600 seconds.

The existing render repair, visual critique, and narration loops operate on the
returned `SceneBundle` exactly as they do for local renders.

## Debugging with the render-farm dashboard

Every cloud render and scene tournament is recorded in a **render-farm ledger**
(`services/render_ledger.RenderJobLedger`, JSON under
`<data_dir>/render_ledger.json`). Open it from **Settings → View render ledger**
to see, per job:

- the status timeline — `queued → in_progress → completed/failed/cancelled/
  rate_limited → artifact_downloaded → rendered`, or `fallback_local`;
- for a tournament, the **per-candidate critic scores with the winner
  highlighted** — i.e. *why* this scene was chosen;
- a **sanitized failure log tail** (tokens/keys are redacted at write time, so
  the ledger is safe to share) and the classified failure kind;
- the **local-fallback reason** and the final output path when cloud was
  unavailable.

The ledger is fail-soft and capped: it never breaks a render and keeps only the
most recent jobs. Because every free-text field is scrubbed on the way in, no
credential is ever persisted. To debug a failed cloud render, read its log tail
and timeline here first; to confirm a tournament, check the candidate scores and
the winner index.
