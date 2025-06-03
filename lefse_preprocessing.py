import subprocess
import hashlib
import hmac
import json
import requests
import pymongo
import os
import pandas as pd

# Load configuration from environment variables
DOCDB_HOST = os.getenv("DOCDB_HOST", "dev-documentdb.cluster-cu9wyuyqqen8.ap-southeast-1.docdb.amazonaws.com")
DOCDB_PORT = int(os.getenv("DOCDB_PORT", "27017"))
DOCDB_PASSWORD = os.getenv("DOCDB_PASSWORD", "YOUR_DOCDB_PASSWORD")
DOCDB_USER = os.getenv("DOCDB_USER", "integratedOmics")
PORTAL_API_BASE_URL = os.getenv("PORTAL_API_BASE_URL", "http://host.docker.internal:8000/api/v1")

API_KEY = os.getenv("API_KEY", "test")
ANALYSIS_ID = os.getenv("ANALYSIS_ID", "001784e5-948f-4c1b-a480-a664da6e022d")
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "db2a6d11-ddaf-4df7-a5c2-1fa34b03f537")

INPUT_FILE = "/data/input_data.txt"

def get_local_client():

    db = pymongo.MongoClient(
        "mongodb://{}:{}@{}:{}/".format(DOCDB_USER, DOCDB_PASSWORD, DOCDB_HOST, DOCDB_PORT),
        tls=True,
        tlsAllowInvalidHostnames=True,
        tlsCAFile="/app/global-bundle.pem",
        replicaSet="rs0",
        readPreference="secondaryPreferred",
        retryWrites=False,
        directConnection=True,
    )
    yield db

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

def main():
    # Step 1: Request metadata
    payload = json.dumps({"analysis_id": ANALYSIS_ID}, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(API_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()

    url = "{}/external/lefse_input?workspace_id={}".format(PORTAL_API_BASE_URL, WORKSPACE_ID)
    headers = {
        "accept": "application/json",
        "X-API-Signature": signature,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    response_json = response.json()

    metadata_df = pd.DataFrame(response_json.get("metadata"))
    # if either column has one distinct value, throw an error
    for col in metadata_df.columns:
        if metadata_df[col].nunique() == 1:
            print("Column {} has only one distinct value: {}".format(col, metadata_df[col].unique()[0]))
            submit_error("One or more columns have only one distinct value. Please check your input data.")
            raise ValueError("One or more columns have only one distinct value. Please check your input data.")
    pipeline_id = response_json.get("pipeline_id")
    tax_level = response_json.get("tax_level", "species")
    pipeline_data_ids = metadata_df["pipeline_data_id"].tolist()

    # Step 2: Query DocumentDB
    doc_db = next(get_local_client())
    result = doc_db.pipeline_run_results[str(pipeline_id)].find(
        {"run_result_id": {"$in": pipeline_data_ids}},
        {"uuid": 0, "_id": 0, "run_id": 0, "workspace_id": 0, "raw_data_id": 0}
    )
    df = pd.DataFrame(list(result))
    df = df.rename(columns={"run_result_id": "pipeline_data_id"})
    df = df.set_index("pipeline_data_id")
    df = df.select_dtypes(include=["number"])

    # Step 3: GCAS -> species names
    gcas = df.columns.tolist()
    payload = json.dumps({"gcas": gcas, "tax_level": tax_level}, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(API_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()

    url = "{}/external/convert_gcas?workspace_id={}".format(PORTAL_API_BASE_URL, WORKSPACE_ID)
    headers["X-API-Signature"] = signature

    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    df = df.rename(columns=response.json())
    
    # drop columns that are only underscores or one character
    df = df.loc[:, (df.columns.str.len() > 1) & (~df.columns.str.match(r'^_'))]
    
    # collect columns to drop (those containing underscores)
    
    # Create mapping of original column names to cleaned column names
    original_columns = df.columns.tolist()
    cleaned_columns = df.columns.str.replace('[^a-zA-Z0-9_]', '', regex=True).tolist()
    
    # Create bidirectional mapping
    column_name_mapping = {
        "cleaned_to_original": dict(zip(cleaned_columns, original_columns)),
        "original_to_cleaned": dict(zip(original_columns, cleaned_columns))
    }
    
    # Save the mapping to a JSON file for later use
    mapping_file = "/data/column_name_mapping.json"
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(column_name_mapping, f, ensure_ascii=False, indent=2)
    print("Column name mapping saved to {}".format(mapping_file))
    
    df.columns = df.columns.str.replace('[^a-zA-Z0-9_]', '', regex=True)

    
    df = df.groupby(df.columns, axis=1).sum()

    # Step 4: Merge and output as TSV
    df = metadata_df.merge(df, on="pipeline_data_id", how="inner")
    df = pd.concat([pd.DataFrame([df.columns], columns=df.columns), df], ignore_index=True).T
    df.columns = df.iloc[0]
    df = df.drop(df.index[0])

    df.to_csv(INPUT_FILE, sep="\t", index=False, float_format="{:f}".format, encoding="utf-8")
    print("Input data written to {}".format(INPUT_FILE))

if __name__ == "__main__":
    main()