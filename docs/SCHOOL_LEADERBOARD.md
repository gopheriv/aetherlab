# Shared school leaderboard

The desktop app can share full UNT mock results between devices through a
small PhysLab leaderboard API. There is no hosted endpoint bundled with the
app: a school or administrator must deploy the API and give students its
HTTPS address.

## What is shared

Joining is explicit. The app sends the student's name, class, school ID, and
completed full-mock scores to the configured server. Profile photo and login
are not sent. Only attempts marked as a complete 50-point mock are included.
The API stores an HMAC of the school ID instead of the raw ID, and does not
write request bodies to its logs. Scores are self-reported by the desktop app;
this is a classroom leaderboard, not an exam verification system.

## Deploy the API

The API uses the Python standard library and SQLite. Keep its database on a
persistent disk and place it behind a TLS reverse proxy before allowing
internet access. Keep the secret stable across restarts; changing it will make
existing school groups unreachable.

For a local smoke test, set a random secret with at least 32 bytes and run:

```powershell
$env:AETHERLAB_LEADERBOARD_SECRET = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
python -m aetherlab.services.leaderboard_server --host 127.0.0.1 --port 8765 --db .\leaderboard.sqlite3
```

For a hosted service, build `deploy/leaderboard/Dockerfile` from the repository
root. Set `AETHERLAB_LEADERBOARD_SECRET` in the hosting provider's secret
settings, attach persistent storage at `/data`, and route HTTPS traffic to
port `8765`. Do not expose the container port directly on the public internet.
The health check is `GET /health`.

## Connect desktop clients

On every device, open **Leaderboard** on the student dashboard, enter the
server's HTTPS address, and save it. Students enter the same school-issued ID
in their profiles. Press **Join and refresh** to publish that profile's full
mock scores and retrieve the school ranking. Selecting a student in the table
shows every full mock score currently stored for that student.

The same username and school ID identify a student across devices. Students
must use their own username; the app hashes the username and school ID into a
pseudonymous participant key. The public service URL can also be configured
for all clients with `AETHERLAB_LEADERBOARD_URL`.
