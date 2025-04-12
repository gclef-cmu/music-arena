# Music Arena Frontend

A Gradio-based web application for comparing AI-generated music.

## Local Development

To run the application locally:

```bash
cd frontend
python -m frontend.gradio_web_server --port 8080 --share
```

## Deploying to Fly.io

### Prerequisites

1. Install the Fly CLI
   ```bash
   # macOS
   brew install flyctl
   # or using curl
   curl -L https://fly.io/install.sh | sh
   ```

2. Login to Fly
   ```bash
   fly auth login
   ```

### Deployment Steps

1. Initial setup (first time only)
   ```bash
   cd frontend
   fly launch
   ```
   - When prompted, use the app name "music-arena" (or a different name if you prefer)
   - Select the region closest to you or your target audience
   - Answer "no" to setup PostgreSQL or Redis (unless you need those services)

2. Deploy your application
   ```bash
   fly deploy
   ```

3. Set environment variable for backend service
   ```bash
   fly secrets set BACKEND_URL=https://your-backend-url.fly.dev
   ```

4. Open your deployed application
   ```bash
   fly open
   ```

### Updating Your Application

After making changes to your code:

```bash
fly deploy
```

### Managing Your Application

- View application logs
  ```bash
  fly logs
  ```

- SSH into the application VM
  ```bash
  fly ssh console
  ```

- Scale your application
  ```bash
  fly scale count 2  # Run 2 instances
  ```

- Stop your application
  ```bash
  fly apps suspend
  ```

## Configuration

The application can be configured using environment variables:

- `BACKEND_URL` - URL of the backend service (default: http://localhost:12000)
- `MONITOR_URL` - URL of the monitoring service (default: http://localhost:9090)
- `LOGDIR` - Directory for log files (default: ".")
- `FASTCHAT_WORKER_API_TIMEOUT` - API timeout in seconds (default: 100)
- `FASTCHAT_INPUT_CHAR_LEN_LIMIT` - Maximum input character length (default: 12000)

Set these variables as Fly secrets using:
```bash
fly secrets set KEY=VALUE
```