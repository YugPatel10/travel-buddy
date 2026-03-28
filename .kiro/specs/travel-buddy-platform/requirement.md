# Travel Buddy — AI-Powered Travel Intelligence Platform

## Overview
Travel Buddy is a general-purpose travel intelligence platform where users provide a destination and travel dates, and the platform handles everything else — flight scouting, hotel recommendations, local discovery (gyms, restaurants, attractions), weather briefings, document parsing (travel PDFs, booking confirmations), and daily trip summaries.

## Requirement 1: User Trip Input & Management
### User Story
As a traveler, I want to specify where and when I want to travel so the platform can handle all research and planning for me.

### Acceptance Criteria
- User can create a trip by providing: destination(s), travel dates, and optional preferences (budget, interests, fitness needs)
- User can manage multiple trips simultaneously
- User can update or cancel trips
- System validates dates and destinations before processing

---

## Requirement 2: AI Scout Agent (Flight & Hotel Discovery)
### User Story
As a traveler, I want the platform to continuously scout for the best flights and hotels so I don't have to manually search across multiple sites.

### Acceptance Criteria
- Scout agent runs on a configurable schedule (default: every 6 hours) via EventBridge
- Agent searches for flights and hotels matching trip criteria
- Price drop alerts when fares fall below user-defined thresholds
- Results are stored and compared over time to show price trends
- Agent uses Firecrawl/Tavily for web scraping that bypasses anti-bot protections

---

## Requirement 3: Document Ingestion & Parsing
### User Story
As a traveler, I want to upload travel-related documents (booking confirmations, itineraries, contracts) and have the platform extract and organize the information automatically.

### Acceptance Criteria
- User can upload PDFs and images to S3 via the dashboard
- Lambda triggers on S3 upload, sends to Textract/LlamaParse for extraction
- Extracted data is structured into JSON (dates, locations, costs, confirmation numbers)
- Text is embedded using Amazon Titan Embed v2 and stored in Pinecone for semantic search
- User can query documents naturally: "What's my hotel check-in time in Berlin?"

---

## Requirement 4: Multi-Agent Orchestration (LangGraph)
### User Story
As a traveler, I want intelligent agents that can make decisions based on conditions (e.g., "if flight > $600, keep scouting; if under, check my calendar").

### Acceptance Criteria
- LangGraph orchestrates multiple specialized agents: Scout, Parser, Summarizer, Gym Finder
- Agents maintain state across runs (stateful loops)
- Conditional branching: agents can trigger other agents based on results
- Agent actions and decisions are logged for transparency

---

## Requirement 5: Local Discovery — Gym Finder & Points of Interest
### User Story
As an active traveler, I want the platform to find gyms with specific equipment near my hotels, plus restaurants and attractions.

### Acceptance Criteria
- Gym Finder agent uses Google Places API to locate gyms near accommodation
- User can specify equipment preferences (e.g., "hack squat machine", "Olympic platform")
- Results include ratings, hours, distance from hotel, and equipment details when available
- General POI discovery for restaurants, attractions, and transit options

---

## Requirement 6: Daily Briefing & Summary Generation
### User Story
As a traveler, I want a daily summary that includes weather, scheduled activities, gym recommendations, and any alerts.

### Acceptance Criteria
- System generates a daily briefing for each active trip
- Includes: weather forecast, day's itinerary, gym of the day, local tips
- Briefing available as in-app view and downloadable PDF (react-pdf)
- Delivered on a schedule or on-demand

---

## Requirement 7: Next.js Dashboard with Map Visualization
### User Story
As a user, I want a visual dashboard to manage my trips, view my itinerary on a map, and interact with the AI agents.

### Acceptance Criteria
- Next.js 15+ app with Shadcn/UI component library
- MapLibre integration showing trip routes, hotel locations, POIs
- Document upload interface with drag-and-drop
- Chat interface to query the AI agents naturally
- Trip timeline view with all events, bookings, and alerts
- Responsive design for mobile use while traveling

---

## Requirement 8: AWS Serverless Backend
### User Story
As a developer, I want the backend to be fully serverless on AWS so it scales automatically and costs are minimal when idle.

### Acceptance Criteria
- S3 for document storage
- Lambda functions for processing (PDF parsing, embedding generation, agent triggers)
- EventBridge for scheduled agent runs
- API Gateway for REST/WebSocket endpoints
- DynamoDB for trip metadata, user preferences, and agent state
- Cognito for user authentication
- CDK (TypeScript) for infrastructure as code
- All resources deployed in a single AWS account (855676085285)

---

## Requirement 9: Hosting & Deployment
### User Story
As a developer, I want the entire platform deployed and accessible via the web with automated deployments from GitHub.

### Acceptance Criteria
- Frontend hosted on AWS Amplify Hosting, auto-deploying from the GitHub repo (main branch)
- Backend infrastructure deployed via CDK to the same AWS account
- Optional custom domain via Route 53
- CI/CD: push to main triggers frontend redeploy automatically
- Environment variables managed through Amplify and AWS Secrets Manager for API keys (Pinecone, Google Places, Firecrawl, etc.)
