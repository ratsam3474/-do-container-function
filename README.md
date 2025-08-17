# DO Container Function

DigitalOcean Function for managing Docker containers on separate GCP VMs via SSH.

## Architecture

```
┌─────────────────┐
│   Your App      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DO Function    │ (This function)
└────┬───────┬────┘
     │       │
     │SSH    │SSH
     │       │
     ▼       ▼
┌────────┐ ┌────────┐
│WAHA VM │ │USER VM │
└────────┘ └────────┘
```

## Setup on DigitalOcean

1. Create a new Function in DigitalOcean
2. Upload this code
3. Set environment variables:
   - `WAHA_VM_IP` - External IP of WAHA GCP VM
   - `WAHA_SSH_USER` - SSH username for WAHA VM
   - `WAHA_SSH_PASSWORD` - SSH password for WAHA VM
   - `USER_VM_IP` - External IP of User containers GCP VM  
   - `USER_SSH_USER` - SSH username for User VM
   - `USER_SSH_PASSWORD` - SSH password for User VM

## Actions

### For User Containers (USER VM)
- `action: create` - Creates user container with 3 services
- `action: stop` - Stops user container
- `action: restart` - Restarts user container
- `action: delete` - Deletes user container

### For WAHA Instances (WAHA VM)
- `action: create_waha` - Creates new WAHA instance
- `action: list_waha` - Lists all WAHA instances and capacity
- `action: find_available_waha` - Finds WAHA with available sessions

## Usage Examples

### Create User Container
```json
{
  "action": "create",
  "user_id": "user123",
  "plan_type": "pro"
}
```

### Create WAHA Instance
```json
{
  "action": "create_waha",
  "max_sessions": 100
}
```

### Find Available WAHA
```json
{
  "action": "find_available_waha",
  "sessions_needed": 10
}
```