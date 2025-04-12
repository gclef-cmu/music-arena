# Deploying Music Arena to Fly.io

This document provides a step-by-step guide to deploy the Music Arena application to Fly.io.

## Prerequisites

1. **Fly.io Account**: Sign up at [fly.io](https://fly.io/app/sign-up)
2. **Fly CLI**: Install the Fly CLI tool:
   ```bash
   # macOS
   brew install flyctl
   
   # Linux/WSL
   curl -L https://fly.io/install.sh | sh
   
   # Windows (PowerShell)
   iwr https://fly.io/install.ps1 -useb | iex
   ```

3. **Docker**: Used locally for building the image (Fly.io can also build remotely)

## Deployment Steps

### 1. Authenticate with Fly.io

```bash
fly auth login
```

### 2. Launch the Application

Navigate to your frontend directory:

```bash
cd /path/to/music-arena/frontend
```

Initialize the Fly.io application:

```bash
fly launch
```

During the interactive setup:
- Choose a unique app name or accept the generated one
- Select the region closest to your target users
- Choose "No" for PostgreSQL and Redis unless needed

This creates your `fly.toml` configuration file.

### 3. Configure Environment Variables

Set the necessary environment variables for connecting to your backend service:

```bash
# Replace with actual URL of your backend service
fly secrets set BACKEND_URL=https://your-backend-api.fly.dev
```

Additional settings if needed:
```bash
fly secrets set MONITOR_URL=https://your-monitoring-api.fly.dev
fly secrets set FASTCHAT_WORKER_API_TIMEOUT=120
```

### 4. Deploy the Application

```bash
fly deploy
```

This step:
1. Builds a Docker image from your Dockerfile
2. Uploads the image to Fly.io
3. Deploys and starts the application

### 5. Access Your Application

Open your application in a browser:

```bash
fly open
```

Or visit `https://your-app-name.fly.dev` directly.

## Scaling Your Application

### Add More Resources

If you need more memory or CPU:

```bash
fly scale memory 2048  # 2GB RAM
fly scale cpus 2       # 2 CPUs
```

### Multiple Instances

To run more instances for high availability:

```bash
fly scale count 2      # 2 instances
```

## Monitoring and Maintenance

### View Logs

```bash
fly logs
```

### SSH into VM

For troubleshooting:

```bash
fly ssh console
```

### Update Application

After making changes to your code:

```bash
fly deploy
```

### Suspend the Application

To temporarily stop your application (to save costs):

```bash
fly apps suspend
```

Resume it later with:

```bash
fly apps resume
```

## Common Issues

### Connection to Backend Services

If the frontend can't connect to backend services:

1. Verify the backend services are running and accessible
2. Check environment variables with:
   ```bash
   fly secrets list
   ```
3. Review logs for connection errors:
   ```bash
   fly logs
   ```

### Memory or Performance Issues

If experiencing performance issues:

1. Increase memory allocation:
   ```bash
   fly scale memory 2048
   ```
2. Review resource usage on the dashboard at `https://fly.io/apps/your-app-name`

## Automating Deployments

For CI/CD integration, you can use GitHub Actions to automatically deploy on commits:

1. Add GitHub repository secrets:
   - `FLY_API_TOKEN` (get with `fly auth token`)

2. Create `.github/workflows/deploy.yml`:
   ```yaml
   name: Deploy to Fly.io
   on:
     push:
       branches: [main]
   
   jobs:
     deploy:
       name: Deploy app
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - uses: superfly/flyctl-actions/setup-flyctl@master
         - run: flyctl deploy --remote-only
           env:
             FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
   ```