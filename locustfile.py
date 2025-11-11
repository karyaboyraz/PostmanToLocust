import json
from datetime import datetime
from locust import HttpUser, task, between, events, User
@events.init_command_line_parser.add_listener
def add_test_type_option(parser):
    parser.add_argument("--test-type", type=str, default="api", help="Test type: 'api' or 'client'")
import requests
import os
import sys
from collections import defaultdict
import re
import logging
from configparser import ConfigParser

# Prometheus metrics exporter
from flask import Response
import threading
import time

# Config dosyasını oku
config = ConfigParser()
config.read('locust.conf')
TEST_TYPE = config.get('settings', 'test-type', fallback='api')

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
    """ Replace path variables and Postman variables like {{baseUrl}} in URL """
    # First replace Postman variables like {{baseUrl}}
    # Pattern: {{variableName}}
    postman_vars = re.findall(r'\{\{(\w+)\}\}', url)
    for var_name in postman_vars:
        replacement = None
        if var_name in url_variables:
            replacement = url_variables[var_name]
        elif var_name in headers:
            replacement = headers[var_name]
        
        if replacement:
            # Replace {{varName}} with the value
            url = url.replace(f'{{{{{var_name}}}}}', str(replacement))
    
    # Then replace path variables like :id (these are typically in URL paths)
    path_variables = re.findall(r':(\w+)', url)
    for var_name in path_variables:
        replacement = None
        if var_name in headers:
            replacement = headers[var_name]
        elif var_name in url_variables:
            replacement = url_variables[var_name]
        else:
            replacement = replace_placeholders(f"<{var_name}>")
        
        url = url.replace(f':{var_name}', str(replacement))
    
    return url

def parse_json(raw_body):
    """ Processes JSON body and replaces placeholders with appropriate data types """
    try:
        data = json.loads(raw_body)
        return replace_placeholders(data)
    except json.JSONDecodeError:
        return None

class DynamicTaskSet:
    def __init__(self, parent):
        self.parent = parent
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
        # Extract variables from collection if they exist
        collection_variables = {var['key']: var['value'] for var in self.collection.get('variable', [])}
        
        # Set default baseUrl if not found in collection
        self.url_variables = collection_variables.copy()
        if 'baseUrl' not in self.url_variables:
            self.url_variables['baseUrl'] = 'https://www.obilet.com'
        
        # Extract base URL for HttpUser host
        base_url = self.url_variables.get('baseUrl', 'https://www.obilet.com')
        # Remove trailing slash if present
        base_url = base_url.rstrip('/')
        self.base_url = base_url
        
        # Set host in parent user's environment
        if hasattr(self.parent, 'environment') and self.parent.environment:
            self.parent.environment.host = base_url

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

            url = replace_path_variables(url, headers, self.url_variables)
            
            # Convert full URL to relative path if it starts with baseUrl
            from urllib.parse import urlparse
            base_url = self.base_url if hasattr(self, 'base_url') else self.url_variables.get('baseUrl', 'https://www.obilet.com')
            base_url = base_url.rstrip('/')
            
            # Initialize url_name
            url_name = url
            
            # If URL is a full URL and starts with baseUrl, convert to relative path
            if url.startswith(base_url):
                # Extract path from full URL
                parsed = urlparse(url)
                url_path = parsed.path
                if parsed.query:
                    url_path += f"?{parsed.query}"
                url = url_path
                url_name = url_path
            elif url.startswith('http://') or url.startswith('https://'):
                # Full URL but different base - extract path for name, but we'll need to handle this differently
                parsed = urlparse(url)
                url_path = parsed.path
                if parsed.query:
                    url_path += f"?{parsed.query}"
                url_name = url_path
                # For now, keep the full URL - we'll handle it in the task function
                # But this shouldn't happen if baseUrl is set correctly
                print(f"Warning: URL {url} doesn't match baseUrl {base_url}")
            else:
                # Relative URL - use as is
                url_name = url

            @task
            def task_func(user):
                request_method = getattr(user.client, method)
                body = None

                if 'body' in request_item['request'] and 'raw' in request_item['request']['body']:
                    raw_body = request_item['request']['body']['raw'].strip()
                    if raw_body:
                        # Replace {{baseUrl}} and other variables in body if it's a string
                        if isinstance(raw_body, str):
                            # Replace Postman variables in body
                            body_vars = re.findall(r'\{\{(\w+)\}\}', raw_body)
                            for var_name in body_vars:
                                if var_name in self.url_variables:
                                    raw_body = raw_body.replace(f'{{{{{var_name}}}}}', str(self.url_variables[var_name]))
                                elif var_name in headers:
                                    raw_body = raw_body.replace(f'{{{{{var_name}}}}}', str(headers[var_name]))
                        body = parse_json(raw_body)

                # Use the processed URL (now relative path)
                with request_method(url, headers=headers, json=body, name=url_name, catch_response=False) as response:
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
    host = "https://www.obilet.com"  # Default host, will be updated from collection variables
    tasks = []

    def on_start(self):
        """ Loads dynamic task set when test starts """
        self.dynamic_task_set = DynamicTaskSet(self)
        self.tasks = [task for _, task in self.dynamic_task_set.tasks]
        self.environment.dynamic_task_set = self.dynamic_task_set
        # Update host from baseUrl variable if available
        if hasattr(self.dynamic_task_set, 'base_url'):
            self.host = self.dynamic_task_set.base_url
            self.environment.host = self.dynamic_task_set.base_url

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

# Expose only TestUser to Locust to avoid duplicate user class names
del WebUser, APITestUser

# Prometheus metrics exporter
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Add Prometheus metrics endpoint to Locust web UI"""
    
    def metrics_handler():
        """Generate Prometheus metrics from Locust stats"""
        stats = environment.stats
        runner = environment.runner
        
        metrics = []
        # Get current number of users from runner
        current_users = 0
        if runner and hasattr(runner, 'user_count'):
            current_users = runner.user_count
        elif runner and hasattr(runner, 'user_classes_count'):
            current_users = sum(runner.user_classes_count.values())
        
        metrics.append('# HELP locust_users_current Current number of users')
        metrics.append('# TYPE locust_users_current gauge')
        metrics.append(f'locust_users_current {current_users}')
        
        metrics.append('# HELP locust_users_total Total number of users')
        metrics.append('# TYPE locust_users_total gauge')
        metrics.append(f'locust_users_total {current_users}')
        
        metrics.append('# HELP locust_requests_total Total number of requests')
        metrics.append('# TYPE locust_requests_total counter')
        metrics.append(f'locust_requests_total{{method="",name="Total"}} {stats.total.num_requests}')
        
        metrics.append('# HELP locust_requests_failures_total Total number of failed requests')
        metrics.append('# TYPE locust_requests_failures_total counter')
        metrics.append(f'locust_requests_failures_total{{method="",name="Total"}} {stats.total.num_failures}')
        
        metrics.append('# HELP locust_response_time_seconds Response time in seconds')
        metrics.append('# TYPE locust_response_time_seconds summary')
        # Always export count, even if 0
        metrics.append(f'locust_response_time_seconds_count{{method="",name="Total"}} {stats.total.num_requests}')
        if stats.total.num_requests > 0:
            try:
                metrics.append(f'locust_response_time_seconds{{method="",name="Total",quantile="0.5"}} {stats.total.median_response_time / 1000.0}')
                metrics.append(f'locust_response_time_seconds{{method="",name="Total",quantile="0.95"}} {stats.total.get_response_time_percentile(0.95) / 1000.0}')
                metrics.append(f'locust_response_time_seconds{{method="",name="Total",quantile="0.99"}} {stats.total.get_response_time_percentile(0.99) / 1000.0}')
                metrics.append(f'locust_response_time_seconds_sum{{method="",name="Total"}} {stats.total.total_response_time / 1000.0}')
            except (AttributeError, ZeroDivisionError, TypeError):
                pass
        
        # Also export as histogram for better Grafana compatibility
        metrics.append('# HELP locust_response_time_median_seconds Median response time in seconds')
        metrics.append('# TYPE locust_response_time_median_seconds gauge')
        if stats.total.num_requests > 0:
            try:
                metrics.append(f'locust_response_time_median_seconds{{method="",name="Total"}} {stats.total.median_response_time / 1000.0}')
            except (AttributeError, ZeroDivisionError):
                metrics.append(f'locust_response_time_median_seconds{{method="",name="Total"}} 0')
        else:
            metrics.append(f'locust_response_time_median_seconds{{method="",name="Total"}} 0')
        
        metrics.append('# HELP locust_response_time_p95_seconds 95th percentile response time in seconds')
        metrics.append('# TYPE locust_response_time_p95_seconds gauge')
        if stats.total.num_requests > 0:
            try:
                metrics.append(f'locust_response_time_p95_seconds{{method="",name="Total"}} {stats.total.get_response_time_percentile(0.95) / 1000.0}')
            except (AttributeError, ZeroDivisionError):
                metrics.append(f'locust_response_time_p95_seconds{{method="",name="Total"}} 0')
        else:
            metrics.append(f'locust_response_time_p95_seconds{{method="",name="Total"}} 0')
        
        metrics.append('# HELP locust_response_time_p99_seconds 99th percentile response time in seconds')
        metrics.append('# TYPE locust_response_time_p99_seconds gauge')
        if stats.total.num_requests > 0:
            try:
                metrics.append(f'locust_response_time_p99_seconds{{method="",name="Total"}} {stats.total.get_response_time_percentile(0.99) / 1000.0}')
            except (AttributeError, ZeroDivisionError):
                metrics.append(f'locust_response_time_p99_seconds{{method="",name="Total"}} 0')
        else:
            metrics.append(f'locust_response_time_p99_seconds{{method="",name="Total"}} 0')
        
        metrics.append('# HELP locust_requests_per_second Requests per second')
        metrics.append('# TYPE locust_requests_per_second gauge')
        metrics.append(f'locust_requests_per_second {stats.total.total_rps}')
        
        # Add metrics for each endpoint
        for key, entry in stats.entries.items():
            # Handle both tuple (method, name) and string keys
            if isinstance(key, tuple):
                method = key[0] or ""
                name = key[1] or ""
            else:
                method = entry.method or ""
                name = str(key)
            
            # Sanitize name for Prometheus labels
            safe_name = str(name).replace('"', '\\"').replace('\n', '\\n').replace('\\', '\\\\')[:200]  # Limit length
            safe_method = str(method).replace('"', '\\"').replace('\n', '\\n')[:50]
            
            metrics.append(f'locust_requests_total{{method="{safe_method}",name="{safe_name}"}} {entry.num_requests}')
            metrics.append(f'locust_requests_failures_total{{method="{safe_method}",name="{safe_name}"}} {entry.num_failures}')
            
            # Always export count
            metrics.append(f'locust_response_time_seconds_count{{method="{safe_method}",name="{safe_name}"}} {entry.num_requests}')
            
            if entry.num_requests > 0:
                try:
                    metrics.append(f'locust_response_time_seconds{{method="{safe_method}",name="{safe_name}",quantile="0.5"}} {entry.median_response_time / 1000.0}')
                    metrics.append(f'locust_response_time_seconds{{method="{safe_method}",name="{safe_name}",quantile="0.95"}} {entry.get_response_time_percentile(0.95) / 1000.0}')
                    metrics.append(f'locust_response_time_seconds{{method="{safe_method}",name="{safe_name}",quantile="0.99"}} {entry.get_response_time_percentile(0.99) / 1000.0}')
                    metrics.append(f'locust_response_time_seconds_sum{{method="{safe_method}",name="{safe_name}"}} {entry.total_response_time / 1000.0}')
                    
                    # Also export as separate gauge metrics for easier querying
                    metrics.append(f'locust_response_time_median_seconds{{method="{safe_method}",name="{safe_name}"}} {entry.median_response_time / 1000.0}')
                    metrics.append(f'locust_response_time_p95_seconds{{method="{safe_method}",name="{safe_name}"}} {entry.get_response_time_percentile(0.95) / 1000.0}')
                    metrics.append(f'locust_response_time_p99_seconds{{method="{safe_method}",name="{safe_name}"}} {entry.get_response_time_percentile(0.99) / 1000.0}')
                except (AttributeError, ZeroDivisionError, TypeError):
                    # Skip if response time data is not available
                    metrics.append(f'locust_response_time_median_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
                    metrics.append(f'locust_response_time_p95_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
                    metrics.append(f'locust_response_time_p99_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
            else:
                metrics.append(f'locust_response_time_median_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
                metrics.append(f'locust_response_time_p95_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
                metrics.append(f'locust_response_time_p99_seconds{{method="{safe_method}",name="{safe_name}"}} 0')
        
        return '\n'.join(metrics) + '\n'
    
    def prometheus_metrics():
        """Handler for /metrics endpoint"""
        try:
            metrics_data = metrics_handler()
            return Response(
                metrics_data,
                mimetype='text/plain; version=0.0.4; charset=utf-8'
            )
        except Exception as e:
            return Response(f'Error generating metrics: {str(e)}', status=500)
    
    # Add /metrics endpoint to Locust web UI when it's available
    def setup_metrics_endpoint():
        if hasattr(environment, 'web_ui') and environment.web_ui and hasattr(environment.web_ui, 'app'):
            environment.web_ui.app.add_url_rule('/metrics', 'metrics', prometheus_metrics, methods=['GET'])
            print("Prometheus metrics exporter enabled at http://localhost:8089/metrics")
        else:
            # Retry after a short delay if web_ui is not ready yet
            threading.Timer(1.0, setup_metrics_endpoint).start()
    
    setup_metrics_endpoint()