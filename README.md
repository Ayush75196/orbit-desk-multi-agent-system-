# Multi-Agent Productivity Assistant

This project demonstrates a multi-agent AI system for managing tasks, schedules, and notes with:

- A primary coordinator agent
- Specialized sub-agents for planning, scheduling, and knowledge capture
- Durable persistence with Firestore
- Multiple tools integrated through MCP-style servers
- Vertex AI as the LLM provider
- A FastAPI service that is easy to run in Google Cloud Shell Editor
- A chat-style browser UI for normal users

## Architecture

```text
User Request
    |
    v
Coordinator Agent (Vertex AI)
    |
    +--> Planning Agent
    +--> Scheduling Agent
    +--> Knowledge Agent
    |
    v
Workflow Executor
    |
    +--> MCP Calendar Server
    +--> MCP Task Server
    +--> MCP Notes Server
    |
    v
SQLite Database
```

## Features

- Breaks down a natural-language request into a multi-step workflow
- Understands plain human-language requests such as "show my tasks", "schedule a meeting tomorrow", and "save this as a note"
- Can search the web for general queries and show readable results in the UI
- Delegates work to sub-agents
- Calls calendar, task, and notes tools through MCP-compatible JSON-RPC over stdio
- Stores users, workflow runs, tasks, events, and notes in SQLite
- Exposes REST endpoints for running workflows and inspecting stored data
- Serves a polished chat interface at `/`

## Project Structure

```text
src/app/
  agents/
  mcp/
  models/
  services/
  app.py
  config.py
  db.py
servers/
  calendar_server.py
  notes_server.py
  task_server.py
Dockerfile
```

## Run In Google Cloud Shell Editor

1. Open the project in Google Cloud Shell Editor.
2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```bash
cp .env.example .env
```

Set these values:

- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `VERTEX_MODEL`
- `FIRESTORE_DATABASE`

5. Authenticate in Cloud Shell if needed:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

6. Start the API:

```bash
uvicorn src.app.app:app --reload --host 0.0.0.0 --port 8080
```

7. Open the web UI:

```text
http://localhost:8080
```

## Example Request

```bash
curl -X POST http://localhost:8080/workflows/run \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "request": "Plan a project kickoff next Tuesday, create follow-up tasks, and save meeting notes."
  }'
```

## Example Workflow

The system can:

- Create a calendar event for the kickoff
- Create tasks for stakeholders
- Save meeting notes or summaries
- Record workflow execution history in the database

## Deploy To Cloud Run

Enable services:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com firestore.googleapis.com
```

Deploy the app:

```bash
gcloud run deploy orbit-desk \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,VERTEX_MODEL=gemini-2.5-pro,FIRESTORE_DATABASE='(default)'
```

After deployment, Google Cloud prints the live service URL. Open that URL in your browser.

## Production Note

- This demo uses SQLite.
- On Cloud Run, `FIRESTORE_DATABASE='(default)'` is ephemeral and may be reset between container restarts.
- For production durability, switch persistence to Cloud SQL, Firestore, or another managed database.

## Notes

- The MCP servers in `servers/` are lightweight local demo servers that follow the same interaction pattern as MCP JSON-RPC tool servers.
- You can replace them with real calendar, task manager, or notes MCP servers later without changing the coordinator flow.
- If Vertex AI is unavailable, the coordinator falls back to deterministic planning so the demo remains usable.
