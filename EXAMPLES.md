# Example API Calls

## 1. Health Check
```bash
curl http://localhost:3000/health
```

## 2. Metrics
```bash
curl http://localhost:3000/metrics
```

## 3. Create PA Request
```bash
curl -X POST http://localhost:3000/v1/pa-requests \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -d '{
    "patientName": "John Doe",
    "procedure": "Total Knee Arthroplasty",
    "notes": "Patient requesting TKA approval"
  }'
```

## 4. Upload Document (with Test Data from Assignment)

First, save the request ID from step 3, then:

```bash
# Replace YOUR_REQUEST_ID with actual request ID from step 3
REQUEST_ID="YOUR_REQUEST_ID"

curl -X POST http://localhost:3000/v1/pa-requests/$REQUEST_ID/documents \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -H "Idempotency-Key: test-key-001" \
  -d '{
    "documentText": "Clinical note (synthetic)\nPatient: John Doe\nDx: Knee pain, suspected osteoarthritis.\nImaging: X-ray shows joint space narrowing and osteophytes.\nTherapy: Trial of NSAIDs for 3 weeks. No documented physical therapy.\nFunction: Difficulty climbing stairs; cannot walk > 1 block; ADLs impacted.\nPlan: Requesting total knee arthroplasty."
  }'
```

## 5. Get PA Request (with Evidence Pack)

Wait a few seconds after upload, then:

```bash
# Wait for processing
sleep 5

# Get request with evidence pack
curl http://localhost:3000/v1/pa-requests/$REQUEST_ID
```

## 6. Get Audit Log

```bash
# All audit logs
curl http://localhost:3000/v1/audit

# Audit logs for specific request
curl "http://localhost:3000/v1/audit?request_id=$REQUEST_ID"
```

## 7. Test Idempotency

Upload the same document twice with the same Idempotency-Key:

```bash
# First upload
curl -X POST http://localhost:3000/v1/pa-requests/$REQUEST_ID/documents \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -H "Idempotency-Key: duplicate-test-123" \
  -d '{"documentText": "Test document"}'

# Second upload (should return same document)
curl -X POST http://localhost:3000/v1/pa-requests/$REQUEST_ID/documents \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -H "Idempotency-Key: duplicate-test-123" \
  -d '{"documentText": "Test document"}'
```

## Complete Example Flow

```bash
#!/bin/bash

# 1. Health check
echo "1. Health check..."
curl -s http://localhost:3000/health | jq
echo ""

# 2. Create PA request
echo "2. Creating PA request..."
CREATE_RESPONSE=$(curl -s -X POST http://localhost:3000/v1/pa-requests \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -d '{
    "patientName": "John Doe",
    "procedure": "Total Knee Arthroplasty",
    "notes": "Test request"
  }')

echo $CREATE_RESPONSE | jq
REQUEST_ID=$(echo $CREATE_RESPONSE | jq -r '.requestId')
echo "Request ID: $REQUEST_ID"
echo ""

# 3. Upload document
echo "3. Uploading document..."
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:3000/v1/pa-requests/$REQUEST_ID/documents \
  -H "Content-Type: application/json" \
  -H "x-api-key: dev_api_key_12345" \
  -H "Idempotency-Key: test-$(date +%s)" \
  -d '{
    "documentText": "Clinical note (synthetic)\nPatient: John Doe\nDx: Knee pain, suspected osteoarthritis.\nImaging: X-ray shows joint space narrowing and osteophytes.\nTherapy: Trial of NSAIDs for 3 weeks. No documented physical therapy.\nFunction: Difficulty climbing stairs; cannot walk > 1 block; ADLs impacted.\nPlan: Requesting total knee arthroplasty."
  }')

echo $UPLOAD_RESPONSE | jq
echo ""

# 4. Wait for processing
echo "4. Waiting for processing (10 seconds)..."
sleep 10

# 5. Get PA request with evidence pack
echo "5. Getting PA request with evidence pack..."
curl -s http://localhost:3000/v1/pa-requests/$REQUEST_ID | jq
echo ""

# 6. Get audit log
echo "6. Getting audit log..."
curl -s "http://localhost:3000/v1/audit?request_id=$REQUEST_ID" | jq
echo ""

# 7. Get metrics
echo "7. Getting metrics..."
curl -s http://localhost:3000/metrics | jq
echo ""

echo "Done!"
```

Save the above script as `test_flow.sh`, make it executable, and run:

```bash
chmod +x test_flow.sh
./test_flow.sh
```
