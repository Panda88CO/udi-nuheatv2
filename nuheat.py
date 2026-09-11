#!/usr/bin/env python3
import sys
import time
import requests

from nodes.base import LOGGER, BaseNode

try:
    import udi_interface
    Custom = udi_interface.Custom
    OAuth = udi_interface.OAuth

except ImportError:

    class Custom:
        def __init__(self, *args, **kwargs):
            self._data = {}
        def load(self, data):
            self._data = data or {}
        def get(self, key, default=None):
            return self._data.get(key, default)
        def __getitem__(self, item):
            return self._data[item]
        def __setitem__(self, key, value):
            self._data[key] = value
        def __contains__(self, item):
            return item in self._data

    class OAuth:
        def __init__(self, *args, **kwargs):
            pass
        def getAccessToken(self):
            return None
        def customNsHandler(self, key, data):
            pass
        def oauthHandler(self, token):
            pass

from nodes import ThermostatNode_F
from nodes import ThermostatNode_C
from nodes import EnergyLogDayNode
from nodes import EnergyLogWeekNode
from nodes import EnergyLogYearNode
from nuheat import NuHeat


class Controller(BaseNode):
    id = 'controller'
    drivers = [{'driver': 'ST', 'value': 1, 'uom': 2}]

    def __init__(self, polyglot, primary='controller', address='controller', name='NuHeat'):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = name
        self.customParams = Custom(polyglot, 'customparams')
        self.Notices = getattr(polyglot, 'Notices', {})
        self.oauth = OAuth(polyglot)
        self.NuHeat = NuHeat(token_or_provider=self.get_access_token)
        self.temperature_scale = None
        self.temp_uom = 17
        self.tz = "America/New_York"
        self.disco = 0

        # Subscribe to PG3 events if the interface supports event subscriptions
        if hasattr(self.poly, 'subscribe'):
            self.poly.subscribe(self.poly.START, self.start, address)
            self.poly.subscribe(self.poly.POLL, self.poll)
            self.poly.subscribe(self.poly.CUSTOMNS, self.customNsHandler)
            self.poly.subscribe(self.poly.OAUTH, self.oauthHandler)
            self.poly.subscribe(self.poly.CUSTOMPARAMS, self.customParamsHandler)
            self.poly.subscribe(self.poly.DISCOVER, self.discover)

    def get_access_token(self):
        try:
            return self.oauth.getAccessToken()
        except (ValueError, KeyError, AttributeError) as e:
            LOGGER.debug(f"NuHeat getAccessToken: {e}")
            return None

    def customNsHandler(self, key, data):
        try:
            self.oauth.customNsHandler(key, data)
        except Exception as e:
            LOGGER.error(f"Error handling customNs {key}: {e}")

    def oauthHandler(self, token):
        try:
            self.oauth.oauthHandler(token)
            if hasattr(self.Notices, 'delete'):
                self.Notices.delete('auth')
            LOGGER.info("NuHeat OAuth token received successfully!")
            self.discover()
        except Exception as e:
            LOGGER.error(f"Error in oauthHandler: {e}")

    def customParamsHandler(self, data):
        self.customParams.load(data)
        if 'tz' in self.customParams and self.customParams['tz']:
            self.tz = self.customParams['tz']
        else:
            self.tz = "America/New_York"
            self.customParams['tz'] = self.tz

        client_id = self.customParams.get('clientId') or self.customParams.get('client_id')
        client_secret = self.customParams.get('clientSecret') or self.customParams.get('client_secret')
        if client_id and client_secret:
            oauth_cfg = {
                'name': 'Nuheat',
                'client_id': client_id,
                'client_secret': client_secret,
                'auth_endpoint': 'https://identity.mynuheat.com/connect/authorize',
                'token_endpoint': 'https://identity.mynuheat.com/connect/token',
                'scope': 'openapi openid profile offline_access',
                'addScope': True,
                'addRedirect': True
            }
            self.oauth.customNsHandler('oauth', oauth_cfg)

    def start(self):
        LOGGER.info('Starting NuHeat NodeServer...')
        self.setDriver('ST', 1)
        if hasattr(self.poly, 'updateProfile'):
            self.poly.updateProfile()

        token = self.get_access_token()
        if token:
            if hasattr(self.Notices, 'delete'):
                self.Notices.delete('auth')
            self.discover()
        else:
            LOGGER.warning("NuHeat is not authenticated. Please click 'Authenticate' in the PG3 dashboard.")
            if hasattr(self.Notices, '__setitem__'):
                self.Notices['auth'] = "Please click 'Authenticate' in the PG3 dashboard to link your NuHeat account."

    def poll(self, polltype):
        if 'shortPoll' in polltype:
            self.shortPoll()
        elif 'longPoll' in polltype:
            self.longPoll()

    def shortPoll(self):
        if self.disco == 1:
            get_nodes = getattr(self.poly, 'getNodes', None)
            nodes = get_nodes() if callable(get_nodes) else getattr(self, 'nodes', {})
            nodes_iterable = nodes.values() if isinstance(nodes, dict) else nodes
            for node in nodes_iterable:
                if getattr(node, 'address', None) != self.address and hasattr(node, 'update_info'):
                    node.update_info()

    def longPoll(self):
        if self.disco == 1:
            get_nodes = getattr(self.poly, 'getNodes', None)
            nodes = get_nodes() if callable(get_nodes) else getattr(self, 'nodes', {})
            nodes_iterable = nodes.values() if isinstance(nodes, dict) else nodes
            for node in nodes_iterable:
                if getattr(node, 'address', None) != self.address and hasattr(node, 'update_info'):
                    node.update_info()

    def query(self, command=None):
        self.reportDrivers()
        get_nodes = getattr(self.poly, 'getNodes', None)
        nodes = get_nodes() if callable(get_nodes) else getattr(self, 'nodes', {})
        nodes_iterable = nodes.values() if isinstance(nodes, dict) else nodes
        for node in nodes_iterable:
            if hasattr(node, 'reportDrivers'):
                node.reportDrivers()

    def discover(self, *args, **kwargs):
        token = self.get_access_token()
        if not token:
            LOGGER.warning("Discover aborted: NuHeat is not authenticated.")
            if hasattr(self.Notices, '__setitem__'):
                self.Notices['auth'] = "Please click 'Authenticate' in the PG3 dashboard to link your NuHeat account."
            return

        if hasattr(self.Notices, 'delete'):
            self.Notices.delete('auth')

        account_info = self.NuHeat.get_account()
        if account_info:
            self.temperature_scale = account_info.get('temperatureScale', 'Fahrenheit')
            self.temp_uom = 17 if self.temperature_scale == "Fahrenheit" else 4
        else:
            self.temp_uom = 17

        thermostats = self.NuHeat.get_thermostat()
        if not thermostats:
            LOGGER.warning("No thermostats found or error retrieving thermostats.")
            return

        if isinstance(thermostats, dict):
            thermostats = [thermostats]

        for stat in thermostats:
            stat_address = str(stat['serialNumber'])
            name = stat.get('name') or f"NuHeat {stat_address}"
            energy_log_day_address = "eld" + stat_address
            energy_log_week_address = "elw" + stat_address
            energy_log_year_address = "ely" + stat_address

            add_node = getattr(self.poly, 'addNode', getattr(self, 'addNode', None))
            if not callable(add_node):
                continue

            if self.temp_uom == 17:
                add_node(ThermostatNode_F(self.poly, self.address, stat_address, name, self))
            else:
                add_node(ThermostatNode_C(self.poly, self.address, stat_address, name, self))

            time.sleep(0.5)
            add_node(EnergyLogDayNode(self.poly, stat_address, energy_log_day_address, f"{name} Energy-Day", self))
            time.sleep(0.5)
            add_node(EnergyLogWeekNode(self.poly, stat_address, energy_log_week_address, f"{name} Energy-Week", self))
            time.sleep(0.5)
            add_node(EnergyLogYearNode(self.poly, stat_address, energy_log_year_address, f"{name} Energy-Year", self))
            time.sleep(0.5)

        self.disco = 1

    def update_profile(self, command=None):
        LOGGER.info('Installing / Updating profile...')
        if hasattr(self.poly, 'updateProfile'):
            return self.poly.updateProfile()
        elif hasattr(self.poly, 'installprofile'):
            return self.poly.installprofile()
        return True

    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile
    }


if __name__ == "__main__":
    try:
        LOGGER.info('Starting NuHeat Polyglot interface...')

        polyglot = udi_interface.Interface([])
        polyglot.start('2.0.2')
        control = Controller(polyglot, 'controller', 'controller', 'NuHeat')
        polyglot.ready()
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
