# PulseLink Backend

FastAPI backend for the PulseLink real-time alert notification system.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file from template:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the server:
```bash
uvicorn main:app --reload
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (min 32 chars) |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry (default: 1440) |

## API Endpoints

- `POST /api/auth/login` - User login
- `POST /api/auth/signup` - User registration
- `GET /api/health` - Health check
- `WS /ws/{user_id}` - WebSocket for real-time updates

## Default Admin

On first run, a default admin user is created:
- Username: `admin`
- Password: `admin123`

**⚠️ Change the admin password immediately in production!**
