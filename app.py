from flask import Flask, request, render_template
from flask_socketio import SocketIO
import logging
import time
import datetime
from cosmos_data_migration import get_cosmos_client, get_container, count_items, migrate_data
from werkzeug.exceptions import BadRequest
import os

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
    'not_migrated_items': []
}

# Route for the main page

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            source_config = {
                'endpoint': request.form['source_endpoint'],
                'key': request.form['source_key'],
                'database_name': request.form['source_database_name'],
                'container_name': request.form['source_container_name']
            }
            destination_config = {
                'endpoint': request.form['destination_endpoint'],
                'key': request.form['destination_key'],
                'database_name': request.form['destination_database_name'],
                'container_name': request.form['destination_container_name']
            }
            batch_size = int(request.form['batch_size'])
        except KeyError as e:
            logging.error(f"Missing form data: {e}")
            raise BadRequest(f"Missing form data: {e}")
        batch_size = int(request.form['batch_size'])

        # Log form data (excluding keys for security)
        source_config_log = {k: v for k, v in source_config.items() if k != 'key'}
        destination_config_log = {k: v for k, v in destination_config.items() if k != 'key'}
        logging.info(f"Source Config: {source_config_log}")
        logging.info(f"Destination Config: {destination_config_log}")
        logging.info(f"Batch Size: {batch_size}")

        # Store the configurations in the global status
        migration_status['source_config'] = source_config
        migration_status['destination_config'] = destination_config

        # Start the migration in a background task
        socketio.start_background_task(migrate, source_config, destination_config, batch_size)

        return render_template('index.html')

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
        # Attempt to read the item from the destination container
        destination_container.read_item(item['id'], partition_key=item['partition_key'])
        return True
    except Exception:
        return False

def migrate(source_config, destination_config, batch_size):
    """
    Migrates data from a source Cosmos DB container to a destination Cosmos DB container.
    
    Args:
        source_config (dict): Configuration for the source Cosmos DB.
        destination_config (dict): Configuration for the destination Cosmos DB.
        batch_size (int): Number of items to migrate in each batch.
    
    Emits:
        'update' (dict): Emits progress updates and errors via socketio.
    
    Raises:
        Exception: If an error occurs during migration.
    """
    try:
        # Initialize clients and containers for both source and destination Cosmos DB
        source_client = get_cosmos_client(source_config)
        source_container = get_container(source_client, source_config['database_name'], source_config['container_name'])

        destination_client = get_cosmos_client(destination_config)
        destination_container = get_container(destination_client, destination_config['database_name'], destination_config['container_name'])

        # Count the number of items in the source container and log the count
        source_count = count_items(source_container)
        logging.info(f"Number of items in source container: {source_count}")
        migration_status = {'progress': f"Number of items in source container: {source_count}", 'errors': ''}
        socketio.emit('update', {
            'progress': migration_status['progress']
        })

        # Retrieve all items from the source container
        source_items = list(source_container.read_all_items())
        progress_percentage = 0
        successfully_migrated_count = 0

        # Open the skipped files log
        with open('skipped_files.txt', 'a') as skipped_files_log:
            migration_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            skipped_files_log.write(f"Migration Date and Time: {migration_date_time}\n")

            for i, item in enumerate(source_items):
                if item_exists_in_target(item, destination_container):
                    message = f"File {item['id']} already exists in target, skipping."
                    logging.info(message)
                    skipped_files_log.write(f"Skipped File ID: {item['id']}\n")
                    socketio.emit('update', {
                        'progress': migration_status['progress'],
                        'progress_percentage': progress_percentage,
                        'file_exists': message
                    })
                    continue

                try:
                    # Migration logic for items that do not exist in the target
                    destination_container.create_item(body=item)
                    successfully_migrated_count += 1
                except Exception as e:
                    if 'Conflict' in str(e):
                        message = f"Conflict: File {item['id']} already exists in target, skipping."
                        logging.info(message)
                        skipped_files_log.write(f"Skipped File ID: {item['id']}\n")
                        socketio.emit('update', {
                            'progress': migration_status['progress'],
                            'progress_percentage': progress_percentage,
                            'file_exists': message
                        })
                        continue
                    else:
                        raise e

                # Update progress
                progress_percentage = (i + 1) / source_count * 100
                migration_status['progress'] = f"Migrating item {i + 1} of {source_count}"
                socketio.emit('update', {
                    'progress': migration_status['progress'],
                    'progress_percentage': progress_percentage
                })

            # Final progress update
            final_progress = f"Data migration completed successfully. {successfully_migrated_count} items migrated."
            logging.info(final_progress)
            migration_status['progress'] = final_progress
            socketio.emit('update', {
                'progress': migration_status['progress'],
                'progress_percentage': 100
            })

            # Start validation in a separate background task
            socketio.start_background_task(validate_data, source_container, destination_container)
    except Exception as e:
        logging.error(f"Error during migration: {e}")
        migration_status['errors'] = str(e)
        socketio.emit('update', {'errors': migration_status['errors']})

def validate_data(source_container, destination_container):
    """
    Validate the migrated data by comparing item counts in source and destination containers.
    Args:
        source_container (ContainerProxy): The source container.
        destination_container (ContainerProxy): The destination container.
    """
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