# Wisteria — YouTube Creator Analytics Tool

Wisteria helps YouTube creators understand their channel's performance and predict how a new video might perform *before* they publish it — combining a trained ML model, an LLM-powered chat interface, and a live BI/analytics layer, all built on a real cloud data warehouse, containerized and deployed to production.

**Skills demonstrated:** Python · SQL · Snowflake (data warehousing, Snowpark) · Machine Learning (scikit-learn, cross-validation, hyperparameter tuning) · LLM integration (text-to-SQL, vision, prompt engineering) · OAuth2 · FastAPI · Docker · CI/CD (GitHub Actions) · Google Cloud Run · Tableau · Frontend design & development

## Demo

[![Wisteria Demo](https://img.youtube.com/vi/h3BNZOOuMQk/maxresdefault.jpg)](https://youtu.be/h3BNZOOuMQk)

*This video is the best way to see the full app working end-to-end: real Q&A against live data, a pre-publish performance prediction, and the interactive analytics dashboard.*

**Note:** the demo video uses a public creator's dataset (SSSniperWolf's channel) to showcase the analytics with a fully populated history. In the live app, each creator who signs in sees their own real channel's data, scoped correctly per `channel_id` throughout.

## ⚠️ Before you click the live link — please read this first

**🔗 Live app:** [wisteria-712895776373.us-west2.run.app](https://wisteria-712895776373.us-west2.run.app)

This is a genuinely deployed, real production app — not a mockup — but there are two things that will very likely stop you from getting past the login screen, through no fault of the app itself:

1. **You almost certainly cannot sign in.** Google requires any app requesting YouTube's sensitive Analytics scopes to complete an app verification review before the general public can use it — this applies to every developer, at every stage, with no exceptions. Until that review is complete, only a short, manually-approved list of test accounts can sign in at all. If you try with your own Google account, you should expect Google to block it with a warning screen — **this is expected, not a bug.**
2. **The backend depends on a Snowflake trial account**, which will eventually expire. Once it does, the app will stop being able to reach its data warehouse entirely, and may not load at all.

**For these two reasons, the demo video above — not this live link — is the reliable way to see the app actually working.** The live link exists as proof that this is a real, deployed, containerized production service, not just code that runs on one laptop.

## Screenshots

**Login** — real Google OAuth, gating access per creator:

![Login screen](readme-assets/screenshot-login.png)

**Ask Wisteria** — real-time Q&A against a live Snowflake connection:

![Ask Wisteria chat interface](readme-assets/screenshot-ask-wisteria.png)

**Analytics dashboard** — native, per-creator, with interactive date filtering:

![Analytics dashboard](readme-assets/screenshot-analytics.png)

All three interfaces were custom-designed and built from scratch — a cohesive visual identity (custom typography, a hand-designed color system, illustrated branding), careful attention to conversational UX (loading states, graceful error handling, edge-case guidance for incomplete inputs), not just a functional wrapper around the backend.

## Architecture

```
User's browser
      │
      ▼
Google OAuth consent  ◄──────────────►  /login, /oauth/callback
      │                                  (session-based, per-creator)
      ▼
YouTube Data API / Analytics API  →  Ingestion (auth.py, fetch_data.py)
                                            │
                                            ▼
                              Snowflake — RAW schema (per-creator tables)
                                            │
                              SQL views: weekday performance, best-day-to-post,
                              video-vs-channel-baseline (all NULL-safe for
                              creators with insufficient history)
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            Snowpark ML pipeline    FastAPI backend           Tableau (prototype)
            (training, tuning,      /ask  /upload  /analytics  live Snowflake
             Model Registry)              │                    connection
                    │                      ▼
                    └──────────►   Claude API layer
                                   (text-to-SQL + validation,
                                    vision-based thumbnail comparison)
                                            │
                                            ▼
                                 Single containerized app
                            (FastAPI serves both the API and
                             the static frontend, same origin)
                                            │
                                            ▼
                    Docker → GitHub Actions CI/CD → Google Cloud Run
```

## What it does

### Real per-creator login
- Real Google OAuth 2.0 — a creator clicks "Connect Your Channel," authorizes via Google's actual consent screen, and their `channel_id` is stored in a signed session. Every subsequent request (chat, analytics) uses *that specific creator's* real data — not a shared demo account.
- Built on the full OAuth Authorization Code flow with PKCE, correctly handling the stateful `code_verifier` exchange between the initial redirect and the callback — a detail many simpler OAuth implementations get wrong (the two steps happen across separate HTTP requests, so the verifier has to be explicitly persisted server-side between them).

### Ask Wisteria — LLM-powered chat
- Open-ended questions ("What are my average views by category?") are answered by having Claude **generate real SQL against the live schema**, then validate it before execution — a word-boundary regex blocks any DDL statement and requires a `channel_id` filter on every query, so a bad or unscoped generation can never run. Results are summarized back into plain English by a second Claude call — retrieval-augmented generation over **structured, queryable data**, not a vector store.
- Attach a video + thumbnail before publishing to get a **performance tier prediction** (below/typical/above average, relative to that specific channel's own history) from a trained Random Forest model, plus **thumbnail feedback** from Claude's vision model comparing it against that creator's own historical top and bottom performers.

### Analytics dashboard — native, per-creator
- Real KPIs, a best-day-to-post recommendation, and two live charts, all scoped by `channel_id`.
- Interactive date-range filtering (Last 30/90 Days, All Time) recalculates every stat consistently — including the best-day recommendation, which is derived directly from the same filtered dataset as the rest of the page, with a minimum-sample-size guard (`≥5` videos) so a narrow window never confidently recommends a day based on one or two posts.

## ML methodology

- **Target:** performance tier (below/typical/above average), defined by each video's percentile **within its own channel's distribution** (33rd/67th cutoffs) — not a raw view-count regression, so predictions stay meaningful across channels of wildly different scale.
- **Features (24 total):** duration, published hour, title length/word count/has-number/has-question/caps-ratio, plus one-hot encoded weekday and category.
- **No data leakage:** `LIKE_COUNT` and `COMMENT_COUNT` are explicitly excluded, since they don't exist until after a video is published.
- **Tuning:** `RandomizedSearchCV`, 5-fold cross-validation, 20 iterations. Training accuracy (66%) vs. held-out test accuracy (63%) — a ~3-point gap indicating the model isn't overfit.
- **Baseline comparison:** 63% vs. a 33% random baseline (3-class problem). The below-average tier hits 82% precision — the most actionable signal for a creator deciding whether to adjust before publishing.

## Deployment & infrastructure

The app is fully containerized and deployed with a real CI/CD pipeline:

- **Docker:** a single container runs the FastAPI backend, which also serves the static frontend directly (one deployable unit, not two separate services).
- **CI:** every push runs a `pytest` suite (SQL-injection-style validation, ML feature vector correctness, category mapping) via GitHub Actions.
- **CD:** on a successful test run, the same pipeline automatically builds the Docker image, pushes it to Google Artifact Registry, and deploys it to Google Cloud Run — a full `git push` → live deployment pipeline, no manual steps.
- **Secrets:** OAuth credentials are stored in Google Secret Manager and mounted into the container at runtime; all other credentials are injected as environment variables from GitHub Actions secrets — nothing sensitive is ever baked into the image or committed to source control.

**A few real production issues worth mentioning, since they reflect genuine debugging rather than a clean first pass:**
- **PKCE state bug:** the OAuth login and callback steps each created independent `Flow` objects, losing the `code_verifier` that PKCE requires to persist between them — fixed by explicitly storing it in the session.
- **Reverse-proxy HTTPS detection:** Cloud Run terminates HTTPS at its own edge and forwards requests to the container over plain HTTP internally, which made `oauthlib` incorrectly think the connection was insecure — fixed by configuring `uvicorn` to trust Cloud Run's forwarded-protocol headers.
- **Secret-mount directory collision:** an early attempt mounted a secret file directly at `/app` — the same directory as the entire application — which silently replaced the whole directory's contents rather than merging with it, deleting the app in the process. Fixed by mounting to a dedicated `/secrets` path instead.

## Real engineering challenge worth mentioning

While productionizing the model-loading step, the backend intermittently crashed with a low-level `FileNotFoundError` deep inside Snowflake's own connector library — reproducible from a plain script, unrelated to any code in this project. I traced it to a [documented bug in `snowflake-connector-python`](https://github.com/snowflakedb/snowflake-connector-python/issues/1485) specific to GCS-backed Snowflake accounts, fixed by upgrading the connector — which then surfaced a second, legitimate issue: a version-mismatch safety check between the environment used to train the model and the one loading it, resolved by pinning `cloudpickle`/`scikit-learn`/`numpy` versions to match.

## Tableau prototype

Before building the native analytics dashboard, I prototyped the same analysis in **Tableau**, live-connected to Snowflake:

[**View the interactive Tableau dashboard →**](https://public.tableau.com/app/profile/sruti.medavaram/viz/Wisteria-ChannelAnalytics/Dashboard1)

*(Includes a real dashboard action — clicking a category filters the related chart.)*

I kept the final product's analytics native to the app rather than embedding this dashboard, since a single published Tableau view can't personalize per user — the native charts scale correctly to any number of real creators, while Tableau was the right tool for quickly prototyping the analysis itself.

## Tech stack

| Layer | Tools |
|---|---|
| Backend | FastAPI, Python |
| Data warehouse | Snowflake (live connection) |
| ML | Snowpark, scikit-learn, Snowflake Model Registry |
| LLM | Claude API (text-to-SQL, vision) |
| Auth | Google OAuth 2.0 (PKCE), signed sessions |
| Frontend | Vanilla JS, Tailwind CSS, Chart.js |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Cloud | Google Cloud Run, Artifact Registry, Secret Manager |
| BI prototyping | Tableau |

## Known limitations

- **Public sign-in is currently blocked by Google's own app verification process** — not by anything in this codebase. Any app requesting YouTube's sensitive Analytics scopes must pass Google's review before the general public can sign in; until then, only a short list of pre-approved test accounts can complete login. The login and session architecture itself is fully built and confirmed working end-to-end (see Screenshots and Demo above) — this is an external process requirement, not an unfinished feature.
- **The live deployment depends on a Snowflake trial account**, which will eventually expire. Once it does, the backend will lose its connection to the data warehouse entirely and may stop responding. The demo video is the permanent, working record of the app, independent of the live deployment's status at any given time.
- **Data reflects the last ingestion sync**, not a live real-time connection — similar to how YouTube's own Studio analytics and Google Analytics both have their own processing delays.
- **Running this yourself locally requires your own Snowflake account and Google API credentials** (see `.env.example` for what's needed) — this repo doesn't include a working demo environment, since it depends on live, private data infrastructure that only I have access to.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages

cp .env.example .env   # fill in your own Snowflake/API credentials — see
                        # "Known limitations" above, this step requires
                        # infrastructure you'd need to provision yourself

uvicorn backend:app --reload
```

Then open `http://127.0.0.1:8000/index.html` in a browser.

To run with Docker instead:

```bash
docker build -t wisteria .
docker run -p 8080:8080 --env-file .env wisteria
```
