import os
import json
import time
import logging
import argparse
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceExistsError, CosmosHttpResponseError
from dotenv import load_dotenv
from tqdm import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure the log directory exists
log_directory = os.path.dirname(os.path.abspath('migration.log'))
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)

# Load environment variables from .env file
load_dotenv()

# Configuration for source and destination Cosmos DB
source_config = {
    'endpoint': os.getenv('SOURCE_ENDPOINT'),
    'key': os.getenv('SOURCE_KEY'),
    'database_name': os.getenv('SOURCE_DATABASE_NAME'),
    'container_name': os.getenv('SOURCE_CONTAINER_NAME')
}

destination_config = {
    'endpoint': os.getenv('DESTINATION_ENDPOINT'),
    'key': os.getenv('DESTINATION_KEY'),
    'database_name': os.getenv('DESTINATION_DATABASE_NAME'),
    'container_name': os.getenv('DESTINATION_CONTAINER_NAME')
}

def get_cosmos_client(config):
    """
    Create and return a CosmosClient instance using the provided configuration.
    """
    return CosmosClient(config['endpoint'], config['key'])

def get_container(client, database_name, container_name):
    """
    Get a container from the specified database.
    """
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    return container

def count_items(container):
    """
    Count the number of items in the specified container.
    """
    query = "SELECT VALUE COUNT(1) FROM c"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items[0] if items else 0

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def upsert_item_with_retry(container, item):
    """
    Upsert an item with retry mechanism for transient errors.
    """
    try:
        container.upsert_item(body=item)
    except CosmosHttpResponseError as e:
        logging.error(f"Failed to upsert item with id {item['id']}: {e}")
        raise

def migrate_batch(source_container, destination_container, items):
    not_migrated_items = []
    for item in items:
        try:
            destination_container.create_item(body=item)
        except CosmosHttpResponseError as e:
            if e.status_code == 409:  # Conflict
                logging.warning(f"Item with id {item['id']} already exists in the destination container.")
                not_migrated_items.append(item)
            else:
                logging.error(f"Failed to create item with id {item['id']}: {e}")
                raise
    return not_migrated_items

def migrate_data(source_container, destination_container, batch_size, max_workers, socketio=None):
    items = list(source_container.read_all_items(max_item_count=batch_size))
    not_migrated_items = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(migrate_batch, source_container, destination_container, items[i:i + batch_size])
                   for i in range(0, len(items), batch_size)]
        
        for i, future in enumerate(tqdm(as_completed(futures), total=len(futures), desc="Migrating data")):
            not_migrated_items.extend(future.result())
            if socketio:
                progress = (i + 1) / len(futures) * 100
                socketio.emit('update', {'progress': f"Migrating data: {progress:.2f}%"})

    return not_migrated_items

def verify_data(source_container, destination_container):
    """
    Verify that the number of items in the source and destination containers match.
    """
    source_count = count_items(source_container)
    destination_count = count_items(destination_container)
    if source_count == destination_count:
        validation_result = "Data verification successful. Source and destination containers have the same number of items."
        logging.info(validation_result)
        print(validation_result)
    else:
        validation_result = f"Data verification failed. Source has {source_count} items, but destination has {destination_count} items."
        logging.error(validation_result)
        print(validation_result)
    return validation_result

def main():
    """
    Main function to handle the migration process.
    """
    parser = argparse.ArgumentParser(description='Migrate data from one Cosmos DB container to another.')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of items to process in each batch.')
    parser.add_argument('--max-workers', type=int, default=4, help='Maximum number of worker threads.')
    args = parser.parse_args()

    batch_size = args.batch_size
    max_workers = args.max_workers

    # Source Cosmos DB client and container
    source_client = get_cosmos_client(source_config)
    source_container = get_container(source_client, source_config['database_name'], source_config['container_name'])

    # Destination Cosmos DB client and container
    destination_client = get_cosmos_client(destination_config)
    destination_container = get_container(destination_client, destination_config['database_name'], destination_config['container_name'])

    # Count items in source container
    source_count = count_items(source_container)
    logging.info(f"Number of items in source container: {source_count}")
    print(f"Number of items in source container: {source_count}")

    # Migrate data
    start_time = time.time()
    migrate_data(source_container, destination_container, batch_size, max_workers)
    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"Data migration took {duration:.2f} seconds.")
    print(f"Data migration took {duration:.2f} seconds.")

    # Verify data
    verify_data(source_container, destination_container)

if __name__ == '__main__':
    main()