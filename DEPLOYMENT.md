# Deployment Instructions

## Prerequisites
1. Two GCP VMs created:
   - WAHA VM (for WhatsApp instances)
   - USER VM (for user containers)
2. DigitalOcean account with Functions enabled
3. GitHub repository created

## Step 1: Push to GitHub

```bash
cd /Users/JE/Documents/102102/do-container-function
git init
git add .
git commit -m "Initial DO container function"
git remote add origin https://github.com/YOUR_USERNAME/do-container-function.git
git push -u origin main
```

## Step 2: Deploy to DigitalOcean

### Option A: Using DO CLI
```bash
doctl serverless deploy .
```

### Option B: Using DO Dashboard
1. Go to Functions in DigitalOcean
2. Create new Function
3. Connect to GitHub repository
4. Select this repository
5. Deploy

## Step 3: Configure Environment Variables

In DigitalOcean Functions dashboard, set:

```
WAHA_VM_IP=<External IP of your WAHA GCP VM>
WAHA_SSH_USER=root
WAHA_SSH_PASSWORD=<SSH password for WAHA VM>

USER_VM_IP=<External IP of your User containers GCP VM>
USER_SSH_USER=root
USER_SSH_PASSWORD=<SSH password for User VM>
```

## Step 4: Get Function URL

After deployment, copy the function URL:
```
https://faas-nyc1-xxx.doserverless.co/api/v1/namespaces/fn-xxx/actions/container-manager
```

## Step 5: Update Your Application

Set this environment variable in your 10210-api:
```
DO_CONTAINER_FUNCTION_URL=<your function URL from step 4>
```

## Step 6: Configure GCP Firewall

Add firewall rules to allow SSH from DO Function IPs:
- Port 22 (SSH)
- Source: DigitalOcean Functions IP range (check DO docs)

## Testing

Test user container creation:
```bash
curl -X POST <function-url> \
  -H "Content-Type: application/json" \
  -d '{"action": "create", "user_id": "test123", "plan_type": "free"}'
```

Test WAHA instance:
```bash
curl -X POST <function-url> \
  -H "Content-Type: application/json" \
  -d '{"action": "find_available_waha", "sessions_needed": 1}'
```