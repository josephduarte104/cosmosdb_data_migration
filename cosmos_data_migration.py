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

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(filename='migration.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

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
    Get and return a container client for the specified database and container.
    """
    database = client.get_database_client(database_name)
    return database.get_container_client(container_name)

def count_items(container):
    """
    Count and return the number of items in the specified container.
    """
    return len(list(container.read_all_items()))

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

def migrate_data(source_container, destination_container, batch_size=100):
    """
    Migrate data from the source container to the destination container.
    Uses batch processing to handle large datasets efficiently.
    """
    count = 0
    query = "SELECT * FROM c"
    items = source_container.query_items(query=query, enable_cross_partition_query=True, max_item_count=batch_size)
    for item in tqdm(items, desc="Migrating items"):
        try:
            upsert_item_with_retry(destination_container, item)
            count += 1
        except CosmosResourceExistsError:
            logging.warning(f"Item with id {item['id']} already exists in the destination container. Skipping.")
        except Exception as e:
            logging.error(f"Failed to migrate item with id {item['id']}: {e}")
    logging.info(f"Data migration completed successfully. {count} items migrated.")
    print(f"Data migration completed successfully. {count} items migrated.")

def verify_data(source_container, destination_container):
    """
    Verify that the number of items in the source and destination containers match.
    """
    source_count = count_items(source_container)
    destination_count = count_items(destination_container)
    if source_count == destination_count:
        logging.info("Data verification successful. Source and destination containers have the same number of items.")
        print("Data verification successful. Source and destination containers have the same number of items.")
    else:
        logging.error(f"Data verification failed. Source has {source_count} items, but destination has {destination_count} items.")
        print(f"Data verification failed. Source has {source_count} items, but destination has {destination_count} items.")

def main():
    """
    Main function to handle the migration process.
    """
    parser = argparse.ArgumentParser(description='Migrate data from one Cosmos DB container to another.')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of items to process in each batch.')
    args = parser.parse_args()

    batch_size = args.batch_size

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
    migrate_data(source_container, destination_container, batch_size)
    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"Data migration took {duration:.2f} seconds.")
    print(f"Data migration took {duration:.2f} seconds.")

    # Verify data
    verify_data(source_container, destination_container)

if __name__ == '__main__':
    main()