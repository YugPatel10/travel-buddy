# Travel Buddy

AI-powered travel intelligence platform. Provide a destination and dates — Travel Buddy handles flight scouting, hotel recommendations, local discovery, weather briefings, document parsing, and daily trip summaries.

## Architecture

```
Frontend (Next.js 15 + Shadcn/UI)  →  API Gateway + Cognito  →  Lambda Functions  →  DynamoDB
                                                                       │
                                                              ┌────────┴────────┐
                                                              │  Async Layer    │
                                                              │  S3 → Textract  │
                                                              │  EventBridge    │
                                                              │  LangGraph      │
                                                              │  Pinecone       │
                                                              └─────────────────┘
```

- **Frontend** — Next.js 15, App Router, Tailwind CSS, Shadcn/UI, MapLibre GL JS
- **Backend** — Python Lambda functions behind API Gateway with Cognito auth
- **Agents** — LangGraph-orchestrated agents (Scout, Parser, Gym Finder, Summarizer)
- **Infra** — AWS CDK (TypeScript), fully serverless

## Project Structure

```
travel-buddy/
├── frontend/          # Next.js 15 app
├── backend/           # Python Lambda functions + shared utilities
│   ├── lambdas/       # trip, document, agent, chat, briefing
│   └── shared/        # models, dynamo helpers, embeddings, config
├── infra/             # CDK stacks (storage, auth, API, events, amplify)
└── README.md
```

## Prerequisites

- Node.js 18+
- Python 3.11+
- AWS CLI configured with appropriate credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- An AWS account with Bedrock model access enabled (Claude, Titan Embed v2)

## Setup

### 1. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Infrastructure

```bash
cd infra
npm install
npx cdk bootstrap   # first time only
npx cdk deploy --all
```

## Environment Variables

### Lambda Functions (set via CDK)

| Variable | Description |
|----------|-------------|
| `TRIPS_TABLE` | DynamoDB Trips table name |
| `DOCUMENTS_TABLE` | DynamoDB Documents table name |
| `SCOUT_RESULTS_TABLE` | DynamoDB ScoutResults table name |
| `AGENT_RUNS_TABLE` | DynamoDB AgentRuns table name |
| `UPLOAD_BUCKET` | S3 bucket for document uploads |
| `PINECONE_API_KEY_SECRET` | Secrets Manager ARN for Pinecone key |
| `PINECONE_INDEX` | Pinecone index name |

### External API Keys (stored in AWS Secrets Manager)

| Secret | Service |
|--------|---------|
| `travel-buddy/pinecone` | Pinecone vector DB |
| `travel-buddy/firecrawl` | Firecrawl web scraping |
| `travel-buddy/tavily` | Tavily web search |
| `travel-buddy/google-places` | Google Places API |
| `travel-buddy/openweathermap` | OpenWeatherMap |

## Key Features

- **Trip Management** — Create trips with destination, dates, budget, and preferences
- **AI Scout** — Automated flight and hotel price scouting on a schedule (EventBridge)
- **Document Parsing** — Upload PDFs/images, extract data via Textract, embed in Pinecone for semantic search
- **Local Discovery** — Find gyms, restaurants, and attractions near your hotel via Google Places
- **Daily Briefings** — Weather, itinerary, gym of the day, and alerts compiled into a daily summary
- **Chat Interface** — Natural language queries against your trip data and documents
- **Map View** — Interactive MapLibre map with trip destinations, hotels, and POIs

## API Endpoints

All endpoints require a Cognito JWT in the `Authorization` header.

```
POST   /trips                       Create a trip
GET    /trips                       List trips
GET    /trips/{tripId}              Get trip details
PUT    /trips/{tripId}              Update trip
DELETE /trips/{tripId}              Cancel trip
GET    /trips/{tripId}/scouts       Scout results
POST   /documents/upload-url        Get presigned upload URL
GET    /documents                   List documents
POST   /chat                        Chat with AI agents
GET    /trips/{tripId}/briefing     Get daily briefing
GET    /trips/{tripId}/pois         Get nearby POIs
```

## Deployment

- **Frontend**: AWS Amplify Hosting, auto-deploys from `main` branch
- **Backend**: `npx cdk deploy --all` from the `infra/` directory
