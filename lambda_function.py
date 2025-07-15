import json
import logging
import os
import subprocess
import tempfile

from lefse_preprocessing import preprocess_data
from submit_results import submit_error, submit_results

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def lambda_handler(event, context):
    """
    Lambda handler for LEfSe analysis
    """

    logging.info("Received event: %s", json.dumps(event, indent=2))

    # Create a temporary working directory
    work_dir = tempfile.mkdtemp()

    try:
        # Extract parameters from event
        config = {
            "workspace_id": event["workspace_id"],
            "analysis_id": event["analysis_id"],
        }

        os.chdir(work_dir)

        # Step 1: Preprocess data
        logging.info("Starting preprocessing...")
        input_file = os.path.join(work_dir, "input_data.txt")
        mapping_file = os.path.join(work_dir, "column_name_mapping.json")

        params = preprocess_data(
            config=config, output_file=input_file, mapping_file=mapping_file
        )

        # Step 2: Run LEfSe
        logging.info("Running LEfSe analysis...")
        formatted_file = os.path.join(work_dir, "formatted.in")
        output_file = os.path.join(work_dir, "lda_results.txt")

        # Format input - explicitly use Python 2 if needed
        format_cmd = [
            "python",
            "/var/task/lefse_format_input.py",  # The wrapper script handles Python 2
            input_file,
            formatted_file,
            "-u",
            params.get("subject_row", 1),
            "-c",
            params.get("class_row", 2),
            str(1),
            "-u",
            str(2),
            "-o",
            params.get("norm_value", 1000000),
            str(1000000),  # This is the normalization value
        ]

        logging.info("Running command: %s", " ".join(format_cmd))
        result = subprocess.run(
            format_cmd, capture_output=True, text=True, cwd=work_dir
        )
        if result.returncode != 0:
            raise Exception(f"format_input failed: {result.stderr}")

        # Run LEfSe
        lefse_cmd = ["python", "/var/task/lefse_run.py", formatted_file, output_file]
        logging.info("Running command: %s", " ".join(lefse_cmd))
        result = subprocess.run(lefse_cmd, capture_output=True, text=True, cwd=work_dir)
        if result.returncode != 0:
            raise Exception(f"run_lefse failed: {result.stderr}")

        # Step 3: Submit results
        logging.info("Submitting results...")
        response = submit_results(
            config=config, output_file=output_file, mapping_file=mapping_file
        )
        logging.info("Results submitted successfully: %s", response)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "LEfSe analysis completed successfully",
                    "analysis_id": config["analysis_id"],
                }
            ),
        }

    except Exception as e:
        logging.error("Error occurred: %s", str(e))
        try:
            submit_error(config, str(e))
        except Exception as error_submit:
            logging.error("Failed to submit error: %s", str(error_submit))

        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": str(e), "analysis_id": event.get("analysis_id", "unknown")}
            ),
        }
