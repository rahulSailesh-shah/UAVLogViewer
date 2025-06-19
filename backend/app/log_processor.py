from MAVdataflash import DataFlash
import json
import os
from datetime import datetime
import pandas as pd
from pandas import Timestamp
import logging

logger = logging.getLogger(__name__)

class PandasJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling Pandas Timestamp objects"""
    def default(self, obj):
        if isinstance(obj, Timestamp):
            return obj.strftime('%Y-%m-%d %H:%M:%S.%f')
        return super().default(obj)

def convert_timestamps_to_strings(data):
    """Convert any Timestamp objects in the data to strings"""
    if isinstance(data, dict):
        return {key: convert_timestamps_to_strings(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_timestamps_to_strings(item) for item in data]
    elif isinstance(data, Timestamp):
        return data.strftime('%Y-%m-%d %H:%M:%S.%f')
    return data

async def process_log_file(bin_file: str, output_dir: str) -> str:
    """
    Process a log file and return the path to the processed JSON file
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Ensured output directory exists: {output_dir}")

        logger.info(f"Opening log file: {bin_file}")
        analysis = DataFlash(bin_file)

        combined_data = {
            "messages": {}
        }

        # Get available message types
        if hasattr(analysis, 'DFdict'):
            message_types = list(analysis.DFdict.keys())
        else:
            message_types = []

        logger.info(f"Processing {len(message_types)} message types: {message_types}")

        for msg_type in message_types:
            try:
                logger.info(f"Processing {msg_type} data...")

                # Get data as pandas DataFrame
                df = analysis.GetData(msg_type)

                if df is not None and not df.empty:
                    # Ensure we only get the first 10 messages
                    df = df.head(10)

                    # Convert DataFrame to dictionary
                    data_dict = df.to_dict(orient='records')

                    # Convert any Timestamp objects to strings
                    data_dict = convert_timestamps_to_strings(data_dict)

                    # Add message count for verification
                    logger.info(f"Added {len(data_dict)} messages for {msg_type}")

                    combined_data["messages"][msg_type] = data_dict
                else:
                    logger.info(f"No data found for {msg_type}")

            except Exception as e:
                logger.error(f"Error processing {msg_type}: {str(e)}")
                continue

        # Verify the data structure
        for msg_type, messages in combined_data["messages"].items():
            if len(messages) > 10:
                logger.warning(f"{msg_type} has {len(messages)} messages, truncating to 10")
                combined_data["messages"][msg_type] = messages[:10]

        # Create output filename based on input filename
        base_name = os.path.splitext(os.path.basename(bin_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_processed.json")

        # Write the combined data to the output file
        with open(output_file, 'w') as f:
            json.dump(combined_data, f, indent=2, cls=PandasJSONEncoder)

        logger.info(f"Successfully created processed file: {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"Error processing log file: {str(e)}")
        raise
