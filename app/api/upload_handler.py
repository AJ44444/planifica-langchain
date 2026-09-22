import uuid
import boto3
from botocore.config import Config
from starlette.requests import Request
from starlette.responses import JSONResponse
from core.config import get_env_variable


MIN_FILE_SIZE = 1
MAX_FILE_SIZE = 10 * 1024 * 1024
EXPIRES_IN_SECONDS = 300


def get_s3_client():
    endpoint_url = get_env_variable("AWS_ENDPOINT_URL")
    bucket_name = get_env_variable("AWS_S3_BUCKET_NAME")
    region_name = get_env_variable("AWS_DEFAULT_REGION")
    aws_access_key_id = get_env_variable("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = get_env_variable("AWS_SECRET_ACCESS_KEY")

    client_kwargs = {
        "endpoint_url": endpoint_url,
        "region_name": region_name,
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "config": Config(signature_version="s3v4")
    }

    s3_client = boto3.client("s3", **client_kwargs)
    return s3_client, bucket_name


async def generate_presigned_url_endpoint(request: Request) -> JSONResponse:
    try:
        if request.method == "OPTIONS":
            return JSONResponse({"status": "ok"}, status_code=200)

        try:
            s3_client, bucket_name = get_s3_client()
        except ValueError as e:
            return JSONResponse({"detail": str(e)}, status_code=500)

        file_id = uuid.uuid4().hex
        s3_key = f"cnb/{file_id}.pdf"

        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket_name,
            Key=s3_key,
            Fields={
                "Content-Type": "application/pdf"
            },
            Conditions=[
                {"Content-Type": "application/pdf"},
                ["content-length-range", MIN_FILE_SIZE, MAX_FILE_SIZE]
            ],
            ExpiresIn=EXPIRES_IN_SECONDS
        )

        return JSONResponse(
            {
                "status": "success",
                "url": presigned_post["url"],
                "fields": presigned_post["fields"],
                "file_key": s3_key,
                "expires_in": EXPIRES_IN_SECONDS
            },
            status_code=200
        )

    except Exception as e:
        return JSONResponse({"detail": f"Internal server error generating upload URL: {str(e)}"}, status_code=500)
