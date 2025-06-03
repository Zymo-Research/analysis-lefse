import hmac
import hashlib
import json
import subprocess
import os
import requests
import argparse
import pandas as pd

API_KEY = os.getenv("API_KEY", "test")
ANALYSIS_ID = os.getenv("ANALYSIS_ID")
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
OUTPUT_FILE = "/data/lda_results.txt"
PORTAL_API_BASE_URL = os.getenv("PORTAL_API_BASE_URL", "")

def submit_error(message):
    payload_dict = {
        "analysis_id": ANALYSIS_ID,
        "result": {
            "error": message
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
    print("Error submitted successfully.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--error_message', type=str, default=None, help='Error message to submit if LEfSe fails')
    args = parser.parse_args()

    if args.error_message:
        submit_error(args.error_message)
        return

    # Read LDA results as a DataFrame
    df = pd.read_csv(OUTPUT_FILE, sep='\t', dtype=str)

    # Rename columns to match required output (adjust if your file uses different names)
    rename_map = {
        df.columns[0]: "feature",
        df.columns[1]: "log_highest_mean",
        df.columns[2]: "class",
        df.columns[3]: "lda",
        df.columns[4]: "p_value"
    }
    df = df.rename(columns=rename_map)

    # Replace feature names using the mapping
    with open("/data/column_name_mapping.json", "r", encoding="utf-8") as f:
        column_name_mapping = json.load(f)
    df["feature"] = df["feature"].replace(column_name_mapping["cleaned_to_original"])

    # Omit any rows where class is NaN
    df = df[df["class"].notna()]

    # Cast numeric columns as numbers
    for col in ["lda", "p_value", "log_highest_mean"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert to list of dicts
    lda_json = df.to_dict(orient="records")

    payload_dict = {
        "analysis_id": ANALYSIS_ID,
        "result": {"lefse": lda_json}
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
