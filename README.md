# QuestAI

**One AI superapp. Six specialist agents behind a single universal layer.**

You type a task in plain language. A universal routing layer decides which
specialist should handle it, pre-extracts that specialist's form fields, and
hands the user over with the work already done. Six LangGraph agents do the
actual research, and **every single search in the product runs through
[SerpApi](https://serpapi.com)** — there is no other search backend.

```
"cheapest headphones under 3000"
        |
        v
  universal layer  ── intent classification + field extraction
        |
        v
  Shopping agent ── SerpApi: google_shopping + amazon
        |
        v
  normalised products, cheapest first
```

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [Job alerts with n8n](#job-alerts-with-n8n)
- [SerpApi usage](#serpapi-usage)
- [The universal layer](#the-universal-layer)
- [The six agent graphs](#the-six-agent-graphs)
- [Architecture](#architecture)
- [API surface](#api-surface)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Why this exists

Most AI products make you choose a tool before you can start. You pick
"Research" or "Jobs" or "Travel", then fill in that tool's form, even when your
actual question is simpler than the form.

QuestAI inverts that. You describe the outcome you want; the routing layer picks
the specialist and pre-fills what it can infer. There are six agents —
**Research, Trips, Flights, Hotels, Shopping and Jobs** — behind five tabs, since
the three travel agents share one Travel tab.

---

## Quick start

**Prerequisites**

| Requirement | Version tested |
|---|---|
| Python | 3.12.2 |
| Node.js | 24.14.0 (any modern LTS) |
| MongoDB | local instance or a free [Atlas](https://www.mongodb.com/atlas) cluster |
| SerpApi key | [serpapi.com](https://serpapi.com) — free tier is 250 searches/month |
| Groq key | [console.groq.com](https://console.groq.com) — free tier is enough |

### 1. Backend

```bash
git clone <your-fork-url> questai
cd questai

python -m venv .venv
# Windows:   .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env     # Windows: copy .env.example .env
# then fill in the four REQUIRED values in .env.
# Nothing else is needed: email, Google OAuth and n8n are all optional.
# Do NOT set MAIL_ENABLED=true unless you are configuring SMTP — signup and
# login work with no email setup at all.

uvicorn backend.main:app --port 8000
```

The backend serves on **http://localhost:8000**. `GET /health` lists all
services and is the fastest way to confirm it booted.

> MongoDB Atlas users: add your machine's IP to the cluster access list, or every
> authenticated request will fail while the API itself still appears healthy.

### 2. Frontend (the app — this is the one you want)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and sign up.

### 3. Verify it works

```bash
# Frontend integrity checks (no network, no API keys needed)
cd frontend && npm test

# Confirm the research parsers match live SerpApi responses.
# Costs 3 searches.
.venv/bin/python -m backend.agents.research.tools.verify_parsers
# Windows: .venv\Scripts\python.exe -m backend.agents.research.tools.verify_parsers
```

---

## Environment variables

`.env.example` is the full annotated template. Only four values are required:

| Variable | Required | Purpose |
|---|---|---|
| `SERP_API_KEY` | **yes** | The only search provider in the product |
| `GROQ_API_KEY` | **yes** | Runs every LLM node, including resume-image parsing |
| `MONGODB_URI` | **yes** | Users, sessions, job alerts |
| `JWT_SECRET_KEY` | **yes** | Signs tokens — defaults to `""`, which is an empty HMAC secret, so set it |

Everything else has a working default. Optional groups: Google OAuth, SMTP
(email delivery), and `N8N_SERVICE_KEY` (scheduled job alerts).

### Email is off by default — use it that way

`.env.example` ships `MAIL_ENABLED=false`, and that is the recommended setup for
running and evaluating the app. **Leave it false.** Normal signup and login work
exactly as they do with email enabled:

- `POST /api/auth/signup` returns access + refresh tokens immediately
- `POST /api/auth/login` returns them immediately
- No OTP, no confirmation link, no SMTP account needed

There is no verification gate anywhere in the login path. What turns off with
`MAIL_ENABLED=false`:

| Feature | With `MAIL_ENABLED=false` |
|---|---|
| Signup / login / logout / refresh | fully working |
| Every agent and all six graphs | fully working |
| Verify banner on `/home` | never shown |
| Email OTP on signup | not sent, signup just succeeds |
| Forgot password by email | returns 400 "disabled on this instance" |
| Google OAuth | unaffected, controlled by its own variables |

So: sign up with any email and password of 6+ characters, and you are in. If you
forgot a password, set `MAIL_ENABLED=true` first and configure SMTP — there is no
other reset path.

### Email (`MAIL_ENABLED`)

`MAIL_ENABLED` is the master switch for all outgoing email. It defaults to
`false`, so a fresh clone is fully usable with no email configuration:

| | `false` (default) | `true` |
|---|---|---|
| Verify banner on `/home` | never shown | shown until verified or skipped |
| OTP / password-reset email | not sent, clean "disabled" response | sent |
| Rest of the app | fully working | fully working |

Set it to `true` only after filling in `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USERNAME` and `SMTP_PASSWORD`. Gmail needs an **App Password**, not your
account password.

Verification is a request, never a gate — `/login` does not check
`email_verified`, so "Skip for now" leaves a fully usable account.

Without Google credentials the OAuth button still renders but returns an error
page. Fill in `GOOGLE_CLIENT_ID` / `GOOGLE_SECRET_KEY` / `GOOGLE_REDIRECT_URI`
to enable it.

One Groq key covers everything, vision included. Resume upload reads the PDF text
layer first; a scanned PDF has none, so its pages are rendered to PNG and read by
`qwen/qwen3.8-27b`, hardcoded.

---

## Job alerts with n8n

A user creates an alert in the Jobs page (roles, locations, email, schedule). The
backend stores it and schedules it. **n8n is the piece that actually fires it** —
it polls for alerts that are due, runs each one, and emails the result.

Two endpoints do this. They are the only routes in the app that are **not**
authenticated with a user JWT:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/jobs/alerts/due` | `GET` | Alerts whose `next_run_at` has passed |
| `/api/jobs/alerts/{alert_id}/run` | `POST` | Run one alert, return its new jobs |

They take `X-Service-Key` instead, checked against `N8N_SERVICE_KEY` in constant
time. The split is deliberate: `GET /alerts` returns every user's email address
and `/{id}/run` spends SerpApi quota, so an open door here is not an option. If
`N8N_SERVICE_KEY` is unset these routes fail closed with a 503 rather than
allowing anything through.

### 1. Expose the backend

n8n runs on its own machine, so `localhost:8000` will not reach it. Use a tunnel
(any of these work):

```bash
ngrok http 8000
# or
cloudflared tunnel --url http://localhost:8000
```

Copy the HTTPS URL it prints.

### 2. Import the workflow

`Job Alert System.json` in the repo root is the ready workflow. In n8n:
**Workflows → Import from File** and select it.

### 3. Set the two variables it needs

The workflow ships with placeholders so it is safe to commit. Set these inside
n8n (**Settings → Variables**, both flagged as available everywhere):

| Variable | Value |
|---|---|
| `QUESTAI_BACKEND_URL` | The tunnel URL from step 1, with no trailing slash |
| `N8N_SERVICE_KEY` | The **same** value you set as `N8N_SERVICE_KEY` in `.env` |

That key must match, or every request returns 403.

### 4. Connect Gmail

The **Send Job Alert Email** node uses n8n's built-in Gmail node. Select it and
pick your Gmail credential — **Import from Google** is the fastest path. Then
replace the `To` field with `{{ $json.email }}` so it goes to the user who set the
alert rather than to you.

### 5. Activate

Toggle the workflow to **Active**. It runs every 5 minutes on a schedule trigger,
polls `/alerts/due`, and loops over whatever comes back. Alerts with nothing new
skip the email.

### Testing without waiting 5 minutes

```bash
# Make an alert due right now, with your own email and target role:
curl -H "X-Service-Key: <your key from .env>" \
  "http://localhost:8000/api/jobs/alerts/due?now=2026-09-25T09:01:00+05:30"

# Then run it through the local tunnel:
curl -X POST -H "X-Service-Key: <your key>" \
  "<tunnel-url>/api/jobs/alerts/<alert_id>/run"
```

The `?now=` parameter is optional and exists only for testing — it overrides what
"due" means.

### How the workflow runs

```
Every 5 Minutes  ──▶  Get Due Alerts  ──▶  Split Due Alerts
                                                      │
                                              Loop Over Alerts
                                                      │
                                    ┌─────────────────┴──────────────────┐
                                    ▼                                    ▼
                               Run Alert                          (next alert)
                                    │
                            Has New Jobs?
                              │          │
                             yes         no
                              ▼          ▼
                       Build Email    skip
                              │
                       Send Job Alert Email
```

**Everything is optional except the backend.** A fresh clone works fully without
n8n — alerts are stored and editable, they just never fire on a schedule. The
in-app "run now" path does not need n8n either.

---

## SerpApi usage

SerpApi is not an add-on here — it is the product's entire search surface.
Eight engines across six tool modules:

| Engine | Agent | Implementation |
|---|---|---|
| `google` | Research | `research/tools/search.py` — `google_search` |
| `google_scholar` | Research | `research/tools/search.py` — `google_scholar_search` |
| `google_news` | Research | `research/tools/search.py` — `google_news_search` |
| `google_shopping` | Shopping | `shopping/tools/google_shopping.py` |
| `amazon` | Shopping | `shopping/tools/amazon.py` |
| `google_flights` | Travel | `travel/tools/google_flights.py` |
| `google_hotels` | Travel | `travel/tools/google_hotels.py` |
| `google_jobs` | Jobs | `job/tools/google_jobs.py` |

Every non-jobs engine goes through one shared client,
`backend/agents/shared/serpapi_client.py`, which owns the shared connection and
retries one transient provider failure (429/5xx/timeout). A 400 is never
retried — the request itself is wrong, so a retry would burn a credit to fail
identically. Jobs keeps its own client.

Two integrations are worth calling out, because they are the parts that are easy
to get wrong:

**Google Flights runs a full three-step token chain.** A single search is not
enough to show return legs or booking options:

```
departure_token  ──▶  return-leg options  ──▶  booking_token  ──▶  booking_options
        google_flights           google_flights              google_flights         google_flights
```

Implemented as `search_flights`, `get_return_leg_options` and
`get_booking_options` in `google_flights.py`. Each extra step costs another SerpApi
credit, so the code deliberately never calls them speculatively.

**Google Jobs retries unresolvable locations — but only on a 400.** SerpApi does
not fuzzy-match a location it cannot resolve; it returns a bad-request error.
`google_jobs.py` retries with corrected spellings, and it distinguishes a bad
location from a quota, network or auth failure so those surface immediately
instead of burning the retry budget. Up to three searches are then run in parallel
with `ThreadPoolExecutor`, preserving input order because the normalizer depends
on it.

> Jobs needs a resolvable location. `remote` on its own returns nothing, because
> Google matches on a city or region, not a work mode.

### Response shapes

`google_news` returns no article text, and `google_scholar` puts the publication
year inside a citation string rather than a `year` field. Both are handled in
`search.py` and both are covered by `verify_parsers.py`, which asserts that
every engine survives the downstream `process_sources()` filter.

---

## The universal layer

`backend/agents/router/` is what makes this one product instead of six.

**`services/catalog.py`** is the single registry of every specialist — used by
both the intent classifier and the Assistant's system prompt, so they can never
disagree about what agents exist. Adding a specialist makes it routable and
documented in one edit.

**`services/intent.py`** classifies a free-text query with a deliberate
escalation ladder, so the common cases cost nothing:

```
chit-chat regex  ──▶  LLM classification  ──▶  deterministic keyword fallback
   (free)              (8s timeout)              (free, never fails)
```

It returns the chosen agent, a short reason, a confidence score, and the
pre-extracted form fields. Design rules baked into the module:

- It **only chooses and pre-fills**. It never runs a search — the user stays in
  control of spending.
- Anything the LLM cannot decide falls back to keywords, then to the Assistant.
  It never routes to a paid specialist by guessing and never returns a 500.
- Extracted fields are normalised on the way out: ISO dates, numeric counts,
  comma-split lists, and blank values dropped so the frontend only sees real
  data.

`POST /api/agent/route` exposes it. The response travels to the destination page
in React Router's `location.state` rather than the URL, so a page refresh cannot
re-apply values the user has since edited — `frontend/src/shared/useRouterPrefill.js`
reads it, and every agent page calls that one hook.

---

## The six agent graphs

Every specialist is a real LangGraph `StateGraph`, not a single prompt. Across
all six there are **34 nodes and 10 conditional edges**, including two bounded
feedback loops.

| Graph | Nodes | Conditional edges | Shape |
|---|---|---|---|
| **Research** | 9 | 2 | `planner → router → collector → evaluator → gap_analyzer`, then a conditional edge re-enters `collector` while evidence gaps remain (bounded by `max_rounds`), then `synthesizer → validator`, with a second conditional edge allowing exactly one resynthesis on validation failure |
| **Trips** | 8 | 3 | `extract → validate → merge_answers → detect_impact → load_session → update_state → dispatch → synthesize`; `detect_impact` re-runs only the sub-agents a revision actually affects |
| **Jobs** | 8 | 2 | `input_analyzer → resume_vision_parser → query_analyzer → profile_builder → validate_profile → search_planner → google_jobs_search → normalize_validate`, branching after `input_analyzer` and `validate_profile` |
| **Flights** | 3 | 1 | `extract_params → validate_params → search_flights` |
| **Hotels** | 3 | 1 | `extract_params → validate_params → search_hotels` |
| **Shopping** | 3 | 1 | `extract_params → validate_params → search_shopping` — no LLM in the loop |

Flights and Hotels share one graph builder (`travel/agent/graph.py`) that
registers the same three node names twice — once bound to the flight tools, once
to the hotel tools — so each search runs a three-node path. Trips is its own
eight-node graph in `trip_graph.py`.

Two patterns are worth noting:

- **Research is self-critical.** `gap_analyzer` inspects what was collected and
  sends the graph back for another round if a sub-question is still unanswered;
  `validator` then checks the synthesis and permits one rewrite if it finds
  unsupported claims.
- **Trips asks before it runs.** Its validator returns
  `[{field, question, why, options}]` and the session parks in `awaiting_input`
  until answered, so a half-specified trip never becomes a wrong itinerary.

Long-running graphs run as background tasks. Research (`POST /api/research/run`)
and Trips (`POST /api/trips/plan`) return `202`, report per-node progress to
MongoDB, and are polled by the frontend; Research additionally exposes
`POST /{session_id}/cancel`. Shopping, Flights, Hotels and Jobs are synchronous
requests. Every agent's session history supports delete.

---

## Architecture

```
frontend/  React 19 + Vite (port 5173) — app, auth, all six agent UIs
backend/   FastAPI + LangGraph (port 8000)
             auth/          JWT + refresh, bcrypt, email OTP, Google OAuth
             agents/
               router/      the universal layer (catalog + intent classifier)
               research/    9-node graph: web + scholar + news, with evidence
               travel/      flights, hotels, and the 8-node trip planner
               shopping/    google_shopping + amazon, price normalisation
               job/         resume parsing, matching, alerts, n8n scheduler
               assistant/   conversational fallback for everything else
             database/      MongoDB repositories per domain
```

Auth is JWT access + refresh with type-tagged payloads and cross-type rejection,
bcrypt password hashing, email OTPs stored as SHA-256 hashes, and Google OAuth.
The two machine-only n8n endpoints take a shared `X-Service-Key` instead of a
user token, compared in constant time and failing closed with a 503 when unset.

---

## API surface

All routes require a JWT except `/health`, `/api/auth/*`, and the two n8n
endpoints.

| Prefix | Purpose |
|---|---|
| `/api/auth` | signup, login, refresh, me, forgot/reset, OTP, Google OAuth |
| `/api/agent/route` | universal intent routing — the layer described above |
| `/api/assistant/chat` | stateless conversational fallback |
| `/api/research` | run, history, cancel, delete |
| `/api/shopping`, `/api/flights`, `/api/hotels`, `/api/trips` | search, history, session delete |
| `/api/jobs` | resume profile CRUD, search, history, delete |
| `/api/jobs/alerts` | recurring job alerts; `/due` and `/{id}/run` are the n8n surface |

Agent endpoints share one shape throughout: `POST /search` → `202` → poll
`GET /history` → resume `GET /{session_id}`.

---

## Project layout

```
backend/
  main.py                  FastAPI app, router mounting, index creation
  auth/                    config, database, security, routes, mail
  agents/
    router/                universal layer
    research/ shopping/ travel/ job/ assistant/
  database/                MongoDB repositories
frontend/src/
  auth/                    login, signup, Home (the universal entry point)
  research/ shopping/ travel/ jobs/
  shared/                  agents registry, useRouterPrefill, api client
```

---

## Tests

```bash
cd frontend && npm test
```

No network and no API keys needed. Three suites:
- `test_agents.cjs` — the frontend agent registry and the backend catalog agree:
  ids are unique, every agent is selectable, and every path matches
- `test_merge_fields.cjs` — router fields merge with per-page parsers, and the
  router wins on conflict
- `test_currency.cjs` — budget parsing (symbols, `k` suffixes, bare numbers)

On the backend, `verify_parsers` checks the research parsers against live SerpApi
response shapes and confirms every engine produces at least one source that
survives `process_sources()`. Costs 3 searches. It exists because those parsers
originally shipped unverified, which turned out to matter: `google_news` returns
no `snippet`, and `process_sources()` discards sources with an empty snippet, so
the entire news branch was being dropped without any error being raised.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `/health` ok, every authenticated request 401/403 | JWT secret is the default `""`. Set `JWT_SECRET_KEY`. |
| Auth works, SerpApi calls return 403 | `SERP_API_KEY` is wrong or expired. |
| Everything works on localhost, not from n8n | n8n needs a public URL. Use a tunnel and update `QUESTAI_BACKEND_URL`. |
| n8n requests return 403 | `N8N_SERVICE_KEY` in n8n does not match the one in `.env`. |
| n8n requests return 503 | `N8N_SERVICE_KEY` is unset in `.env`. These routes fail closed on purpose. |
| Mongo queries hang | Atlas cluster is not allowing your IP. Add it to the access list. |
| Job search returns 0 results | Google Jobs needs a resolvable location. "remote" alone is not a city — include a real one. |
| Resume parses but finds nothing | The profile needs skills, which come from the resume text or vision pass. |
| Forgot password, reset returns 400 | `MAIL_ENABLED` is `false`. Password reset is the one feature that needs real email. |

---

## License

MIT — see [LICENSE](LICENSE).

Built for the SerpApi India Hackathon 2026. Not affiliated with or endorsed by
SerpApi.