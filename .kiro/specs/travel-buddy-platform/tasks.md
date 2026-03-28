# Travel Buddy — Implementation Tasks

## Task 1: Project Scaffolding & Monorepo Setup

- [x] 1.1 Initialize the monorepo structure with `frontend/`, `backend/`, and `infra/` directories
- [x] 1.2 Create `frontend/` as a Next.js 15 app with TypeScript, App Router, and Tailwind CSS
- [x] 1.3 Install and configure Shadcn/UI in the frontend
- [x] 1.4 Create `backend/` with Python project structure (`pyproject.toml`, `requirements.txt`, `lambdas/`, `shared/`)
- [x] 1.5 Create `infra/` as a CDK TypeScript project (`cdk init app --language typescript`)
- [x] 1.6 Add a root `README.md` with project overview, setup instructions, and architecture summary
- [x] 1.7 Git commit and push: `feat: scaffold monorepo with frontend, backend, and infra`

## Task 2: CDK Infrastructure — Storage & Auth

- [x] 2.1 Create `storage-stack.ts` with S3 bucket for document uploads (versioned, lifecycle rules, CORS for frontend uploads)
- [x] 2.2 Create DynamoDB tables in `storage-stack.ts`: Trips table (PK: `USER#userId`, SK: `TRIP#tripId`), ScoutResults table, Documents table, AgentRuns table — all with on-demand billing and TTL where specified
- [x] 2.3 Create `auth-stack.ts` with Cognito User Pool (email/password sign-up, email verification) and User Pool Client for the frontend
- [x] 2.4 Wire up the CDK app entry point (`bin/app.ts`) to instantiate storage and auth stacks
- [x] 2.5 Git commit and push: `feat(infra): add storage and auth CDK stacks`

## Task 3: CDK Infrastructure — API Gateway & Lambda Functions

- [x] 3.1 Create `api-stack.ts` with REST API Gateway and Cognito authorizer
- [x] 3.2 Create Trip Lambda function (`backend/lambdas/trip/handler.py`) with CRUD operations: create, list, get, update, delete trips in DynamoDB
- [x] 3.3 Create Document Lambda function (`backend/lambdas/document/handler.py`) with presigned URL generation for S3 uploads and document listing/detail endpoints
- [x] 3.4 Create Chat Lambda function (`backend/lambdas/chat/handler.py`) as a stub that accepts user messages and returns placeholder responses
- [x] 3.5 Create Briefing Lambda function (`backend/lambdas/briefing/handler.py`) as a stub that returns placeholder briefing data
- [x] 3.6 Define all API routes in CDK connecting endpoints to Lambda functions with proper IAM permissions
- [x] 3.7 Create shared Python utilities: `shared/models.py` (Pydantic models for Trip, Document, ScoutResult), `shared/dynamo.py` (DynamoDB helper), `shared/config.py` (env config)
- [x] 3.8 Git commit and push: `feat(infra): add API Gateway, Lambda functions, and shared utils`

## Task 4: Document Ingestion Pipeline

- [x] 4.1 Add S3 event notification in CDK that triggers a Lambda on object upload to the `uploads/` prefix
- [x] 4.2 Implement document processing Lambda: receive S3 event, call Amazon Textract `analyze_document` for text extraction
- [x] 4.3 Structure extracted text into JSON (dates, locations, costs, confirmation numbers) using Bedrock Claude for intelligent parsing
- [x] 4.4 Implement embedding generation using Amazon Titan Embed v2 via Bedrock runtime
- [x] 4.5 Implement Pinecone upsert: store embeddings with metadata (userId, tripId, docId, contentType, location)
- [x] 4.6 Update Documents table status through the pipeline: `uploaded` → `processing` → `parsed` / `failed`
- [-] 4.7 Git commit and push: `feat(backend): add document ingestion pipeline with Textract and embeddings`

## Task 5: LangGraph Agent Orchestration

- [ ] 5.1 Set up LangGraph dependency in backend and create the agent Lambda handler (`backend/lambdas/agent/handler.py`)
- [ ] 5.2 Implement Scout agent graph (`graphs/scout.py`): Fetch Prices → Evaluate Price → (under budget: Alert User) / (over budget: Schedule Rescan) → Save Results
- [ ] 5.3 Implement Firecrawl tool (`tools/firecrawl_tool.py`) for web scraping flight and hotel prices
- [ ] 5.4 Implement Tavily tool (`tools/tavily_tool.py`) as a fallback web search tool
- [ ] 5.5 Implement Gym Finder graph (`graphs/gym_finder.py`) using Google Places API tool (`tools/google_places_tool.py`)
- [ ] 5.6 Implement Summarizer graph (`graphs/summarizer.py`) that compiles trip data into daily briefings using Bedrock Claude
- [ ] 5.7 Implement weather tool (`tools/weather_tool.py`) using OpenWeatherMap API
- [ ] 5.8 Implement Pinecone query tool (`tools/pinecone_tool.py`) for semantic search over parsed documents
- [ ] 5.9 Add agent decision logging: each node records its decisions to the AgentRuns DynamoDB table
- [ ] 5.10 Git commit and push: `feat(backend): add LangGraph agent orchestration with tools`

## Task 6: EventBridge Scheduled Agent Runs

- [ ] 6.1 Create `events-stack.ts` in CDK with EventBridge rule that triggers the Agent Lambda every 6 hours
- [ ] 6.2 Implement the Agent Lambda entry point to iterate over all active trips and run the Scout agent for each
- [ ] 6.3 Add EventBridge rule for daily briefing generation (runs once per morning per active trip)
- [ ] 6.4 Git commit and push: `feat(infra): add EventBridge scheduled agent runs`

## Task 7: Frontend — Trip Management UI

- [ ] 7.1 Create API client library (`lib/api.ts`) with typed fetch wrappers for all backend endpoints, including Cognito JWT handling
- [ ] 7.2 Implement Cognito auth flow in the frontend: sign-up, sign-in, sign-out using `@aws-amplify/auth`
- [ ] 7.3 Build Trip creation form: destination input (with geocoding), date picker, budget, interests, fitness preferences, equipment preferences
- [ ] 7.4 Build Trip list page showing all user trips with status badges and key details
- [ ] 7.5 Build Trip detail page showing scout results, documents, POIs, and briefing for a selected trip
- [ ] 7.6 Git commit and push: `feat(frontend): add trip management UI with auth`

## Task 8: Frontend — Map, Chat & Document Upload

- [ ] 8.1 Integrate MapLibre GL JS: display trip destination markers, hotel locations, and POI pins on an interactive map
- [ ] 8.2 Build document upload component with drag-and-drop using presigned S3 URLs, showing upload progress and parsing status
- [ ] 8.3 Build chat interface component: message input, message history, streaming-style response display
- [ ] 8.4 Connect chat UI to the `/chat` backend endpoint
- [ ] 8.5 Git commit and push: `feat(frontend): add map, chat, and document upload`

## Task 9: Frontend — Daily Briefing & POI Views

- [ ] 9.1 Build daily briefing view: weather card, itinerary timeline, gym of the day, local tips, alerts
- [ ] 9.2 Add PDF export for daily briefing using `react-pdf`
- [ ] 9.3 Build POI discovery view: list of gyms, restaurants, attractions near hotel with ratings, hours, distance
- [ ] 9.4 Build price trends chart for scout results (flight/hotel prices over time)
- [ ] 9.5 Git commit and push: `feat(frontend): add daily briefing and POI views`

## Task 10: Amplify Hosting & Deployment

- [ ] 10.1 Create `amplify-stack.ts` in CDK to configure Amplify Hosting connected to the GitHub repo (main branch)
- [ ] 10.2 Configure Amplify build settings for Next.js 15 (build command, output directory, environment variables)
- [ ] 10.3 Set up AWS Secrets Manager entries for all external API keys (Pinecone, Firecrawl, Tavily, Google Places, OpenWeatherMap)
- [ ] 10.4 Deploy full CDK stack to AWS account and verify end-to-end: frontend loads, API responds, auth works
- [ ] 10.5 Update README with deployment instructions, environment variable list, and architecture diagram
- [ ] 10.6 Git commit and push: `feat(infra): add Amplify hosting and finalize deployment`
