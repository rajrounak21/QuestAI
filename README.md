# QuestAI

**One AI superapp. Four specialist agents behind a single universal layer.**

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
- [SerpApi usage](#serpapi-usage)
- [The universal layer](#the-universal-layer)
- [The six agent graphs](#the-six-agent-graphs)
- [Architecture](#architecture)
- [API surface](#api-surface)
- [Project layout](#project-layout)
- [Tests and verification](#tests-and-verification)
- [License](#license)

---

## Why this exists

Most AI products make you choose a tool before you can start. You pick
"Research" or "Jobs" or "Travel", then fill in that tool's form, even when your
actual question is simpler than the form.

QuestAI inverts that. You describe the outcome you want; the routing layer picks
the specialist and pre-fills what it can infer. The four user-facing
experiences are **Research, Travel, Shopping and Jobs** — Travel covers flights,
hotels and full itineraries through three graphs.

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
# then fill in the four REQUIRED values in .env

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

### 3. Landing site (optional)

A separate static marketing site with no backend or auth. It is also served at
`/` inside the app, so you only need this to work on the site standalone.

```bash
cd landing
npm install
npm run dev     # http://localhost:5174
```

### 4. Verify it works

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
(OTP delivery), and `N8N_SERVICE_KEY` (scheduled job alerts). Without SMTP the
app runs but cannot deliver a signup code; without Google credentials the OAuth
button stays hidden.

There is only **one** Groq key — the same `GROQ_API_KEY` makes vision calls.
`GROQ_VISION_MODELS` is not a credential; it is a comma-separated list of model
IDs for the scanned-PDF resume path, and it ships **empty on purpose** because
the models it previously used now return 404/400 on Groq. Leave it empty and Jobs
falls back to text extraction, which handles normal text PDFs correctly.

---

## SerpApi usage

SerpApi is not an add-on here — it is the product's entire search surface.
Eight engines across ten call sites:

| Engine | Agent | Implementation |
|---|---|---|
| `google` | Research | `backend/agents/research/tools/search.py:67` |
| `google_scholar` | Research | `backend/agents/research/tools/search.py:94` |
| `google_news` | Research | `backend/agents/research/tools/search.py:137` |
| `google_shopping` | Shopping | `backend/agents/shopping/tools/google_shopping.py:30` |
| `amazon` | Shopping | `backend/agents/shopping/tools/amazon.py:29` |
| `google_flights` | Travel | `backend/agents/travel/tools/google_flights.py:45` |
| `google_hotels` | Travel | `backend/agents/travel/tools/google_hotels.py:46` |
| `google_jobs` | Jobs | `backend/agents/job/tools/google_jobs.py:242` |

Two integrations are worth calling out, because they are the parts that are easy
to get wrong:

**Google Flights runs a full three-step token chain.** A single search is not
enough to show return legs or booking options:

```
departure_token  ──▶  return-leg options  ──▶  booking_token  ──▶  booking_options
        google_flights           google_flights              google_flights         google_flights
```

Implemented at `google_flights.py:45`, `:92` and `:134`. Each extra step costs
another SerpApi credit, so the code deliberately never calls them speculatively.

**Google Jobs retries unresolvable locations — but only on a 400.** SerpApi does
not fuzzy-match a location it cannot resolve; it returns a bad-request error.
`google_jobs.py:254-279` retries with corrected spellings, and it distinguishes
a bad location from a quota, network or auth failure so those surface
immediately instead of burning the retry budget. Up to three searches are then
run in parallel with `ThreadPoolExecutor`, preserving input order because the
normalizer depends on it.

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
landing/   React 19 + Vite (port 5174) — standalone static marketing site
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
landing/src/landing/       standalone marketing site
```

---

## Tests and verification

```bash
cd frontend && npm test
```

Checks that the frontend agent registry and the backend router agree — ids are
unique, every agent is selectable, and every path matches `catalog.py`. Pure
Node, no network, no API keys.

```bash
.venv/bin/python -m backend.agents.research.tools.verify_parsers
```

Live check that the three research parsers match current SerpApi response shapes
**and** that every engine produces at least one source that survives
`process_sources()`. Costs 3 searches. This exists because those parsers
originally shipped unverified, which turned out to matter: `google_news` returns
no `snippet`, and `process_sources()` discards sources with an empty snippet, so
the entire news branch was being dropped without any error being raised.

---

## License

MIT — see [LICENSE](LICENSE).

Built for the SerpApi India Hackathon 2026. Not affiliated with or endorsed by
SerpApi.