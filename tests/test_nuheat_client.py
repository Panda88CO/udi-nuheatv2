import unittest
from unittest.mock import patch, MagicMock
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

    @patch('requests.get')
    def test_get_account(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'userName': 'Jane Doe',
            'temperatureScale': 'Fahrenheit',
            'language': 'en'
        }
        mock_get.return_value = mock_resp

        client = NuHeat('dummy')
        account = client.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['userName'], 'Jane Doe')
        self.assertEqual(account['temperatureScale'], 'Fahrenheit')
        mock_get.assert_called_once_with('https://api.mynuheat.com/api/v2/Account', headers=client.headers)

    @patch('requests.get')
    def test_get_thermostat_list_and_normalization(self, mock_get):
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
        mock_get.return_value = mock_resp

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
        mock_get.assert_called_once_with('https://api.mynuheat.com/api/v2/Thermostat', headers=client.headers)

    @patch('requests.get')
    def test_get_single_thermostat(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'serialNumber': '87654321',
            'name': 'Kitchen',
            'currentTemperature': 2000,
            'setPointTemperature': 2000,
            'mode': 1
        }
        mock_get.return_value = mock_resp

        client = NuHeat('dummy')
        stat = client.get_thermostat('87654321')
        self.assertEqual(stat['serialNumber'], '87654321')
        self.assertEqual(stat['setPointTemp'], 2000)
        mock_get.assert_called_once_with('https://api.mynuheat.com/api/v2/Thermostat/87654321', headers=client.headers)

    @patch('requests.put')
    def test_set_mode_auto(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_auto('12345678')
        self.assertTrue(res)
        mock_put.assert_called_once_with(
            'https://api.mynuheat.com/api/v2/Mode/Auto',
            headers=client.headers,
            json={'serialNumber': '12345678'}
        )

    @patch('requests.put')
    def test_set_mode_hold(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_put.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_hold('12345678', 2300, hold_until='2026-09-06T20:00:00Z')
        self.assertTrue(res)
        mock_put.assert_called_once_with(
            'https://api.mynuheat.com/api/v2/Mode/Hold',
            headers=client.headers,
            json={
                'serialNumber': '12345678',
                'temperature': 2300,
                'temperatureType': 0,
                'holdUntil': '2026-09-06T20:00:00Z'
            }
        )

    @patch('requests.put')
    def test_set_mode_manual(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        client = NuHeat('dummy')
        res = client.set_mode_manual('12345678', 2100)
        self.assertTrue(res)
        mock_put.assert_called_once_with(
            'https://api.mynuheat.com/api/v2/Mode/Manual',
            headers=client.headers,
            json={'serialNumber': '12345678', 'temperature': 2100, 'temperatureType': 0}
        )

    @patch('requests.put')
    def test_set_thermostat_setpoint_compat(self, mock_put):
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_put.return_value = mock_resp

        client = NuHeat('dummy')
        # Default behavior routes to hold
        res = client.set_thermostat_setpoint('12345678', 2250)
        self.assertTrue(res)
        mock_put.assert_called_with(
            'https://api.mynuheat.com/api/v2/Mode/Hold',
            headers=client.headers,
            json={'serialNumber': '12345678', 'temperature': 2250, 'temperatureType': 0}
        )

    @patch('requests.get')
    def test_get_energy_log_day(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'mondayIsFirstDay': True,
            'energyUsage': [
                {'entry': '0', 'minutes': 15, 'energyKWattHour': 0.25, 'chargeKWattHour': 3.0},
                {'entry': '1', 'minutes': 30, 'energyKWattHour': 0.50, 'chargeKWattHour': 7.0}
            ]
        }
        mock_get.return_value = mock_resp

        client = NuHeat('dummy')
        result = client.get_energy_log_day('12345678', '2026-09-06')
        self.assertEqual(result, [45, 0.75, 0.10])  # 3.0 + 7.0 = 10.0 cents -> 0.10 usd
        mock_get.assert_called_once_with(
            'https://api.mynuheat.com/api/v1/EnergyLog/Day/12345678/2026-09-06',
            headers=client.headers
        )

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

if __name__ == '__main__':
    unittest.main()
