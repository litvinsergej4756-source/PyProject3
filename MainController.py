import json
from ChatgptAiManager import ChatgptAiManager
from BatchModule import BatchModule
from DbModule import DbModule
from configuration.configurate_logs import setup_logger
from configuration.print_help import print_help
import sys
import time

logger = setup_logger()
POLL_INTERVAL_SECONDS = 300

class MainController:
    def __init__(self):
        self.ai = ChatgptAiManager()
        self.db_module = DbModule()
        self.batch_module = BatchModule()

    def send_to_chatgpt(self, name, full_prompt):
        #response = self.ai.generate_description(product_name=name, prompt_text=full_prompt)
        response = self.ai.call_itemdesc_with_browsing(prompt_text=full_prompt) 
            
        if not isinstance(response, dict):
            logger.warning(f"⚠️ ChatGPT's response is raw: {response}")
            return None

        formatted_json = json.dumps(response, ensure_ascii=False, indent=4)
        logger.info(f"📤 ChatGPT's response to '{name}':\n{formatted_json}")
        return response
    
    #The function processes the list of products synchronously — that is, one by one.
    def process_synchronously(self, items, full_prompt):
        logger.info(f"🔄 Running in SYNCHRONOUS mode. Processing {len(items)} items.")

        if not full_prompt:
            logger.error("❌ Cannot process: Prompt not loaded.")
            return
        
        for item in items:
            product_id = item["product_id"]
            product_name = item.get('name', '')
            manufactorId = ""
            if item.get("ean"):
                manufactorId += item["ean"] + " "
            if item.get("upc"):
                manufactorId += item["upc"] + " "
            if manufactorId.strip():
                name += ", weitere Herstellernummer: " + manufactorId

            logger.info(f"➡️ Requesting synchronous completion for ID={product_id}")

            try:
                response_json = self.ai.generate_description(product_name=product_name, prompt_text=full_prompt)
                self.db_module.update_database(product_id, response_json)
                
                logger.info(f"✅ Successfully updated product ID={product_id}")

            except Exception as e:
                logger.error(f"❌ Critical failure during synchronous processing for ID={product_id}: {e}")
                time.sleep(1)

    #The function gets the batch processing results by batch_id, loads them and updates the database
    def process_finished_batch_results(self, batch_id):
        logger.info(f"🔄 Starting retrieval of results for Batch ID: {batch_id}")
        try:
            final_job = self.batch_module.check_status(batch_id) 
            output_file_id, error_message = self.batch_module.get_output_file_id(final_job)
            
            if error_message:
                logger.error(f"❌ Failed to process batch {batch_id}: {error_message}")
                return
                
            jsonl_results_text = self.batch_module.retrieve_results(output_file_id)

            if jsonl_results_text:
                self.db_module.process_batch_results(jsonl_results_text)
                logger.info("Batch results processed and database updated.")
            else:
                logger.error(f"❌ Could not retrieve JSONL content for batch {batch_id}.")
                            
        except Exception as e:
            logger.error(f"❌ Critical failure during batch result processing for ID={batch_id}: {e}")

    #The process_all function receives products by limit or pid and processes them one by one
    def process_all(self, mode, limit=None, pid=None, batch_id_to_monitor=None):
        logger.info("Start of goods processing")

        if batch_id_to_monitor:
            self.process_finished_batch_results(batch_id_to_monitor)
            logger.info("Finishing processing after monitor.")
            return
        
        if limit is None and pid is None:
            limit = 3
            logger.info("ℹ️ No parameters provided — using default limit=3")

        items, prompt_text  = self.db_module.fetch_products_and_prompt(limit=limit, pid=pid)

        if not items:
            if pid:
                logger.error(f"❌ Product with ID={pid} not found or already processed")
            else:
                logger.warning("⚠️ There are no products to process")
            return
        
        if not prompt_text:
            logger.error("❌ Prompt is empty or not found!")
            return
        
        if mode == 1:
            final_limit = limit if limit else (1 if pid else None)
            logger.info(f"🔄 Running in BATCH SUBMISSION mode (limit={final_limit}).")
            input_file_path = self.batch_module.create_input_file(items, prompt_text)
            batch_job = self.batch_module.submit_batch_job(input_file_path)
            
            logger.info(f"✨ To monitor status, run: python MainController.py batch_id={batch_job.id}")
        
        elif mode == 0:
            self.process_synchronously(items, prompt_text)

        else:
            logger.error(f"❌ Unknown mode: {mode}. Use 0 (Synchronous) or 1 (Batch).")
        logger.info("Finishing processing.")

if __name__ == "__main__":
    limit = None
    pid = None
    mode = None
    batch_id_to_monitor = None

    help_flags = ['-h', '--help', 'h=1']
    if any(arg in sys.argv[1:] for arg in help_flags):
        print_help()
        sys.exit(0)

    #Processes command line arguments, setting limit and pid after checking their numeric format
    for arg in sys.argv[1:]:
        if arg.startswith("mode="):
            try:
                mode = int(arg.split("=")[1])
            except ValueError:
                logger.error("❌ Error: mode must be 0 or 1")
                sys.exit(1)
        elif arg.startswith("pid="):
            try:
                pid = int(arg.split("=")[1])
            except ValueError:
                logger.error("❌ Error: pid must be a number")
                sys.exit(1)
        elif arg.startswith("count="):
            try:
                limit = int(arg.split("=")[1])
            except ValueError:
                logger.error("❌ Error: count must be a number")
                sys.exit(1)
        elif arg.startswith("batch_id="):
            batch_id_to_monitor = arg.split("=")[1]

    controller = MainController()

    if mode is not None or batch_id_to_monitor is not None:
        controller.process_all(mode=mode, limit=limit, pid=pid, batch_id_to_monitor=batch_id_to_monitor)