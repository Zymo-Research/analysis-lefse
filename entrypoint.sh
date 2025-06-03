#!/bin/bash
set -e

# Parameters
: "${WORKSPACE_ID:=db2a6d11-ddaf-4df7-a5c2-1fa34b03f537}"
: "${API_KEY:=test}"
: "${ANALYSIS_ID:=001784e5-948f-4c1b-a480-a664da6e 022d}"
INPUT_FILE="input_data.txt"
FORMATTED_FILE="formatted.in"
: "${OUTPUT_FILE:=lda_results.txt}"
: "${CLASS_COL:=2}"
: "${SUBJECT_COL:=1}"
: "${NORM_VALUE:=1000000}"
: "${PORTAL_API_BASE_URL:=http://host.docker.internal:8000}"

# Step 1: Request input data, transform from DocumentDB, and generate input file
echo "Fetching and transforming input data..."

python3 /app/lefse_preprocessing.py

# Step 2: Run LEfSe
echo "Running format_input.py..."
format_input.py /data/${INPUT_FILE} /data/${FORMATTED_FILE} -c $CLASS_COL -u $SUBJECT_COL -o $NORM_VALUE

echo "Running run_lefse.py..."
if run_lefse.py /data/${FORMATTED_FILE} /data/${OUTPUT_FILE}; then
    echo "LDA analysis complete."
    # Step 3: Submit results (same as before)
    echo "Preparing and submitting results..."
    python3 /app/submit_results.py
    echo "Submission complete."
else
    echo "run_lefse.py failed!" >&2
    python3 /app/submit_results.py --error_message "Lefse failed"
    exit 1
fi
