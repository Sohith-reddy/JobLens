# JobLens AI Client

This is the React frontend for JobLens AI.

## Setup

Due to environment restrictions, dependencies were not automatically installed. Please run:

```bash
cd client
npm install
```

## Development

To start the development server:

```bash
npm run dev
```

## Backend Integration

The client now calls JobLens FastAPI endpoints directly:

- `POST /scoring/text`
- `POST /scoring/url`
- `POST /resume/match`
- `GET /health`
- `GET /rules`

By default, API calls go to:

```bash
http://localhost:8000
```

To override this, set:

```bash
VITE_JOBLENS_API_BASE_URL=http://your-api-host:8000
```

## Features

- **Home**: Job Description Input & Resume Upload.
- **Dashboard**: Scam Analysis, Company Verification, Resume Match, and Review Sentiment.
- **Components**: Built with React, Tailwind CSS, and shadcn/ui patterns.
