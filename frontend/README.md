# Research Paper Answer Bot - React + Vite + TypeScript Starter

## Requirements

Node.js 18+ is recommended.

Check:

```powershell
node --version
npm --version
```

## Install

```powershell
npm install
```

## Configure backend URL

Copy:

```text
.env.example
```

to:

```text
.env
```

Default:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

## Start

```powershell
npm run dev
```

Open:

```text
http://localhost:5173
```

## Build

```powershell
npm run build
```

## TypeScript

This project uses:

- TypeScript
- React
- Vite
- Axios
- React Router
- React Markdown

Main TypeScript files:

```text
src/App.tsx
src/main.tsx
src/types.ts
vite.config.ts
```

## Current UI

- Research paper PDF upload
- Backend health check
- Chat/question UI
- Answer area
- Top-3 source cards
- Paper title
- Page number
- Retrieval score

## Backend endpoints

```text
GET  /api/health
POST /api/documents/upload
POST /api/chat
```

The upload and chat endpoints are ready to connect to the FastAPI backend.

## Project architecture

React + TypeScript + Vite
        ↓
FastAPI
        ↓
PDF processing
        ↓
Embeddings
        ↓
ChromaDB
        ↓
Retrieval
        ↓
LLM
        ↓
Answer + Top 3 Sources
