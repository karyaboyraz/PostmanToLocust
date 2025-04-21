import json
from datetime import datetime, timedelta
from locust import HttpUser, task, between, events, User
import requests
import os
import sys
from collections import defaultdict
import re
import logging
from configparser import ConfigParser

# Config dosyasını oku
config = ConfigParser()
config.read('locust.conf')
TEST_TYPE = config.get('locust', 'test-type', fallback='api')

# Locust Configurations
MAX_RESPONSE_TIME = 90
COLLECTION_FILE_NAME = 'Collections/RAC-TEST.postman_collection.json'
LOG_FILE = 'locust.log'

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    filemode='w'  # 'w' mode overwrites the file on each run
)

class TokenManager:
    token_file = "token.json"
    _token_cache = None

    def __init__(self, auth_config):
        self.auth_config = auth_config

    def get_stored_token(self):
        if TokenManager._token_cache:
            return TokenManager._token_cache

        if os.path.exists(TokenManager.token_file):
            with open(TokenManager.token_file, 'r') as file:
                data = json.load(file)
                if datetime.now() < datetime.fromisoformat(data["expiry_time"]):
                    TokenManager._token_cache = data["token"]
                    return data["token"]
        return None

    def save_token(self, token, expiry_time):
        TokenManager._token_cache = token
        with open(TokenManager.token_file, 'w') as file:
            json.dump({"token": token, "expiry_time": expiry_time.isoformat()}, file)

    def fetch_new_token(self, environment):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'username': self.auth_config['username'],
            'password': self.auth_config['password'],
            'grant_type': 'password',
            'client_id': self.auth_config['client_id'],
            'client_secret': self.auth_config['client_secret'],
            'scope': self.auth_config['scope']
        }
        try:
            response = requests.post(self.auth_config['url'], headers=headers, data=data)
            response.raise_for_status()
            token = response.json().get('access_token')
            expiry_time = datetime.now() + timedelta(hours=24)
            self.save_token(token, expiry_time)
            return token
        except requests.exceptions.HTTPError:
            environment.runner.quit()
        except Exception:
            environment.runner.quit()

    def get_token(self, environment):
        return self.get_stored_token() or self.fetch_new_token(environment)

def replace_placeholders(data):
    """ Replaces placeholder values with appropriate data types """
    if isinstance(data, dict):
        return {key: replace_placeholders(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [replace_placeholders(item) for item in data]
    elif isinstance(data, str):
        placeholders = {
            "<integer>": "123",
            "<id>": "123",
            "<string>": "example_string",
            "<boolean>": "true",
            "<array>": "[]",
            "<object>": "{}",
            "<double>": "12.34",
            "<dateTime>": datetime.now().isoformat()
        }
        for placeholder, value in placeholders.items():
            data = data.replace(placeholder, value)
        return re.sub(r'<[^>]+>', '333', data)
    return data

def replace_path_variables(url, headers, url_variables):
    path_variables = re.findall(r':\w+|\{\{\w+\}\}', url)
    for var in path_variables:
        var_name = var.strip(":{}")
        url = url.replace(var, str(headers.get(var_name, url_variables.get(var_name, replace_placeholders(f"<{var_name}>")))))
    return url

def parse_json(raw_body):
    """ Processes JSON body and replaces placeholders with appropriate data types """
    try:
        data = json.loads(raw_body)
        return replace_placeholders(data)
    except json.JSONDecodeError:
        return None

class DynamicTaskSet:
    def __init__(self, parent, auth_config=None):
        self.parent = parent
        self.token_manager = TokenManager(auth_config) if auth_config else None
        self.url_variables = {}
        self.tasks = []
        self.error_summary = defaultdict(list)
        self.seen_errors = set()

        with open(COLLECTION_FILE_NAME) as f:
            self.collection = json.load(f)

        self.extract_variables()
        self.create_tasks(self.collection['item'])

    def extract_variables(self):
        """ Extracts URL variables """
        self.url_variables = {var['key']: var['value'] for var in self.collection.get('variable', [])}

    def create_tasks(self, items, parent_key=None):
        """ Dynamically creates tasks """
        for item in items:
            if 'item' in item:
                self.create_tasks(item['item'], parent_key=item.get('name', 'Unknown'))
            elif 'request' in item:
                self.add_task(item, parent_key)

    def add_task(self, request_item, parent_key):
        """ Adds a task for each request """
        try:
            method = request_item['request']['method'].lower()
            
            # URL'yi farklı formatlardan alabilmek için esnek bir yaklaşım
            url = None
            if 'url' in request_item['request']:
                url_data = request_item['request']['url']
                if isinstance(url_data, str):
                    url = url_data
                elif isinstance(url_data, dict):
                    if 'raw' in url_data:
                        url = url_data['raw']
                    elif 'path' in url_data:
                        url = '/'.join(url_data['path'])
                        if 'host' in url_data:
                            url = f"{url_data['host']}/{url}"
                        if 'query' in url_data:
                            query_params = '&'.join([f"{q['key']}={q['value']}" for q in url_data['query']])
                            url = f"{url}?{query_params}"
            
            if not url:
                raise ValueError("URL could not be extracted from request")
            
            headers = {header['key']: replace_placeholders(header['value']) 
                      for header in request_item['request'].get('header', [])}
            
            if self.token_manager:
                headers["Authorization"] = f"Bearer {self.token_manager.get_token(self.parent.environment)}"
            
            url = replace_path_variables(url, headers, self.url_variables)

            @task
            def task_func(user):
                request_method = getattr(user.client, method)
                body = None

                if 'body' in request_item['request'] and 'raw' in request_item['request']['body']:
                    raw_body = request_item['request']['body']['raw'].strip()
                    if raw_body:
                        body = parse_json(raw_body)

                with request_method(url, headers=headers, json=body, name=url, catch_response=False) as response:
                    error_message = f"{method.upper()} request to {url}. Response: {response.text}"
                    if response.status_code >= 400:
                        if error_message not in self.seen_errors:
                            self.seen_errors.add(error_message)
                            self.error_summary[response.status_code].append(error_message)
                            response.failure(f"Error: {response.status_code} - {response.text}")
                    else:
                        self.check_response_time(response)

            self.tasks.append((f"{parent_key} - {request_item['name']}", task_func))
        
        except KeyError as e:
            error_message = f"KeyError: '{e.args[0]}' not found in the request item or URL."
            if error_message not in self.seen_errors:
                self.seen_errors.add(error_message)
                print(error_message)
        except Exception as e:
            error_message = f"Error processing request: {str(e)}"
            if error_message not in self.seen_errors:
                self.seen_errors.add(error_message)
                print(error_message)

    def replace_url_variables(self, url):
        """ Replaces placeholders in URL """
        try:
            url = replace_placeholders(url)
            for key, value in self.url_variables.items():
                url = url.replace(f"{{{{{key}}}}}", value)
            return url
        except KeyError as e:
            error_message = f"KeyError: '{e.args[0]}' not found in the URL or variables."
            if error_message not in self.seen_errors:
                self.seen_errors.add(error_message)
                print(error_message)
            return url

    def check_response_time(self, response):
        """ Checks response time """
        if response.elapsed.total_seconds() > MAX_RESPONSE_TIME:
            response.failure(f"Response time exceeded {MAX_RESPONSE_TIME} seconds.")
        else:
            response.success()

class WebUser(User):
    wait_time = between(1, 5)
    host = "http://localhost"

    def on_start(self):
        """Web kullanıcısı başlatıldığında çalışır"""
        self.client.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    @task
    def load_homepage(self):
        """Ana sayfayı yükle"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")

    @task
    def load_static_resources(self):
        """Statik kaynakları yükle (CSS, JS, images)"""
        static_resources = [
            "/static/css/main.css",
            "/static/js/app.js",
            "/static/images/logo.png"
        ]
        for resource in static_resources:
            with self.client.get(resource, catch_response=True) as response:
                if response.status_code == 200:
                    response.success()
                else:
                    response.failure(f"Status code: {response.status_code}")

class APITestUser(HttpUser):
    wait_time = between(1, 5)
    host = "http://localhost"
    tasks = []

    def on_start(self):
        """ Loads dynamic task set when test starts """
        self.dynamic_task_set = DynamicTaskSet(self)
        self.tasks = [task for _, task in self.dynamic_task_set.tasks]
        self.environment.dynamic_task_set = self.dynamic_task_set

    @events.test_start.add_listener
    def on_test_start(environment, **kwargs):
        """ Called when test starts """
        # Clear and reinitialize log file
        try:
            # Remove old log file if exists
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            
            # Reconfigure logging
            logging.getLogger().handlers = []  # Clear existing handlers
            logging.basicConfig(
                filename=LOG_FILE,
                level=logging.INFO,
                format='[%(asctime)s] %(levelname)s: %(message)s',
                filemode='w'
            )
            logging.info("Test Started")
        except Exception as e:
            print(f"Error handling log file: {str(e)}")
        print("Test Started")

    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """ Called when test ends """
        print("Test Ended")
        dynamic_task_set = getattr(environment, 'dynamic_task_set', None)
        if dynamic_task_set and dynamic_task_set.error_summary:
            print("\nError Summary:")
            for status_code, messages in dynamic_task_set.error_summary.items():
                print(f"{status_code} Errors:")
                for message in messages:
                    print(f" - {message}")

# Test tipine göre kullanılacak User sınıfını belirle
if TEST_TYPE.lower() == 'client':
    UserClass = WebUser
else:
    UserClass = APITestUser

# Locust'a hangi User sınıfını kullanacağını söyle
class TestUser(UserClass):
    pass