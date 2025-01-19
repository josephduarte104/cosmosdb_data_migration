Collecting workspace information Script

# Cosmos Data Migration

This project provides a script to migrate data from one Azure Cosmos DB container to another. It includes features for logging, retry mechanisms, and data verification to ensure a smooth and reliable migration process.

## Features

- **Environment Configuration**: Uses 

.env

 file to manage configuration settings.
- **Logging**: Logs important events and errors to `migration.log`.
- **Retry Mechanism**: Implements retry logic for transient errors using the 

tenacity

 library.
- **Batch Processing**: Handles large datasets efficiently by processing data in batches.
- **Data Verification**: Verifies that the number of items in the source and destination containers match after migration.

## Performance

- **Batch Processing**: The script processes data in batches to handle large datasets efficiently.
- **Retry Mechanism**: Uses exponential backoff strategy to retry failed operations, reducing the likelihood of transient errors affecting the migration process.

## Best Practices Applied

- **Environment Variables**: Sensitive information such as database endpoints and keys are stored in a 

.env

 file and loaded using `python-dotenv`.
- **Logging**: Logs are written to `migration.log` to keep track of the migration process and any errors that occur.
- **Error Handling**: Implements retry logic for transient errors and logs errors for failed operations.
- **Data Verification**: Ensures data integrity by verifying that the number of items in the source and destination containers match after migration.

## Prerequisites

- Python 3.6 or higher
- Azure Cosmos DB account
- Install required Python packages using 

requirements.txt



## Installation

1. Clone the repository:
    ```sh
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

4. Create a 

.env

 file in the project directory with the following content:
    ```env
    SOURCE_ENDPOINT=<source_endpoint>
    SOURCE_KEY=<source_key>
    SOURCE_DATABASE_NAME=<source_database_name>
    SOURCE_CONTAINER_NAME=<source_container_name>

    DESTINATION_ENDPOINT=<destination_endpoint>
    DESTINATION_KEY=<destination_key>
    DESTINATION_DATABASE_NAME=<destination_database_name>
    DESTINATION_CONTAINER_NAME=<destination_container_name>
    ```

## Usage

1. Run the migration script:
    ```sh
    python cosmos_data_migration.py --batch-size <batch_size>
    ```

    - `--batch-size`: Number of items to process in each batch (default is 100).

2. Check the `migration.log` file for detailed logs of the migration process.

## Code Explanation

- **Environment Configuration**: Loads environment variables from 

.env

 file using 

load_dotenv()

.
- **Logging Configuration**: Configures logging to write logs to `migration.log`.
- **Cosmos DB Clients**: Creates Cosmos DB clients for source and destination using 

get_cosmos_client()

.
- **Container Clients**: Retrieves container clients for source and destination using 

get_container()

.
- **Item Counting**: Counts the number of items in a container using 

count_items()

.
- **Retry Mechanism**: Implements retry logic for upserting items using 

upsert_item_with_retry()

.
- **Data Migration**: Migrates data from source to destination container in batches using 

migrate_data()

.
- **Data Verification**: Verifies that the number of items in source and destination containers match using 

verify_data()

.

## License

This project is licensed under the MIT License. See the LICENSE file for details.


# Flask Web Application for Cosmos Data Migration

This is a Flask web application for migrating data between Cosmos DB containers.

## Prerequisites

- Python 3.6 or higher
- Flask
- Flask-SocketIO

## Setup

1. Clone the repository:

    ```sh
    git clone https://github.com/your-repo/flask-cosmos-migration.git
    cd flask-cosmos-migration
    ```

2. Create a virtual environment and activate it:

    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required packages:

    ```sh
    pip install -r requirements.txt
    ```

4. Configure logging:

    Ensure that the `logging_config.py` file is correctly set up to log to [migration.log](http://_vscodecontentref_/1).

## Running the Application

1. Start the Flask application:

    ```sh
    flask run
    ```

2. Open your web browser and navigate to `http://127.0.0.1:5000/`.

## Logging

All logs are written to [migration.log](http://_vscodecontentref_/2) in the root directory of the project. Ensure that the log directory exists and is writable.

## Usage

1. Fill in the source and destination Cosmos DB configurations in the web form.
2. Specify the batch size for data migration.
3. Click the "Migrate" button to start the migration process.
4. Monitor the progress and errors in the [migration.log](http://_vscodecontentref_/3) file.

## License

This project is licensed under the MIT License - see the LICENSE file for details.


# Flask Web Application for Cosmos Data Migration

This is a Flask web application for migrating data between Cosmos DB containers.

## Prerequisites

- Docker
- Docker Compose

## Setup

1. Clone the repository:

    ```sh
    git clone https://github.com/your-repo/flask-cosmos-migration.git
    cd flask-cosmos-migration
    ```

2. Create a virtual environment and activate it (optional, for local development):

    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required packages (optional, for local development):

    ```sh
    pip install -r requirements.txt
    ```

## Running the Application as a Docker Container

1. Ensure the [requirements.txt](http://_vscodecontentref_/1) file includes all necessary dependencies:

    ```plaintext
    Flask==2.0.2
    Werkzeug==2.0.2
    Flask-SocketIO==5.1.1
    python-socketio==5.4.0
    python-engineio==4.3.0
    requests==2.26.0
    azure-cosmos==4.2.0
    gunicorn==20.1.0
    python-dotenv==0.19.2
    tqdm==4.62.3
    tenacity==8.0.1
    gevent==21.8.0
    gevent-websocket==0.10.1
    ```

2. Ensure the [Dockerfile](http://_vscodecontentref_/2) is correctly set up:

    ```Dockerfile
    # Use the official Python image from the Docker Hub
    FROM python:3.9-slim

    # Set the working directory in the container
    WORKDIR /app

    # Update the package list and install any required system dependencies
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

    # Copy the requirements file into the container
    COPY requirements.txt .

    # Install the dependencies
    RUN pip install --no-cache-dir -r requirements.txt

    # Copy the rest of the application code into the container
    COPY . .

    # Expose the port the app runs on
    EXPOSE 5000

    # Define the command to run the application using Gunicorn with gevent
    CMD ["gunicorn", "-b", "0.0.0.0:5000", "-k", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", "app:app"]
    ```

3. Ensure the `docker-compose.yml` file is correctly set up:

    ```yaml
    version: '3.8'

    services:
      web:
        build: .
        ports:
          - "5000:5000"
        volumes:
          - .:/app
        environment:
          FLASK_ENV: development
          FLASK_APP: app.py
    ```

4. Build and run the Docker container:

    ```sh
    # Build the Docker image
    docker-compose build

    # Run the Docker container
    docker-compose up
    ```

5. Access the application:

    Open your web browser and navigate to `http://localhost:5000/` to access your Flask web application running inside the Docker container.

## Logging

All logs are written to [migration.log](http://_vscodecontentref_/3) in the root directory of the project. Ensure that the log directory exists and is writable.

## Usage

1. Fill in the source and destination Cosmos DB configurations in the web form.
2. Specify the batch size for data migration.
3. Click the "Migrate" button to start the migration process.
4. Monitor the progress and errors in the [migration.log](http://_vscodecontentref_/4) file.

## License

This project is licensed under the MIT License - see the LICENSE file for details.