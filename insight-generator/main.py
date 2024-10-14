import argparse
import os
import boto3
from botocore.config import Config
import json
import glob
import logging
import chardet
import sys
import datetime
import concurrent.futures

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

def read_transcript(file_path):
    # Detect the file encoding
    with open(file_path, 'rb') as file:
        raw_data = file.read()
    detected = chardet.detect(raw_data)
    encoding = detected['encoding']

    logging.info(f"Detected encoding: {encoding}")

    try:
        # Try to decode the file with the detected encoding
        transcript = raw_data.decode(encoding)
        return transcript
    except UnicodeDecodeError:
        logging.warning(f"Failed to decode with {encoding}. Trying common Chinese encodings.")
        # If the detected encoding fails, try common Chinese encodings
        chinese_encodings = ['utf-8', 'gb18030', 'big5', 'gbk']
        for enc in chinese_encodings:
            try:
                transcript = raw_data.decode(enc)
                logging.info(f"Successfully decoded with {enc}")
                return transcript
            except UnicodeDecodeError:
                continue
        
        # If all attempts fail, raise an error
        logging.error(f"Failed to decode file {file_path}. Please check the file encoding.")
        raise UnicodeDecodeError(f"Unable to decode the file with any known encoding.")

def call_bedrock_api(client, model_id, prompt):
    body = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 1,
        "top_p": 0.999,
        "top_k": 200,
    })

    # Log truncated prompt body to console
    if len(body) > 600:
        truncated_body = f"{body[:300]}...{body[-300:]}"
    else:
        truncated_body = body
    logging.info(f"Prompt body (truncated):\n{truncated_body}")

    response = client.invoke_model(
        body=body,
        modelId=model_id,
        accept='application/json',
        contentType='application/json'
    )

    response_body = json.loads(response['body'].read())
    content = response_body['content']

    # Extract the 'text' from the content structure
    if isinstance(content, list):
        extracted_text = content[0]['text']
    else:
        extracted_text = str(content)  # Fallback to string representation if structure is unexpected

    logging.info(f"Raw content structure: {content}")
    logging.info(f"Extracted text: {extracted_text}")

    print("API Response:")
    print(extracted_text)
    print("End of response.")

    return extracted_text  # Return only the extracted text content

def select_prompt(prompt_type):
    summary_prompt = """You are a professional conference secretary.
Below the following instructions there is a raw transcription for you to process. Please apply the tasks to the meeting transcription below:
1. The output should be in markdown format, keep the language of the output the same language as the transcript, and the output language can only be Simplified Chinese or English, only when the transcript is totally in English.
2. Split the transcription into paragraphs which focus on different and progressive topics
3. Generate comprehensive summary for each paragraph at the beginning of each paragraph. Can switch lines and reformat the bullet points to make it nice and clear
4. Convert each original transcript paragraph into professional blog style to make it readable. Put the converted paragraph under each summary of the paragraph, for all summaries. So the reader can see the summaries but also reference the well-readable transcript right below
5. In all the output information, make bold font for all the numbers mentioned. this formatting work should be performed on all the transcription and the summaries
6. Make Italic and 20% bigger in size(but not bolder) for all the insights mentioned that are possibly not covered by the public internet
7. Fully utilize the total output size window. At least use 80% of the configured maximum length of the output

The raw transcription is as below, please generate the detailed summary with insights and facts based on the instructions above:
"""

    faq_prompt = """You are a professional technical writer with knowledge of AWS(Amazon Web Services). 
Below the following instructions there is a raw transcription for you to process. Please apply the tasks to the meeting transcription below:
1. The output should be in markdown format, keep the language of the output the same language as the transcript, and the output language can only be Simplified Chinese or English, only when the transcript is totally in English.
2. Generate a list of frequently asked questions and their answers based on what you find in the transcript
3. Put each question and answer pair in a separate line
4. In all the output information, make bold font for all the numbers mentioned. this formatting work should be performed on all the questions and answers
The raw transcription is as below:
"""
    transcript_prompt = "Provide a cleaned and formatted version of the following transcript: "
    conversation_prompt = "Analyze the conversation flow and key points discussed in the following transcript: "
    mention_prompt = """You are a professional technical writer with knowledge of AWS(Amazon Web Services). 
Below the following instructions there is a raw transcription for you to process. Please apply the tasks to the meeting transcription below:
1. The output should be in markdown format, keep the language of the output the same language as the transcript, and the output language can only be Simplified Chinese or English, only when the transcript is totally in English.
2. Extract and list all mentions of AWS products, services, or important concepts. Keep the context of mentioning in the output, but group by the service name or product name.
The raw transcription is as below:
    """

    prompts = {
        "summary": summary_prompt,
        "faq": faq_prompt,
        "transcript": transcript_prompt,
        "conversation": conversation_prompt,
        "mention": mention_prompt
    }

    return prompts.get(prompt_type, summary_prompt)

def process_transcript(transcript, client, model_id, md_file, prompt_type, chunk_size=3000, overlap=300):
    chunks = []
    
    for i in range(0, len(transcript), chunk_size - overlap):
        chunk = transcript[i:i + chunk_size]
        chunks.append(chunk)

    results = []
    base_prompt = select_prompt(prompt_type)

    for i, chunk in enumerate(chunks):
        # Ensure chunk is a string
        if isinstance(chunk, list):
            chunk = ' '.join(chunk)
        prompt = base_prompt + chunk
        try:
            content = call_bedrock_api(client, model_id, prompt)
            results.append(content)
            write_to_markdown(md_file, content)
            print(f"Chunk {i+1}/{len(chunks)} processed and written to {md_file}")
        except Exception as e:
            logging.error(f"Error processing chunk {i+1}: {str(e)}")

    return results

def write_to_markdown(file_path, content):
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(content + '\n\n')
    logging.info(f"Appended content to: {file_path}")

def process_single_prompt(transcript, client, model_id, md_file, prompt_type, chunk_size, overlap):
    results = process_transcript(transcript, client, model_id, md_file, prompt_type, chunk_size, overlap)
    print(f"All results for {prompt_type} have been processed and written to {md_file}")
    return results

def main():
    parser = argparse.ArgumentParser(description="Process meeting transcript using Bedrock API")
    parser.add_argument("--folder", required=True, help="Folder containing the transcript file (relative to Downloads)")
    parser.add_argument("--prompttype", required=True, help="Type(s) of prompt to use for processing (space-separated if multiple)")
    args = parser.parse_args()

    # Split the prompttype argument into a list
    prompt_types = args.prompttype.split()

    # Get the user's home directory
    home_dir = os.path.expanduser("~")
    # Construct the path to the Downloads folder
    downloads_dir = os.path.join(home_dir, "Downloads")
    # Construct the path to the specified folder
    folder_path = os.path.join(downloads_dir, args.folder)

    # Find the first .txt file in the folder
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        print(f"Error: No .txt files found in {folder_path}")
        return

    transcript_file = txt_files[0]
    print(f"Using transcript file: {transcript_file}")

    if not os.path.exists(transcript_file):
        print(f"Error: Transcript file not found at {transcript_file}")
        return

    transcript = read_transcript(transcript_file)

    # Configure Bedrock client
    bedrock_config = Config(
        region_name='us-east-1',  # Replace with your preferred region
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    bedrock_client = boto3.client('bedrock-runtime', config=bedrock_config)

    model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Claude 3.5 Sonnet model ID

    # Process each prompt type concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(prompt_types)) as executor:
        futures = []
        for prompt_type in prompt_types:
            # Create the markdown file path with prompt type appended
            md_file = os.path.splitext(transcript_file)[0] + f'_{prompt_type}.md'
            
            # If the markdown file already exists, archive it with a timestamp
            if os.path.exists(md_file):
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_file = f"{os.path.splitext(md_file)[0]}_{prompt_type}_{timestamp}.md"
                os.rename(md_file, archive_file)
                logging.info(f"Archived existing file to: {archive_file}")

            # Create a new markdown file
            open(md_file, 'w').close()
            logging.info(f"Created new markdown file: {md_file}")

            future = executor.submit(process_single_prompt, transcript, bedrock_client, model_id, md_file, prompt_type, 999999999, 20)
            futures.append(future)

        # Wait for all tasks to complete
        concurrent.futures.wait(futures)

    print("All prompt types have been processed.")

if __name__ == "__main__":
    main()
