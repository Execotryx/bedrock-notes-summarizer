# Bedrock Notes Summarizer

An AWS Lambda function that automatically summarizes meeting notes using AWS Bedrock's DeepSeek V3 model. The service processes multipart email messages, generates concise summaries with key points and action items, and stores them in Amazon S3 with intelligent file naming.

## Features

- **AI-Powered Summarization**: Leverages AWS Bedrock's DeepSeek V3 model for intelligent meeting notes summarization
- **Multipart Email Support**: Extracts and processes text content from multipart email message formats
- **Automatic File Naming**: Uses AI to infer descriptive, SEO-friendly file names based on meeting content
- **S3 Storage**: Automatically stores summaries in S3 with organized date-based folder structure (`YYYY/MM/DD/filename.txt`)
- **Automatic Bucket Creation**: Creates the S3 bucket if it doesn't exist
- **Error Handling**: Comprehensive error handling with detailed logging and graceful degradation
- **Type Safety**: Full type hints for improved code maintainability

## Architecture

### Components

1. **NotesSummarizer**: Core class that handles:
   - Extraction of text from multipart email messages
   - Communication with AWS Bedrock Converse API
   - Meeting notes summarization
   - Intelligent file name inference

2. **S3BucketManager**: Manages S3 operations:
   - Automatic bucket creation with proper region configuration
   - File uploads with date-based organization

3. **lambda_handler**: AWS Lambda entry point:
   - Input validation
   - Base64 decoding of message content
   - Orchestration of summarization and storage

### AWS Services Used

- **AWS Lambda**: Serverless compute for running the summarization service
- **AWS Bedrock**: AI/ML service providing access to DeepSeek V3 model
- **Amazon S3**: Object storage for summarized meeting notes
- **IAM**: Identity and Access Management for service permissions

## Prerequisites

- Python 3.9 or higher
- AWS Account with appropriate permissions
- AWS CLI configured (for local development)
- Access to AWS Bedrock with DeepSeek V3 model enabled in `eu-north-1` region

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd bedrock-notes-summarizer
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure AWS Credentials

Ensure your AWS credentials are configured with permissions for:
- Bedrock Runtime (converse)
- S3 (create bucket, put object, head bucket)
- Lambda (if deploying as Lambda function)

## Configuration

### Region Configuration

The default region is set to `eu-north-1`. To change it, modify the `PARAM_REGION` constant in [lambda_function.py](lambda_function.py#L17):

```python
PARAM_REGION: str = "eu-north-1"
```

### Model Configuration

The default model is DeepSeek V3. To use a different model, modify the `SUMMARIZER_MODEL_ID` in the `NotesSummarizer` class:

```python
SUMMARIZER_MODEL_ID: str = "deepseek.v3-v1:0"
```

### S3 Bucket Name

The default bucket name is `meeting-notes-summaries-bucket`. To change it, modify the initialization in [lambda_function.py](lambda_function.py#L232):

```python
s3_bucket_manager: S3BucketManager = S3BucketManager(bucket_name="your-bucket-name")
```

## Usage

### Input Format

The Lambda function expects an event with the following structure:

```json
{
  "body": "<base64-encoded-multipart-email-message>"
}
```

The `body` parameter should contain a base64-encoded multipart email message (MIME format) with meeting notes in the text/plain parts.

### Example Request

```python
import base64
import json

# Sample email content
email_content = b"""Content-Type: text/plain; charset="utf-8"

Meeting Notes - Q1 Planning
Date: January 8, 2026

Attendees: John, Sarah, Mike

Discussion Points:
1. Reviewed Q4 results - exceeded targets by 15%
2. Set Q1 goals for new product launch
3. Budget allocation for marketing campaign

Action Items:
- John: Prepare marketing budget proposal by Jan 15
- Sarah: Finalize product roadmap by Jan 12
- Mike: Schedule follow-up meeting for Jan 20
"""

event = {
    "body": base64.b64encode(email_content).decode('utf-8')
}

# Invoke Lambda function
response = lambda_handler(event, None)
```

### Response Format

**Success Response (200):**
```json
{
  "statusCode": 200,
  "body": "Summary of the meeting notes with key points and action items..."
}
```

**Error Response (400):**
```json
{
  "statusCode": 400,
  "body": "{\"error\": \"Missing required parameter: body\"}"
}
```

**Error Response (500):**
```json
{
  "statusCode": 500,
  "body": "{\"error\": \"Error description...\"}"
}
```

### S3 Storage Structure

Summaries are stored in S3 with the following structure:
```
s3://meeting-notes-summaries-bucket/
├── 2026/
│   ├── 1/
│   │   ├── 8/
│   │   │   ├── q1-planning-meeting-summary.txt
│   │   │   └── budget-review-discussion-summary.txt
│   │   └── 9/
│   │       └── product-launch-meeting-summary.txt
```

## Deployment

### Deploy to AWS Lambda

1. **Create a deployment package:**

```bash
# Create a directory for the deployment package
mkdir lambda-package
cd lambda-package

# Install dependencies
pip install -r ../requirements.txt -t .

# Copy the Lambda function
cp ../lambda_function.py .

# Create a ZIP file
zip -r ../lambda-deployment.zip .
cd ..
```

2. **Create the Lambda function:**

```bash
aws lambda create-function \
  --function-name bedrock-notes-summarizer \
  --runtime python3.9 \
  --role arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_LAMBDA_ROLE \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://lambda-deployment.zip \
  --timeout 60 \
  --memory-size 512
```

3. **Update function configuration (if needed):**

```bash
aws lambda update-function-configuration \
  --function-name bedrock-notes-summarizer \
  --timeout 60 \
  --memory-size 512
```

### IAM Permissions

Create an IAM role with the following policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock-runtime:Converse"
      ],
      "Resource": "arn:aws:bedrock:eu-north-1::foundation-model/deepseek.v3-v1:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutObject",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::meeting-notes-summaries-bucket",
        "arn:aws:s3:::meeting-notes-summaries-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Development

### Local Testing

```python
from lambda_function import lambda_handler
import base64

# Prepare test event
test_event = {
    "body": base64.b64encode(b"Your meeting notes content").decode('utf-8')
}

# Invoke handler
response = lambda_handler(test_event, None)
print(response)
```

### Type Checking

The project uses type hints. Run type checking with mypy:

```bash
pip install mypy
mypy lambda_function.py
```

## Error Handling

The function includes comprehensive error handling:

- **Missing Parameters**: Returns 400 with descriptive error message
- **Empty Content**: Returns 400 if transcript is empty after decoding
- **Bedrock API Errors**: Catches exceptions with retry logic (max 3 attempts)
- **S3 Errors**: Handles bucket creation and upload failures
- **General Exceptions**: Returns 500 with error details and logs full traceback

## Performance Considerations

- **Max Tokens**: Set to 1024 for summaries (configurable in `inferenceConfig`)
- **Temperature**: Set to 0.2 for more deterministic outputs
- **Timeout**: Recommended Lambda timeout of 60 seconds
- **Memory**: Recommended Lambda memory of 512MB
- **Retry Logic**: Automatic retry with max 3 attempts for Bedrock API calls

## Limitations

- Only processes `text/plain` content from multipart messages
- Requires base64-encoded input
- Supports only DeepSeek V3 model by default (can be changed)
- Region locked to `eu-north-1` by default
- Maximum summary length limited to 1024 tokens

## Dependencies

See [requirements.txt](requirements.txt) for full list:

- **boto3**: AWS SDK for Python
- **python-dotenv**: Environment variable management
- **pydantic**: Data validation
- **boto3-stubs**: Type stubs for boto3 (development)

## Troubleshooting

### Common Issues

1. **"Model not found" error**
   - Ensure DeepSeek V3 model is available in your region
   - Check model ID spelling: `deepseek.v3-v1:0`

2. **Permission denied errors**
   - Verify IAM role has necessary Bedrock and S3 permissions
   - Check bucket name doesn't conflict with existing buckets

3. **Timeout errors**
   - Increase Lambda timeout setting (default: 60 seconds)
   - Check network connectivity to Bedrock service

4. **Empty summaries**
   - Verify input is properly base64-encoded
   - Check that multipart message contains text/plain parts

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

[Specify your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check AWS Bedrock documentation
- Review CloudWatch logs for detailed error messages

## Changelog

### Version 1.0.0
- Initial release
- DeepSeek V3 integration
- Multipart email support
- Intelligent file naming
- Date-based S3 organization
