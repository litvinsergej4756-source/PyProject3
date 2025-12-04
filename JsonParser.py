from configuration.configurate_logs import setup_logger
from OpenCartModul import OpencartProductController
import json

logger = setup_logger()

class JsonParser:
    def __init__(self):
        self.opencart = OpencartProductController()      
    
    #The function parses JSONL text line by line, returning JSON objects and logging decoding errors.
    @staticmethod
    def parse_jsonl_results(json_results_text):
        for line in json_results_text.splitlines():
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSONL parsing error: '{e}' in line: {line[:100]}...")
                    continue
                
    #The function processes the result of a single product from a batch query
    def process_single_batch_result(self, data):
        product_id = None
        content_json = None
        log_output = None
        error_message = None

        try:
            custom_id = data.get('custom_id')
            if not custom_id:
                return None, None, None, "Missing custom_id"

            product_id = int(custom_id.split('-')[-1])
            response_obj = data.get('response')
            error_obj = data.get('error')
            
            if response_obj:
                response_json = response_obj.get('body')
            if error_obj:
                error_message = error_obj.get('message')

            if response_json:
                # 2. Den inneren JSON-String aus content holen
                content_str = response_json["choices"][0]["message"]["content"]

                # 3. Inneren JSON-String erneut parsen
                content_json = json.loads(content_str)
                
                pretty_json = json.dumps(content_json, indent=2, ensure_ascii=False)
                log_output = f"\n=== ✅ Product {product_id} Response Start ===\n"
                log_output += pretty_json
                log_output += f"\n=== Product {product_id} Response End ===\n"
            
        except Exception as e:
            logger.error(f"💥 Error inside process_single_batch_result for {data.get('custom_id')}: {e}")
            error_message = f"Internal parsing error: {e}"
            
        return product_id, content_json, log_output, error_message
    
    #The function processes a JSONL result set (with multiple products) and updates the corresponding products in the database.
    def process_batch_results(self, jsonl_results_text):
        successful_updates = 0
        
        for data in self.parse_jsonl_results(jsonl_results_text):
            product_id = -1
            try:
                product_id, response_json, log_output, error_message = \
                    self.process_single_batch_result(data)
                
                if not product_id or not isinstance(product_id, int):
                    continue

                if response_json:
                    if log_output:
                        # print(log_output)
                        logger.info(log_output)

                    self.opencart.ProcessProduct(product_id, response_json) 
                    successful_updates += 1                    

                elif error_message:
                    logger.error(f"❌ Batch error for ID={product_id}: {error_message}")
                    print(f"❌ Batch error for ID={product_id}: {error_message}")
            except Exception as e:
                logger.error(f"💥 Critical Loop Error processing item {product_id}: {e}")

        logger.info(f"🎉 Batch results processing finished. Updated {successful_updates} products.")