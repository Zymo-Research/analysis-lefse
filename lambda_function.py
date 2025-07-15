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
        output_file = os.path.join(work_dir, "lda_results.res")

        # Format input - explicitly use Python 2 if needed
        format_cmd = [
            "python",
            "/var/task/lefse_format_input.py",  # The wrapper script handles Python 2
            input_file,
            formatted_file,
            "-u",
            params.get("subject_row", str(2)),
            "-c",
            params.get("class_row", str(1)),
            "-o",
            params.get("norm_value", str(1000000)),
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

        output_file_image = os.path.join(work_dir, "output_file_image.res")
        # replace ' ' with '_' in output_file in bash, write new file for cladogram
        # Read output_file, replace ' ' with '_', write to output_file_image
        with open(output_file, "r") as fin, open(output_file_image, "w") as fout:
            for line in fin:
                fout.write(line.replace(" ", "_"))

        # run cladogram
        cladogram_cmd = [
            "python",
            "/var/task/lefse_plot_cladogram.py",
            output_file_image,
            os.path.join(work_dir, "cladogram.png"),
            "--format",
            "png",
        ]
        logging.info("Running command: %s", " ".join(cladogram_cmd))
        result = subprocess.run(
            cladogram_cmd, capture_output=True, text=True, cwd=work_dir
        )
        if result.returncode != 0:
            raise Exception(f"run_cladogram failed: {result.stderr}")

        # run plot features
        # plot_cmd = [
        #    "python",
        #    "/var/task/lefse_plot_features.py",
        #    formatted_file,
        #    output_file,
        #    os.path.join(work_dir, "features.png"),
        # ]
        # logging.info("Running command: %s", " ".join(plot_cmd))
        # result = subprocess.run(
        #    plot_cmd, capture_output=True, text=True, cwd=work_dir
        # )
        # if result.returncode != 0:
        #    raise Exception(f"run_plot_features failed: {result.stderr}")
        #
        # run plot res
        plot_res_cmd = [
            "python",
            "/var/task/lefse_plot_res.py",
            output_file_image,
            os.path.join(work_dir, "res.png"),
        ]

        logging.info("Running command: %s", " ".join(plot_res_cmd))
        result = subprocess.run(
            plot_res_cmd, capture_output=True, text=True, cwd=work_dir
        )
        if result.returncode != 0:
            raise Exception(f"run_plot_res failed: {result.stderr}")

        # Step 3: Submit results
        logging.info("Submitting results...")
        response = submit_results(
            config=config,
            output_files=[
                output_file,
                os.path.join(work_dir, "cladogram.png"),
                os.path.join(work_dir, "res.png"),
            ],
            mapping_file=mapping_file,
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
