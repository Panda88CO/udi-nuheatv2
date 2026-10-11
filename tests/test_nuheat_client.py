import unittest
from unittest.mock import patch, MagicMock, call
import requests
from nuheat.nuheat import NuHeat

class TestNuHeatClient(unittest.TestCase):
    def test_static_token_and_headers(self):
        client = NuHeat('initial_token')
        self.assertEqual(client.headers['Authorization'], 'Bearer initial_token')
        self.assertEqual(client.headers['Content-Type'], 'application/json')
        client.set_access_token('updated_token')
        self.assertEqual(client.headers['Authorization'], 'Bearer updated_token')

    def test_dynamic_token_provider(self):
        current_token = 'token_v1'
        client = NuHeat(lambda: current_token)
        self.assertEqual(client.headers['Authorization'], 'Bearer token_v1')
        current_token = 'token_v2_refreshed'
        self.assertEqual(client.headers['Authorization'], 'Bearer token_v2_refreshed')

    @patch.object(requests.Session, 'request')
    def test_get_account(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'userName': 'Jane Doe',
            'temperatureScale': 'Fahrenheit',
            'language': 'en'
        }
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Jane Doe')
        self.assertEqual(account['temperatureScale'], 'Fahrenheit')
        mock_request.assert_called_once_with(
            'GET',
            'https://api.mynuheat.com/api/v2/Account',
            headers=client.headers,
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_get_thermostat_list_and_normalization(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{
            'serialNumber': '12345678',
            'name': 'Master Bath',
            'currentTemperature': 2150,
            'online': True,
            'isHeating': True,
            'setPointTemperature': 2200,
            'holdUntil': '2026-09-06T18:00:00Z',
            'mode': 2,
            'errorState': None
        }]
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        stats = client.get_thermostat()
        self.assertEqual(len(stats), 1)
        stat = stats[0]
        # Check that both v2 keys and normalized v1 keys are present
        self.assertEqual(stat['setPointTemperature'], 2200)
        self.assertEqual(stat['setPointTemp'], 2200)
        self.assertEqual(stat['mode'], 2)
        self.assertEqual(stat['operatingMode'], 2)
        self.assertEqual(stat['holdUntil'], '2026-09-06T18:00:00Z')
        self.assertEqual(stat['holdSetPointDateTime'], '2026-09-06T18:00:00Z')
        self.assertIsNone(stat['error'])
        mock_request.assert_called_once_with(
            'GET',
            'https://api.mynuheat.com/api/v2/Thermostat',
            headers=client.headers,
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_get_single_thermostat(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'serialNumber': '87654321',
            'name': 'Kitchen',
            'currentTemperature': 2000,
            'setPointTemperature': 2000,
            'mode': 1
        }
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        stat = client.get_thermostat('87654321')
        self.assertEqual(stat['serialNumber'], '87654321')
        self.assertEqual(stat['setPointTemp'], 2000)
        mock_request.assert_called_once_with(
            'GET',
            'https://api.mynuheat.com/api/v2/Thermostat/87654321',
            headers=client.headers,
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_set_mode_auto(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_auto('12345678')
        self.assertTrue(res)
        mock_request.assert_called_once_with(
            'PUT',
            'https://api.mynuheat.com/api/v2/Mode/Auto',
            headers=client.headers,
            json={'serialNumber': '12345678'},
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_set_mode_hold(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_hold('12345678', 2300, hold_until='2026-09-06T20:00:00Z')
        self.assertTrue(res)
        mock_request.assert_called_once_with(
            'PUT',
            'https://api.mynuheat.com/api/v2/Mode/Hold',
            headers=client.headers,
            json={
                'serialNumber': '12345678',
                'temperature': 2300,
                'temperatureType': 0,
                'holdUntil': '2026-09-06T20:00:00Z'
            },
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_set_mode_manual(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_manual('12345678', 2100)
        self.assertTrue(res)
        mock_request.assert_called_once_with(
            'PUT',
            'https://api.mynuheat.com/api/v2/Mode/Manual',
            headers=client.headers,
            json={'serialNumber': '12345678', 'temperature': 2100, 'temperatureType': 0},
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_set_thermostat_setpoint_compat(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        # Default behavior routes to hold
        res = client.set_thermostat_setpoint('12345678', 2250)
        self.assertTrue(res)
        mock_request.assert_called_with(
            'PUT',
            'https://api.mynuheat.com/api/v2/Mode/Hold',
            headers=client.headers,
            json={'serialNumber': '12345678', 'temperature': 2250, 'temperatureType': 0},
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_get_energy_log_day(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'mondayIsFirstDay': True,
            'energyUsage': [
                {'entry': '0', 'minutes': 15, 'energyKWattHour': 0.25, 'chargeKWattHour': 3.0},
                {'entry': '1', 'minutes': 30, 'energyKWattHour': 0.50, 'chargeKWattHour': 7.0}
            ]
        }
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        result = client.get_energy_log_day('12345678', '2026-09-06')
        self.assertEqual(result, [45, 0.75, 0.10])  # 3.0 + 7.0 = 10.0 cents -> 0.10 usd
        mock_request.assert_called_once_with(
            'GET',
            'https://api.mynuheat.com/api/v1/EnergyLog/Day/12345678/2026-09-06',
            headers=client.headers,
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_get_energy_log_month_and_year(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'energyUsageType': 'Month',
            'mondayIsFirstDay': False,
            'energyUsage': [
                {'entry': '8', 'minutes': 30, 'energyKWattHour': 0.25, 'chargeKWattHour': 5.0},
                {'entry': '9', 'minutes': 60, 'energyKWattHour': 1.50, 'chargeKWattHour': 20.0}
            ]
        }
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        month_res = client.get_energy_log_month('12345678', '2026', 9)
        self.assertEqual(month_res, [60, 1.50, 0.20])

        # Test year sums all entries
        year_res = client.get_energy_log_year('12345678', '2026')
        self.assertEqual(year_res, [90, 1.75, 0.25])

        # Verify caching: mock_request was only called once for both month and year queries
        mock_request.assert_called_once_with(
            'GET',
            'https://api.mynuheat.com/api/v1/EnergyLog/Month/12345678/2026',
            headers=client.headers,
            timeout=10
        )

    @patch.object(requests.Session, 'request')
    def test_get_energy_summary_live_format(self, mock_request):
        def mock_dispatch(method, url, headers=None, timeout=None, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if 'EnergyLog/Day/' in url:
                resp.json.return_value = {
                    'energyUsageType': 'Day',
                    'energyUsage': [{'entry': str(i), 'minutes': 0, 'energyKWattHour': 0} for i in range(24)]
                }
            elif 'EnergyLog/Week/' in url:
                resp.json.return_value = {
                    'energyUsageType': 'Week',
                    'energyUsage': [
                        {'entry': '11', 'minutes': 0, 'energyKWattHour': 0},
                        {'entry': '10', 'minutes': 0, 'energyKWattHour': 0},
                        {'entry': '9', 'minutes': 0, 'energyKWattHour': 0},
                        {'entry': '8', 'minutes': 0, 'energyKWattHour': 0.015},
                        {'entry': '7', 'minutes': 0, 'energyKWattHour': 0.055},
                        {'entry': '6', 'minutes': 0, 'energyKWattHour': 0.1116666}
                    ]
                }
            elif 'EnergyLog/Month/' in url:
                resp.json.return_value = {
                    'energyUsageType': 'Month',
                    'energyUsage': [
                        {'entry': '12', 'minutes': 0, 'energyKWattHour': 0},
                        {'entry': '9', 'minutes': 0, 'energyKWattHour': 1.381666},
                        {'entry': '8', 'minutes': 0, 'energyKWattHour': 0.253333},
                        {'entry': '1', 'minutes': 0, 'energyKWattHour': 0}
                    ]
                }
            return resp

        mock_request.side_effect = mock_dispatch

        client = NuHeat('dummy')
        summary = client.get_energy_summary('1262811', '2026-09-12', '2026', 9)
        self.assertEqual(summary['day'], 0.0)
        self.assertEqual(summary['week'], 0.18)
        self.assertEqual(summary['month'], 1.38)
        self.assertEqual(summary['year'], 1.63)

    def test_temperature_conversions(self):
        client = NuHeat('dummy')
        # 2000 hundredths C = 20.0 C -> 68.0 F
        self.assertEqual(client.nuheat_celsius_to_fahrenheit(2000), 68.0)
        # 68 F -> 2000 hundredths C
        self.assertEqual(client.nuheat_fahrenheit_to_celsius_json(68), 2000)
        # 21.5 C to json hundredths
        self.assertEqual(client.nuheat_celsius_to_json(21), 2100)
        # 2100 hundredths C to normal C
        self.assertEqual(client.nuheat_celsius_to_normal(2100), 21.0)
        # 150 cents to usd
        self.assertEqual(client.nuheat_cents_to_dollars(150), 1.50)

    @patch('nuheat.nuheat.LOGGER.debug')
    @patch.object(requests.Session, 'request')
    def test_logger_debug_formatted_json(self, mock_request, mock_debug):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'result': 'ok'}
        mock_request.return_value = mock_resp

        client = NuHeat('dummy')
        client.get_account()

        mock_debug.assert_called_once()
        log_msg = mock_debug.call_args[0][0]
        self.assertIn('"result": "ok"', log_msg)
        self.assertIn("HTTP 200", log_msg)

    # -------------------------------------------------------------
    # New Phase 1 Tests: Timeout, Retries, Backoff, Caching, Close
    # -------------------------------------------------------------

    @patch.object(requests.Session, 'request')
    def test_enforced_and_configurable_timeout(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'userName': 'Test'}
        mock_request.return_value = mock_resp

        # Default timeout
        client = NuHeat('dummy')
        self.assertEqual(client.timeout, 10)
        client.get_account()
        mock_request.assert_called_with('GET', 'https://api.mynuheat.com/api/v2/Account', headers=client.headers, timeout=10)

        # Custom configured timeout
        client.timeout = 15
        client.get_account()
        mock_request.assert_called_with('GET', 'https://api.mynuheat.com/api/v2/Account', headers=client.headers, timeout=15)

    @patch('time.sleep')
    @patch.object(requests.Session, 'request')
    def test_retry_on_5xx_server_error(self, mock_request, mock_sleep):
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.text = "Internal Server Error"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {'userName': 'Success After Retry'}

        mock_request.side_effect = [resp_500, resp_200]

        client = NuHeat('dummy')
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Success After Retry')
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)

    @patch('time.sleep')
    @patch.object(requests.Session, 'request')
    def test_retry_on_429_respects_retry_after(self, mock_request, mock_sleep):
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {'Retry-After': '5'}
        resp_429.text = "Too Many Requests"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {'userName': 'Rate Limit Recovered'}

        mock_request.side_effect = [resp_429, resp_200]

        client = NuHeat('dummy')
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Rate Limit Recovered')
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(5.0)

    @patch('time.sleep')
    @patch.object(requests.Session, 'request')
    def test_retry_on_401_unauthorized_token_refresh(self, mock_request, mock_sleep):
        token_holder = {'token': 'old_expired_token'}

        def token_provider():
            return token_holder['token']

        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "Unauthorized"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {'userName': 'Refreshed User'}

        def side_effect(method, url, headers=None, **kwargs):
            if headers.get('Authorization') == 'Bearer old_expired_token':
                # Token was expired; simulate refresh happening
                token_holder['token'] = 'fresh_token_123'
                return resp_401
            return resp_200

        mock_request.side_effect = side_effect

        client = NuHeat(token_provider)
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Refreshed User')
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    @patch('time.sleep')
    @patch.object(requests.Session, 'request')
    def test_retry_on_network_timeout(self, mock_request, mock_sleep):
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {'userName': 'Recovered From Timeout'}

        mock_request.side_effect = [requests.exceptions.Timeout("Read timeout"), resp_200]

        client = NuHeat('dummy')
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Recovered From Timeout')
        self.assertEqual(mock_request.call_count, 2)
        mock_sleep.assert_called_once_with(2.0)

    @patch.object(requests.Session, 'request')
    def test_day_and_week_energy_log_caching(self, mock_request):
        mock_resp_day = MagicMock()
        mock_resp_day.status_code = 200
        mock_resp_day.json.return_value = {
            'mondayIsFirstDay': True,
            'energyUsage': [{'entry': '0', 'minutes': 30, 'energyKWattHour': 0.5, 'chargeKWattHour': 6.0}]
        }

        mock_resp_week = MagicMock()
        mock_resp_week.status_code = 200
        mock_resp_week.json.return_value = {
            'mondayIsFirstDay': True,
            'energyUsage': [{'entry': '1', 'minutes': 60, 'energyKWattHour': 1.0, 'chargeKWattHour': 12.0}]
        }

        mock_request.side_effect = [mock_resp_day, mock_resp_day, mock_resp_week, mock_resp_week]

        client = NuHeat('dummy')

        # First call to day log -> network call
        res_day_1 = client.get_energy_log_day('12345678', '2026-10-11')
        self.assertEqual(res_day_1, [30, 0.5, 0.06])
        self.assertEqual(mock_request.call_count, 1)

        # Second call within TTL -> cached
        res_day_2 = client.get_energy_log_day('12345678', '2026-10-11')
        self.assertEqual(res_day_2, [30, 0.5, 0.06])
        self.assertEqual(mock_request.call_count, 1)

        # Third call with force=True -> network call
        res_day_3 = client.get_energy_log_day('12345678', '2026-10-11', force=True)
        self.assertEqual(res_day_3, [30, 0.5, 0.06])
        self.assertEqual(mock_request.call_count, 2)

        # First call to week log -> network call
        res_week_1 = client.get_energy_log_week('12345678', '2026-10-11')
        self.assertEqual(res_week_1, [60, 1.0, 0.12])
        self.assertEqual(mock_request.call_count, 3)

        # Second call within TTL -> cached
        res_week_2 = client.get_energy_log_week('12345678', '2026-10-11')
        self.assertEqual(res_week_2, [60, 1.0, 0.12])
        self.assertEqual(mock_request.call_count, 3)

        # Third call with force=True -> network call
        res_week_3 = client.get_energy_log_week('12345678', '2026-10-11', force=True)
        self.assertEqual(res_week_3, [60, 1.0, 0.12])
        self.assertEqual(mock_request.call_count, 4)

    def test_client_close(self):
        mock_session = MagicMock()
        client = NuHeat('dummy', session=mock_session)
        client.close()
        mock_session.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
