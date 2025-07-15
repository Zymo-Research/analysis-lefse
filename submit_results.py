import hashlib
import hmac
import json

import boto3
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


def upload_to_s3(file, analysis_id, s3_client):
    """Upload file content to S3 bucket"""
    # This function should implement the logic to upload the file_content to S3
    # file is the path to the file to be uploaded

    file_name = f"{settings.ENV}/anaysis_results/{analysis_id}/{file.split('/')[-1]}"
    s3_client.upload_file(file, settings.S3_BUCKET, file_name)

    print(f"File {file_name} uploaded to S3 bucket {settings.S3_BUCKET}")

    return f"s3://{settings.S3_BUCKET}/{file_name}"  # noqa: E231


def submit_results(config, output_files, mapping_file):
    """Submit results with config parameter"""
    # Read LDA results
    df = pd.read_csv(output_files[0], sep="\t", dtype=str, header=None)

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
    lda_json = df.to_dict(orient="records")
    # Submit

    s3_client = boto3.client("s3")
    s3_paths = []
    # post images to s3
    for each in output_files[1:]:
        # Assuming a function upload_to_s3 exists to handle S3 uploads
        s3_path = upload_to_s3(each, config["analysis_id"], s3_client)
        s3_paths.append(s3_path)

    payload_dict = {
        "analysis_id": config["analysis_id"],
        "result": {"s3_paths": s3_paths, "lefse": lda_json},
    }
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
