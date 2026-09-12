import importlib.util
import os
import unittest
from unittest.mock import MagicMock, patch
from nuheat import NuHeat
from nodes import ThermostatNode, ThermostatNode_F, ThermostatNode_C, EnergyLogDayNode, EnergyLogWeekNode, EnergyLogYearNode

controller_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'nuheat.py'))
spec = importlib.util.spec_from_file_location("controller_module", controller_path)
controller_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller_module)
Controller = controller_module.Controller
_build_profile_definition = controller_module._build_profile_definition


class TestPG3Nodes(unittest.TestCase):
    def setUp(self):
        self.mock_poly = MagicMock()
        self.mock_poly.subscribe = MagicMock()
        self.mock_poly.Notices = {}
        self.mock_poly.addNode = MagicMock()
        self.mock_poly.getNodes.return_value = {}
        self.mock_poly.getNode.return_value = None
        self.mock_poly.ADDNODEDONE = 'ADDNODEDONE'
        self.mock_poly.DELNODEDONE = 'DELNODEDONE'

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
        controller.handleCustomParamsDone = True
        controller.discover = MagicMock()
        controller.oauth.oauthHandler = MagicMock()

        controller.oauthHandler({'access_token': 'new_token'})
        controller.oauth.oauthHandler.assert_called_once_with({'access_token': 'new_token'})
        controller.discover.assert_called_once()

    def test_controller_custom_params_handler_with_temp_unit(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.updateOauthSettings = MagicMock()
        controller._publish_profile = MagicMock()

        params = {
            'tz': 'America/Chicago',
            'TEMP_UNIT': 'C'
        }
        controller.customParamsHandler(params)
        self.assertEqual(controller.tz, 'America/Chicago')
        self.assertEqual(controller.temp_unit, 'C')
        self.assertEqual(controller.temp_uom, 4)
        controller._publish_profile.assert_called_once()

    def test_controller_discover(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.get_access_token = MagicMock(return_value='valid_token')
        controller._confirmed_node_addresses.add('99887766')

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
        # Should have added 1 controller node + 1 thermostat node + 3 energy nodes = 5 nodes
        self.assertEqual(self.mock_poly.addNode.call_count, 5)

    def test_controller_discover_migrates_existing_node(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.get_access_token = MagicMock(return_value='valid_token')
        controller._confirmed_node_addresses.add('99887766')

        controller.NuHeat.get_account = MagicMock(return_value={'temperatureScale': 'Fahrenheit'})
        controller.NuHeat.get_thermostat = MagicMock(return_value=[{
            'serialNumber': '99887766',
            'name': 'Guest Bath',
            'currentTemperature': 2100,
            'setPointTemperature': 2200,
            'mode': 2,
            'isHeating': True
        }])

        existing_node = MagicMock()
        existing_node.primary = 'controller'
        self.mock_poly.getNode = MagicMock(return_value=existing_node)
        self.mock_poly.delNode = MagicMock()

        controller.discover()
        self.mock_poly.delNode.assert_called_once_with('99887766')

    def test_thermostat_node_f(self):
        controller = MagicMock()
        controller.temp_uom = 17
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

        node = ThermostatNode(self.mock_poly, '99887766', '99887766', 'Guest Bath', controller, temp_uom=17)
        self.assertEqual(node.id, 'THERMOSTAT')
        node.setDriver = MagicMock()

        # Test update_info
        node.update_info()
        # ST = 68.0, CLISPH = 69.8, CLIMD = 3 (Auto), CLIHCS = 1 (Heating)
        node.setDriver.assert_any_call('ST', 68.0, uom=17)
        node.setDriver.assert_any_call('CLISPH', 69.8, uom=17)
        node.setDriver.assert_any_call('CLIMD', 3, uom=67)
        node.setDriver.assert_any_call('CLIHCS', 1, uom=66)
        # Verify TIME driver updated
        time_calls = [c for c in node.setDriver.call_args_list if c[0][0] == 'TIME']
        self.assertEqual(len(time_calls), 1)
        self.assertEqual(time_calls[0][1].get('uom'), 151)

        # Test setpoint_heat
        node.setpoint_heat({'value': 72})
        controller.NuHeat.set_thermostat_setpoint.assert_called_once_with('99887766', 2222)
        node.setDriver.assert_any_call('CLISPH', 72, uom=17)

    def test_thermostat_node_c(self):
        controller = MagicMock()
        controller.temp_uom = 4
        controller.NuHeat = MagicMock()
        controller.NuHeat.get_thermostat.return_value = {
            'serialNumber': '99887766',
            'currentTemperature': 2000,
            'setPointTemperature': 2100,
            'mode': 2, # Manual
            'isHeating': False
        }
        controller.NuHeat.nuheat_celsius_to_normal.side_effect = lambda val: val / 100
        controller.NuHeat.nuheat_celsius_to_json.side_effect = lambda c: round(c * 100)
        controller.NuHeat.set_thermostat_setpoint.return_value = True

        node = ThermostatNode(self.mock_poly, '99887766', '99887766', 'Guest Bath', controller, temp_uom=4)
        node.setDriver = MagicMock()

        node.update_info()
        node.setDriver.assert_any_call('ST', 20.0, uom=4)
        node.setDriver.assert_any_call('CLISPH', 21.0, uom=4)
        node.setDriver.assert_any_call('CLIMD', 1, uom=67)
        node.setDriver.assert_any_call('CLIHCS', 0, uom=66)

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
        time_calls = [c for c in node.setDriver.call_args_list if c[0][0] == 'TIME']
        self.assertEqual(len(time_calls), 1)
        self.assertEqual(time_calls[0][1].get('uom'), 151)
        # Verify GV1 is no longer called
        gv1_calls = [c for c in node.setDriver.call_args_list if c[0][0] == 'GV1']
        self.assertEqual(len(gv1_calls), 0)

    def test_energy_log_week_and_year_nodes(self):
        controller = MagicMock()
        controller.NuHeat = MagicMock()
        controller.tz = 'America/New_York'
        controller.NuHeat.get_energy_log_week.return_value = [420, 8.75, 1.26]
        controller.NuHeat.get_energy_log_year.return_value = [5000, 104.2, 15.0]

        week_node = EnergyLogWeekNode(self.mock_poly, '99887766', 'elw99887766', 'Energy-Week', controller)
        week_node.setDriver = MagicMock()
        week_node.update_info()
        week_node.setDriver.assert_any_call('GV0', 420, uom=45)
        week_node.setDriver.assert_any_call('ST', 8.75, uom=33)

        year_node = EnergyLogYearNode(self.mock_poly, '99887766', 'ely99887766', 'Energy-Year', controller)
        year_node.setDriver = MagicMock()
        year_node.update_info()
        year_node.setDriver.assert_any_call('GV0', 5000, uom=45)
        year_node.setDriver.assert_any_call('ST', 104.2, uom=33)

    def test_profile_builder(self):
        profile_f = _build_profile_definition("F")
        self.assertIn("editors", profile_f)
        self.assertIn("nodedefs", profile_f)
        self.assertEqual(profile_f["linkdefs"], [])

        # Check CLITEMP editor ranges in F mode
        clitemp_editor = next(e for e in profile_f["editors"] if e["id"] == "CLITEMP")
        self.assertEqual(clitemp_editor["ranges"][0]["uom"], "17")

        # Check CLITEMP editor ranges in C mode
        profile_c = _build_profile_definition("C")
        clitemp_c = next(e for e in profile_c["editors"] if e["id"] == "CLITEMP")
        self.assertEqual(clitemp_c["ranges"][0]["uom"], "4")

        # Verify nodedefs include controller, THERMOSTAT, and ENERGYLOG
        nodedef_ids = {nd["id"] for nd in profile_f["nodedefs"]}
        self.assertEqual(nodedef_ids, {"controller", "THERMOSTAT", "ENERGYLOG"})

        # Verify TIME driver in each nodedef and GV1 is removed
        editor_ids = {e["id"] for e in profile_f["editors"]}
        self.assertNotIn("GV1", editor_ids)

        for nd in profile_f["nodedefs"]:
            prop_ids = {p["id"] for p in nd["properties"]}
            self.assertIn("TIME", prop_ids, f"Node {nd['id']} missing TIME property")
            self.assertNotIn("GV1", prop_ids, f"Node {nd['id']} should not contain GV1 property")

    def test_node_done_and_wait_confirmation(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        self.assertNotIn("99887766", controller._confirmed_node_addresses)

        controller.node_done({"address": "99887766"})
        self.assertIn("99887766", controller._confirmed_node_addresses)

        # Should immediately return True since already confirmed
        self.assertTrue(controller._wait_for_node_confirmed("99887766", timeout=0.1))

        controller.node_deleted({"address": "99887766"})
        self.assertNotIn("99887766", controller._confirmed_node_addresses)
        self.assertIn("99887766", controller._deleted_node_addresses)

    def test_controller_custom_ns_oauth_credentials(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.customNsHandler = MagicMock()
        controller.customNsHandler('oauth', {'client_id': 'test_oauth_id', 'client_secret': 'test_oauth_sec'})
        self.assertEqual(controller.client_id, 'test_oauth_id')
        self.assertEqual(controller.client_secret, 'test_oauth_sec')
        self.assertTrue(controller.portalReady)
        self.assertTrue(controller.customNsDone)
        self.assertTrue(controller.customNsHandlerDone)
        controller.oauth.customNsHandler.assert_called_once_with('oauth', {'client_id': 'test_oauth_id', 'client_secret': 'test_oauth_sec'})

    def test_controller_custom_ns_nsdata_credentials(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.updateOauthSettings = MagicMock()
        controller.customNsHandler('nsdata', {'portalID': 'test_portal_id', 'PortalSecret': 'test_portal_secret'})
        self.assertEqual(controller.portalID, 'test_portal_id')
        self.assertEqual(controller.portalSecret, 'test_portal_secret')
        self.assertEqual(controller.client_id, 'test_portal_id')
        self.assertEqual(controller.client_secret, 'test_portal_secret')
        self.assertTrue(controller.portalReady)
        self.assertTrue(controller.customNsDone)

    def test_controller_start_synchronization(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.customParam_done = True
        controller.customNsDone = True
        controller.config_done = True
        controller.portalReady = True
        controller.get_access_token = MagicMock(return_value='test_valid_token')
        controller.discover = MagicMock()
        controller._publish_profile = MagicMock()

        controller.start()
        controller.discover.assert_called_once()
        self.assertEqual(controller.drivers[0]['value'], 1)  # ST driver


if __name__ == '__main__':
    unittest.main()
