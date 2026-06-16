# Architecture

# VoiceMind AI Architecture

## Overview

VoiceMind AI is a cross-platform AI-powered voice note and knowledge management platform built using a unified React Native codebase and a Python backend.

The architecture follows an **Offline-First**, **Cloud-Synchronized**, and **AI-Augmented** approach.

Key principles:

- Single codebase across platforms
- Offline-first experience
- Client-side transcription
- Cloud-based AI intelligence
- Low operational cost
- Scalable multi-tenant architecture
- Event-driven processing

---

# High-Level Architecture

```text
┌───────────────────────────────────────────────┐
│                  CLIENT APPS                  │
├───────────────────────────────────────────────┤
│ iOS                                           │
│ Android                                       │
│ macOS                                         │
│ Windows                                       │
└───────────────────┬───────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────┐
│             React Native Shared Core          │
├───────────────────────────────────────────────┤
│ UI Layer                                      │
│ Audio Engine                                  │
│ Local Database                                │
│ Sync Engine                                   │
│ AI Transcription Engine                       │
│ Authentication                                │
└───────────────────┬───────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────┐
│                FastAPI Backend                │
├───────────────────────────────────────────────┤
│ Auth Service                                  │
│ Notes Service                                 │
│ Sync Service                                  │
│ Search Service                                │
│ AI Service                                    │
│ Email Service                                 │
│ Notification Service                          │
└───────────────────┬───────────────────────────┘
                    │
    ┌───────────────┼──────────────────┐
    ▼               ▼                  ▼

PostgreSQL      Cloudflare R2     AI Providers
+ pgvector      Audio Storage     OpenAI
                                  Anthropic
                                  Gemini
```

---

# Client Architecture

## Technology Stack

### Framework

- React Native
- TypeScript

### Platforms

- iOS
- Android
- macOS
- Windows

### Shared Code Percentage

Target:

- 90%+ shared code

---

# Client Modules

## UI Layer

Responsibilities:

- Screens
- Navigation
- Components
- Themes
- Accessibility

Structure:

```text
src/
├── screens/
├── components/
├── navigation/
├── hooks/
├── theme/
└── assets/
```

---

## Audio Engine

Responsibilities:

- Voice recording
- Audio buffering
- Audio enhancement
- Streaming transcription

Features:

- Background recording
- Long-running recordings
- Pause / Resume
- Noise reduction

Supported Formats:

- WAV
- MP3
- AAC
- M4A

---

## Transcription Engine

Runs locally on the device.

### Models

- Whisper
- Distil Whisper
- Faster Whisper
- ONNX Runtime models

Responsibilities:

- Real-time transcription
- Offline transcription
- Language detection
- Timestamp generation
- Speaker separation

Benefits:

- Reduced cloud costs
- Improved privacy
- Offline support

---

## Local Storage Layer

Technology:

- SQLite

Stores:

- Audio metadata
- Notes
- Draft summaries
- Pending sync events
- User settings

Purpose:

- Offline operation
- Fast access
- Reliable synchronization

---

## Sync Engine

Responsible for:

- Uploading recordings
- Syncing metadata
- Conflict resolution
- Incremental synchronization

Pattern:

```text
Local Database
       │
       ▼
Sync Queue
       │
       ▼
Background Worker
       │
       ▼
Cloud APIs
```

---

# Backend Architecture

## API Gateway

Technology:

- FastAPI

Responsibilities:

- Request routing
- Authentication
- Rate limiting
- API versioning

Example:

```text
/api/v1
/api/v2
```

---

# Service Layer

## Authentication Service

Responsibilities:

- Registration
- Login
- Token refresh
- Session management

Providers:

- Email
- Google
- Apple
- Microsoft

Authentication Flow:

```text
User
 │
 ▼
Identity Provider
 │
 ▼
FastAPI
 │
 ▼
JWT Access Token
```

---

## Notes Service

Responsibilities:

- Notes CRUD
- Transcript storage
- Metadata management
- Tag management

Entities:

```text
User
Workspace
Folder
Recording
Transcript
Summary
Tag
```

---

## Sync Service

Responsibilities:

- Device synchronization
- Conflict resolution
- Version tracking

Pattern:

```text
Client Changes
      │
      ▼
Change Log
      │
      ▼
Server Merge
      │
      ▼
Updated State
```

---

## AI Service

Responsibilities:

- Summary generation
- Meeting Minutes generation
- Note enhancement
- Knowledge extraction

Supported Operations:

```text
Transcript
    │
    ▼
Prompt Builder
    │
    ▼
LLM Provider
    │
    ▼
Structured Output
```

---

## Search Service

Responsibilities:

- Full-text search
- Semantic search
- Knowledge retrieval

Powered by:

- PostgreSQL
- pgvector

---

## Email Service

Responsibilities:

- Summary delivery
- Meeting minutes delivery
- Report delivery

Providers:

- SMTP
- Gmail
- Outlook

---

# Data Layer

## PostgreSQL

Primary database.

Stores:

```text
users
workspaces
folders
recordings
transcripts
summaries
action_items
tags
devices
sync_events
```

---

## pgvector

Stores embeddings for:

- Notes
- Transcripts
- Summaries
- Documents

Used for:

- Semantic search
- Knowledge retrieval
- AI chat context

---

## Cloudflare R2

Stores:

```text
audio/
exports/
attachments/
```

Benefits:

- Low storage cost
- S3-compatible API
- No egress fees

---

# AI Architecture

## Philosophy

Use AI only where it creates value.

Avoid sending raw audio to LLMs whenever possible.

---

## Transcription Pipeline

```text
Audio Recording
       │
       ▼
On-Device Whisper
       │
       ▼
Transcript
       │
       ▼
Cloud Sync
```

---

## Summary Pipeline

```text
Transcript
      │
      ▼
Prompt Builder
      │
      ▼
OpenAI / Claude / Gemini
      │
      ▼
Summary
      │
      ▼
Database
```

---

## Meeting Minutes Pipeline

```text
Transcript
      │
      ▼
AI Processing
      │
      ▼
Meeting Minutes
      │
      ▼
Action Items
      │
      ▼
Database
```

---

## Knowledge Chat Pipeline

```text
User Question
        │
        ▼
Embedding Search
        │
        ▼
Relevant Context
        │
        ▼
LLM
        │
        ▼
Response
```

---

# NotebookLM-Style Knowledge Layer

## Sources

Supported inputs:

- Voice recordings
- PDFs
- Documents
- Presentations
- Notes

---

## Indexing Pipeline

```text
Document
    │
    ▼
Chunking
    │
    ▼
Embeddings
    │
    ▼
pgvector
```

---

## Retrieval Pipeline

```text
Question
   │
   ▼
Embedding Generation
   │
   ▼
Similarity Search
   │
   ▼
Relevant Chunks
   │
   ▼
LLM Response
```

---

# Security Architecture

## Authentication

- OAuth2
- JWT
- Refresh Tokens

---

## Encryption

### In Transit

- TLS 1.3

### At Rest

- Database encryption
- Storage encryption

---

## Access Control

Role-based permissions:

```text
Owner
Admin
Editor
Viewer
```

---

# Deployment Architecture

## Frontend

Build Targets:

```text
iOS
Android
macOS
Windows
```

Distribution:

- App Store
- Google Play
- Microsoft Store
- Direct Desktop Distribution

---

## Backend

Deployment Options:

- Railway
- Fly.io
- Render
- AWS

Containerization:

```text
Docker
Docker Compose
```

---

# Scalability Strategy

## Horizontal Scaling

Stateless APIs.

```text
Load Balancer
      │
      ├── API Instance 1
      ├── API Instance 2
      └── API Instance N
```

---

## Database Scaling

Future:

- Read replicas
- Partitioning
- Query optimization

---

## Storage Scaling

Cloudflare R2 scales independently from application infrastructure.

---

# Monitoring

## Metrics

- API latency
- Error rates
- Sync failures
- AI processing duration
- Search performance

Tools:

- Grafana
- Prometheus

---

# Future Architecture Enhancements

## Phase 2

- Real-time collaboration
- Shared workspaces
- Team notes

## Phase 3

- AI Agents
- Automated workflows
- Calendar integrations
- CRM integrations

## Phase 4

- Enterprise SSO
- Audit logs
- Compliance controls
- Advanced governance

---

# Architecture Goals

- Single codebase
- Offline-first experience
- Multi-language support
- Low infrastructure costs
- Fast synchronization
- AI-native workflows
- Enterprise-ready scalability
- Secure by design
