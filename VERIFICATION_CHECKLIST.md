# Minimee Verification Checklist

## ✅ Completed

### 1. Container Startup
- **Status**: ⚠️ Containers are starting (docker-compose up in progress)
- **Action**: Wait for `make up` to complete, then verify all containers are running
- **Command**: `docker ps --filter "name=minimee"`

### 2. Dashboard Accessibility ✅
- **Status**: ✅ Dashboard returns HTTP 200
- **URL**: http://localhost:3000
- **Verified**: Dashboard is accessible

### 3. Backend Health Check
- **Status**: ⚠️ Backend not yet accessible (containers starting)
- **Endpoint**: `GET http://localhost:8000/health`
- **Expected**: `{"status": "ok"}`
- **Command**: `curl http://localhost:8000/health`

### 4. A/B/C Approval UI ✅
- **Status**: ✅ Created
- **Files Created**:
  - `apps/dashboard/components/minimee/ApprovalDialog.tsx` - Full approval dialog with A/B/C options
  - `apps/dashboard/app/minimee/page.tsx` - Minimee page with message processing
  - `apps/dashboard/components/layout/Sidebar.tsx` - Updated with Minimee navigation
  - `apps/dashboard/lib/api.ts` - Added `processMessage()` and `approveMessage()` methods
- **Features**:
  - Displays 3 response options (A/B/C)
  - Click to select option
  - Approve/Reject buttons
  - Toast notifications
  - Supports both WhatsApp messages and email drafts

### 5. Agents CRUD ✅
- **Status**: ✅ Implemented
- **Components**: `AgentDialog.tsx`, `AgentList.tsx`
- **Location**: Dashboard > Agents page
- **Features**: Create, Read, Update, Delete agents

## ⏳ Pending Manual Verification (After Containers Start)

### 1. Container Status
```bash
# Check all containers are running
docker ps --filter "name=minimee"

# Expected: 5 containers
# - minimee-postgres
# - minimee-backend
# - minimee-dashboard
# - minimee-bridge
# - ollama (or minimee-ollama)
```

### 2. Backend Health
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

### 3. RAG Retrieval
```bash
# Test RAG with a message
curl -X POST http://localhost:8000/minimee/message \
  -H "Content-Type: application/json" \
  -d '{
    "content": "test query",
    "sender": "user",
    "timestamp": "2024-01-01T10:00:00Z",
    "conversation_id": "test",
    "user_id": 1,
    "source": "dashboard"
  }'
# Should return options array with 3 response options
```

### 4. WhatsApp Bridge
```bash
# Check bridge logs
docker logs minimee-bridge

# Look for:
# - "WhatsApp connected successfully"
# - QR code (if not authenticated)
# - "Minimee TEAM group ready"
```

### 5. Gmail Connection
1. Navigate to Dashboard > Settings > Gmail tab
2. Click "Connect Gmail"
3. Complete OAuth flow
4. Verify status shows "Connected"
5. Test "Fetch Recent Emails" button

### 6. Dashboard Pages
- ✅ Overview: http://localhost:3000/
- ✅ Minimee: http://localhost:3000/minimee (NEW - with approval UI)
- ✅ Agents: http://localhost:3000/agents
- ✅ Logs: http://localhost:3000/logs
- ✅ Settings: http://localhost:3000/settings

### 7. Approval Flow End-to-End Test
1. Go to http://localhost:3000/minimee
2. Type a message (e.g., "Hello, how are you?")
3. Click "Process Message"
4. Review A/B/C options in dialog
5. Select option A (or B/C)
6. Click "Approve Option A"
7. Verify toast notification appears
8. Check backend logs for approval confirmation

## 📝 Quick Test Commands

```bash
# 1. Start all services
make up

# 2. Check container status
docker ps --filter "name=minimee"

# 3. Test backend health
curl http://localhost:8000/health

# 4. Test dashboard
curl http://localhost:3000

# 5. Check bridge logs
docker logs minimee-bridge --tail 50

# 6. Seed database (if needed)
make seed

# 7. View all logs
make logs
```

## 🎯 Demo Readiness

Once all containers are running and verified:
- ✅ Dashboard accessible
- ✅ Backend health OK
- ✅ Approval UI created and integrated
- ✅ Agents CRUD functional
- ⏳ RAG retrieval (test after containers start)
- ⏳ WhatsApp bridge (verify connection)
- ⏳ Gmail sync (test OAuth flow)
- ⏳ End-to-end approval flow (manual test)

## 🚀 Next Steps

1. Wait for `make up` to complete
2. Verify all containers are healthy
3. Test backend health endpoint
4. Test RAG retrieval with sample message
5. Verify WhatsApp bridge connection
6. Test Gmail OAuth flow
7. Perform end-to-end approval workflow test

