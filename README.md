# Secret Santa Website

A web application to manage Secret Santa gift exchanges with automated assignments and message sharing

## Features

### Admin Features
- Add and manage participants
- View and edit past Secret Santa assignments via scoreboard
- Start new Secret Santa rounds with customizable settings
- Option to require messages from all participants before starting
- Track participant history

### Participant Features
- Personal dashboard showing current and past Secret Santa assignments
- Write and save messages for the current year's exchange
- View messages from past Secret Santa partners
- Edit personal login details
- Festive Christmas-themed interface with animated snowflakes and light decorations

### Assignment Logic
- Intelligent assignment system that prevents participants from:
  - Being assigned to themselves
  - Getting the same person they had in the previous 2 years
- Automatic validation of assignments to ensure fair distribution

### Security
- Password-protected accounts for all users
- Role-based access control (admin/participant)
- Secure password hashing

## Database Structure
- Participants table for user management
- Assignments table for Secret Santa pairings
- Messages table for yearly participant messages

## Note
Due to the assignment restrictions (no repeat assignments from previous 2 years), there is a minimum required number of participants for the system to work effectively. For smaller groups, the code must be modified to get good results

## Environment Variables
Create a file named `.env` in the `instance` directory with the following variables:

## Setup and Configuration

### Quick Start (Unraid/Docker)

```bash
# 1. Clone repository
cd /mnt/user/appdata/
git clone https://github.com/yourusername/secret-santa-backend.git
cd secret-santa-backend

# 2. Create .env file (see .env.example)
nano .env

# 3. Deploy
docker-compose up -d

# 4. Create admin user
docker exec -it secret-santa-backend python create_admin.py
```

### Environment Configuration

Create a `.env` file with:

```env
# Database (external PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:password@192.168.0.12:5432/secret_santa

# Security
SECRET_KEY=your-very-long-secret-key-here

# Network (br0 static IP)
BACKEND_IP=192.168.0.14

# CORS
CORS_ORIGINS=["http://192.168.0.15:3000"]

# Optional
LOG_LEVEL=INFO
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Documentation

- **Quick Start:** See [SETUP_UNRAID.md](SETUP_UNRAID.md)
- **Detailed Guide:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Docker Setup:** See [DOCKER_SETUP.md](DOCKER_SETUP.md)
- **Quick Answers:** See [QUICK_ANSWERS.md](QUICK_ANSWERS.md)

### Network Architecture

```
┌─────────────────────────────────────┐
│         br0 Network                  │
├─────────────────────────────────────┤
│  PostgreSQL  → 192.168.0.12:5432    │
│  Backend     → 192.168.0.14:8000    │
│  Frontend    → 192.168.0.15:3000    │
└─────────────────────────────────────┘
```

### Logging

Logging is automatically configured:
- **Console:** Colored output via `docker logs`
- **Files:** Persisted in `./logs/` directory
- **Rotation:** Weekly, keeps 4 weeks of logs

See `logging_config.yaml` for configuration