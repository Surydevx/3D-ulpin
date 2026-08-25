import asyncio
import httpx
import random
import time
from collections import Counter

API_URL = "http://127.0.0.1:8000/api/v1/cadastre/validate-building"

def generate_random_building():
    return {
        "parent_2d_ulpin": f"IN-DL-TEST-{random.randint(1000, 9999)}",
        "latitude": round(random.uniform(28.5, 28.7), 6),
        "longitude": round(random.uniform(77.1, 77.3), 6),
        "registered_height_m": round(random.uniform(10.0, 50.0), 2),
        "sensor_evidence": [
            {
                "source_name": "LiDAR_Monte_Carlo",
                "height_m": round(random.uniform(10.0, 55.0), 2),
                "variance": round(random.uniform(0.01, 0.05), 4)
            }
        ]
    }

async def send_request(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, index: int, results: Counter):
    payload = generate_random_building()

    async with semaphore:
        try:
            response = await client.post(API_URL, json=payload)
            results[response.status_code] += 1
            
            if response.status_code == 500 and index == 0:
                # Print the exact error message from the server on the first request
                print(f"\n[!] SERVER ERROR DETAIL: {response.text}\n")
            
            if index % 50 == 0:
                print(f"Request {index:03d}: Status {response.status_code}")
        except Exception as e:
            # Tally network-level failures
            results["Failed"] += 1
            print(f"Request {index:03d} Failed: {type(e).__name__}")

async def run_stress_test(total_requests: int = 500, max_concurrent: int = 40):
    print(f"Initiating Monte Carlo Stress Test: {total_requests} Requests...")
    print(f"Concurrency Limit (Semaphore): {max_concurrent} simultaneous requests.\n")

    start_time = time.time()
    semaphore = asyncio.Semaphore(max_concurrent)
    limits = httpx.Limits(max_connections=max_concurrent, max_keepalive_connections=max_concurrent)
    
    # Using a Counter to track how many 200s, 500s, etc., we get
    results = Counter()

    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        tasks = [send_request(client, semaphore, i, results) for i in range(total_requests)]
        await asyncio.gather(*tasks)

    duration = time.time() - start_time
    rps = total_requests / duration

    # --- Print Telemetry ---
    print(f"\n--- STRESS TEST COMPLETE ---")
    print(f"Total Time : {duration:.2f} seconds")
    print(f"Throughput : {rps:.2f} Requests / Second")
    print("Status Codes:")
    for status, count in results.items():
        print(f"  [{status}]: {count}")

if __name__ == "__main__":
    asyncio.run(run_stress_test(total_requests=500, max_concurrent=40))