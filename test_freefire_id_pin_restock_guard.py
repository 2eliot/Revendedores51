import unittest
from unittest.mock import MagicMock, patch

import requests

import app


class FreefireIdPinRestockGuardTests(unittest.TestCase):
    def test_verify_pin_already_redeemed_ignores_missing_stock_by_default(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {'count': 0}

        with patch.object(app.requests, 'post', side_effect=requests.exceptions.RequestException), \
             patch.object(app, 'get_db_connection', return_value=conn):
            result = app.verify_pin_already_redeemed('PINCODE123456', '123456789')

        self.assertFalse(result)
        conn.execute.assert_called_once()

    def test_restore_skips_restock_when_pin_was_verified_used(self):
        with patch.object(app, 'verify_pin_already_redeemed', return_value=True), \
             patch.object(app, 'get_db_connection') as get_db_connection:
            result = app.restore_freefire_id_pin_if_unverified(1, 'PINCODE123456', '123456789')

        self.assertTrue(result['verified_used'])
        self.assertFalse(result['restored'])
        get_db_connection.assert_not_called()

    def test_restore_reinserts_pin_when_not_verified_used(self):
        conn = MagicMock()

        with patch.object(app, 'verify_pin_already_redeemed', return_value=False), \
             patch.object(app, 'get_db_connection', return_value=conn):
            result = app.restore_freefire_id_pin_if_unverified(2, 'PINCODE654321', '123456789')

        self.assertFalse(result['verified_used'])
        self.assertTrue(result['restored'])
        conn.execute.assert_called_once_with(
            'INSERT INTO pines_freefire_global (monto_id, pin_codigo, usado) VALUES (?, ?, FALSE)',
            (2, 'PINCODE654321'),
        )
        conn.commit.assert_called_once()
        conn.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()