# Deployment Guide

## Quick Start (Local Testing)

1. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Run Locally**
   ```bash
   ./run_local.sh
   ```

## Railway Deployment

### Prerequisites

- GitHub account
- Railway account (sign up at railway.app)
- Git installed locally

### Step 1: Create Git Repository

```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Kalshi data collector"

# Create GitHub repo and push
git remote add origin <your-github-repo-url>
git branch -M main
git push -u origin main
```

### Step 2: Deploy to Railway

1. **Go to Railway Dashboard**
   - Visit https://railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"

2. **Connect Repository**
   - Authorize Railway to access your GitHub
   - Select your kalshi-data-collector repository

3. **Configure Environment Variables**

   Click on your service → Variables → Add all variables from `.env`:

   ```
   KALSHI_API_KEY=your_kalshi_email@example.com
   KALSHI_API_SECRET=your_kalshi_password
   KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2

   POLYROUTER_API_KEY=your_polyrouter_key
   POLYROUTER_BASE_URL=https://api.polyrouter.io/functions/v1

   SUPABASE_URL=https://rggnsdnqdlinhafmksmh.supabase.co
   SUPABASE_KEY=your_supabase_service_role_key

   TARGET_SPORTS=NFL,NHL,NBA,CFB
   COLLECTION_INTERVAL_SECONDS=3
   ENABLE_HISTORICAL_BACKFILL=true
   ENABLE_LIVE_STREAMING=true
   ENABLE_REST_POLLING=true

   POLYROUTER_REQUESTS_PER_MINUTE=10
   KALSHI_REST_REQUESTS_PER_MINUTE=100
   BATCH_INSERT_SIZE=500

   LOG_LEVEL=INFO
   HEALTH_CHECK_INTERVAL_SECONDS=60
   ENABLE_HEALTH_MONITORING=true

   WS_RECONNECT_DELAY_SECONDS=5
   WS_MAX_RECONNECT_ATTEMPTS=10
   WS_PING_INTERVAL_SECONDS=30

   ENVIRONMENT=production
   PORT=8000
   ```

4. **Deploy**
   - Railway will automatically detect the Dockerfile
   - Click "Deploy"
   - Wait for build to complete

5. **Monitor Deployment**
   - Check the "Deployments" tab for build logs
   - Once deployed, check "Logs" tab for runtime logs
   - Access the health check: `https://<your-railway-url>/health`

### Step 3: Verify Deployment

1. **Check Health Endpoint**
   ```bash
   curl https://<your-railway-url>/health
   ```

2. **Monitor Logs**
   - In Railway dashboard → Logs
   - Look for "data_collector_running" message
   - Verify markets are being discovered
   - Check for successful data inserts

3. **Verify Database**
   - Check Supabase dashboard
   - Query `market_metadata` table for discovered markets
   - Query `market_snapshots` table for incoming data
   - Check `collection_health` table for health metrics

## Post-Deployment

### Monitoring

1. **Railway Metrics**
   - CPU and Memory usage
   - Restart count
   - Deployment health

2. **Application Logs**
   - WebSocket connection status
   - Market discovery progress
   - Data insertion rates
   - Error messages

3. **Database Queries**
   ```sql
   -- Check recent snapshots
   SELECT
       market_ticker,
       COUNT(*) as snapshot_count,
       MAX(timestamp) as last_snapshot
   FROM market_snapshots
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY market_ticker
   ORDER BY snapshot_count DESC;

   -- Check health status
   SELECT *
   FROM collection_health
   ORDER BY timestamp DESC
   LIMIT 10;

   -- Check for errors
   SELECT *
   FROM data_collection_logs
   WHERE log_level IN ('ERROR', 'CRITICAL')
   ORDER BY timestamp DESC
   LIMIT 20;
   ```

### Maintenance

1. **Update Deployment**
   ```bash
   git add .
   git commit -m "Update: description"
   git push
   ```
   Railway will auto-deploy on push to main branch.

2. **Restart Service**
   - Railway Dashboard → Your Service → "Restart"

3. **View Logs**
   - Railway Dashboard → Logs
   - Filter by log level or search for keywords

4. **Scale Resources (if needed)**
   - Railway Dashboard → Settings
   - Adjust memory/CPU limits

## Troubleshooting

### Build Failures

**Issue**: Docker build fails
```bash
# Check Dockerfile syntax
docker build -t kalshi-collector .

# Check requirements.txt
pip install -r requirements.txt
```

**Issue**: Missing environment variables
- Verify all required variables are set in Railway
- Check .env.example for reference

### Runtime Issues

**Issue**: WebSocket keeps disconnecting
- Check Kalshi API status
- Verify credentials are correct
- Review WebSocket logs for errors

**Issue**: No data being collected
- Check market discovery is finding markets
- Verify target sports are active
- Check rate limiting isn't being hit

**Issue**: Database insert failures
- Verify Supabase service role key
- Check Supabase project is active
- Review database logs in Supabase dashboard

### Performance Issues

**Issue**: High memory usage
- Reduce `BATCH_INSERT_SIZE`
- Decrease number of tracked markets
- Increase flush frequency

**Issue**: Rate limit errors
- Decrease `COLLECTION_INTERVAL_SECONDS`
- Reduce `KALSHI_REST_REQUESTS_PER_MINUTE`
- Disable REST polling if WebSocket is working

## Costs

### Railway
- Free tier: 500 hours/month (always-on = ~730 hours)
- Hobby plan: $5/month for unlimited hours
- Pro plan: Usage-based pricing

### Supabase
- Free tier: 500 MB database, 2 GB bandwidth
- Pro tier: $25/month for larger database

### PolyRouter
- Free tier: 10 requests/minute
- Paid tiers: Contact PolyRouter for pricing

## Best Practices

1. **Start Small**
   - Begin with one sport (NFL or NHL)
   - Test locally before deploying
   - Monitor for 24 hours before adding more markets

2. **Monitor Health**
   - Check health endpoint regularly
   - Set up alerts for failures
   - Review logs daily initially

3. **Database Management**
   - Monitor database size
   - Archive old data periodically
   - Index frequently queried columns

4. **Rate Limiting**
   - Stay well below API limits
   - Use adaptive rate limiting
   - Prefer WebSocket over REST when possible

5. **Backups**
   - Enable Supabase automatic backups
   - Export critical data regularly
   - Keep backups of configuration
