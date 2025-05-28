import hmac
import hashlib
import json
import subprocess
import os
import requests

API_KEY = os.getenv("API_KEY", "test")
ANALYSIS_ID = os.getenv("ANALYSIS_ID")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
OUTPUT_FILE = "/data/lda_results.txt"
PORTAL_API_BASE_URL = os.getenv("PORTAL_API_BASE_URL", "")

def main():
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lda_data = f.read().replace('\t', ',')

    payload_dict = {
        "analysis_id": ANALYSIS_ID,
        "result": {
            "lda": lda_data
        }
    }
    payload = json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(API_KEY.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()

    url = "{}/external/submit_analysis_result?workspace_id={}".format(PORTAL_API_BASE_URL, WORKSPACE_ID)
    headers = {
        "accept": "application/json",
        "X-API-Signature": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()

    subprocess.run([
        "curl", "-s", "-X", "POST",
        "{}/external/submit_analysis_result?workspace_id={}".format(PORTAL_API_BASE_URL, WORKSPACE_ID),
        "-H", "Content-Type: application/json",
        "-H", "X-API-Signature: {}".format(signature),
        "-d", payload
    ], check=True)

    print("Results submitted successfully.")

if __name__ == "__main__":
    main()
