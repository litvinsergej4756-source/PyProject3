import os
import json
from configuration.configurate_logs import setup_logger
from dotenv import load_dotenv
from openai import OpenAI
import time

logger = setup_logger()
load_dotenv()

class BatchModule:
    def __init__(self, model="gpt-5.1"):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("❌ OPENAI_API_KEY not found in environment variables!")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.batch_dir = "batch_files"

        if not os.path.exists(self.batch_dir):
            os.makedirs(self.batch_dir)

    #The function creates a local JSONL file with requests for batch processing, substituting product names in the prompt and forming a structure for the API.
    def create_input_file(self, items, full_prompt):
        filename = os.path.join(self.batch_dir, f"batch_input_{int(time.time())}.jsonl")
        
        with open(filename, 'w', encoding='utf-8') as f:
            for item in items:
                product_id = item['product_id']
                product_name = item.get('name', '')

                user_content = full_prompt.replace("{product_name}", product_name) 

                request_data = {
                    "custom_id": f"product-id-{product_id}", 
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": user_content}
                        ],
                    }
                }
                f.write(json.dumps(request_data, ensure_ascii=False) + '\n')

        logger.info(f"✅ Created local input file: {filename} with {len(items)} requests.")
        return filename
    
    #The function loads a file with batch queries and launches a new batch processing in the API based on it, returning the created batch job.
    def submit_batch_job(self, input_filepath):
        logger.info("⬆️ Uploading batch input file...")
        file_obj = self.client.files.create(
            file=open(input_filepath, "rb"),
            purpose="batch"
        )
        logger.info(f"✅ File uploaded. ID: {file_obj.id}")

        logger.info("🚀 Creating batch job...")
        batch_job = self.client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )
        logger.info(f"🔥 Batch job created. ID: {batch_job.id}, Status: {batch_job.status}")
        return batch_job
        
    #The function checks and returns the current status of a batch task by its ID.
    def check_status(self, batch_id):
        try:
            return self.client.batches.retrieve(batch_id)
        except Exception as e:
            logger.error(f"Error retrieving batch status for {batch_id}: {e}")
            return None
        
    #The function loads and returns the text content of the batch file results by its ID
    def retrieve_results(self, output_file_id):
        try:
            file_response = self.client.files.content(output_file_id)
            return file_response.text 
        except Exception as e:
            logger.error(f"Error retrieving batch results for file {output_file_id}: {e}")
            return None
    
    #The function checks the status of the batch job and, if it is completed, returns the ID of the output file
    def get_output_file_id(self, batch_job):
        if not batch_job:
            return None, "Job object is None."

        output_file_id = batch_job.output_file_id
        
        if batch_job.status != 'completed':
            return None, f"Batch is not completed (Status: {batch_job.status})"

        if not output_file_id:
            return None, "Completed job has no output file ID."
            
        return output_file_id, None
    
    #The function periodically polls the status of the batch job until it completes, and returns the result or an error on failure.
    def wait_for_completion(self, batch_id, poll_interval=30):
        logger.info(f"⏳ Starting asynchronous wait for batch ID: {batch_id}")

        while True:
            batch_job = self.check_status(batch_id)

            if not batch_job:
                logger.error(f"Failed to retrieve job {batch_id}.")
                return None
            
            status = batch_job.status

            if status == 'completed':
                logger.info("🎉 Batch job COMPLETED.")
                return batch_job
            
            elif status in['failed', 'expired', 'cancelled']:
                logger.error(f"❌ Batch job TERMINATED with status: {status}.")
                return None
            
            else:
                logger.info(f"⌛ Job status is: {status}. Waiting {poll_interval}s...")
                time.sleep(poll_interval)