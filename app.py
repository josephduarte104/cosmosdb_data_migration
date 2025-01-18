from flask import Flask, request, render_template
from flask_socketio import SocketIO
import logging
import time
from cosmos_data_migration import get_cosmos_client, get_container, count_items, migrate_data
import os

app = Flask(__name__)
socketio = SocketIO(app)

# Ensure the log directory exists
log_directory = os.path.dirname(os.path.abspath('migration.log'))
if not os.path.exists(log_directory):
    os.makedirs(log_directory)

# Configure logging
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
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

        # Log form data
        source_config_log = {k: v for k, v in source_config.items() if k != 'key'}
        destination_config_log = {k: v for k, v in destination_config.items() if k != 'key'}
        logging.info(f"Source Config: {source_config_log}")
        logging.info(f"Destination Config: {destination_config_log}")
        logging.info(f"Batch Size: {batch_size}")

        # Store the configurations in the global status
        migration_status['source_config'] = source_config
        migration_status['destination_config'] = destination_config

        # Call the migration function
        socketio.start_background_task(migrate, source_config, destination_config, batch_size)

        return render_template('index.html')

    return render_template('index.html')

def migrate(source_config, destination_config, batch_size):
    try:
        source_client = get_cosmos_client(source_config)
        source_container = get_container(source_client, source_config['database_name'], source_config['container_name'])

        destination_client = get_cosmos_client(destination_config)
        destination_container = get_container(destination_client, destination_config['database_name'], destination_config['container_name'])

        source_count = count_items(source_container)
        logging.info(f"Number of items in source container: {source_count}")
        migration_status['source_count'] = source_count
        migration_status['progress'] = f"Number of items in source container: {source_count}"
        socketio.emit('update', {
            'progress': migration_status['progress'],
            'source_config': migration_status['source_config'],
            'destination_config': migration_status['destination_config'],
            'source_count': migration_status['source_count']
        })

        start_time = time.time()
        not_migrated_items = []
        for i, item in enumerate(migrate_data(source_container, destination_container, batch_size)):
            elapsed_time = time.time() - start_time
            items_per_second = (i + 1) / elapsed_time
            progress = f"Migrating items: {i + 1}it [{elapsed_time:.2f}s, {items_per_second:.2f}it/s]"
            progress_percentage = ((i + 1) / source_count) * 100
            logging.info(progress)
            migration_status['progress'] = progress
            socketio.emit('update', {'progress': migration_status['progress'], 'progress_percentage': progress_percentage})
            if item in not_migrated_items:
                not_migrated_items.append(item)
                
        # Calculate duration
        end_time = time.time()
        duration = end_time - start_time
        final_progress = f"Data migration completed successfully in {duration:.2f} seconds. {source_count} items migrated."
        logging.info(final_progress)
        migration_status['progress'] = final_progress
        socketio.emit('update', {'progress': migration_status['progress'], 'progress_percentage': 100})

        # Start validation in a separate background task
        socketio.start_background_task(validate_data, source_container, destination_container)
    except Exception as e:
        logging.error(f"Error during migration: {e}")
        migration_status['errors'] = str(e)
        socketio.emit('update', {'errors': migration_status['errors']})

def validate_data(source_container, destination_container):
    try:
        source_count = count_items(source_container)
        destination_count = count_items(destination_container)
        if source_count != destination_count:
            validation_message = f"Data verification failed. Source has {source_count} items, but destination has {destination_count} items."
            logging.error(validation_message)
            migration_status['validation'] = validation_message
        else:
            validation_message = "Data verification successful."
            logging.info(validation_message)
            migration_status['validation'] = validation_message
        socketio.emit('update', {'validation': migration_status['validation']})
        socketio.emit('update', {'not_migrated_items': migration_status['not_migrated_items']})
    except Exception as e:
        logging.error(f"Error during validation: {e}")
        migration_status['errors'] = str(e)
        socketio.emit('update', {'errors': migration_status['errors']})

if __name__ == '__main__':
    socketio.run(app, debug=True)