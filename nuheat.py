import json
import sys
import time
import requests
import threading

from nodes.base import LOGGER, BaseNode

VERSION = "2.2.5"

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
            self._oauthConfig = {}
            self._oauthConfigOverride = {}
            self._oauthConfigInitialized = False
        def getAccessToken(self):
            return None
        def customNsHandler(self, key, data):
            if key == 'oauth':
                if isinstance(data, dict):
                    self._oauthConfig.update(data)
                self._oauthConfig.update(self._oauthConfigOverride)
                self._oauthConfigInitialized = True
        def updateOauthSettings(self, update):
            self._oauthConfigOverride = update or {}
            self._oauthConfig.update(self._oauthConfigOverride)
        def oauthHandler(self, token):
            pass

from nodes import ThermostatNode
from nodes import ThermostatNode_F
from nodes import ThermostatNode_C
from nodes import EnergyLogDayNode
from nodes import EnergyLogWeekNode
from nodes import EnergyLogYearNode
from nuheat import NuHeat

'''
def _build_profile_definition(temp_unit: str = "F") -> dict:
    """Build the dynamic JSON profile definition for PG3/PG3x.

    CLITEMP supports both temperature UOMs: 'F' -> 17 and 'C' -> 4.
    """
    if temp_unit == "C":
        clitemp_ranges = [
            {"uom": "4", "min": 5, "max": 40, "step": 1, "prec": 0},
            {"uom": "25", "subset": "0,1", "names": {"0": "Schedule", "1": "Permanent Hold"}},
        ]
        clitemp_range_input = [
            {"uom": "4", "min": 5, "max": 40, "step": 1, "prec": 0},
        ]
    else:
        clitemp_ranges = [
            {"uom": "17", "min": 41, "max": 104, "step": 1, "prec": 0},
            {"uom": "25", "subset": "0,1", "names": {"0": "Schedule", "1": "Permanent Hold"}},
        ]
        clitemp_range_input = [
            {"uom": "17", "min": 41, "max": 104, "step": 1, "prec": 0},
        ]

    editors = [
        {
            "id": "bool",
            "ranges": [
                {"uom": "2", "subset": "0-1", "names": {"0": "Offline", "1": "Online"}}
            ],
        },
        {
            "id": "CLIHCS",
            "ranges": [
                {"uom": "66", "subset": "0-1", "names": {"0": "Idle", "1": "Heating"}}
            ],
        },
        {
            "id": "MODE_SEL",
            "ranges": [
                {
                    "uom": "25",
                    "subset": "1,2,3",
                    "names": {
                        "1": "Auto",
                        "2": "Hold",
                        "3": "Permanent Hold",
                    },
                }
            ],
        },
        {
            "id": "CLITEMP",
            "ranges": clitemp_ranges,
        },
        {
            "id": "clitemp_range_input",
            "ranges": clitemp_range_input,
        },
        {
            "id": "CLITEMP_INPUT",
            "ranges": clitemp_range_input,
        },
        {
            "id": "HOLD_TIME",
            "ranges": [
                {"uom": "151", "min": 0, "max": 4294967295, "prec": 0},
                {
                    "uom": "25",
                    "subset": "0,1",
                    "names": {
                        "0": "Schedule",
                        "1": "Permanent Hold",
                    },
                },
            ],
        },
        {
            "id": "HOLD_MINS",
            "ranges": [
                {"uom": "45", "min": 0, "max": 1440, "step": 1, "prec": 0}
            ],
        },
        {
            "id": "TPW",
            "ranges": [
                {"uom": "33", "min": 0, "max": 100000, "prec": 2}
            ],
        },
        {
            "id": "timestamp",
            "ranges": [
                {"uom": "151", "min": 0, "max": 4294967295, "prec": 0}
            ],
        },
    ]

    nodedefs = [
        {
            "id": "controller",
            "name": "NuHeat Signature Controller",
            "icon": "Thermostat",
            "properties": [
                {"id": "ST", "name": "NodeServer Online", "editor": "bool"},
                {"id": "TIME", "name": "Last Update", "editor": "timestamp"},
            ],
            "cmds": {
                "accepts": [
                    {"id": "UPDATE", "name": "Update"},
                ],
                "sends": [
                    {"id": "DON"},
                    {"id": "DOF"},
                ],
            },
            "links": {"ctl": [], "rsp": []},
        },
        {
            "id": "THERMOSTAT",
            "name": "Thermostat Node",
            "icon": "Thermostat",
            "properties": [
                {"id": "ST", "name": "Current Temperature", "editor": "CLITEMP"},
                {"id": "CLISPH", "name": "Heat Setpoint", "editor": "CLITEMP"},
                {"id": "CLIMD", "name": "Mode", "editor": "MODE_SEL"},
                {"id": "CLIHCS", "name": "Heat State", "editor": "CLIHCS"},
                {"id": "GV0", "name": "Daily Energy", "editor": "TPW"},
                {"id": "GV1", "name": "Last 7 Days Energy", "editor": "TPW"},
                {"id": "GV2", "name": "Monthly Energy", "editor": "TPW"},
                {"id": "GV3", "name": "Yearly Energy", "editor": "TPW"},
                {"id": "GV4", "name": "Hold End Time", "editor": "HOLD_TIME"},
                {"id": "GV5", "name": "Online", "editor": "bool"},
                {"id": "TIME", "name": "Last Update", "editor": "timestamp"},
            ],
            "cmds": {
                "accepts": [
                    {"id": "UPDATE", "name": "Force Update"},
                    {"id": "SET_AUTO", "name": "Set Auto"},
                    {
                        "id": "SET_HOLD",
                        "name": "Set Hold",
                        "parameters": [
                            {"id": "temp", "name": "Temperature", "editor": "clitemp_range_input", "init": "CLISPH"},
                            {"id": "hold", "name": "Hold Minutes", "editor": "HOLD_MINS"},
                        ],
                    },
                    {
                        "id": "SET_PERM_HOLD",
                        "name": "Set Permanent Hold",
                        "parameters": [
                            {"id": "temp", "name": "Temperature", "editor": "clitemp_range_input", "init": "CLISPH"},
                        ],
                    },
                ],
                "sends": [],
            },
            "links": {"ctl": [], "rsp": []},
        },
    ]

    return {
        "delete": {
            "editors": ["*"],
            "nodedefs": ["*"],
            "linkdefs": ["*"],
        },
        "editors": editors,
        "nodedefs": nodedefs,
        "linkdefs": [],
    }

'''
class Controller(BaseNode):
    id = 'controller'
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary='controller', address='controller', name='NuHeat'):
        super(Controller, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = name
        self.customParams = Custom(polyglot, 'customparams')
        self.Notices = getattr(polyglot, 'Notices', {})
        self.oauth = OAuth(polyglot)
        # Pre-register NuHeat OAuth endpoints so they are never missing in udi_interface.OAuth
        oauth_defaults = {
            'name': 'Nuheat',
            'auth_endpoint': 'https://identity.mynuheat.com/connect/authorize',
            'token_endpoint': 'https://identity.mynuheat.com/connect/token',
            'scope': 'openapi openid profile offline_access',
            'addScope': True,
            'addRedirect': True
        }
        if hasattr(self.oauth, 'updateOauthSettings'):
            self.oauth.updateOauthSettings(oauth_defaults)

        self.NuHeat = NuHeat(token_or_provider=self.get_access_token)
        self.temperature_scale = None
        self.temp_unit = "F"
        self.temp_uom = 17
        self.tz = "America/New_York"
        self.disco = 0

        self.client_id = None
        self.client_secret = None
        self.oauthReady = False
        self.hb_state = 0

        # Confirmation tracking
        self._confirmed_node_addresses = set()
        self._deleted_node_addresses = set()
        self._node_confirmed_events = {}
        self._node_deleted_events = {}
        self.temp_unit_ready = False

        # Thread synchronization flags
        self.customParam_done = False
        self.handleCustomParamsDone = False
        self.customNsDone = False
        self.customNsHandlerDone = False
        self.config_done = False
        self.configDone = False
        self.oauth_lock = threading.Lock()

        if hasattr(self.poly, 'addNode'):
            self.poly.addNode(self)

        # Subscribe to PG3 events if the interface supports event subscriptions
        if hasattr(self.poly, 'subscribe'):
            self.poly.subscribe(self.poly.START, self.start, address)
            self.poly.subscribe(self.poly.POLL, self.poll)
            self.poly.subscribe(self.poly.CUSTOMNS, self.customNsHandler)
            self.poly.subscribe(self.poly.OAUTH, self.oauthHandler)
            self.poly.subscribe(self.poly.CUSTOMPARAMS, self.customParamsHandler)
            if hasattr(self.poly, 'CONFIGDONE'):
                self.poly.subscribe(self.poly.CONFIGDONE, self.configDoneHandler)
            if hasattr(self.poly, 'ADDNODEDONE'):
                self.poly.subscribe(self.poly.ADDNODEDONE, self.node_done)
            if hasattr(self.poly, 'DELNODEDONE'):
                self.poly.subscribe(self.poly.DELNODEDONE, self.node_deleted)
            self.poly.subscribe(self.poly.DISCOVER, self.discover)

    def node_done(self, node):
        address = getattr(node, "address", None)
        if address is None and isinstance(node, dict):
            address = node.get("address") or node.get("node")
        if address:
            self._confirmed_node_addresses.add(address)
            evt = self._node_confirmed_events.get(address)
            if evt:
                evt.set()
        LOGGER.debug(f"[node_done] Node {address or 'unknown'} is done")

    def node_deleted(self, node):
        address = getattr(node, "address", None)
        if address is None and isinstance(node, dict):
            address = node.get("address") or node.get("node")
        if address:
            self._deleted_node_addresses.add(address)
            self._confirmed_node_addresses.discard(address)
            evt = self._node_deleted_events.get(address)
            if evt:
                evt.set()
        LOGGER.debug(f"[node_deleted] Node {address or 'unknown'} deletion complete")

    def _wait_for_node_confirmed(self, address: str, timeout: float = 10.0) -> bool:
        """Block until PG3 sends ADDNODEDONE for *address*, or timeout expires."""
        if address in self._confirmed_node_addresses:
            LOGGER.debug(f"[_wait_for_node_confirmed] Node {address} already confirmed")
            return True

        if not hasattr(self.poly, 'subscribe') or not hasattr(self.poly, 'ADDNODEDONE'):
            return True

        evt = self._node_confirmed_events.setdefault(address, threading.Event())
        if address in self._confirmed_node_addresses:
            return True

        confirmed = evt.wait(timeout=timeout)
        if not confirmed:
            LOGGER.warning(f"[_wait_for_node_confirmed] Timeout waiting for PG3 to confirm node {address}")
        else:
            LOGGER.debug(f"[_wait_for_node_confirmed] PG3 confirmed node {address}")
        return confirmed

    def _wait_for_node_deleted(self, address: str, timeout: float = 5.0) -> bool:
        """Block until PG3 sends DELNODEDONE for *address*, or timeout expires."""
        if address in self._deleted_node_addresses:
            LOGGER.debug(f"[_wait_for_node_deleted] Node {address} already deleted")
            return True

        if not hasattr(self.poly, 'subscribe') or not hasattr(self.poly, 'DELNODEDONE'):
            return True

        evt = self._node_deleted_events.setdefault(address, threading.Event())
        if address in self._deleted_node_addresses:
            return True

        deleted = evt.wait(timeout=timeout)
        if not deleted:
            LOGGER.warning(f"[_wait_for_node_deleted] Timeout waiting for PG3 to confirm deletion of node {address}")
        else:
            LOGGER.debug(f"[_wait_for_node_deleted] PG3 confirmed node {address} deleted")
        return deleted

    def update_profile(self) -> None:
        """Update ISY profile using static profile files in profile/."""
        if hasattr(self.poly, "updateProfile"):
            try:
                LOGGER.info("Updating profile from static profile directory...")
                self.poly.updateProfile()
                if hasattr(self.poly, "Notices") and hasattr(self.poly.Notices, "delete"):
                    self.poly.Notices.delete("profile")
            except Exception as err:
                LOGGER.error(f"Static profile update failed: {err}")
                if hasattr(self.poly, "Notices") and hasattr(self.poly.Notices, "__setitem__"):
                    self.poly.Notices["profile"] = f"Profile update failed: {err}"

    def _publish_profile(self, wait_response: bool = False) -> None:
        """Backwards compatibility alias for update_profile."""
        self.update_profile()

    def _determine_temp_unit(self) -> str:
        """Determine temperature scale ('F' or 'C') from customParams or NuHeat account API."""
        configured_unit = self.get_configured_temp_unit()
        if configured_unit:
            self.temp_unit = configured_unit
            self.temp_uom = 4 if configured_unit == 'C' else 17
            self.temp_unit_ready = True
        else:
            token = self.get_access_token()
            if token:
                try:
                    account_info = self.NuHeat.get_account()
                    if account_info:
                        self.temperature_scale = account_info.get('temperatureScale', 'Fahrenheit')
                        if str(self.temperature_scale).lower().startswith('c'):
                            self.temp_unit = "C"
                            self.temp_uom = 4
                        else:
                            self.temp_unit = "F"
                            self.temp_uom = 17
                        self.temp_unit_ready = True
                except Exception as e:
                    LOGGER.warning(f"Could not retrieve NuHeat account temperature scale: {e}")
            if not self.temp_unit_ready:
                self.temp_unit = "F"
                self.temp_uom = 17
                self.temp_unit_ready = True
        LOGGER.info(f"Temperature unit determined: {self.temp_unit} (UOM {self.temp_uom})")
        return self.temp_unit

    def get_access_token(self):
        try:
            return self.oauth.getAccessToken()
        except (ValueError, KeyError, AttributeError) as e:
            LOGGER.debug(f"NuHeat getAccessToken: {e}")
            return None

    def is_oauth_configured(self):
        oauth_cfg = getattr(self.oauth, '_oauthConfig', {})
        override = getattr(self.oauth, '_oauthConfigOverride', {})
        client_id = self.client_id or (oauth_cfg.get('client_id') if hasattr(oauth_cfg, 'get') else None) or (override.get('client_id') if hasattr(override, 'get') else None)
        client_secret = self.client_secret or (oauth_cfg.get('client_secret') if hasattr(oauth_cfg, 'get') else None) or (override.get('client_secret') if hasattr(override, 'get') else None)
        return bool(client_id and client_secret)

    def update_oauth_config(self):
        """Updates OAuth settings if credentials were provided in customParams, customNs, or controller attributes."""
        with self.oauth_lock:
            client_id = self.client_id or self.customParams.get('clientId') or self.customParams.get('client_id')
            client_secret = self.client_secret or self.customParams.get('clientSecret') or self.customParams.get('client_secret')
            if client_id and client_secret:
                self.client_id = client_id
                self.client_secret = client_secret
                self.oauthReady = True
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
                if hasattr(self.oauth, 'updateOauthSettings'):
                    self.oauth.updateOauthSettings(oauth_cfg)
                # If customNsHandler('oauth') hasn't initialized _oauthConfig, initialize it now
                if hasattr(self.oauth, '_oauthConfigInitialized') and not self.oauth._oauthConfigInitialized:
                    if hasattr(self.oauth, 'customNsHandler'):
                        self.oauth.customNsHandler('oauth', {})
                if hasattr(self.Notices, 'delete'):
                    self.Notices.delete('oauth_creds')

    def customNsHandler(self, key, data):
        LOGGER.debug(f"customNsHandler called for {key}: {data}")
        try:
            # Polyglot sends empty customns values as empty strings ('') instead of dicts
            if isinstance(data, str) or not isinstance(data, dict):
                data = {}

            if key == 'oauth':
                # Check if credentials exist in customparams or controller attributes
                self.update_oauth_config()

                # Extract credentials if PG3 OAuth setup provided them in data
                client_id = data.get('client_id') or data.get('clientId') or self.client_id
                client_secret = data.get('client_secret') or data.get('clientSecret') or self.client_secret
                if client_id:
                    self.client_id = client_id
                if client_secret:
                    self.client_secret = client_secret

                override = getattr(self.oauth, '_oauthConfigOverride', {})
                has_client = bool(self.client_id or (isinstance(override, dict) and override.get('client_id')))
                has_secret = bool(self.client_secret or (isinstance(override, dict) and override.get('client_secret')))

                # If PG3 sends empty oauth data and no credentials have been configured yet,
                # do not pass empty data to self.oauth to avoid spurious error logs from udi_interface
                if not (has_client and has_secret):
                    LOGGER.info("OAuth configuration is pending credentials in PG3 configuration.")
                    self.customNsDone = True
                    self.customNsHandlerDone = True
                    return

                # If credentials are present, update oauth override and delegate to udi_interface.OAuth
                oauth_cfg = {
                    'name': 'Nuheat',
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'auth_endpoint': 'https://identity.mynuheat.com/connect/authorize',
                    'token_endpoint': 'https://identity.mynuheat.com/connect/token',
                    'scope': 'openapi openid profile offline_access',
                    'addScope': True,
                    'addRedirect': True
                }
                if hasattr(self.oauth, 'updateOauthSettings'):
                    self.oauth.updateOauthSettings(oauth_cfg)

                if hasattr(self.oauth, 'customNsHandler'):
                    self.oauth.customNsHandler(key, data)

                self.oauthReady = True
                LOGGER.debug("OAuth configuration automatically populated from PG3 OAuth setup")

            elif key == 'oauthTokens':
                if hasattr(self.oauth, 'customNsHandler'):
                    self.oauth.customNsHandler(key, data)

            if key in ('oauth', 'oauthTokens'):
                self.customNsDone = True
                self.customNsHandlerDone = True
            LOGGER.debug(f"customNsHandler finished for {key}")
        except Exception as e:
            LOGGER.error(f"Error handling customNs {key}: {e}")

    def configDoneHandler(self):
        LOGGER.info("configDoneHandler: PG3 initial configuration messages complete.")
        self.configDone = True
        self.config_done = True

    def oauthHandler(self, token):
        try:
            wait_seconds = 0
            while not (self.customParam_done or self.handleCustomParamsDone) and wait_seconds < 5:
                time.sleep(0.5)
                wait_seconds += 0.5

            self.oauth.oauthHandler(token)
            if hasattr(self.Notices, 'delete'):
                self.Notices.delete('auth')
            LOGGER.info("NuHeat OAuth token received successfully!")
            self.discover()
        except Exception as e:
            LOGGER.error(f"Error in oauthHandler: {e}")

    def get_configured_temp_unit(self):
        """Returns 'C', 'F', or None if not configured in customParams."""
        for key in ('temp_unit', 'temp_unt', 'TEMP_UNIT', 'TEMP_UNT'):
            if key in self.customParams:
                val = self.customParams[key]
                if val:
                    raw = str(val).strip().upper()
                    if raw.startswith('C'):
                        return 'C'
                    elif raw.startswith('F'):
                        return 'F'

        rawdata = getattr(self.customParams, '_rawdata', None)
        if isinstance(rawdata, dict):
            for key, val in rawdata.items():
                if key.lower() in ('temp_unit', 'temp_unt'):
                    raw = str(val).strip().upper()
                    if raw.startswith('C'):
                        return 'C'
                    elif raw.startswith('F'):
                        return 'F'
        return None

    def customParamsHandler(self, data):
        LOGGER.debug(f"customParamsHandler called with {len(data) if hasattr(data, '__len__') else 'unknown'} params")
        self.customParams.load(data)
        if 'tz' in self.customParams and self.customParams['tz']:
            self.tz = self.customParams['tz']
        else:
            self.tz = "America/New_York"
            self.customParams['tz'] = self.tz

        prev_temp_unit = self.temp_unit
        configured_unit = self.get_configured_temp_unit()
        if configured_unit:
            self.temp_unit = configured_unit
            self.temp_uom = 4 if configured_unit == 'C' else 17
            self.temp_unit_ready = True
        else:
            # Pre-populate temp_unit so it displays in PG3 Custom Configuration Parameters
            self.customParams['temp_unit'] = 'F'
            self.temp_unit = 'F'
            self.temp_uom = 17
            self.temp_unit_ready = True

        if self.temp_unit != prev_temp_unit:
            self.update_profile()
            if self.disco == 1:
                LOGGER.info(f"Temperature unit changed from {prev_temp_unit} to {self.temp_unit}; re-discovering nodes...")
                self.discover()
            else:
                get_nodes = getattr(self.poly, 'getNodes', None)
                nodes = get_nodes() if callable(get_nodes) else getattr(self, 'nodes', {})
                nodes_iterable = nodes.values() if isinstance(nodes, dict) else nodes
                for node in nodes_iterable:
                    if hasattr(node, 'temp_uom'):
                        node.temp_uom = self.temp_uom
                        if hasattr(node, 'update_info'):
                            node.update_info()
                        if hasattr(node, 'update_energy'):
                            node.update_energy()

        self.update_oauth_config()
        self.handleCustomParamsDone = True
        self.customParam_done = True
        LOGGER.debug(f"customParamsHandler finished: tz={self.tz}, temp_unit={self.temp_unit} (uom {self.temp_uom})")

    def start(self):
        LOGGER.info('Starting NuHeat NodeServer...')

        # In PG3 multi-threaded startup, ensure customParams, customNS, and config are handled before starting
        wait_seconds = 0
        max_wait = 15
        while not (self.customParam_done and self.customNsDone and self.config_done and self.oauthReady) and wait_seconds < max_wait:
            LOGGER.info(
                f"Waiting for node to initialize: customParams={self.customParam_done}, "
                f"customNS={self.customNsDone}, configDone={self.config_done}, oauthReady={self.oauthReady} ({wait_seconds}s)"
            )
            time.sleep(1)
            wait_seconds += 1

        self.update_oauth_config()
        self.setDriver('ST', 1, uom=2)
        self.setDriver('TIME', int(time.time()), uom=151)
        self.update_profile()

        if not self.is_oauth_configured():
            LOGGER.warning("NuHeat OAuth credentials (clientId & clientSecret) are missing. Please configure them in PG3.")
            if hasattr(self.Notices, '__setitem__'):
                self.Notices['oauth_creds'] = "OAuth credentials required: Please configure 'clientId' and 'clientSecret' in Custom Configuration Parameters."
        else:
            if hasattr(self.Notices, 'delete'):
                self.Notices.delete('oauth_creds')

        token = self.get_access_token()
        if token:
            if hasattr(self.Notices, 'delete'):
                self.Notices.delete('auth')
            # Wait to determine temperature unit before creating nodes
            self._determine_temp_unit()
            self.discover()
            self.longPoll()
        else:
            LOGGER.warning("NuHeat is not authenticated. Please click 'Authenticate' in the PG3 dashboard.")
            if hasattr(self.Notices, '__setitem__'):
                self.Notices['auth'] = "Please click 'Authenticate' in the PG3 dashboard to link your NuHeat account."

    def poll(self, polltype):
        self.setDriver('TIME', int(time.time()), uom=151)
        if 'shortPoll' in polltype:
            self.shortPoll()
        elif 'longPoll' in polltype:
            self.longPoll()

    def heartbeat(self):
        """Toggle DON / DOF command to indicate node server heartbeat."""
        if self.hb_state == 0:
            self.hb_state = 1
            if hasattr(self, 'reportCmd'):
                self.reportCmd('DON')
        else:
            self.hb_state = 0
            if hasattr(self, 'reportCmd'):
                self.reportCmd('DOF')

    def shortPoll(self):
        self.heartbeat()
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
                if getattr(node, 'address', None) != self.address:
                    if hasattr(node, 'update_info'):
                        node.update_info()
                    if hasattr(node, 'update_energy'):
                        node.update_energy()

    def discover(self, *args, **kwargs):
        token = self.get_access_token()
        if not token:
            LOGGER.warning("Discover aborted: NuHeat is not authenticated.")
            if hasattr(self.Notices, '__setitem__'):
                self.Notices['auth'] = "Please click 'Authenticate' in the PG3 dashboard to link your NuHeat account."
            return

        if hasattr(self.Notices, 'delete'):
            self.Notices.delete('auth')

        # Wait and ensure temperature unit is resolved before creating nodes
        self._determine_temp_unit()

        thermostats = self.NuHeat.get_thermostat()
        if not thermostats:
            LOGGER.warning("No thermostats found or error retrieving thermostats.")
            return

        if isinstance(thermostats, dict):
            thermostats = [thermostats]

        target_node_cls = ThermostatNode_C if self.temp_unit == 'C' else ThermostatNode_F
        target_node_id = target_node_cls.id

        add_node = getattr(self.poly, 'addNode', getattr(self, 'addNode', None))
        if not callable(add_node):
            return

        for stat in thermostats:
            stat_address = str(stat['serialNumber'])
            name = stat.get('name') or f"NuHeat {stat_address}"
            energy_log_day_address = "eld" + stat_address
            energy_log_week_address = "elw" + stat_address
            energy_log_year_address = "ely" + stat_address

            # Check existing node
            existing_node = None
            if hasattr(self.poly, '_nodes') and isinstance(self.poly._nodes, dict):
                existing_node = self.poly._nodes.get(stat_address)
            if existing_node is None and hasattr(self.poly, 'getNode'):
                existing_node = self.poly.getNode(stat_address)
            elif existing_node is None and hasattr(self, 'nodes') and isinstance(self.nodes, dict):
                existing_node = self.nodes.get(stat_address)

            needs_deletion = False
            if existing_node is not None:
                current_primary = None
                if isinstance(existing_node, dict):
                    current_primary = existing_node.get('primaryNode') or existing_node.get('primary')
                    existing_id = existing_node.get('nodeDefId') or existing_node.get('id')
                else:
                    current_primary = getattr(existing_node, 'primary', None) or getattr(existing_node, 'primaryNode', None)
                    existing_id = getattr(existing_node, 'id', None)

                if (current_primary and current_primary != stat_address) or (existing_id and existing_id != target_node_id):
                    LOGGER.info(
                        f"Node {stat_address} requires recreation (existing id={existing_id}, target={target_node_id}, "
                        f"primary={current_primary}). Deleting before recreation..."
                    )
                    needs_deletion = True

            if needs_deletion and hasattr(self.poly, 'delNode'):
                self._confirmed_node_addresses.discard(stat_address)
                self.poly.delNode(stat_address)
                self._wait_for_node_deleted(stat_address, timeout=5.0)

            stat_node = target_node_cls(self.poly, stat_address, stat_address, name, self, temp_uom=self.temp_uom)
            LOGGER.info(f"Adding thermostat node {stat_address} ({name}) as {stat_node.id}...")
            add_node(stat_node)

            # Wait for PG3 confirmation of this node serially (1 by 1)
            confirmed = self._wait_for_node_confirmed(stat_address, timeout=10.0)
            if not confirmed:
                LOGGER.warning(f"Timeout waiting for PG3 confirmation of node {stat_address}; proceeding.")

            try:
                stat_node.update_info()
                stat_node.update_energy()
            except Exception as e:
                LOGGER.error(f"Error updating thermostat {stat_address} on discovery: {e}")

            # Clean up any legacy energy child nodes from previous versions
            for child_addr in (energy_log_day_address, energy_log_week_address, energy_log_year_address):
                legacy_child = None
                if hasattr(self.poly, '_nodes') and isinstance(self.poly._nodes, dict):
                    legacy_child = self.poly._nodes.get(child_addr)
                if legacy_child is None and hasattr(self.poly, 'getNode'):
                    legacy_child = self.poly.getNode(child_addr)
                elif legacy_child is None and hasattr(self, 'nodes') and isinstance(self.nodes, dict):
                    legacy_child = self.nodes.get(child_addr)

                if legacy_child is not None:
                    LOGGER.info(f"Removing legacy child node {child_addr} from PG3...")
                    if hasattr(self.poly, 'delNode'):
                        self.poly.delNode(child_addr)
                        self._wait_for_node_deleted(child_addr, timeout=3.0)

        self.disco = 1

    def update_nodes(self, command=None):
        """Forces an immediate update across all nodes (executes longPoll)."""
        LOGGER.info('Forcing update across all nodes...')
        self.setDriver('TIME', int(time.time()), uom=151)
        self.longPoll()
        return True

    commands = {
        'UPDATE': update_nodes,
    }


if __name__ == "__main__":
    try:
        LOGGER.info(f'Starting NuHeat Polyglot interface v{VERSION}...')

        polyglot = udi_interface.Interface([])
        polyglot.start(VERSION)
        if hasattr(polyglot, 'setCustomParamsDoc'):
            polyglot.setCustomParamsDoc()
        control = Controller(polyglot, 'controller', 'controller', 'NuHeat')
        polyglot.ready()
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
