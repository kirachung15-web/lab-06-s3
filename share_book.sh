
#!/bin/bash
# Download one book, upload it privately to S3, and create a temporary link.

set -euo pipefail

# Check that all three arguments were provided.
if [ "$#" -ne 3 ]; then
    echo "Usage: ./share_book.sh <book_url> <bucket_name> <expiration_seconds>"
    exit 1
fi

BOOK_URL="$1"
BUCKET="$2"
EXPIRATION="$3"

# Check that expiration is a positive number.
if ! [[ "$EXPIRATION" =~ ^[0-9]+$ ]] || [ "$EXPIRATION" -eq 0 ]; then
    echo "Error: expiration must be a positive number of seconds."
    exit 1
fi

# Create a local folder for the downloaded book.
mkdir -p books

FILENAME="$(basename "$BOOK_URL")"
FILE_PATH="books/$FILENAME"

# Download the book.
echo "Downloading $FILENAME..."
curl -fL "$BOOK_URL" -o "$FILE_PATH"

# Create the private bucket if it does not exist.
if aws s3 ls "s3://$BUCKET" >/dev/null 2>&1; then
    echo "Bucket already exists: $BUCKET"
else
    echo "Creating private bucket: $BUCKET"
    aws s3 mb "s3://$BUCKET" --region us-east-1
fi

# Upload the book without granting public access.
echo "Uploading $FILENAME to private bucket..."
aws s3 cp "$FILE_PATH" "s3://$BUCKET/$FILENAME" \
    --content-type "text/plain; charset=utf-8"

# Generate a temporary sharing link.
echo "Presigned URL (expires in $EXPIRATION seconds):"
aws s3 presign "s3://$BUCKET/$FILENAME" \
    --expires-in "$EXPIRATION" \
    --region us-east-1
