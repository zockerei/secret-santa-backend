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

Setup varies depending how you want to host the application. Example below for a docker-compose that can be used and for
hosting it on an unraid NAS.

### Docker-Compose

The network `br0` is used if you want to use a reverse proxy (npm for example) and host the application on unraid.
Normally not needed

```yaml
services:
  app:
    image: python:3.12-slim
    container_name: secret_santa
    working_dir: /app
    volumes:
      - /mnt/user/appdata/secret-santa:/app
    command: sh -c "pip install --no-cache-dir -r requirements.txt && python app.py"
    build:
      context: /mnt/user/appdata/secret-santa
      dockerfile: Dockerfile
    networks:
      - br0

networks:
  br0:
    external: true
```

Create a `instance/.env` file with the following structure:

```env
SECRET_KEY=secret_key (16 characters)
ADMIN_NAME=admin_name
ADMIN_PASSWORD=password
FLASK_RUN_PORT=your_port (default for flask is 5000)
FLASK_ENV=production (or development, testing)
FLASK_DEBUG=0 (or 1 to enable debugging)
```

Change the `config/logging_config.yaml` file if needed