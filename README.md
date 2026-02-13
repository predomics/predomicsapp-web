# PredomicsApp Web

Modern web application for [gpredomics](https://github.com/predomics/gpredomics) — sparse, interpretable ML model discovery for omics data.

**Architecture:** FastAPI (Python) backend + Vue.js frontend, powered by [gpredomicspy](https://github.com/predomics/gpredomicspy).

## Quick Start

### Backend (development)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Optional: install gpredomicspy for real ML engine
# pip install ../gpredomicspy  # or: cd ../gpredomicspy && maturin develop

uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs

### Frontend (development)

```bash
cd frontend
npm install
npm run dev
```

Frontend at http://localhost:5173

### Docker (production)

```bash
docker compose up --build
```

App at http://localhost:8000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + engine status |
| POST | `/api/projects/` | Create project |
| GET | `/api/projects/` | List projects |
| GET | `/api/projects/{id}` | Get project |
| DELETE | `/api/projects/{id}` | Delete project |
| POST | `/api/projects/{id}/datasets` | Upload dataset |
| POST | `/api/analysis/{id}/run` | Launch analysis |
| GET | `/api/analysis/{id}/jobs/{jid}` | Job status |
| GET | `/api/analysis/{id}/jobs/{jid}/detail` | Full results |

## Project Structure

```
predomicsapp-web/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── core/config.py   # Settings
│   │   ├── models/schemas.py # Pydantic models
│   │   ├── routers/         # API endpoints
│   │   └── services/        # Business logic
│   └── tests/
├── frontend/                # Vue.js SPA
├── data/sample/             # Sample datasets
├── Dockerfile
└── docker-compose.yml
```

## License

GPL-3.0
