import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_socketio import SocketIO
from app import app, migrate, validate_data, migration_status

class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    @patch('app.get_cosmos_client')
    @patch('app.get_container')
    @patch('app.count_items')
    @patch('app.migrate_data')
    def test_migrate(self, mock_migrate_data, mock_count_items, mock_get_container, mock_get_cosmos_client):
        # Mock the return values
        mock_get_cosmos_client.return_value = MagicMock()
        mock_get_container.return_value = MagicMock()
        mock_count_items.return_value = 10
        mock_migrate_data.return_value = range(10)

        source_config = {
            'endpoint': 'source_endpoint',
            'key': 'source_key',
            'database_name': 'source_database_name',
            'container_name': 'source_container_name'
        }
        destination_config = {
            'endpoint': 'destination_endpoint',
            'key': 'destination_key',
            'database_name': 'destination_database_name',
            'container_name': 'destination_container_name'
        }
        batch_size = 5

        with patch('app.socketio.emit') as mock_emit:
            migrate(source_config, destination_config, batch_size)
            self.assertEqual(migration_status['source_count'], 10)
            self.assertIn('Data migration completed successfully', migration_status['progress'])
            mock_emit.assert_called()

    @patch('app.get_cosmos_client')
    @patch('app.get_container')
    @patch('app.count_items')
    def test_validate_data(self, mock_count_items, mock_get_container, mock_get_cosmos_client):
        # Mock the return values
        mock_get_cosmos_client.return_value = MagicMock()
        mock_get_container.return_value = MagicMock()
        mock_count_items.side_effect = [10, 10]

        source_container = MagicMock()
        destination_container = MagicMock()

        with patch('app.socketio.emit') as mock_emit:
            validate_data(source_container, destination_container)
            self.assertEqual(migration_status['validation'], 'Data verification successful.')
            mock_emit.assert_called()

    def test_index_get(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<form', response.data)

    @patch('app.socketio.start_background_task')
    def test_index_post(self, mock_start_background_task):
        response = self.app.post('/', data={
            'source_endpoint': 'source_endpoint',
            'source_key': 'source_key',
            'source_database_name': 'source_database_name',
            'source_container_name': 'source_container_name',
            'destination_endpoint': 'destination_endpoint',
            'destination_key': 'destination_key',
            'destination_database_name': 'destination_database_name',
            'destination_container_name': 'destination_container_name',
            'batch_size': '5'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<form', response.data)
        mock_start_background_task.assert_called()

if __name__ == '__main__':
    unittest.main()