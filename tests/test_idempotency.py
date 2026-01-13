"""
Test: Idempotency - Duplicate document uploads should not create duplicate jobs

This test verifies that when the same document is uploaded multiple times
with the same Idempotency-Key, only one job is created and processed.

Expected behavior:
1. First upload creates a new document and job
2. Second upload with same idempotency key returns existing document
3. No duplicate job is created in the queue
4. Database maintains consistency
"""
import requests
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import redis

# Configuration
API_BASE_URL = "http://localhost:3000"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "basys_pa",
    "user": "basys",
    "password": "basys_local_dev"
}
REDIS_URL = "redis://localhost:6379"

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_redis_client():
    """Get Redis client"""
    return redis.from_url(REDIS_URL, decode_responses=True)

def test_idempotency():
    """Test idempotency of document upload"""
    print("\n=== Testing Idempotency ===\n")
    
    # Step 1: Create a PA request
    print("1. Creating PA request...")
    response = requests.post(
        f"{API_BASE_URL}/v1/pa-requests",
        json={
            "patientName": "Test Patient",
            "procedure": "TKA",
            "notes": "Idempotency test"
        },
        headers={"x-api-key": "test_key"}
    )
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}"
    request_data = response.json()
    request_id = request_data['requestId']
    print(f"✓ PA request created: {request_id}")
    
    # Step 2: Upload document with idempotency key
    idempotency_key = f"test-idempotency-{int(time.time())}"
    document_text = """
    Clinical note: Patient has osteoarthritis.
    X-ray shows joint space narrowing.
    Trial of NSAIDs completed.
    Difficulty with ADLs noted.
    """
    
    print(f"\n2. First upload with idempotency key: {idempotency_key}")
    response1 = requests.post(
        f"{API_BASE_URL}/v1/pa-requests/{request_id}/documents",
        json={"documentText": document_text},
        headers={
            "x-api-key": "test_key",
            "idempotency-key": idempotency_key
        }
    )
    
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}"
    doc1 = response1.json()
    document_id_1 = doc1['documentId']
    print(f"✓ First upload successful: {document_id_1}")
    
    # Check database for job creation
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as count FROM core.jobs WHERE request_id = %s",
        (request_id,)
    )
    job_count_1 = cursor.fetchone()['count']
    print(f"✓ Jobs in database after first upload: {job_count_1}")
    
    # Check Redis queue
    redis_client = get_redis_client()
    queue_size_1 = redis_client.llen("pa:documents")
    print(f"✓ Queue size after first upload: {queue_size_1}")
    
    # Step 3: Upload same document with same idempotency key (duplicate)
    print(f"\n3. Second upload with SAME idempotency key: {idempotency_key}")
    time.sleep(0.5)  # Brief delay
    
    response2 = requests.post(
        f"{API_BASE_URL}/v1/pa-requests/{request_id}/documents",
        json={"documentText": document_text},
        headers={
            "x-api-key": "test_key",
            "idempotency-key": idempotency_key
        }
    )
    
    assert response2.status_code == 201, f"Expected 201, got {response2.status_code}"
    doc2 = response2.json()
    document_id_2 = doc2['documentId']
    print(f"✓ Second upload returned: {document_id_2}")
    
    # Verify same document ID returned
    assert document_id_1 == document_id_2, \
        f"Expected same document ID, got {document_id_1} vs {document_id_2}"
    print("✓ Same document ID returned (idempotency preserved)")
    
    # Check database for job count
    cursor.execute(
        "SELECT COUNT(*) as count FROM core.jobs WHERE request_id = %s",
        (request_id,)
    )
    job_count_2 = cursor.fetchone()['count']
    print(f"✓ Jobs in database after second upload: {job_count_2}")
    
    # Verify no duplicate job created
    assert job_count_1 == job_count_2, \
        f"Duplicate job created! Expected {job_count_1}, got {job_count_2}"
    print("✓ No duplicate job created")
    
    # Check Redis queue (should not have duplicate)
    queue_size_2 = redis_client.llen("pa:documents")
    print(f"✓ Queue size after second upload: {queue_size_2}")
    
    assert queue_size_1 == queue_size_2, \
        f"Duplicate queued! Expected {queue_size_1}, got {queue_size_2}"
    print("✓ No duplicate message in queue")
    
    # Step 4: Verify idempotency record in Redis
    idempotency_record = redis_client.get(f"idempotency:{idempotency_key}")
    assert idempotency_record is not None, "Idempotency key not found in Redis"
    print("✓ Idempotency key recorded in Redis")
    
    # Cleanup
    cursor.close()
    conn.close()
    redis_client.close()
    
    print("\n=== Idempotency Test PASSED ===\n")
    return True


if __name__ == "__main__":
    try:
        # Wait for services to be ready
        print("Waiting for services to be ready...")
        time.sleep(5)
        
        # Run test
        success = test_idempotency()
        
        if success:
            print("\n✓✓✓ All idempotency tests passed! ✓✓✓\n")
            exit(0)
        else:
            print("\n✗✗✗ Idempotency tests failed! ✗✗✗\n")
            exit(1)
            
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {e}\n")
        exit(1)
    except Exception as e:
        print(f"\n✗ Test error: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)
