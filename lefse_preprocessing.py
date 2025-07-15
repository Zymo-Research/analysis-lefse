import hashlib
import hmac
import io
import json
import logging
import zipfile

import pandas as pd
import requests

from config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def preprocess_data(config, output_file, mapping_file):
    """Main preprocessing function with config parameter"""

    # Step 1: Request metadata
    payload = json.dumps(
        {"analysis_id": config["analysis_id"]},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    signature = hmac.new(
        settings.API_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    url = f"{settings.PORTAL_API_URL}/lefse_input?workspace_id={config['workspace_id']}"
    headers = {
        "accept": "application/json",
        "X-API-Signature": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    response_json = response.json()

    metadata_df = pd.DataFrame(response_json.get("metadata"))

    # Validate metadata
    for col in metadata_df.columns:
        if metadata_df[col].nunique() == 1:
            unique_val = metadata_df[col].unique()[0]
            raise ValueError(f"Column {col} has only one distinct value: {unique_val}")

    pipeline_id = response_json.get("pipeline_id")
    tax_level = response_json.get("tax_level", "species")
    pipeline_data_ids = metadata_df["pipeline_data_id"].tolist()

    logging.info("Pipeline ID: %s", pipeline_id)

    # experiment with /get_results_by_ids api
    payload = json.dumps(
        {
            "result_ids": pipeline_data_ids,
            "pipeline_id": pipeline_id,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    signature = hmac.new(
        settings.API_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    url = f"{settings.PORTAL_API_URL}/get_results_by_ids"

    headers["X-API-Signature"] = signature
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        with z.open("results.json") as f:
            response_json = json.loads(f.read())
    logging.info("Successfully retrieved results by IDs.")
    df = pd.DataFrame(response_json)
    df = df.rename(columns={"run_result_id": "pipeline_data_id"})
    df = df.set_index("pipeline_data_id")
    df = df.select_dtypes(include=["number"])

    # Step 3: GCAS -> species names
    gcas = df.columns.tolist()
    payload = json.dumps(
        {"gcas": gcas, "tax_level": tax_level},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    signature = hmac.new(
        settings.API_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    url = (
        f"{settings.PORTAL_API_URL}/convert_gcas?workspace_id={config['workspace_id']}"
    )
    headers["X-API-Signature"] = signature

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    df = df.rename(columns=response.json())

    # remove total_counts column if it exists
    if "total_counts" in df.columns:
        df = df.drop(columns=["total_counts"])

    # Clean column names
    df = df.loc[:, (df.columns.str.len() > 1) & (~df.columns.str.match(r"^_"))]

    # Create column name mapping
    original_columns = df.columns.tolist()
    cleaned_columns = df.columns.str.replace("[^a-zA-Z0-9_]", "", regex=True).tolist()

    column_name_mapping = {
        "cleaned_to_original": dict(zip(cleaned_columns, original_columns)),
        "original_to_cleaned": dict(zip(original_columns, cleaned_columns)),
    }

    with open(mapping_file, "w", encoding="utf-8") as f:
        json.dump(column_name_mapping, f, ensure_ascii=False, indent=2)

    df.columns = cleaned_columns
    df = df.groupby(df.columns, axis=1).sum()

    # Step 4: Merge and output
    df = metadata_df.merge(df, on="pipeline_data_id", how="inner")
    df = pd.concat(
        [pd.DataFrame([df.columns], columns=df.columns), df], ignore_index=True
    ).T
    df.columns = df.iloc[0]
    df = df.drop(df.index[0])

    df.to_csv(
        output_file, sep="\t", index=False, float_format="{:f}".format, encoding="utf-8"
    )
