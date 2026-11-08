# Verification

## Completed

- `backend\.venv\Scripts\python.exe -m pytest backend\tests -q`: **30 passed**.
  The tests cover face-only check-in and check-out, rejection of manual punches,
  late/absent calculation, employee data scope, safe shift edits, and reload of
  shared face-recognition settings.
- `.venv\Scripts\python.exe -m pytest tests -q`: **29 passed** for desktop
  matching, regions, tracking, and the synthetic camera pipeline.
- `npm run typecheck` and `npm run build` in `frontend`: **passed**.
- `docker compose config --quiet` and `docker compose up -d --build`: **passed**.
- MongoDB and API containers reported healthy; `http://localhost:8000/api/health`
  returned `{"status":"ok","database":"mongodb"}`, and the web page returned HTTP
  200.
- The signed-in admin workspace and attendance page rendered in the browser.
- A demo employee signed in successfully; the browser showed only the
  attendance navigation item, and logout revoked the session.
- The six seeded demo usernames and shared password from `.env.example` were
  checked against the running API.

## Not validated here

- The real webcam, face-model inference on a person's face, and spoof resistance
  were not tested. Face attendance still requires a camera-capable browser,
  `FACE_ENABLED=true`, and the configured minimum samples per employee (five
  by default).
- The Windows desktop camera tool and live config-file propagation into a
  running Docker Desktop instance were not exercised with a physical camera.
- The employee workspace showed no assigned shift for the seeded test account
  on the test date, so actual face check-in/out was not completed in-browser.
- No desktop SQLite templates were migrated. The desktop database is separate
  from MongoDB; migration needs an explicit employee-code mapping and consent.
