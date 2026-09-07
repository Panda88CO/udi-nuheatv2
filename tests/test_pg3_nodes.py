import importlib.util
import os
import unittest
from unittest.mock import MagicMock, patch
from nuheat import NuHeat
from nodes import ThermostatNode_F, ThermostatNode_C, EnergyLogDayNode

controller_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'nuheat.py'))
spec = importlib.util.spec_from_file_location("controller_module", controller_path)
controller_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller_module)
Controller = controller_module.Controller

class TestPG3Nodes(unittest.TestCase):
    def setUp(self):
        self.mock_poly = MagicMock()
        self.mock_poly.subscribe = MagicMock()
        self.mock_poly.Notices = {}
        self.mock_poly.addNode = MagicMock()
        self.mock_poly.getNodes.return_value = {}

    def test_controller_init_and_token(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        self.assertEqual(controller.name, 'NuHeat')
        self.assertEqual(controller.tz, 'America/New_York')

        # Test get_access_token via oauth
        controller.oauth.getAccessToken = MagicMock(return_value='test_token_123')
        self.assertEqual(controller.get_access_token(), 'test_token_123')
        self.assertEqual(controller.NuHeat.headers['Authorization'], 'Bearer test_token_123')

    def test_controller_oauth_handler(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.discover = MagicMock()
        controller.oauth.oauthHandler = MagicMock()

        controller.oauthHandler({'access_token': 'new_token'})
        controller.oauth.oauthHandler.assert_called_once_with({'access_token': 'new_token'})
        controller.discover.assert_called_once()

    def test_controller_custom_params_handler(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.customNsHandler = MagicMock()

        params = {
            'tz': 'America/Chicago',
            'clientId': 'my_client_id',
            'clientSecret': 'my_client_secret'
        }
        controller.customParamsHandler(params)
        self.assertEqual(controller.tz, 'America/Chicago')
        controller.oauth.customNsHandler.assert_called_once()
        call_args = controller.oauth.customNsHandler.call_args[0]
        self.assertEqual(call_args[0], 'oauth')
        self.assertEqual(call_args[1]['client_id'], 'my_client_id')
        self.assertEqual(call_args[1]['client_secret'], 'my_client_secret')

    def test_controller_discover(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.get_access_token = MagicMock(return_value='valid_token')

        controller.NuHeat.get_account = MagicMock(return_value={'temperatureScale': 'Fahrenheit'})
        controller.NuHeat.get_thermostat = MagicMock(return_value=[{
            'serialNumber': '99887766',
            'name': 'Guest Bath',
            'currentTemperature': 2100,
            'setPointTemperature': 2200,
            'mode': 2,
            'isHeating': True
        }])

        controller.discover()
        self.assertEqual(controller.disco, 1)
        # Should have added 1 thermostat node + 3 energy nodes = 4 nodes
        self.assertEqual(self.mock_poly.addNode.call_count, 4)

    def test_thermostat_node_f(self):
        controller = MagicMock()
        controller.NuHeat = MagicMock()
        controller.NuHeat.get_thermostat.return_value = {
            'serialNumber': '99887766',
            'currentTemperature': 2000,
            'setPointTemperature': 2100,
            'mode': 1, # Auto
            'isHeating': True
        }
        controller.NuHeat.nuheat_celsius_to_fahrenheit.side_effect = lambda val: (val / 100) * 9/5 + 32
        controller.NuHeat.nuheat_fahrenheit_to_celsius_json.side_effect = lambda f: round((f - 32) * 5/9 * 100)
        controller.NuHeat.set_thermostat_setpoint.return_value = True

        node = ThermostatNode_F(self.mock_poly, 'controller', '99887766', 'Guest Bath', controller)
        node.setDriver = MagicMock()

        # Test update_info
        node.update_info()
        # ST = 68.0, CLISPH = 69.8, CLIMD = 3 (Auto), CLIHCS = 1 (Heating)
        node.setDriver.assert_any_call('ST', 68.0)
        node.setDriver.assert_any_call('CLISPH', 69.8)
        node.setDriver.assert_any_call('CLIMD', 3)
        node.setDriver.assert_any_call('CLIHCS', 1)

        # Test setpoint_heat
        node.setpoint_heat({'value': 72})
        controller.NuHeat.set_thermostat_setpoint.assert_called_once_with('99887766', 2222)
        node.setDriver.assert_any_call('CLISPH', 72)

    def test_energy_log_day_node(self):
        controller = MagicMock()
        controller.NuHeat = MagicMock()
        controller.tz = 'America/New_York'
        controller.NuHeat.get_energy_log_day.return_value = [60, 1.25, 0.18]

        node = EnergyLogDayNode(self.mock_poly, '99887766', 'eld99887766', 'Energy-Day', controller)
        node.setDriver = MagicMock()

        node.update_info()
        node.setDriver.assert_any_call('GV0', 60, uom=45)
        node.setDriver.assert_any_call('ST', 1.25, uom=33)
        node.setDriver.assert_any_call('GV1', 0.18, uom=103)

if __name__ == '__main__':
    unittest.main()
