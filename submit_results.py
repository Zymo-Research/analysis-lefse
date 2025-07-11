import hashlib
import hmac
import json

import pandas as pd
import requests

from config import settings


def submit_error(config, message):
    """Submit error with config parameter"""
    payload_dict = {"analysis_id": config["analysis_id"], "result": {"error": message}}
    payload = json.dumps(payload_dict, separators=(",", ":"), ensure_ascii=False)
    signature = hmac.new(
        settings.API_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    url = f"{settings.PORTAL_API_URL}/submit_analysis_error?workspace_id={config['workspace_id']}"
    headers = {
        "accept": "application/json",
        "X-API-Signature": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()


def submit_results(config, output_file, mapping_file):
    """Submit results with config parameter"""
    # Read LDA results
    df = pd.read_csv(output_file, sep="\t", dtype=str)

    # Rename columns
    rename_map = {
        df.columns[0]: "feature",
        df.columns[1]: "log_highest_mean",
        df.columns[2]: "class",
        df.columns[3]: "lda",
        df.columns[4]: "p_value",
    }
    df = df.rename(columns=rename_map)

    # Replace feature names
    with open(mapping_file, "r", encoding="utf-8") as f:
        column_name_mapping = json.load(f)
    df["feature"] = df["feature"].replace(column_name_mapping["cleaned_to_original"])

    # Clean data
    df = df[df["class"].notna()]
    for col in ["lda", "p_value", "log_highest_mean"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Submit
    lda_json = df.to_dict(orient="records")
    payload_dict = {"analysis_id": config["analysis_id"], "result": {"lefse": lda_json}}
    payload = json.dumps(payload_dict, separators=(",", ":"), ensure_ascii=False)
    signature = hmac.new(
        settings.API_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    url = f"{settings.PORTAL_API_URL}/submit_analysis_result?workspace_id={config['workspace_id']}"
    headers = {
        "accept": "application/json",
        "X-API-Signature": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    return response
