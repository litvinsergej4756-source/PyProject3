from configuration.configurate_logs import setup_logger
import json

logger = setup_logger()

class ContextController:
    def __init__(self):
        pass

    #The function executes an SQL query and returns all the rows returned.
    def fetch_all(self, connection, sql, params=None):
        result = []
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ SQL Execution Error (fetch_all): {e}")
            raise e
        return result
    
    #The function executes an SQL query and returns one row of results.
    def fetch_one(self, connection, sql, params=None):
        result = None
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ SQL Execution Error (fetch_one): {e}")
            raise e
        return result

    #The function forms and executes an SQL query to get a list of products by ID or by limit, returning all found records.
    def fetch_products(self, connection, limit=None, pid=None):
        if pid is not None:
            WHERE_PART = "WHERE oc_product.product_id = %s"
        else:
            WHERE_PART = ("WHERE oc_product.chatgpt_state IS NULL AND oc_product.status=1 AND price>0")

        sql3 = f"""SELECT oc_product_description.product_id, name, upc, ean 
                FROM oc_product_description join oc_product on oc_product_description.product_id = oc_product.product_id
                    {WHERE_PART}
                    ORDER BY oc_product.product_id DESC
                """
        if pid is not None:
            params = (pid,)
        else:
            sql3 += " LIMIT %s"
            params = (limit,)
            
        return self.fetch_all(connection, sql3, params)
    
    #The function gets the prompt text from the database according to the specified prompt_typ type
    def fetch_prompt(self, connection, prompt_typ):
        sql4 = "SELECT prompt_text FROM oc_prompts_ai WHERE prompt_id = %s"
        params = (prompt_typ,)
        
        row = self.fetch_one(connection, sql4, params)
        
        return row["prompt_text"] if row and row.get("prompt_text") else None
    
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
        response_json = None
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
                pretty_json = json.dumps(response_json, indent=2, ensure_ascii=False)
                log_output = f"\n=== ✅ Product {product_id} Response Start ===\n"
                log_output += pretty_json
                log_output += f"\n=== Product {product_id} Response End ===\n"
            
        except Exception as e:
            logger.error(f"💥 Error inside process_single_batch_result for {data.get('custom_id')}: {e}")
            error_message = f"Internal parsing error: {e}"
            
        return product_id, response_json, log_output, error_message