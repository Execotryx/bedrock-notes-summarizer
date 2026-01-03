import json
import traceback
import boto3
from email import message_from_bytes
from email.message import Message
from typing import Any, TYPE_CHECKING
from botocore.config import Config
from botocore.exceptions import ClientError
from datetime import datetime
from base64 import b64decode

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime.client import BedrockRuntimeClient
    from mypy_boto3_bedrock_runtime.type_defs import ConverseResponseTypeDef, MessageTypeDef
    from mypy_boto3_s3.client import S3Client

PARAM_REGION: str = "eu-north-1"

s3: "S3Client" = boto3.client(
    service_name="s3",
    region_name=PARAM_REGION
)


class S3BucketManager:
    """
    Manages interactions with an S3 bucket for storing and retrieving code files.
    """
    
    def __init__(self, bucket_name: str) -> None:
        """Initialize the S3 bucket manager with the given S3 client and bucket name."""
        self.s3_client = s3
        self.bucket_name = bucket_name
        # create the bucket if it doesn't exist
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError:
            self.s3_client.create_bucket(Bucket=self.bucket_name, CreateBucketConfiguration={"LocationConstraint": PARAM_REGION} )
    
    def upload(self, key: str, summarized_note: str) -> None:
        """
        Upload code content to the specified S3 bucket under the given key.
        
        Args:
            key: The S3 object key (file name)
            code_content: The code content to upload
        """
        self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=summarized_note)


bedrock_runtime_client: "BedrockRuntimeClient" = boto3.client(
    "bedrock-runtime", 
    config=Config(
        region_name=PARAM_REGION, 
        retries={"max_attempts": 3}
        )
    )


class NotesSummarizer:
    """
    Handles summarization of meeting notes using AWS Bedrock's Converse API.
    """
    PROMPT_SECTION_SEPARATOR: str = "\n###\n"
    SUMMARIZER_MODEL_ID: str = "deepseek.v3-v1:0"
    
    def _extract_text_from_multidata(self, multidata: bytes | bytearray) -> str:
        """
        Extract text content from multipart email message data.
        
        Args:
            multidata: Raw email message bytes or bytearray
        
        Returns:
            Extracted text content from all text/plain parts
        """
        message: Message = message_from_bytes(multidata)

        text: str = ""
        if message.is_multipart():
            for part in message.walk():
                text += self.__extract_text_from_part(part)
        else:
            text += self.__extract_text_from_part(message)

        return text.strip() if text else ""

    def __extract_text_from_part(self, part: Message) -> str:
        """
        Extract text from a single message part if it's plain text.
        
        Args:
            part: Email message part to extract text from
        
        Returns:
            Decoded text content if part is text/plain, otherwise empty string
        """
        content_type: str = part.get_content_type()
        if content_type == "text/plain":
            payload: Any = part.get_payload(decode=True)
            return payload.decode(part.get_content_charset() or "utf-8")
        return ""

    def _extract_text(self, message: dict[str, Any]) -> str:
        """
        Extract text content from a Bedrock message structure.
        
        Args:
            message: Bedrock message dictionary containing content blocks
        
        Returns:
            str: Extracted text from the first text block, or empty string if not found
        """
        content: list[Any] = message.get("content", [])
        text: str = next((str(b["text"]) for b in content if isinstance(b, dict) and "text" in b), "")
        return text
    
    def _call_bedrock(self, messages: list["MessageTypeDef"]) -> "ConverseResponseTypeDef":
        """
        Call AWS Bedrock Converse API with configured model and inference settings.
        
        Args:
            messages: Conversation messages in Bedrock format
        
        Returns:
            Bedrock API response containing the model's output
        """
        return bedrock_runtime_client.converse(
            modelId=self.SUMMARIZER_MODEL_ID,
            system=[{"text": "You are a helpful secretary who excels at summarizing various notes. Be clear and concise."}],
            messages=messages,
            inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
        )
    
    def _get_bedrock_response_and_append(self, conversation: list["MessageTypeDef"]) -> Any:
        """
        Call Bedrock, extract the response message, and append it to the conversation.
        
        Args:
            conversation: The conversation history to send and update
        
        Returns:
            The extracted message dictionary from Bedrock's response
        """
        response: "ConverseResponseTypeDef" = self._call_bedrock(conversation)
        message: Any = response["output"].get("message")
        if message is None:
            raise ValueError("Bedrock response did not contain a message in output")
        conversation.append(message)
        return message

    def infer_meeting_notes_file_name(self, notes: str) -> str:
        """
        Infer a suitable file name for the meeting notes summary based on the content.
        
        Args:
            notes: The meeting notes text
        Returns:
            str: Inferred file name for the meeting notes summary
        """
        prompt: str = (
            "Based on the following meeting notes, suggest a concise and descriptive file name for the summary.\n"
            "The file name should be in lowercase, use hyphens instead of spaces, and end with .txt. "
            "Avoid using special characters or punctuation other than hyphens.\n"
            "Respond with only the file name, without any additional text or explanation.\n"
            "Example 1:\n"
            "Meeting Notes: 'Discussed project timeline and assigned tasks to team members.'\n"
            "Suggested File Name: project-timeline-and-tasks-summary.txt\n"
            "Example 2:\n"
            "Meeting Notes: 'Reviewed quarterly financial results and planned budget adjustments.'\n"
            "Suggested File Name: quarterly-financial-results-and-budget-planning-summary.txt\n\n"
            f"Meeting Notes: '{notes}'\n"
            "Suggested File Name: "
        )

        messages: list["MessageTypeDef"] = []

        messages.append(
            { "role": "user", "content": [ { "text": prompt } ] }
        )

        try:
            response_message: Any = self._get_bedrock_response_and_append(messages)
            file_name: str = self._extract_text(response_message)
            return file_name
        except Exception as e:
            print(f"Error during Bedrock call for file name inference: {e}")
            traceback.print_exc()
            return "meeting-notes-summary.txt"

    def summarize_meeting_notes(self, notes: bytes | bytearray) -> str:
        """
        Summarize meeting notes using AWS Bedrock.
        
        Args:
            notes: Raw meeting notes as multipart message bytes
        
        Returns:
            Summary of the meeting notes with key points and action items
        """
        text: str = self._extract_text_from_multidata(notes)

        meeting_notes_summarization_prompt: str = (
            "Please provide a concise summary of the following meeting notes, highlighting key points and action items:"
            f"{self.PROMPT_SECTION_SEPARATOR}{text}{self.PROMPT_SECTION_SEPARATOR}")

        messages: list["MessageTypeDef"] = []

        messages.append(
            { "role": "user", "content": [ { "text": meeting_notes_summarization_prompt } ] }
        )

        try:
            response_message: Any = self._get_bedrock_response_and_append(messages)
            summary: str = self._extract_text(response_message)
            return summary
        except Exception as e:
            print(f"Error during Bedrock call: {e}")
            traceback.print_exc()
            return "An error occurred while summarizing the meeting notes."

PARAM_TRANSCRIPT: str = "body"

def _validate_input(body_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Validate required input parameters for code generation request.
    
    Args:
        body_data: Dictionary containing request parameters
    
    Returns:
        Error response dict with statusCode 400 if validation fails, None if valid
    """
    if PARAM_TRANSCRIPT not in body_data:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Missing required parameter: {PARAM_TRANSCRIPT}'})
        }
    return None

bedrock_notes_summarizer: NotesSummarizer = NotesSummarizer()
s3_bucket_manager: S3BucketManager = S3BucketManager(bucket_name="meeting-notes-summaries-bucket")

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda function handler.
    
    Args:
        event: Lambda event data
        context: Lambda runtime context
    
    Returns:
        API Gateway response with status code and body
    """
    try:
        # Validate required input parameters
        validation_error: dict[str, Any] | None = _validate_input(event)
        if validation_error:
            return validation_error
        
        message: bytes = b64decode(event[PARAM_TRANSCRIPT])
        if not message:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Transcript content is empty'})
            }

        summarized_note: str = bedrock_notes_summarizer.summarize_meeting_notes(message)

        # get year, month and date for S3 key. Compose S3 key, starting with "{year}/{month}/{date}/{filename_inferred_from_summarized_notes}.ext"
        file_name: str = bedrock_notes_summarizer.infer_meeting_notes_file_name(summarized_note)
        
        now = datetime.now()
        s3_key = f"{now.year}/{now.month}/{now.day}/{file_name}"

        s3_bucket_manager.upload(s3_key, summarized_note)

        return {
            'statusCode': 200,
            'body': summarized_note
        }
    except Exception as e:
        print(f"Error in lambda_handler: {e}")
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
