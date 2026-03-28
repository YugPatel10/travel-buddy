# Travel Buddy — Design Document

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS Amplify Hosting                         │
│                     (Next.js 15 + Shadcn/UI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Trip Mgmt│ │ Map View │ │ Chat UI  │ │ Doc Mgr  │ │ Briefing │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API Gateway (REST + WS)                        │
│                      + Cognito Authorizer                           │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
  │ Trip    ││ Doc     ││ Agent   ││ Chat    ││ Briefing│
  │ Lambda  ││ Lambda  ││ Lambda  ││ Lambda  ││ Lambda  │
  └────┬────┘└────┬────┘└────┬────┘└────┬────┘└────┬────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
  ┌──────────────────────────────────────────────────────┐
  │                     DynamoDB                          │
  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
  │  │  Trips   │ │  Users   │ │  Agents  │             │
  │  └──────────┘ └──────────┘ └──────────┘             │
  └──────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │              Async Processing Layer                   │
  │                                                      │
  │  S3 Upload ──► Doc Lambda ──► Textract ──► Pinecone  │
  │                                    │                  │
  │                              Titan Embed v2           │
  │                                                      │
  │  EventBridge (cron) ──► Agent Lambda ──► LangGraph   │
  │                          │                            │
  │                    ┌─────┴──────┐                     │
  │                    │  Agents    │                     │
  │                    │ ┌────────┐ │                     │
  │                    │ │ Scout  │ │──► Firecrawl/Tavily │
  │                    │ ├────────┤ │                     │
  │                    │ │ Parser │ │──► Textract         │
  │                    │ ├────────┤ │                     │
  │                    │ │Summary │ │──► Bedrock LLM      │
  │                    │ ├────────┤ │                     │
  │                    │ │GymFind │ │──► Google Places    │
  │                    │ └────────┘ │                     │
  │                    └────────────┘                     │
  └──────────────────────────────────────────────────────┘
```

## Project Structure

```
travel-buddy/
├── frontend/                    # Next.js 15 app
│   ├── src/
│   │   ├── app/                 # App router pages
│   │   │   ├── page.tsx         # Landing / dashboard
│   │   │   ├── trips/           # Trip management pages
│   │   │   ├── chat/            # AI chat interface
│   │   │   └── briefing/        # Daily briefing view
│   │   ├── components/          # Shadcn/UI + custom components
│   │   │   ├── ui/              # Shadcn primitives
│   │   │   ├── map/             # MapLibre components
│   │   │   ├── trip/            # Trip-specific components
│   │   │   └── chat/            # Chat interface components
│   │   └── lib/                 # Utilities, API client, types
│   ├── package.json
│   └── next.config.ts
│
├── backend/                     # Python Lambda functions
│   ├── lambdas/
│   │   ├── trip/                # Trip CRUD operations
│   │   │   └── handler.py
│   │   ├── document/            # PDF upload + parsing trigger
│   │   │   └── handler.py
│   │   ├── agent/               # LangGraph agent orchestrator
│   │   │   ├── handler.py
│   │   │   ├── graphs/          # LangGraph graph definitions
│   │   │   │   ├── scout.py     # Flight & hotel scouting
│   │   │   │   ├── parser.py    # Document parsing flow
│   │   │   │   ├── gym_finder.py
│   │   │   │   └── summarizer.py
│   │   │   └── tools/           # Agent tools
│   │   │       ├── firecrawl_tool.py
│   │   │       ├── textract_tool.py
│   │   │       ├── pinecone_tool.py
│   │   │       ├── google_places_tool.py
│   │   │       └── weather_tool.py
│   │   ├── chat/                # Chat endpoint (queries agents)
│   │   │   └── handler.py
│   │   └── briefing/            # Daily briefing generator
│   │       └── handler.py
│   ├── shared/                  # Shared utilities across lambdas
│   │   ├── models.py            # Pydantic data models
│   │   ├── dynamo.py            # DynamoDB helpers
│   │   ├── embeddings.py        # Titan embed + Pinecone helpers
│   │   └── config.py            # Environment config
│   ├── requirements.txt
│   └── pyproject.toml
│
├── infra/                       # CDK infrastructure (TypeScript)
│   ├── bin/
│   │   └── app.ts               # CDK app entry
│   ├── lib/
│   │   ├── api-stack.ts         # API Gateway + Lambdas
│   │   ├── storage-stack.ts     # S3 + DynamoDB
│   │   ├── auth-stack.ts        # Cognito
│   │   ├── events-stack.ts      # EventBridge rules
│   │   └── amplify-stack.ts     # Amplify Hosting config
│   ├── package.json
│   └── cdk.json
│
└── README.md
```


## Data Models

### DynamoDB Tables

#### Trips Table

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | `USER#<userId>` | Partition key |
| SK | `TRIP#<tripId>` | Sort key |
| tripId | String (ULID) | Unique trip identifier |
| userId | String | Cognito user ID |
| destination | String | Destination city/country |
| destinationCoords | Map `{lat, lng}` | Geocoded coordinates |
| startDate | String (ISO 8601) | Trip start date |
| endDate | String (ISO 8601) | Trip end date |
| status | String | `planning` / `active` / `completed` / `cancelled` |
| preferences | Map | `{budget, interests[], fitnessNeeds[], equipmentPrefs[]}` |
| priceAlerts | Map | `{maxFlight, maxHotelPerNight}` |
| createdAt | String (ISO 8601) | Creation timestamp |
| updatedAt | String (ISO 8601) | Last update timestamp |

#### ScoutResults Table

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | `TRIP#<tripId>` | Partition key |
| SK | `SCOUT#<timestamp>#<type>` | Sort key (type = flight/hotel) |
| resultType | String | `flight` / `hotel` |
| provider | String | Source (airline, booking site) |
| price | Number | Price in USD |
| currency | String | Original currency |
| details | Map | Provider-specific details (route, stops, hotel name, rating) |
| url | String | Booking link |
| scoutedAt | String (ISO 8601) | When this was found |
| TTL | Number | Auto-expire old results (30 days) |

#### Documents Table

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | `USER#<userId>` | Partition key |
| SK | `DOC#<docId>` | Sort key |
| docId | String (ULID) | Unique document ID |
| tripId | String | Associated trip (optional) |
| s3Key | String | S3 object key |
| fileName | String | Original filename |
| parsedData | Map | Extracted structured data |
| status | String | `uploaded` / `processing` / `parsed` / `failed` |
| createdAt | String (ISO 8601) | Upload timestamp |

#### AgentRuns Table

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | `TRIP#<tripId>` | Partition key |
| SK | `RUN#<runId>` | Sort key |
| agentType | String | `scout` / `parser` / `gym_finder` / `summarizer` |
| status | String | `running` / `completed` / `failed` |
| input | Map | Agent input parameters |
| output | Map | Agent results |
| decisions | List | Decision log `[{node, condition, result, timestamp}]` |
| startedAt | String (ISO 8601) | Run start |
| completedAt | String (ISO 8601) | Run end |

### Pinecone Index Schema

- Index name: `travel-buddy`
- Dimension: 1024 (Titan Embed v2)
- Metric: cosine
- Metadata fields:
  - `userId` (string) — for filtering
  - `tripId` (string) — for filtering
  - `docId` (string) — source document
  - `contentType` (string) — `itinerary` / `booking` / `contract` / `general`
  - `extractedDate` (string) — date mentioned in content
  - `location` (string) — location mentioned in content

## API Design

### REST Endpoints (API Gateway)

```
POST   /trips                    # Create a trip
GET    /trips                    # List user's trips
GET    /trips/{tripId}           # Get trip details
PUT    /trips/{tripId}           # Update trip
DELETE /trips/{tripId}           # Cancel trip

GET    /trips/{tripId}/scouts    # Get scout results for a trip
GET    /trips/{tripId}/scouts/trends  # Price trends over time

POST   /documents/upload-url     # Get presigned S3 upload URL
GET    /documents                # List user's documents
GET    /documents/{docId}        # Get document details + parsed data

POST   /chat                     # Send message to AI (returns agent response)

GET    /trips/{tripId}/briefing  # Get today's briefing
POST   /trips/{tripId}/briefing  # Generate briefing on-demand

GET    /trips/{tripId}/pois      # Get POIs (gyms, restaurants, etc.)
POST   /trips/{tripId}/pois/search  # Search for specific POI types
```

All endpoints require Cognito JWT in `Authorization` header.

## Agent Orchestration (LangGraph)

### Scout Agent Graph

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │ Fetch   │ ← Firecrawl/Tavily
                    │ Prices  │
                    └────┬────┘
                         │
                    ┌────▼────┐
              ┌─────│ Evaluate│─────┐
              │     │ Price   │     │
              │     └─────────┘     │
         under budget          over budget
              │                     │
         ┌────▼────┐          ┌────▼────┐
         │ Check   │          │ Schedule│
         │ Calendar│          │ Rescan  │
         └────┬────┘          └────┬────┘
              │                    │
         ┌────▼────┐               │
         │ Alert   │               │
         │ User    │               │
         └────┬────┘               │
              │                    │
              └────────┬───────────┘
                  ┌────▼────┐
                  │  Save   │
                  │ Results │
                  └────┬────┘
                  ┌────▼────┐
                  │   END   │
                  └─────────┘
```

### Document Parser Flow

```
S3 Upload Event
      │
      ▼
┌───────────┐     ┌───────────┐     ┌───────────┐
│  Textract  │────►│ Structure │────►│  Embed &  │
│  Extract   │     │  to JSON  │     │  Store    │
└───────────┘     └───────────┘     └─────┬─────┘
                                          │
                                    ┌─────▼─────┐
                                    │  Update   │
                                    │  DynamoDB │
                                    └───────────┘
```

## External Service Integration

| Service | Purpose | Auth Method |
|---------|---------|-------------|
| Amazon Textract | PDF/image text extraction | IAM role (same account) |
| Amazon Bedrock (Titan Embed v2) | Text embeddings | IAM role (same account) |
| Amazon Bedrock (Claude) | LLM for agent reasoning | IAM role (same account) |
| Pinecone | Vector storage & semantic search | API key (Secrets Manager) |
| Firecrawl | Web scraping (flights, hotels) | API key (Secrets Manager) |
| Tavily | Web search fallback | API key (Secrets Manager) |
| Google Places API | Gym & POI discovery | API key (Secrets Manager) |
| OpenWeatherMap | Weather forecasts | API key (Secrets Manager) |

## Security Design

- Cognito User Pool for authentication with email/password sign-up
- API Gateway Cognito authorizer on all endpoints
- S3 bucket policy: users can only access their own uploads (prefixed by userId)
- DynamoDB: partition key includes userId for row-level access control
- All API keys stored in AWS Secrets Manager, referenced by Lambda env vars
- Lambda functions use least-privilege IAM roles
- HTTPS everywhere (Amplify + API Gateway default)

## Deployment Pipeline

```
GitHub Push (main)
      │
      ├──► Amplify Hosting auto-build (frontend)
      │     └── next build → deploy to Amplify CDN
      │
      └──► Manual CDK deploy (backend) — future: GitHub Actions
            └── cdk deploy --all
```

Phase 1 (MVP): Manual `cdk deploy` for backend changes.
Phase 2: Add GitHub Actions workflow to auto-deploy CDK on push.
