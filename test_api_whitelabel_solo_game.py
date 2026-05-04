import unittest
from unittest.mock import MagicMock, patch

import api_whitelabel


class WhitelabelSoloGameTests(unittest.TestCase):
    def test_payload_allows_retry_for_failed_order_payload(self):
        self.assertTrue(api_whitelabel._payload_allows_retry({'order': {'status': 'fallida'}}))
        self.assertTrue(api_whitelabel._payload_allows_retry({'status': 'fallida'}))
        self.assertFalse(api_whitelabel._payload_allows_retry({'order': {'status': 'completada'}}))

    def test_finalize_idempotent_order_completes_successful_orders(self):
        conn = MagicMock()
        order_row = {'id': 12, 'estado': 'completada'}

        with patch.object(api_whitelabel, '_complete_idempotent_order') as complete_mock, \
             patch.object(api_whitelabel, '_clear_idempotent_order') as clear_mock, \
             patch.object(api_whitelabel, '_order_payload', return_value={'ok': True, 'status': 'completada'}):
            api_whitelabel._finalize_idempotent_order(conn, 7, 'api_v1_recharge', 'EXT-1', order_row)

        complete_mock.assert_called_once_with(conn, 7, 'api_v1_recharge', 'EXT-1', {'ok': True, 'status': 'completada'}, '12')
        clear_mock.assert_not_called()

    def test_finalize_idempotent_order_clears_failed_orders(self):
        conn = MagicMock()
        order_row = {'id': 13, 'estado': 'fallida'}

        with patch.object(api_whitelabel, '_complete_idempotent_order') as complete_mock, \
             patch.object(api_whitelabel, '_clear_idempotent_order') as clear_mock:
            api_whitelabel._finalize_idempotent_order(conn, 7, 'api_v1_recharge', 'EXT-1', order_row)

        complete_mock.assert_not_called()
        clear_mock.assert_called_once_with(conn, 7, 'api_v1_recharge', 'EXT-1')

    def test_resolve_package_accepts_dynamic_solo_game(self):
        dyn_pkg = {
            'id': 44,
            'juego_id': 9,
            'activo': True,
            'nombre': 'Paquete Solo Game',
            'precio': 3.5,
            'gamepoint_package_id': None,
            'game_script_only': True,
            'game_script_package_key': 'solo-pack-44',
            'game_script_package_title': 'Solo Pack',
        }
        dyn_game = {'id': 9, 'activo': True, 'nombre': 'Juego Demo', 'slug': 'juego-demo', 'gamepoint_product_id': 777}

        with patch('dynamic_games.get_dynamic_package_by_id', return_value=dyn_pkg), \
             patch('dynamic_games.get_dynamic_game_by_id', return_value=dyn_game):
            resolved = api_whitelabel._resolve_package(9, 44)

        self.assertEqual(resolved[0], 'dynamic')
        self.assertEqual(resolved[1], 'Juego Demo')
        self.assertIsNone(resolved[4])
        self.assertEqual(resolved[6]['provider'], 'game_script')
        self.assertEqual(resolved[6]['script_package_key'], 'solo-pack-44')

    def test_execute_recharge_routes_dynamic_solo_game_to_script_provider(self):
        provider_meta = {'provider': 'game_script', 'script_package_key': 'solo-pack-44'}
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {'saldo': 50.0}

        with patch.object(api_whitelabel, '_execute_dynamic_script_recharge', return_value={'ok': True, 'player_name': 'Jugador', 'reference_no': 'REF-1'}) as script_exec, \
             patch.object(api_whitelabel, '_execute_gamepoint_recharge') as gamepoint_exec, \
             patch.object(api_whitelabel, '_get_conn', return_value=conn), \
             patch.object(api_whitelabel, '_record_whitelabel_profit'), \
             patch.object(api_whitelabel, '_send_webhook_async'), \
             patch.object(api_whitelabel, 'jsonify', side_effect=lambda payload: payload):
            result, status_code = api_whitelabel._execute_recharge(
                order_id=12,
                game_type='dynamic',
                package_id=44,
                player_id='123456',
                player_id2='',
                precio=3.5,
                gp_package_id=None,
                gp_product_id=777,
                usuario_id=1,
                account={'nombre': 'Cuenta Demo'},
                provider_meta=provider_meta,
                game_name='Juego Demo',
                pkg_name='Paquete Solo Game',
            )

        self.assertTrue(result['ok'])
        self.assertEqual(status_code, 200)
        script_exec.assert_called_once_with(12, 44, '123456', provider_meta)
        gamepoint_exec.assert_not_called()


if __name__ == '__main__':
    unittest.main()