#!/bin/bash
set -e

# Parameters
: "${WORKSPACE_ID:=db2a6d11-ddaf-4df7-a5c2-1fa34b03f537}"
: "${API_KEY:=test}"
: "${ANALYSIS_ID:=9fe09e3b-ecd2-4b76-b6ee-6be386dc43c7}"
INPUT_FILE="input_data.txt"
FORMATTED_FILE="formatted.in"
: "${OUTPUT_FILE:=lda_results.txt}"
: "${CLASS_COL:=1}"
: "${SUBJECT_COL:=2}"
: "${NORM_VALUE:=1000000}"

# Step 1: Request input data, transform from DocumentDB, and generate input file
echo "Fetching and transforming input data..."

python3 /app/lefse_preprocessing.py

# Step 2: Run LEfSe
echo "Running format_input.py..."
format_input.py /data/${INPUT_FILE} /data/${FORMATTED_FILE} -c $CLASS_COL -u $SUBJECT_COL -o $NORM_VALUE

echo "Running run_lefse.py..."
run_lefse.py /data/${FORMATTED_FILE} /data/${OUTPUT_FILE} -l 0.5

echo "LDA analysis complete."

# Step 3: Submit results (same as before)
echo "Preparing and submitting results..."

python3 /app/submit_results.py

echo "Submission complete."
