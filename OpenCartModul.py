from configuration.configurate_logs import setup_logger
from configuration.config import host, user, password, db_name
import re
import pymysql

logger = setup_logger()

class DatabaseModel:
    def __init__(self):
        self.connection = None       

    def __connect(self):
        try:
            self.connection = pymysql.connect(
                host=host,
                port=3306,
                user=user,
                password=password,
                database=db_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
            #logger.info("✅ successfully connected to MySQL")
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")

    def __close(self):
        if self.connection:
            try:
                self.connection.close()
                #logger.info("🔒 The connection is closed")
            except:
                pass

    #The function executes an SQL query and returns all the rows returned.
    def fetch_all(self, sql, params=None):
        result = [] 
        try:
            self.__connect()
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ SQL Execution Error (fetch_all): {e}")
            raise e
        finally:
            self.__close()
        return result

     #The function executes an SQL query and returns one row of results.
    def fetch_one(self, sql, params=None):
        result = None
        self.__connect()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ SQL Execution Error (fetch_one): {e}")
            raise e
        finally:
            self.__close()
        return result   
    
   
    def execute_sql_batch(self, statements):
        self.__connect()
        try:
            cursor = self.connection.cursor()           
            for sql, params in statements:
                # params kann None oder ein Tupel/Liste sein
                if params is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, params)

            self.connection.commit()
        except Exception as e:
            logger.error(f"❌ SQL Execution Error (fetch_one): {e}")
            if self.connection.is_connected():
                self.connection.rollback()
            raise e
        finally:
            self.__close()

class OpencartProductController:  
    def __init__(self):
        self.db_model = DatabaseModel() 
        
    #The fetch_products_and_prompt function retrieves products and the corresponding prompt from the database.
    def fetch_products_and_prompt(self, limit=None, pid=None, prompt_typ=1):
        items = self.__read_products(limit=limit, pid=pid)
        prompt_text = self.__read_prompt(prompt_typ)
        return items, prompt_text
    
    def ProcessProduct(self, product_id, response):        
        logger.info(f"Processing of Item ID={product_id}'") 
        try:           
            if response is None or "error" in response:
                try:
                    statements = [
                        ("UPDATE oc_product SET chatgpt_calltime = NOW() WHERE product_id = %s", (product_id))
                    ]
                    self.db_model.execute_sql_batch(statements)
                    logger.warning(f"⚠️ ChatGPT returned error → product {product_id} left with chatgpt_state=NULL")
                finally:
                    pass  
            else:
                self.UpdateItemDescAndSeo(product_id, response)
        except Exception as e:
            logger.error(f"❌ Error in process_product for ID={product_id}: {e}")
    
    def UpdateItemDescAndSeo(self, product_id, response_json):        
        try:
            row = self.db_model.fetch_one("SELECT description FROM oc_product_description WHERE product_id = %s", product_id)
            old_description = row["description"] if row and row["description"] else ""

            description_html = response_json.get("Verkaufstext", "")
            description_html = re.sub(r"(?<!<br>)(?<=\.)\s+", "<br/>", description_html)

            meta_title = response_json.get("titel", "")
            meta_keyword = response_json.get("Kurzbeschreibung", "")
            tag_seo = response_json.get("SEO", "")
            oenummer = self.__array_to_string(response_json.get("OE-Nummer", []))
            quelle =  self.__array_to_string(response_json.get("Quelle", []))
            if oenummer:
                oenummer="<div class='item-oe-nummer'>OE-Nummer: " + oenummer + "</div>"
            if quelle:
                quelle="<div class='item-quelle'>Quelle: <br/>" + quelle + "</div>" 

            compare_text = self.__array_to_html_table(response_json.get("kompatibilität", []))           

            block1 = f"<div class='item-desc-text'>{description_html}</div>"
            block2 = ""
            if compare_text:
                block2 = f"<div class='item-compability-block'><h4>Kompatibilitätsliste (ohne Gewähr)</h4>{compare_text}</div>"
                
            full_description = f"<div class='item-desc-text'>{old_description}</div> <div class='addedTextAi'>{block1}{oenummer}{block2}</div>".strip()
            # logger.info(full_description)

            sql1 = """
                UPDATE oc_product_description
                SET description = %s,
                    meta_title = %s,
                    meta_keyword = %s,
                    tag = %s
                WHERE product_id = %s
            """
            sql2 = "UPDATE oc_product SET chatgpt_state = 1, chatgpt_calltime = NOW() WHERE product_id = %s"
            sql3 = "UPDATE oc_kb_ebay_profile_products SET status='Updated', revise='1' WHERE ebay_status='Active' and id_product = %s"
            statements = [
                (sql1, (full_description, meta_title, meta_keyword,  tag_seo, product_id)),
                (sql2, (product_id)),
                (sql3, (product_id))
            ]
            self.db_model.execute_sql_batch(statements)
                
            logger.info(f"✅ Updated product {product_id}, chatgpt_state=1")
        except Exception as e:
            logger.error(f"❌ Database update error: {e}")
        finally:
            pass


    #The read_products function reads products from the database — either one by pid or a list by limit.
    def __read_products(self, limit=None, pid=None):       
        items = []
        try:
            items = self.__fetch_products(limit=limit, pid=pid)            
            logger.info(f"Received {len(items)} items for processing (chatgpt_state IS NULL)")
            
            if items:
                logger.info("📝 Product names:")
                for item in items:
                    print(f"  - {item['product_id']} {item['name']}")

        except Exception as e:
            logger.error(f"❌ Error reading goods: {e}")
        finally:
            pass
            
        return items
        
    def __read_prompt(self, prompt_typ):
        prompt_text = None
        try:
            prompt_text = self.__fetch_prompt(prompt_typ)
            
            if prompt_text:
                logger.info("✅ Prompt successfully loaded from the database")
            else:
                logger.warning(f"⚠️ Prompt not found for type")
                
        except Exception as e:
            logger.error(f"❌ Error reading prompt: {e}")
        
        return prompt_text
    
    #The function forms and executes an SQL query to get a list of products by ID or by limit, returning all found records.
    def __fetch_products(self, limit=None, pid=None):
        if pid is not None:
            WHERE_PART = " p.product_id = %s"
        else:
            WHERE_PART = f"""  ( p.chatgpt_state IS NULL AND pd.language_id=2 
                                 AND p.status=1 AND p.sku <> ''  
                                 AND p.quantity>0 AND p.price>0 AND ebay_user>0 AND (p.upc <> '' or p.ean <> ''))
                          """

        sql = f"""SELECT pd.product_id, pd.name, p.upc, p.ean 
                    FROM oc_product_description as pd 
                        JOIN oc_language as l on pd.language_id = l.language_id
                        JOIN oc_product as p on pd.product_id = p.product_id
                    WHERE l.name = 'German' AND {WHERE_PART}
                    ORDER BY p.ebay_updatetime
                """
        if pid is not None:
            params = (pid,)
        else:
            sql += " LIMIT %s"
            params = (limit,)
            
        return self.db_model.fetch_all(sql, params)   
    
    #The function gets the prompt text from the database according to the specified prompt_typ type
    def __fetch_prompt(self, prompt_typ):
        sql = "SELECT prompt_text FROM oc_prompts_ai WHERE prompt_typ = %s"
        params = (prompt_typ,)       
        row = self.db_model.fetch_one(sql, params)        
        return row["prompt_text"] if row and row.get("prompt_text") else None

    def __array_to_html_table(self, array):
        if not array or not isinstance(array, list):
            return ""

        html = """
            <table class='item-compability-table'>
                <tr>
                    <th>Marke</th>
                    <th>Modell</th>
                    <th>Baujahr</th>
                    <th>Motorvarianten</th>
                    <th>Bemerkung</th>
                </tr>
            """

        for item in array:
            html += f"""
        <tr>
            <td>{item.get('marke', '')}</td>
            <td>{item.get('modell', '')}</td>
            <td>{item.get('baujahr_von', '')} - {item.get('baujahr_bis', '')}</td>
            <td>{'<br>'.join(item.get('motorvarianten', []))}</td>
            <td>{item.get('bemerkung', '')}</td>
        </tr>
            """

        html += "</table>"
        return html

    def __array_to_string(self, array):
        if not array or not isinstance(array, list):
            return ""
        return ", ".join(array)
    