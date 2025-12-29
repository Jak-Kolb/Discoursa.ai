# Discoursa.ai: Your AI Debate Partner

Discoursa.ai is an intelligent debate platform designed to play "Devil's Advocate." It helps users refine their arguments and critical thinking skills by adopting and strictly maintaining an opposing stance, no matter what position the user takes.

## Key Features

*   **Anti-Sycophancy**: The AI is prompted to strictly disagree with you, avoiding the common "pleasing" bias of LLMs.
*   **Dual-Mode Operation**:
    *   **Web App**: A Next.js chat interface for private, real-time debates.
    *   **Twitter Bot**: A worker process that monitors mentions and engages in public debates on X (formerly Twitter).
*   **RAG-Powered**: Uses Retrieval Augmented Generation to ground arguments in a corpus of facts (when available).
*   **Evaluation Metrics**: Analyzes debates for "Opposition Drift" (did it cave?) and "Hallucinations".

## Technology Stack

*   **Frontend**: [Next.js 13](https://nextjs.org/) (App Router), TailwindCSS, React.
*   **Backend**: [FastAPI](https://fastapi.tiangolo.com/), SQLAlchemy.
*   **Database**: PostgreSQL 17 with `pgvector` extension (for vector search).
*   **AI**: OpenAI API (`gpt-4o-mini`).

## Getting Started

### Prerequisites

*   Node.js & npm
*   Python 3.10+
*   PostgreSQL 17+ (must support `pgvector` extension)

### 1. Database Setup

Ensure PostgreSQL is running and the `pgvector` extension is installed.

```bash
# macOS (using Homebrew)
brew install postgresql@17
brew services start postgresql@17
# Link strictly if needed
brew link postgresql@17 --force

# Create DB and Extension
createdb debate_sessions
psql -d debate_sessions -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 2. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` to include your API keys:
*   `DATABASE_URL=postgresql://localhost/debate_sessions`
*   `OPENAI_API_KEY=sk-...` (Required for debate logic)
*   `ENCRYPTION_KEY`: Generate one using `openssl rand -hex 32`.
*   `NEXTAUTH_SECRET`: Generate a random string.

### 3. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the API server:
```bash
uvicorn app.main:app --reload
# Server running at http://localhost:8000
```

### 4. Frontend Setup

In a new terminal:
```bash
cd frontend
npm install
npm run dev
# App running at http://localhost:3000
```

## Twitter Bot (Optional)

The project includes a separate worker process for the Twitter bot functionality.

1.  Add Twitter/X API credentials to your `.env` file (`TWITTER_BEARER_TOKEN`, `TWITTER_API_KEY`, etc.).
2.  Run the worker process:

```bash
cd backend
python -m app.worker
```

The bot listens for mentions and replies to tweets containing "Debate this".

## License

[MIT](LICENSE)
