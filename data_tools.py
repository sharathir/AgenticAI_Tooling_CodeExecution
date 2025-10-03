# data_tools.py
import os
import pandas as pd

def analyze_applicant_data(file_path: str, filter_column: str, filter_value: str) -> tuple[str, list]:
    """
    Analyzes an applicant data file (CSV) to count and extract applicants 
    matching a specific criteria.

    Returns:
        tuple:
          - str: Summary message (human-readable)
          - list[dict]: Matching applicants as dicts
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at path: {file_path}", []

    try:
        # Load the data
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip().str.lower()

        if filter_column.lower() not in df.columns:
            return f"Error: Column '{filter_column}' not found in the data file.", []

        # Filter the data
        filtered_df = df[df[filter_column].str.upper() == filter_value.upper()]

        # Results
        count = len(filtered_df)
        summary = f"Query successful. Found {count} applicants where {filter_column} equals '{filter_value}'."
        records = filtered_df.to_dict(orient="records")

        return summary, records

    except Exception as e:
        return f"An unexpected error occurred during analysis: {e}", []
