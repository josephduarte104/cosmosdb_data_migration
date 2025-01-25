from flask import Flask, request, render_template, jsonify
from flask_socketio import SocketIO
import logging
import os
import threading
import time
from cosmos_data_migration import get_cosmos_client, get_container, count_items, migrate_data
import traceback
from markupsafe import escape

# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Ensure the log directory exists
log_directory = os.path.dirname(os.path.abspath('migration.log'))
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Configure logging to log to both a file and the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)

logging.info("Logging is configured.")

# Global variable to store migration status
migration_status = {
    'progress': '',
    'errors': '',
    'validation': '',
    'source_config': {},
    'destination_config': {},
    'source_count': 0,
    'skipped_count': 0
}

# Route for the main page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json()
        source_config = {
            'endpoint': escape(data['source_endpoint']),
            'key': escape(data['source_key']),
            'database_name': escape(data['source_database_name']),
            'container_name': escape(data['source_container_name'])
        }
        destination_config = {
            'endpoint': escape(data['destination_endpoint']),
            'key': escape(data['destination_key']),
            'database_name': escape(data['destination_database_name']),
            'container_name': escape(data['destination_container_name'])
        }
        batch_size = int(data['batch_size'])

        # Start migration in a separate thread
        threading.Thread(target=migrate, args=(source_config, destination_config, batch_size)).start()
        return jsonify({'status': 'Migration started'}), 202

    return render_template('index.html')

def item_exists_in_target(item, destination_container):
    """
    Checks if an item exists in the destination container.
    
    Args:
        item (dict): The item to check.
        destination_container (ContainerProxy): The destination container.
    
    Returns:
        bool: True if the item exists in the destination container, False otherwise.
    """
    try:
        query = f"SELECT * FROM c WHERE c.id = '{item['id']}'"
        items = list(destination_container.query_items(query=query, enable_cross_partition_query=True))
        return len(items) > 0
    except Exception as e:
        logging.error(f"Error checking if item exists in target: {e}")
        return False

def migrate(source_config, destination_config, batch_size):
    try:
        start_time = time.time()
        
        # Initialize clients and containers for both source and destination Cosmos DB
        source_client = get_cosmos_client(source_config)
        source_container = get_container(source_client, source_config['database_name'], source_config['container_name'])

        destination_client = get_cosmos_client(destination_config)
        destination_container = get_container(destination_client, destination_config['database_name'], destination_config['container_name'])

        # Count the number of items in the source container and log the count
        source_count = count_items(source_container)
        logging.info(f"Number of items in source container: {source_count}")
        migration_status['source_count'] = source_count
        migration_status['skipped_count'] = 0
        socketio.emit('update', {
            'progress': "Migration started",
            'progress_percentage': 0,
            'start_time': start_time
        })

        # Retrieve all items from the source container
        source_items = list(source_container.read_all_items())
        progress_percentage = 0
        successfully_migrated_count = 0

        # Migrate items
        for i, item in enumerate(source_items):
            if item_exists_in_target(item, destination_container):
                migration_status['skipped_count'] += 1
                continue

            try:
                destination_container.create_item(body=item)
                successfully_migrated_count += 1
            except Exception as e:
                if 'Conflict' in str(e):
                    migration_status['skipped_count'] += 1
                    continue
                else:
                    logging.error(f"Error migrating item {item['id']}: {traceback.format_exc()}")
                    raise e

            # Update progress
            progress_percentage = (i + 1) / source_count * 100
            elapsed_time = time.time() - start_time
            migration_status['progress'] = f"Migrating item {i + 1} of {source_count}"
            socketio.emit('update', {
                'progress': migration_status['progress'],
                'progress_percentage': progress_percentage,
                'elapsed_time': elapsed_time
            })

        # Final progress update
        final_progress = f"Data migration completed successfully. {successfully_migrated_count} items migrated. {migration_status['skipped_count']} items skipped."
        logging.info(final_progress)
        migration_status['progress'] = final_progress
        socketio.emit('update', {
            'progress': migration_status['progress'],
            'progress_percentage': 100,
            'elapsed_time': time.time() - start_time
        })

        # Start validation in a separate background task
        socketio.start_background_task(validate_data, source_container, destination_container)
    except Exception as e:
        logging.error(f"Error during migration: {traceback.format_exc()}")
        migration_status['errors'] = str(e)
        socketio.emit('update', {'errors': migration_status['errors']})

def validate_data(source_container, destination_container):
    try:
        source_count = count_items(source_container)
        destination_count = count_items(destination_container)
        validation_message = f"Validation completed. Source count: {source_count}, Destination count: {destination_count}"
        logging.info(validation_message)
        socketio.emit('update', {'validation': validation_message})
    except Exception as e:
        logging.error(f"Error during validation: {e}")
        socketio.emit('update', {'errors': str(e)})

def count_items(container):
    """
    Count the number of items in a Cosmos DB container.
    
    Args:
        container (ContainerProxy): The container to count items in.
    
    Returns:
        int: The number of items in the container.
    """
    query = "SELECT VALUE COUNT(1) FROM c"
    result = list(container.query_items(query=query, enable_cross_partition_query=True))
    return result[0] if result else 0

# Run the Flask app with SocketIO
if __name__ == '__main__':
    socketio.run(app, debug=True)