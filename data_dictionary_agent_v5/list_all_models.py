import os
import boto3
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

def list_model_ids():
    # Read credentials from environment variables
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    if not aws_access_key or not aws_secret_key:
        raise ValueError("AWS credentials not found in environment variables.")

    # Create Bedrock client in ap-south-1 region
    client = boto3.client(
        "bedrock",
        region_name="ap-south-1",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key
    )

    try:
        response = client.list_foundation_models()

        print("Available Model IDs in ap-south-1:\n")
        for model in response.get("modelSummaries", []):
            print(model.get("modelId"))

    except Exception as e:
        print(f"Error fetching models: {e}")

if __name__ == "__main__":
    list_model_ids()