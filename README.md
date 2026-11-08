# FaceCam Attendance

Web-based attendance for employees, with an admin/HR/manager workspace, face verification,
shift scheduling, attendance reports, requests, and an audit log.

## Run on Windows

1. Install and start Docker Desktop.
2. Review `.env` and set private `MONGO_PASSWORD` and `DEMO_PASSWORD` values.
   The example configuration seeds demo accounts only when the MongoDB database
   is empty. Keep the Mongo password URI-safe (letters and numbers).
3. Run `run_windows.bat` (or `start-docker.bat` / `docker compose up -d --build`)
   to start the web app, then open `http://localhost:3000`.

`run_windows.bat` starts the same Docker-based web application used by the
browser, so camera testing uses the web UI and its MongoDB data. The separate
desktop camera experiment is still available through `install_windows.bat` and
`run_camera_test_windows.bat`; it keeps its own SQLite data and is not the web
attendance source of truth.

The web app is the source of truth: the browser camera sends frames to the Face
API, which stores confirmed attendance and employee face templates in the same
MongoDB database. Both check-in and check-out require a successful face match
using the configured minimum number of enrolled samples (five by default). If a
face profile is not ready, management must enroll it in **Hồ sơ khuôn mặt** before the
employee can punch.

Admin, HR, and managers have equal access to the management workspace.
Employees can view their own dashboard, attendance, schedule, requests,
timesheets, departments, and shifts. They can create and track requests and use
face check-in/check-out, but cannot cancel or review requests or edit management
data. Their dashboard and reports contain only their own records.

## Demo sign-in accounts

The six accounts below are created only when the MongoDB database is empty and
`SEED_DEMO=true`. They all use the `DEMO_PASSWORD` value from `.env`; in a fresh
copy of this project, `.env.example` sets it to `Demo@123456`.

| Username | Name | Role | Demo password |
|---|---|---|---|
| `admin` | Nguyễn Minh Anh | Administrator | `Demo@123456` |
| `hr` | Trần Thu Hà | HR | `Demo@123456` |
| `manager` | Lê Hoàng Nam | Manager | `Demo@123456` |
| `employee` | Nguyễn Đăng Khang | Employee | `Demo@123456` |
| `linh` | Phạm Ngọc Linh | Employee | `Demo@123456` |
| `tuan` | Võ Anh Tuấn | Employee | `Demo@123456` |

Use `employee`, `linh`, or `tuan` to test the employee workspace.
Password changes are made from the key icon in the top bar. The logout control
is at the bottom of the left sidebar. Demo credentials are for local testing
only: change them before exposing the app to a network. Accounts created later
have the individual password set by the administrator and are not listed here.

## Tune face recognition on Windows

1. Run `run_windows.bat` to start the web app and use its camera. This tests the
   exact browser-to-API camera flow with the web MongoDB database.
2. Optionally run `install_windows.bat` and then
   `run_camera_test_windows.bat` to experiment with the separate desktop
   camera tool. Turn on the camera and adjust the recognition
   threshold and runner-up margin.
3. In the desktop tool, select **Dùng cho web** to save those values to
   `config.json`.

Compose mounts `config.json` into the API container. The web API reads the
recognition threshold, runner-up margin, confirmation count, and camera-quality
settings from it for recognition, without rebuilding or restarting Docker.
Run the desktop tool and Docker on the same computer for this file sharing to
work.

The desktop app (`app.py`) stores its face templates in `data/faces.db`. That
SQLite file is separate from the web app's MongoDB face profiles and is not
live-synchronized. The web uses templates enrolled by HR in **Hồ sơ khuôn mặt**.
Use `run_windows.bat` to test web attendance; the desktop tool does not record
web attendance.

If existing desktop templates need to be brought into the web app, first obtain
each affected employee's consent and create an explicit person-ID-to-employee
mapping. Then:

1. Back up `data/faces.db`.
2. Create a small Python environment for the one-time import:

   ```powershell
   py -3.11 -m venv .venv-import
   .\.venv-import\Scripts\python.exe -m pip install -r backend\requirements.txt
   ```

3. List local person IDs and names:

   ```powershell
   .\.venv-import\Scripts\python.exe scripts\import_faces.py --list-people
   ```

4. Copy `scripts/face-mapping.example.csv` to a new CSV. Map each `person_id`
   to the matching active `employee_code` in the web app. Never map by name
   alone.
5. Preview the import first:

   ```powershell
   .\.venv-import\Scripts\python.exe scripts\import_faces.py --mapping .\my-face-mapping.csv
   ```

6. After confirming the employee mapping and each person's consent, apply it:

   ```powershell
   .\.venv-import\Scripts\python.exe scripts\import_faces.py --mapping .\my-face-mapping.csv --apply --consent-confirmed
   ```

The import is append-only, leaves the SQLite source unchanged, and refuses to
overwrite an existing web face profile. Run it from the project root while
MongoDB is running; local configuration reads the root `.env` for the Compose
MongoDB port and credentials.

## Local verification

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm ci
npm run typecheck
npm run build
```
