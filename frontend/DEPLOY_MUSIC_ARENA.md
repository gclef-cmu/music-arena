# Deploying to music-arena.fly.dev

Quick guide to deploy the Music Arena application to Fly.io with the app name `music-arena`.

## Prerequisites

1. Install the Fly CLI
   ```bash
   brew install flyctl   # macOS
   ```

2. Login to Fly.io
   ```bash
   fly auth login
   ```

## Deployment Steps

1. Navigate to your frontend directory
   ```bash
   cd /Users/waynechi/dev/music-arena/frontend
   ```

2. Launch the app with the specific name
   ```bash
   fly launch --name music-arena
   ```
   - When prompted, confirm you want to use `music-arena`
   - Select a region close to your users (e.g., `sjc` for San Francisco)
   - Answer "no" to PostgreSQL and Redis setup prompts
   - This will configure your project and create a `fly.toml` file

3. Set your backend service URL
   ```bash
   fly secrets set BACKEND_URL=https://your-backend-url.fly.dev
   ```
   Replace with your actual backend API URL.

4. Deploy the application
   ```bash
   fly deploy
   ```

5. Open your application
   ```bash
   fly open
   ```

Your application will now be accessible at https://music-arena.fly.dev

## Troubleshooting Tips

If you encounter any issues during deployment:

1. Check logs for specific errors:
   ```bash
   fly logs
   ```

2. Try deploying with the `--remote-only` flag to force a clean build:
   ```bash
   fly deploy --remote-only
   ```
   
3. If you need to make changes to the app, you can SSH into the running machine:
   ```bash
   fly ssh console
   ```

## Managing Your Application

- Update after changes: `fly deploy`
- Suspend app: `fly apps suspend`
- Resume app: `fly apps resume`