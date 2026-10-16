
#!/usr/bin/env python3
"""Download Project Gutenberg books and stage them in a public S3 bucket."""

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

# Set up logging to report progress and errors.
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Create one shared S3 client for the entire script.
s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the book list, index page, and bucket name from the command line."""
    if len(sys.argv) < 4:
        log.error(
            "Usage: python stage_books.py <book_list> <index_file> <bucket>"
        )
        sys.exit(1)

    list_file = sys.argv[1]
    index_path = sys.argv[2]
    bucket = sys.argv[3]

    return list_file, index_path, bucket


def download_books(list_file, dest_dir):
    """Download books from a URL list and return their local file paths."""
    os.makedirs(dest_dir, exist_ok=True)
    downloaded_files = []

    with open(list_file, "r", encoding="utf-8") as file:
        urls = [line.strip() for line in file if line.strip()]

    for url in urls:
        filename = url.split("/")[-1]
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info(f"Skipping existing book: {filename}")
            downloaded_files.append(path)
            continue

        try:
            log.info(f"Downloading: {filename}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(path, "wb") as file:
                file.write(response.content)

            downloaded_files.append(path)
            time.sleep(1)

        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")

    log.info(f"Downloaded or found {len(downloaded_files)} books")
    return downloaded_files


def create_bucket(bucket):
    """Create the S3 bucket if it does not already exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code not in ("404", "NoSuchBucket"):
            log.error(f"Cannot access bucket {bucket}: {e}")
            return False

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True

    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Allow public read access to objects in the S3 bucket."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }

        s3.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(policy),
        )

        log.info(f"Bucket {bucket} is now publicly readable")
        return True

    except ClientError as e:
        log.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload downloaded books to the S3 bucket."""
    uploaded = 0

    for path in file_paths:
        filename = os.path.basename(path)

        try:
            s3.upload_file(
                path,
                bucket,
                filename,
                ExtraArgs={
                    "ContentType": "text/plain; charset=utf-8"
                },
            )

            log.info(f"Uploaded: {filename}")
            uploaded += 1

        except (ClientError, OSError) as e:
            log.error(f"Error uploading {filename}: {e}")

    log.info(f"Successfully uploaded {uploaded} books")
    return uploaded

def upload_index(bucket, index_path):
    """Upload the HTML index page to S3."""
    try:
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )

        log.info("Uploaded index.html")
        return True

    except (ClientError, OSError) as e:
        log.error(f"Error uploading index.html: {e}")
        return False


def main():
    """Download books, create a public bucket, and upload the files."""
    list_file, index_path, bucket = parse_args()

    # Step 1: Download books
    log.info("Starting book downloads...")
    try:
        books = download_books(list_file, "books")
    except OSError as e:
        log.error(f"Could not read or save books: {e}")
        sys.exit(1)

    if not books:
        log.error("No books were downloaded.")
        sys.exit(1)

    # Step 2: Create the S3 bucket
    if not create_bucket(bucket):
        sys.exit(1)

    # Step 3: Make the bucket public
    if not make_public(bucket):
        sys.exit(1)

    # Step 4: Upload the books
    uploaded = upload_files(bucket, books)

    # Step 5: Upload index.html
    index_uploaded = upload_index(bucket, index_path)

    if uploaded != len(books) or not index_uploaded:
        log.error("Some files failed to upload.")
        sys.exit(1)

    log.info("All files uploaded successfully!")
    log.info(f"Public index: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()

