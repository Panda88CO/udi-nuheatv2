import importlib.util
import os
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from nuheat import NuHeat
from nodes import ThermostatNode, ThermostatNode_F, ThermostatNode_C, EnergyLogDayNode, EnergyLogWeekNode, EnergyLogYearNode
from nodes.base import get_current_timestamp, is_uom151_supported, NTP_EPOCH_OFFSET

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
        self.mock_poly.updateProfile = MagicMock()
        self.mock_poly.getNodes.return_value = {}
        self.mock_poly.getNode.return_value = None
        self.mock_poly.ADDNODEDONE = 'ADDNODEDONE'
        self.mock_poly.DELNODEDONE = 'DELNODEDONE'
        self.mock_poly.getValidAddress = MagicMock(side_effect=lambda x: str(x).lower()[:14])
        self.mock_poly.getValidName = MagicMock(side_effect=lambda x: str(x).replace("'", ""))

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
        controller.update_profile = MagicMock()
        controller._publish_profile = controller.update_profile

        # Create mock thermostat node on controller
        mock_stat = MagicMock()
        mock_stat.temp_uom = 17
        self.mock_poly.getNodes.return_value = {'stat_1': mock_stat}

        params = {
            'tz': 'America/Chicago',
            'temp_unit': 'C'
        }
        controller.customParamsHandler(params)
        self.assertEqual(controller.tz, 'America/Chicago')
        self.assertEqual(controller.temp_unit, 'C')
        self.assertEqual(controller.temp_uom, 4)
        self.assertEqual(mock_stat.temp_uom, 4)
        mock_stat.update_info.assert_called_once()
        controller.update_profile.assert_called_once()

    def test_controller_custom_params_handler_with_temp_unt(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.update_profile = MagicMock()
        controller._publish_profile = controller.update_profile

        params = {
            'tz': 'America/Denver',
            'temp_unt': 'C'
        }
        controller.customParamsHandler(params)
        self.assertEqual(controller.temp_unit, 'C')
        self.assertEqual(controller.temp_uom, 4)

        params_f = {
            'tz': 'America/Denver',
            'temp_unt': 'F'
        }
        controller.customParamsHandler(params_f)
        self.assertEqual(controller.temp_unit, 'F')
        self.assertEqual(controller.temp_uom, 17)

    def test_controller_init_preregisters_oauth_endpoints(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        override = getattr(controller.oauth, '_oauthConfigOverride', {})
        self.assertEqual(override.get('auth_endpoint'), 'https://identity.mynuheat.com/connect/authorize')
        self.assertEqual(override.get('token_endpoint'), 'https://identity.mynuheat.com/connect/token')
        self.assertEqual(override.get('name'), 'Nuheat')

    def test_controller_custom_ns_handler_empty_oauth_avoids_spurious_errors(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.customNsHandler = MagicMock()
        # With no credentials configured, calling with empty data should NOT pass empty data to self.oauth
        controller.customNsHandler('oauth', {})
        controller.oauth.customNsHandler.assert_not_called()
        self.assertTrue(controller.customNsDone)

    def test_controller_custom_ns_handler_with_credentials(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.customNsHandler = MagicMock()
        controller.customNsHandler('oauth', {'client_id': 'test_id', 'client_secret': 'test_sec'})
        self.assertEqual(controller.client_id, 'test_id')
        self.assertEqual(controller.client_secret, 'test_sec')
        self.assertTrue(controller.oauthReady)
        controller.oauth.customNsHandler.assert_called_once_with('oauth', {'client_id': 'test_id', 'client_secret': 'test_sec'})

    def test_controller_custom_params_handler_with_credentials(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.customParamsHandler({'clientId': 'cp_id', 'clientSecret': 'cp_sec'})
        self.assertEqual(controller.client_id, 'cp_id')
        self.assertEqual(controller.client_secret, 'cp_sec')
        self.assertTrue(controller.oauthReady)
        override = getattr(controller.oauth, '_oauthConfigOverride', {})
        self.assertEqual(override.get('client_id'), 'cp_id')
        self.assertEqual(override.get('client_secret'), 'cp_sec')

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
        controller.NuHeat.get_energy_log_day = MagicMock(return_value=[60, 1.25, 0.18])
        controller.NuHeat.get_energy_log_week = MagicMock(return_value=[420, 8.75, 1.26])
        controller.NuHeat.get_energy_log_month = MagicMock(return_value=[1800, 35.50, 4.50])
        controller.NuHeat.get_energy_log_year = MagicMock(return_value=[5000, 104.20, 15.00])

        controller.discover()
        self.assertEqual(controller.disco, 1)
        # Should have added 1 controller node + 1 thermostat node = 2 nodes
        self.assertEqual(self.mock_poly.addNode.call_count, 2)

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
        controller.NuHeat.get_energy_log_day = MagicMock(return_value=[60, 1.25, 0.18])
        controller.NuHeat.get_energy_log_week = MagicMock(return_value=[420, 8.75, 1.26])
        controller.NuHeat.get_energy_log_month = MagicMock(return_value=[1800, 35.50, 4.50])
        controller.NuHeat.get_energy_log_year = MagicMock(return_value=[5000, 104.20, 15.00])

        existing_node = MagicMock()
        existing_node.primary = 'controller'
        legacy_child = MagicMock()

        def mock_get_node(addr):
            if addr == '99887766':
                return existing_node
            elif addr in ('eld99887766', 'elw99887766', 'ely99887766'):
                return legacy_child
            return None

        self.mock_poly.getNode = MagicMock(side_effect=mock_get_node)
        self.mock_poly.delNode = MagicMock()

        controller.discover()
        self.mock_poly.delNode.assert_any_call('99887766')
        self.mock_poly.delNode.assert_any_call('eld99887766')
        self.mock_poly.delNode.assert_any_call('elw99887766')
        self.mock_poly.delNode.assert_any_call('ely99887766')

    def test_thermostat_node_f(self):
        controller = MagicMock()
        controller.temp_uom = 17
        controller.NuHeat = MagicMock()
        controller.NuHeat.get_thermostat.return_value = {
            'serialNumber': '99887766',
            'currentTemperature': 2000,
            'setPointTemperature': 2100,
            'mode': 1, # Auto
            'isHeating': True,
            'holdUntil': None
        }
        controller.NuHeat.nuheat_celsius_to_fahrenheit.side_effect = lambda val: (val / 100) * 9/5 + 32
        controller.NuHeat.nuheat_fahrenheit_to_celsius_json.side_effect = lambda f: round((f - 32) * 5/9 * 100)
        controller.NuHeat.set_mode_auto.return_value = True
        controller.NuHeat.set_mode_manual.return_value = True
        controller.NuHeat.set_mode_hold.return_value = True

        node = ThermostatNode(self.mock_poly, '99887766', '99887766', 'Guest Bath', controller, temp_uom=17)
        self.assertEqual(node.id, 'thermostatf')
        node.setDriver = MagicMock()

        # Test update_info in Auto mode (CLISPH reports active setpoint, GV4=0)
        node.update_info()
        node.setDriver.assert_any_call('ST', 68.0, uom=17)
        node.setDriver.assert_any_call('CLIHCS', 1, uom=66)
        node.setDriver.assert_any_call('CLIMD', 1, uom=25)
        node.setDriver.assert_any_call('CLISPH', 69.8, uom=17)
        node.setDriver.assert_any_call('GV4', 0, uom=45)
        node.setDriver.assert_any_call('GV5', 1, uom=2)

        # Test SET_PERM_HOLD - Permanent Hold (takes temp)
        node.set_permanent_hold({'query': {'temp': '72'}})
        controller.NuHeat.set_mode_manual.assert_called_once_with('99887766', 2222)
        node.setDriver.assert_any_call('CLIMD', 3, uom=25)
        node.setDriver.assert_any_call('CLISPH', 72.0, uom=17)
        node.setDriver.assert_any_call('GV4', 0, uom=45)

        # Test SET_HOLD - Temporary Hold (takes temp and hold duration in minutes)
        node.set_hold({'query': {'temp.uom17': '70', 'hold.uom45': '90'}})
        self.assertEqual(controller.NuHeat.set_mode_hold.call_count, 1)
        call_args = controller.NuHeat.set_mode_hold.call_args[0]
        self.assertEqual(call_args[0], '99887766')
        self.assertEqual(call_args[1], 2111)
        self.assertTrue(controller.NuHeat.set_mode_hold.call_args[1].get('hold_until').endswith('Z'))
        node.setDriver.assert_any_call('CLIMD', 2, uom=25)
        node.setDriver.assert_any_call('CLISPH', 70.0, uom=17)
        node.setDriver.assert_any_call('GV4', 90, uom=45)

        # Test SET_PERM_HOLD with empty parameter id (id="" -> .uom17 from nodedefs.xml)
        node.set_permanent_hold({'query': {'.uom17': '41'}})
        controller.NuHeat.set_mode_manual.assert_called_with('99887766', 500)
        node.setDriver.assert_any_call('CLISPH', 41.0, uom=17)

        # Test SET_PERM_HOLD with direct value and uom metadata from PG3 (id="")
        node.set_permanent_hold({'address': '99887766', 'cmd': 'SET_PERM_HOLD', 'value': '70', 'uom': '17', 'query': {}})
        controller.NuHeat.set_mode_manual.assert_called_with('99887766', 2111)
        node.setDriver.assert_any_call('CLISPH', 70.0, uom=17)

        # Test SET_HOLD with TEMPHOLDF.uom17 and HOLD.uom45 (from nodedefs.xml)
        node.set_hold({'query': {'TEMPHOLDF.uom17': '42', 'HOLD.uom45': '6'}})
        call_args = controller.NuHeat.set_mode_hold.call_args[0]
        self.assertEqual(call_args[1], 556)
        node.setDriver.assert_any_call('CLISPH', 42.0, uom=17)

        # Test backwards compatibility with lowercase keys
        node.set_hold({'query': {'tempholdF.uom17': '43', 'hold.uom45': '10'}})
        call_args = controller.NuHeat.set_mode_hold.call_args[0]
        self.assertEqual(call_args[1], 611)
        node.setDriver.assert_any_call('CLISPH', 43.0, uom=17)

        # Test update_info with holdUntil calculates remaining minutes
        future_dt = datetime.now(timezone.utc) + timedelta(minutes=120)
        controller.NuHeat.get_thermostat.return_value = {
            'serialNumber': '99887766',
            'currentTemperature': 2000,
            'setPointTemperature': 2100,
            'mode': 2,
            'isHeating': True,
            'online': True,
            'holdUntil': future_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        node.update_info()
        node.setDriver.assert_any_call('GV4', 120, uom=45)

        # Test SET_AUTO - Auto (takes no parameters)
        node.set_auto()
        controller.NuHeat.set_mode_auto.assert_called_once_with('99887766')
        node.setDriver.assert_any_call('CLIMD', 1, uom=25)
        node.setDriver.assert_any_call('GV4', 0, uom=45)

        # Test update_energy
        controller.NuHeat.get_energy_log_day.return_value = [60, 1.25, 0.18]
        controller.NuHeat.get_energy_log_week.return_value = [420, 8.75, 1.26]
        controller.NuHeat.get_energy_log_month.return_value = [1800, 35.50, 4.50]
        controller.NuHeat.get_energy_log_year.return_value = [5000, 104.20, 15.00]
        controller.tz = 'America/New_York'

        node.update_energy()
        node.setDriver.assert_any_call('GV0', 1.25, uom=33)
        node.setDriver.assert_any_call('GV1', 8.75, uom=33)
        node.setDriver.assert_any_call('GV2', 35.50, uom=33)
        node.setDriver.assert_any_call('GV3', 104.20, uom=33)


        # Test force_update (UPDATE command handler)
        node.reportDrivers = MagicMock()
        node.force_update()
        node.reportDrivers.assert_called_once()
        self.assertEqual(node.commands, {
            'UPDATE': ThermostatNode.force_update,
            'SETAUTO': ThermostatNode.set_auto,
            'SETHOLD': ThermostatNode.set_hold,
            'SETPERMHOLD': ThermostatNode.set_permanent_hold,
            'SET_AUTO': ThermostatNode.set_auto,
            'SET_HOLD': ThermostatNode.set_hold,
            'SET_PERM_HOLD': ThermostatNode.set_permanent_hold,
        })

    def test_thermostat_node_c(self):
        controller = MagicMock()
        controller.temp_uom = 4
        controller.NuHeat = MagicMock()
        controller.NuHeat.get_thermostat.return_value = {
            'serialNumber': '99887766',
            'currentTemperature': 2000,
            'setPointTemperature': 2100,
            'mode': 3, # Permanent Hold / Manual
            'isHeating': False,
            'online': False,
            'holdUntil': None
        }
        controller.NuHeat.nuheat_celsius_to_normal.side_effect = lambda val: val / 100
        controller.NuHeat.nuheat_celsius_to_json.side_effect = lambda c: round(c * 100)
        controller.NuHeat.set_mode_manual.return_value = True

        node = ThermostatNode(self.mock_poly, '99887766', '99887766', 'Guest Bath', controller, temp_uom=4)
        self.assertEqual(node.id, 'thermostatc')
        node.setDriver = MagicMock()

        node.update_info()
        node.setDriver.assert_any_call('ST', 20.0, uom=4)
        node.setDriver.assert_any_call('CLISPH', 21.0, uom=4)
        node.setDriver.assert_any_call('CLIMD', 3, uom=25)
        node.setDriver.assert_any_call('CLIHCS', 0, uom=66)
        node.setDriver.assert_any_call('GV4', 0, uom=45)
        node.setDriver.assert_any_call('GV5', 0, uom=2)

        # Test SET_PERM_HOLD with empty parameter id (id="" -> .uom4 from nodedefs.xml)
        node.set_permanent_hold({'query': {'.uom4': '21'}})
        controller.NuHeat.set_mode_manual.assert_called_with('99887766', 2100)
        node.setDriver.assert_any_call('CLISPH', 21.0, uom=4)

        # Test SET_PERM_HOLD with direct value and uom metadata from PG3 (id="") in Celsius
        node.set_permanent_hold({'address': '99887766', 'cmd': 'SET_PERM_HOLD', 'value': '22', 'uom': '4', 'query': {}})
        controller.NuHeat.set_mode_manual.assert_called_with('99887766', 2200)
        node.setDriver.assert_any_call('CLISPH', 22.0, uom=4)

        # Test SET_PERM_HOLD with temppermC.uom4
        node.set_permanent_hold({'query': {'temppermC.uom4': '20'}})
        controller.NuHeat.set_mode_manual.assert_called_with('99887766', 2000)
        node.setDriver.assert_any_call('CLISPH', 20.0, uom=4)

        # Test SET_HOLD with TEMPHOLDC.uom4 in Celsius
        controller.NuHeat.set_mode_hold.return_value = True
        node.set_hold({'query': {'TEMPHOLDC.uom4': '23', 'HOLD.uom45': '60'}})
        call_args = controller.NuHeat.set_mode_hold.call_args[0]
        self.assertEqual(call_args[0], '99887766')
        self.assertEqual(call_args[1], 2300)
        node.setDriver.assert_any_call('CLISPH', 23.0, uom=4)
        node.setDriver.assert_any_call('CLIMD', 2, uom=25)
        node.setDriver.assert_any_call('GV4', 60, uom=45)

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

    def test_static_profile_files(self):
        import xml.etree.ElementTree as ET
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

        # Check version.txt
        version_path = os.path.join(repo_dir, 'profile', 'version.txt')
        self.assertTrue(os.path.isfile(version_path))
        with open(version_path, 'r') as f:
            v_content = f.read().strip()
        self.assertEqual(v_content, "2.2.19")

        # Check editors.xml
        editors_path = os.path.join(repo_dir, 'profile', 'editor', 'editors.xml')
        self.assertTrue(os.path.isfile(editors_path))
        tree_editors = ET.parse(editors_path)
        root_editors = tree_editors.getroot()
        editor_ids = {e.get('id'): e for e in root_editors.findall('editor')}

        # Must have temperature editors for F, C, and their input variants in UPPERCASE
        self.assertIn('TEMPF', editor_ids)
        self.assertIn('TEMPFINPUT', editor_ids)
        self.assertIn('TEMPC', editor_ids)
        self.assertIn('TEMPCINPUT', editor_ids)
        self.assertIn('ONLINE', editor_ids)
        self.assertIn('TIMESTAMP', editor_ids)
        self.assertNotIn('tempF', editor_ids)
        self.assertNotIn('tempC', editor_ids)
        self.assertNotIn('bool', editor_ids)
        self.assertNotIn('BOOL', editor_ids)

        temp_f = editor_ids['TEMPF'].findall('range')
        self.assertEqual(len(temp_f), 1)
        self.assertEqual(temp_f[0].get('uom'), '17')
        self.assertEqual(temp_f[0].get('min'), '41')
        self.assertEqual(temp_f[0].get('max'), '104')

        temp_f_in = editor_ids['TEMPFINPUT'].findall('range')
        self.assertEqual(len(temp_f_in), 1)
        self.assertEqual(temp_f_in[0].get('uom'), '17')

        temp_c = editor_ids['TEMPC'].findall('range')
        self.assertEqual(len(temp_c), 1)
        self.assertEqual(temp_c[0].get('uom'), '4')
        self.assertEqual(temp_c[0].get('min'), '5')
        self.assertEqual(temp_c[0].get('max'), '40')

        temp_c_in = editor_ids['TEMPCINPUT'].findall('range')
        self.assertEqual(len(temp_c_in), 1)
        self.assertEqual(temp_c_in[0].get('uom'), '4')

        # Verify TEMPF and TEMPC do not have step, while TEMPFINPUT and TEMPCINPUT have step="1"
        self.assertIsNone(temp_f[0].get('step'))
        self.assertEqual(temp_f_in[0].get('step'), '1')
        self.assertIsNone(temp_c[0].get('step'))
        self.assertEqual(temp_c_in[0].get('step'), '1')

        # Verify inputs and display editors have prec="0"
        self.assertEqual(temp_f[0].get('prec'), '0')
        self.assertEqual(temp_f_in[0].get('prec'), '0')
        self.assertEqual(temp_c[0].get('prec'), '0')
        self.assertEqual(temp_c_in[0].get('prec'), '0')

        # Verify HOLDMINS editor and absence of HOLDSTAT/HOLDTIME
        self.assertIn('HOLDMINS', editor_ids)
        self.assertNotIn('HOLDSTAT', editor_ids)
        self.assertNotIn('HOLDTIME', editor_ids)

        hold_mins = editor_ids['HOLDMINS'].findall('range')
        self.assertEqual(hold_mins[0].get('step'), '1')
        self.assertEqual(hold_mins[0].get('prec'), '0')
        self.assertEqual(hold_mins[0].get('uom'), '45')

        online_stat = editor_ids['ONLINE'].findall('range')
        self.assertEqual(len(online_stat), 1)
        self.assertEqual(online_stat[0].get('uom'), '2')
        self.assertEqual(online_stat[0].get('subset'), '0,1')
        self.assertEqual(online_stat[0].get('nls'), 'ONLINE')

        # Verify TIMESTAMP editor defaults to uom="137" in static XML profile for ISY-994 compatibility
        timestamp_stat = editor_ids['TIMESTAMP'].findall('range')
        self.assertEqual(len(timestamp_stat), 1)
        self.assertEqual(timestamp_stat[0].get('uom'), '137')
        self.assertEqual(timestamp_stat[0].get('prec'), '0')

        # Check nodedefs.xml
        nodedefs_path = os.path.join(repo_dir, 'profile', 'nodedef', 'nodedefs.xml')
        self.assertTrue(os.path.isfile(nodedefs_path))
        tree_nodedefs = ET.parse(nodedefs_path)
        root_nodedefs = tree_nodedefs.getroot()
        nodedef_map = {nd.get('id'): nd for nd in root_nodedefs.findall('nodeDef')}

        self.assertIn('controller', nodedef_map)
        self.assertIn('thermostatf', nodedef_map)
        self.assertIn('thermostatc', nodedef_map)

        # Verify controller sts
        sts_ctl = {st.get('id'): st.get('editor') for st in nodedef_map['controller'].find('sts').findall('st')}
        self.assertEqual(sts_ctl['ST'], 'ONLINE')
        self.assertEqual(sts_ctl['TIME'], 'TIMESTAMP')

        # Verify thermostatf uses non-input editor TEMPF and explicit sends
        self.assertIsNotNone(nodedef_map['thermostatf'].find('cmds').find('sends'))
        sts_f = {st.get('id'): st.get('editor') for st in nodedef_map['thermostatf'].find('sts').findall('st')}
        self.assertEqual(sts_f['ST'], 'TEMPF')
        self.assertEqual(sts_f['CLISPH'], 'TEMPF')
        self.assertEqual(sts_f['GV4'], 'HOLDMINS')
        self.assertEqual(sts_f['GV5'], 'ONLINE')
        self.assertNotIn('GV6', sts_f)
        self.assertEqual(sts_f['TIME'], 'TIMESTAMP')

        # Verify thermostatf accepts standard and dedicated commands with UPPERCASE parameter IDs
        cmds_f = {cmd.get('id'): cmd for cmd in nodedef_map['thermostatf'].find('cmds').find('accepts').findall('cmd')}
        self.assertIn('SETHOLD', cmds_f)
        self.assertIn('SETPERMHOLD', cmds_f)
        self.assertIn('SETAUTO', cmds_f)
        params_f = {p.get('id'): p.get('editor') for p in cmds_f['SETHOLD'].findall('p')}
        self.assertEqual(params_f['TEMPHOLDF'], 'TEMPFINPUT')
        self.assertEqual(params_f['HOLD'], 'HOLDMINS')
        self.assertNotIn('tempholdF', params_f)
        self.assertNotIn('hold', params_f)

        # Verify thermostatc uses non-input editor TEMPC and explicit sends
        self.assertIsNotNone(nodedef_map['thermostatc'].find('cmds').find('sends'))
        sts_c = {st.get('id'): st.get('editor') for st in nodedef_map['thermostatc'].find('sts').findall('st')}
        self.assertEqual(sts_c['ST'], 'TEMPC')
        self.assertEqual(sts_c['CLISPH'], 'TEMPC')
        self.assertEqual(sts_c['GV4'], 'HOLDMINS')
        self.assertEqual(sts_c['GV5'], 'ONLINE')
        self.assertNotIn('GV6', sts_c)
        self.assertEqual(sts_c['TIME'], 'TIMESTAMP')

        # Verify thermostatc accepts standard and dedicated commands with UPPERCASE parameter IDs
        cmds_c = {cmd.get('id'): cmd for cmd in nodedef_map['thermostatc'].find('cmds').find('accepts').findall('cmd')}
        self.assertIn('SETHOLD', cmds_c)
        self.assertIn('SETPERMHOLD', cmds_c)
        self.assertIn('SETAUTO', cmds_c)
        params_c = {p.get('id'): p.get('editor') for p in cmds_c['SETHOLD'].findall('p')}
        self.assertEqual(params_c['TEMPHOLDC'], 'TEMPCINPUT')
        self.assertEqual(params_c['HOLD'], 'HOLDMINS')
        self.assertNotIn('tempholdC', params_c)
        self.assertNotIn('hold', params_c)

        # Check en_us.txt
        nls_path = os.path.join(repo_dir, 'profile', 'nls', 'en_us.txt')
        self.assertTrue(os.path.isfile(nls_path))
        with open(nls_path, 'r') as f:
            nls_content = f.read()
        self.assertIn('ND-thermostatf-NAME', nls_content)
        self.assertIn('ND-thermostatc-NAME', nls_content)
        self.assertNotIn('ND-thermostat_f-NAME', nls_content)
        self.assertNotIn('ND-thermostat_c-NAME', nls_content)
        self.assertNotIn('ND-THERMOSTAT_F-NAME', nls_content)
        self.assertNotIn('ND-THERMOSTAT_C-NAME', nls_content)
        self.assertIn('CMD-TSTAT-SETAUTO-NAME', nls_content)
        self.assertIn('CMD-TSTAT-SETHOLD-NAME', nls_content)
        self.assertIn('CMD-TSTAT-SETPERMHOLD-NAME', nls_content)
        self.assertIn('CMDP-TEMPHOLDF-NAME = Hold Temperature', nls_content)
        self.assertIn('CMDP-TEMPHOLDC-NAME = Hold Temperature', nls_content)
        self.assertIn('CMDP-HOLD-NAME = Hold Minutes', nls_content)
        self.assertNotIn('CMDP-tempholdF-NAME', nls_content)
        self.assertNotIn('CMDP-tempholdC-NAME', nls_content)
        self.assertNotIn('CMDP-hold-NAME', nls_content)
        self.assertIn('ONLINE-0 = Offline', nls_content)
        self.assertIn('ONLINE-1 = Online', nls_content)
        self.assertNotIn('BOOL-0', nls_content)
        self.assertNotIn('BOOL-1', nls_content)
        self.assertNotIn('HOLDSTAT', nls_content)
        self.assertNotIn('HOLDNAMES', nls_content)
        self.assertNotIn('HOLD_NAMES', nls_content)
        self.assertIn('ST-TSTAT-GV4-NAME = Hold Time', nls_content)
        self.assertNotIn('GV6', nls_content)

    def test_thermostat_subclasses_f_and_c(self):
        node_f = ThermostatNode_F(self.mock_poly, '112233', '112233', 'Test F')
        self.assertEqual(node_f.id, 'thermostatf')
        self.assertEqual(node_f.temp_uom, 17)
        self.assertEqual(node_f.drivers[0]['uom'], 17)
        self.assertEqual(node_f.drivers[1]['uom'], 17)
        gv4_f = [d for d in node_f.drivers if d['driver'] == 'GV4'][0]
        self.assertEqual(gv4_f['uom'], 45)
        self.assertNotIn('GV6', [d['driver'] for d in node_f.drivers])

        node_c = ThermostatNode_C(self.mock_poly, '445566', '445566', 'Test C')
        self.assertEqual(node_c.id, 'thermostatc')
        self.assertEqual(node_c.temp_uom, 4)
        self.assertEqual(node_c.drivers[0]['uom'], 4)
        self.assertEqual(node_c.drivers[1]['uom'], 4)
        gv4_c = [d for d in node_c.drivers if d['driver'] == 'GV4'][0]
        self.assertEqual(gv4_c['uom'], 45)
        self.assertNotIn('GV6', [d['driver'] for d in node_c.drivers])

    def test_controller_serial_1_by_1_node_creation(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.get_access_token = MagicMock(return_value='valid_token')
        controller.NuHeat.get_account = MagicMock(return_value={'temperatureScale': 'Fahrenheit'})
        controller.NuHeat.get_thermostat = MagicMock(return_value=[
            {'serialNumber': '101', 'name': 'Stat 1', 'currentTemperature': 2000, 'setPointTemperature': 2100, 'mode': 1, 'isHeating': False},
            {'serialNumber': '102', 'name': 'Stat 2', 'currentTemperature': 2200, 'setPointTemperature': 2300, 'mode': 1, 'isHeating': False}
        ])
        controller.NuHeat.get_energy_log_day = MagicMock(return_value=[60, 1.0, 0.1])
        controller.NuHeat.get_energy_log_week = MagicMock(return_value=[420, 7.0, 1.0])
        controller.NuHeat.get_energy_log_month = MagicMock(return_value=[1800, 30.0, 4.0])
        controller.NuHeat.get_energy_log_year = MagicMock(return_value=[5000, 100.0, 15.0])

        order_of_ops = []

        original_add_node = self.mock_poly.addNode
        def mock_add(node):
            order_of_ops.append(('addNode', node.address))
            # Simulate PG3 acknowledging the node
            controller.node_done(node)
        self.mock_poly.addNode = MagicMock(side_effect=mock_add)

        wait_spy = MagicMock(side_effect=lambda addr, timeout=10.0: (order_of_ops.append(('waitConfirmed', addr)), True)[1])
        controller._wait_for_node_confirmed = wait_spy

        controller.discover()

        # Verify that node 101 was added AND waited for confirmation BEFORE node 102 was added
        self.assertEqual(order_of_ops, [
            ('addNode', '101'),
            ('waitConfirmed', '101'),
            ('addNode', '102'),
            ('waitConfirmed', '102')
        ])

    def test_controller_update_nodes(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.longPoll = MagicMock()
        controller.setDriver = MagicMock()

        res = controller.update_nodes()
        self.assertTrue(res)
        controller.longPoll.assert_called_once()
        controller.setDriver.assert_called_with('TIME', unittest.mock.ANY, uom=151)

    def test_controller_heartbeat(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.reportCmd = MagicMock()

        # First heartbeat call toggles to DON (hb_state = 1)
        controller.heartbeat()
        controller.reportCmd.assert_called_with('DON')
        self.assertEqual(controller.hb_state, 1)

        # Second heartbeat call toggles to DOF (hb_state = 0)
        controller.heartbeat()
        controller.reportCmd.assert_called_with('DOF')
        self.assertEqual(controller.hb_state, 0)

        # shortPoll calls heartbeat
        controller.shortPoll()
        controller.reportCmd.assert_called_with('DON')
        self.assertEqual(controller.hb_state, 1)

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
        self.assertTrue(controller.oauthReady)
        self.assertTrue(controller.customNsDone)
        self.assertTrue(controller.customNsHandlerDone)
        controller.oauth.customNsHandler.assert_called_once_with('oauth', {'client_id': 'test_oauth_id', 'client_secret': 'test_oauth_sec'})

    def test_controller_custom_ns_oauth_tokens(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.oauth.customNsHandler = MagicMock()
        controller.customNsHandler('oauthTokens', {'access_token': 'test_tok'})
        self.assertTrue(controller.customNsDone)
        self.assertTrue(controller.customNsHandlerDone)
        controller.oauth.customNsHandler.assert_called_once_with('oauthTokens', {'access_token': 'test_tok'})

    def test_controller_start_synchronization(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        controller.customParam_done = True
        controller.customNsDone = True
        controller.config_done = True
        controller.oauthReady = True
        controller.get_access_token = MagicMock(return_value='test_valid_token')
        controller.discover = MagicMock()
        controller._publish_profile = MagicMock()

        controller.start()
        controller.discover.assert_called_once()
        self.assertEqual(controller.drivers[0]['value'], 1)  # ST driver

    def test_is_uom151_supported(self):
        # Default with no version or mock without version
        self.assertTrue(is_uom151_supported(MagicMock()))
        self.assertTrue(is_uom151_supported(None))

        # Test pg3init dict
        mock_poly = MagicMock()
        mock_poly.pg3init = {'isyVersion': '5.3.4'}
        self.assertFalse(is_uom151_supported(mock_poly))

        mock_poly.pg3init = {'isyVersion': '5.0.16'}
        self.assertFalse(is_uom151_supported(mock_poly))

        mock_poly.pg3init = {'isyVersion': '5.7.0'}
        self.assertFalse(is_uom151_supported(mock_poly))

        mock_poly.pg3init = {'isyVersion': '5.8.0'}
        self.assertTrue(is_uom151_supported(mock_poly))

        mock_poly.pg3init = {'isyVersion': '5.8.4'}
        self.assertTrue(is_uom151_supported(mock_poly))

        mock_poly.pg3init = {'isyVersion': '6.0.2'}
        self.assertTrue(is_uom151_supported(mock_poly))

        # Test serverdata dict
        mock_poly.pg3init = None
        mock_poly.serverdata = {'isyVersion': '5.3.4'}
        self.assertFalse(is_uom151_supported(mock_poly))

        mock_poly.serverdata = {'isyVersion': '5.8.0'}
        self.assertTrue(is_uom151_supported(mock_poly))

        # Test getIsyVersion method
        mock_poly.serverdata = None
        mock_poly.getIsyVersion.return_value = '5.3.4'
        self.assertFalse(is_uom151_supported(mock_poly))

        mock_poly.getIsyVersion.return_value = '5.8.3'
        self.assertTrue(is_uom151_supported(mock_poly))

    def test_get_current_timestamp(self):
        now = int(time.time())
        ts_151 = get_current_timestamp(151)
        self.assertAlmostEqual(ts_151, now, delta=2)

        ts_137 = get_current_timestamp(137)
        self.assertAlmostEqual(ts_137, now + NTP_EPOCH_OFFSET, delta=2)
        self.assertEqual(ts_137 - ts_151, NTP_EPOCH_OFFSET)

    def test_build_profile_definition(self):
        # Fahrenheit profile with UOM 151
        profile_f_151 = _build_profile_definition(temp_unit="F", time_uom=151)
        self.assertEqual(profile_f_151['version'], "2.2.19")
        editors_f = {e['id']: e for e in profile_f_151['editors']}
        self.assertIn('TEMPF', editors_f)
        self.assertIn('TEMPFINPUT', editors_f)
        self.assertIn('HOLDMINS', editors_f)
        self.assertIn('ONLINE', editors_f)
        self.assertIn('TIMESTAMP', editors_f)
        self.assertEqual(editors_f['TIMESTAMP']['ranges'][0]['uom'], '151')

        # Celsius profile with UOM 137
        profile_c_137 = _build_profile_definition(temp_unit="C", time_uom=137)
        editors_c = {e['id']: e for e in profile_c_137['editors']}
        self.assertIn('TEMPC', editors_c)
        self.assertIn('TEMPCINPUT', editors_c)
        self.assertEqual(editors_c['TIMESTAMP']['ranges'][0]['uom'], '137')

        # Verify nodedefs have UPPERCASE IDs and no underscores
        for nd in profile_f_151['nodedefs']:
            for prop in nd['properties']:
                self.assertEqual(prop['id'], prop['id'].upper())
                self.assertNotIn('_', prop['id'])
                self.assertEqual(prop['editor'], prop['editor'].upper())
                self.assertNotIn('_', prop['editor'])
            for cmd in nd.get('cmds', {}).get('accepts', []):
                self.assertEqual(cmd['id'], cmd['id'].upper())
                self.assertNotIn('_', cmd['id'])
                for param in cmd.get('parameters', []):
                    self.assertEqual(param['id'], param['id'].upper())
                    self.assertNotIn('_', param['id'])
                    self.assertEqual(param['editor'], param['editor'].upper())
                    self.assertNotIn('_', param['editor'])

    def test_controller_isy994_uom137_fallback(self):
        mock_poly = MagicMock()
        mock_poly.subscribe = MagicMock()
        mock_poly.Notices = {}
        mock_poly.getNodes.return_value = {}
        mock_poly.getNode.return_value = None
        mock_poly.pg3init = {'isyVersion': '5.3.4'}

        controller = Controller(mock_poly, 'controller', 'controller', 'NuHeat')
        self.assertEqual(controller.time_uom, 137)
        time_drv = [d for d in controller.drivers if d['driver'] == 'TIME'][0]
        self.assertEqual(time_drv['uom'], 137)

        now = int(time.time())
        c_time = controller.get_current_time()
        self.assertAlmostEqual(c_time, now + NTP_EPOCH_OFFSET, delta=2)

        # Thermostat created under this controller
        node = ThermostatNode(mock_poly, 'controller', '99887766', 'Bath', controller=controller)
        self.assertEqual(node.time_uom, 137)
        stat_time_drv = [d for d in node.drivers if d['driver'] == 'TIME'][0]
        self.assertEqual(stat_time_drv['uom'], 137)

    def test_controller_publish_profile(self):
        controller = Controller(self.mock_poly, 'controller', 'controller', 'NuHeat')
        # Case A: poly has updateJsonProfile
        self.mock_poly.updateJsonProfile = MagicMock()
        self.mock_poly.updateProfile = MagicMock()
        controller._publish_profile(wait_response=True)
        self.mock_poly.updateJsonProfile.assert_called_once()
        self.mock_poly.updateProfile.assert_not_called()

        # Case B: poly does NOT have updateJsonProfile
        delattr(self.mock_poly, 'updateJsonProfile')
        controller._last_profile_hash = None
        controller._publish_profile(wait_response=True)
        self.mock_poly.updateProfile.assert_called_once()


if __name__ == '__main__':
    unittest.main()
