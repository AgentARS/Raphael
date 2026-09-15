import sys
from fastapi.testclient import TestClient
from main import app
import traceback
import time

try:
    print("Starting TestClient with lifespan...")
    with TestClient(app) as client:
        time.sleep(1) # Let the scheduler start
        print("Testing GET /api/tasks")
        response = client.get("/api/tasks")
        print("GET /api/tasks Status:", response.status_code)
        
        print("Testing GET /api/ideas")
        response = client.get("/api/ideas")
        print("GET /api/ideas Status:", response.status_code)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
