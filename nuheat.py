import json
import sys
import time
import requests
import threading

from nodes.base import LOGGER, BaseNode

VERSION = "2.1.0"

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


def _build_profile_definition(temp_unit: str = "F") -> dict:
    """Build the dynamic JSON profile definition for PG3/PG3x.

    CLITEMP supports both temperature UOMs: 'F' -> 17 and 'C' -> 4.
    """
    if temp_unit == "C":
        clitemp_ranges = [
            {"uom": "4", "min": 5, "max": 40, "step": 1, "prec": 0},
            {"uom": "17", "min": 41, "max": 104, "step": 1, "prec": 0},
        ]
    else:
        clitemp_ranges = [
            {"uom": "17", "min": 41, "max": 104, "step": 1, "prec": 0},
            {"uom": "4", "min": 5, "max": 40, "step": 1, "prec": 0},
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
            "id": "CLIMD",
            "ranges": [
                {"uom": "67", "subset": "1,3", "names": {"1": "Heat / Manual", "3": "Auto / Schedule"}}
            ],
        },
        {
            "id": "CLITEMP",
            "ranges": clitemp_ranges,
        },
        {
            "id": "TPW",
            "ranges": [
                {"uom": "33", "min": 0, "max": 10000, "prec": 2}
            ],
        },
        {
            "id": "GV0",
            "ranges": [
                {"uom": "45", "min": 0, "max": 43830, "prec": 0}
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
                    {"id": "QUERY", "name": "Query"},
                    {"id": "DISCOVER", "name": "Discover"},
                    {"id": "UPDATE_PROFILE", "name": "Update Profile"},
                ],
                "sends": [],
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
                {"id": "CLIMD", "name": "Thermostat Mode", "editor": "CLIMD"},
                {"id": "CLIHCS", "name": "Heat State", "editor": "CLIHCS"},
                {"id": "TIME", "name": "Last Update", "editor": "timestamp"},
            ],
            "cmds": {
                "accepts": [
                    {"id": "QUERY", "name": "Query"},
                    {
                        "id": "CLISPH",
                        "name": "Heat Setpoint",
                        "params": [
                            {"id": "", "name": "Temperature", "editor": "CLITEMP", "init": "CLISPH"}
                        ],
                    },
                ],
                "sends": [],
            },
            "links": {"ctl": [], "rsp": []},
        },
        {
            "id": "ENERGYLOG",
            "name": "Energy Log Node",
            "icon": "EnergyMonitor",
            "properties": [
                {"id": "ST", "name": "Energy Used", "editor": "TPW"},
                {"id": "GV0", "name": "Energy Minutes", "editor": "GV0"},
                {"id": "TIME", "name": "Last Update", "editor": "timestamp"},
            ],
            "cmds": {
                "accepts": [
                    {"id": "QUERY", "name": "Query"},
                ],
                "sends": [],
            },
            "links": {"ctl": [], "rsp": []},
        },
    ]

    return {"editors": editors, "nodedefs": nodedefs, "linkdefs": []}


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
        self.portalData = Custom(polyglot, 'customNSdata')
        self.Notices = getattr(polyglot, 'Notices', {})
        self.oauth = OAuth(polyglot)
        self.NuHeat = NuHeat(token_or_provider=self.get_access_token)
        self.temperature_scale = None
        self.temp_unit = "F"
        self.temp_uom = 17
        self.tz = "America/New_York"
        self.disco = 0

        self.client_id = None
        self.client_secret = None
        self.portalID = None
        self.portalSecret = None
        self.portalReady = False

        # Confirmation tracking
        self._confirmed_node_addresses = set()
        self._deleted_node_addresses = set()

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
        LOGGER.debug(f"[node_done] Node {address or 'unknown'} is done")

    def node_deleted(self, node):
        address = getattr(node, "address", None)
        if address is None and isinstance(node, dict):
            address = node.get("address") or node.get("node")
        if address:
            self._deleted_node_addresses.add(address)
            self._confirmed_node_addresses.discard(address)
        LOGGER.debug(f"[node_deleted] Node {address or 'unknown'} deletion complete")

    def _wait_for_node_confirmed(self, address: str, timeout: float = 10.0) -> bool:
        """Block until PG3 sends ADDNODEDONE for *address*, or timeout expires."""
        if address in self._confirmed_node_addresses:
            LOGGER.debug(f"[_wait_for_node_confirmed] Node {address} already confirmed")
            return True

        event = threading.Event()

        def _handler(node):
            node_addr = getattr(node, "address", None)
            if node_addr is None and isinstance(node, dict):
                node_addr = node.get("address") or node.get("node")
            if node_addr == address:
                event.set()

        if hasattr(self.poly, 'subscribe') and hasattr(self.poly, 'ADDNODEDONE'):
            self.poly.subscribe(self.poly.ADDNODEDONE, _handler)
            if address in self._confirmed_node_addresses:
                if hasattr(self.poly, 'unsubscribe'):
                    self.poly.unsubscribe(self.poly.ADDNODEDONE, _handler)
                LOGGER.debug(f"[_wait_for_node_confirmed] Node {address} confirmed before local wait")
                return True
            confirmed = event.wait(timeout=timeout)
            if hasattr(self.poly, 'unsubscribe'):
                self.poly.unsubscribe(self.poly.ADDNODEDONE, _handler)
            if not confirmed:
                LOGGER.warning(f"[_wait_for_node_confirmed] Timeout waiting for PG3 to confirm node {address}")
            else:
                LOGGER.debug(f"[_wait_for_node_confirmed] PG3 confirmed node {address}")
            return confirmed
        return True

    def _profiles_match(self, current_profile, expected_profile) -> bool:
        if not isinstance(current_profile, dict) or not isinstance(expected_profile, dict):
            return False
        return all(
            current_profile.get(k, []) == expected_profile.get(k, [])
            for k in ("editors", "nodedefs", "linkdefs")
        )

    def _publish_profile(self, wait_response: bool = False) -> None:
        update_json_profile = getattr(self.poly, "updateJsonProfile", None)
        if not callable(update_json_profile):
            LOGGER.info("[_publish_profile] updateJsonProfile is unavailable, falling back to updateProfile")
            if hasattr(self.poly, "updateProfile"):
                self.poly.updateProfile()
            return

        profile = _build_profile_definition(self.temp_unit)

        current_profile_getter = getattr(self.poly, "getJsonProfile", None)
        if callable(current_profile_getter):
            try:
                current_profile = current_profile_getter({"waitResponse": False})
                if self._profiles_match(current_profile, profile):
                    LOGGER.info("[_publish_profile] Profile already up to date, skipping publish")
                    return
            except TypeError:
                try:
                    current_profile = current_profile_getter()
                    if self._profiles_match(current_profile, profile):
                        LOGGER.info("[_publish_profile] Profile already up to date, skipping publish")
                        return
                except Exception as err:
                    LOGGER.warning(f"[_publish_profile] Unable to read existing profile: {err}")
            except Exception as err:
                LOGGER.warning(f"[_publish_profile] Unable to read existing profile: {err}")

        try:
            LOGGER.debug(f"[_publish_profile] Publishing profile: {json.dumps(profile, sort_keys=True, indent=2)}")
            update_json_profile(profile, {"waitResponse": wait_response})
            LOGGER.info("[_publish_profile] Dynamic JSON profile published successfully")
            if hasattr(self.poly, "Notices") and hasattr(self.poly.Notices, "delete"):
                self.poly.Notices.delete("profile")
        except TypeError:
            update_json_profile(profile)
            LOGGER.info("[_publish_profile] Dynamic JSON profile published successfully")
            if hasattr(self.poly, "Notices") and hasattr(self.poly.Notices, "delete"):
                self.poly.Notices.delete("profile")
        except Exception as err:
            LOGGER.error(f"[_publish_profile] Profile publish failed: {err}")
            if hasattr(self.poly, "Notices") and hasattr(self.poly.Notices, "__setitem__"):
                self.poly.Notices["profile"] = f"Dynamic profile publish failed: {err}"

    def get_access_token(self):
        try:
            return self.oauth.getAccessToken()
        except (ValueError, KeyError, AttributeError) as e:
            LOGGER.debug(f"NuHeat getAccessToken: {e}")
            return None

    def update_oauth_config(self):
        with self.oauth_lock:
            client_id = self.client_id or self.portalID or self.customParams.get('clientId') or self.customParams.get('client_id')
            client_secret = self.client_secret or self.portalSecret or self.customParams.get('clientSecret') or self.customParams.get('client_secret')
            if client_id and client_secret:
                self.client_id = client_id
                self.client_secret = client_secret
                self.portalReady = True
                oauth_cfg = {
                    'name': 'Nuheat',
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'auth_endpoint': 'https://identity.mynuheat.com/connect/authorize',
                    'token_endpoint': 'https://identity.mynuheat.com/connect/token',
                    'scope': 'openapi openid offline_access',
                    'addScope': True,
                    'addRedirect': True
                }
                if hasattr(self.oauth, 'updateOauthSettings'):
                    self.oauth.updateOauthSettings(oauth_cfg)
                elif hasattr(self.oauth, 'customNsHandler'):
                    self.oauth.customNsHandler('oauth', oauth_cfg)

                # Explicitly persist oauth config to Polyglot so PG3 has it for the Authenticate button
                if hasattr(self.poly, 'send'):
                    self.poly.send({'set': [{'key': 'oauth', 'value': oauth_cfg}]}, 'custom')

    def customNsHandler(self, key, data):
        LOGGER.debug(f"customNsHandler called for {key}: {data}")
        try:
            # Polyglot sends empty customns values as empty strings ('') instead of dicts
            if isinstance(data, str):
                data = {}
            if not isinstance(data, dict):
                data = {}

            if hasattr(self, 'portalData') and hasattr(self.portalData, 'load'):
                self.portalData.load(data)

            if key == 'nsdata':
                if 'portalID' in data:
                    self.portalID = data['portalID']
                    self.client_id = data['portalID']
                elif 'client_id' in data:
                    self.client_id = data['client_id']
                    self.portalID = data['client_id']
                elif 'clientId' in data:
                    self.client_id = data['clientId']
                    self.portalID = data['clientId']

                if 'PortalSecret' in data:
                    self.portalSecret = data['PortalSecret']
                    self.client_secret = data['PortalSecret']
                elif 'portalSecret' in data:
                    self.portalSecret = data['portalSecret']
                    self.client_secret = data['portalSecret']
                elif 'client_secret' in data:
                    self.client_secret = data['client_secret']
                    self.portalSecret = data['client_secret']
                elif 'clientSecret' in data:
                    self.client_secret = data['clientSecret']
                    self.portalSecret = data['clientSecret']

                if self.client_id and self.client_secret:
                    self.portalReady = True
                    LOGGER.debug(f"CustomNS portal credentials received: {self.client_id}")

            elif key == 'oauth':
                if 'client_id' in data:
                    self.client_id = data['client_id']
                elif 'clientId' in data:
                    self.client_id = data['clientId']

                if 'client_secret' in data:
                    self.client_secret = data['client_secret']
                elif 'clientSecret' in data:
                    self.client_secret = data['clientSecret']

                if self.client_id and self.client_secret:
                    self.portalReady = True
                    LOGGER.debug(f"OAuth credentials received: {self.client_id}")

            self.update_oauth_config()

            if key == 'oauth':
                # If PG3 sends empty oauth data and no credentials have been entered yet,
                # do not pass empty data to self.oauth to avoid spurious error logs
                override = getattr(self.oauth, '_oauthConfigOverride', {})
                if not data and not (override and override.get('client_id')) and not self.client_id:
                    LOGGER.info("OAuth configuration is pending credentials in PG3 configuration.")
                    self.customNsDone = True
                    self.customNsHandlerDone = True
                    return

            if hasattr(self.oauth, 'customNsHandler'):
                self.oauth.customNsHandler(key, data or {})

            if key in ('oauth', 'oauthTokens', 'nsdata'):
                self.customNsDone = True
                self.customNsHandlerDone = True
            LOGGER.debug(f"customNsHandler finished for {key}")
        except Exception as e:
            LOGGER.error(f"Error handling customNs {key}: {e}")

    def configDoneHandler(self):
        LOGGER.info("configDoneHandler: PG3 initial configuration messages complete.")
        self.configDone = True
        self.config_done = True
        self.update_oauth_config()

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
        else:
            # Pre-populate temp_unit so it displays in PG3 Custom Configuration Parameters
            self.customParams['temp_unit'] = 'F'
            self.temp_unit = 'F'
            self.temp_uom = 17

        if self.temp_unit != prev_temp_unit:
            self._publish_profile()
            get_nodes = getattr(self.poly, 'getNodes', None)
            nodes = get_nodes() if callable(get_nodes) else getattr(self, 'nodes', {})
            nodes_iterable = nodes.values() if isinstance(nodes, dict) else nodes
            for node in nodes_iterable:
                if hasattr(node, 'temp_uom'):
                    node.temp_uom = self.temp_uom
                    if hasattr(node, 'update_info'):
                        node.update_info()

        self.handleCustomParamsDone = True
        self.customParam_done = True
        LOGGER.debug(f"customParamsHandler finished: tz={self.tz}, temp_unit={self.temp_unit} (uom {self.temp_uom})")

    def start(self):
        LOGGER.info('Starting NuHeat NodeServer...')

        # In PG3 multi-threaded startup, ensure customParams, customNS, and config are handled before starting
        wait_seconds = 0
        max_wait = 15
        while not (self.customParam_done and self.customNsDone and self.config_done and self.portalReady) and wait_seconds < max_wait:
            LOGGER.info(
                f"Waiting for node to initialize: customParams={self.customParam_done}, "
                f"customNS={self.customNsDone}, configDone={self.config_done}, portalReady={self.portalReady} ({wait_seconds}s)"
            )
            time.sleep(1)
            wait_seconds += 1

        self.update_oauth_config()
        self.setDriver('ST', 1, uom=2)
        self.setDriver('TIME', int(time.time()), uom=151)
        self._publish_profile()

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
        self.setDriver('TIME', int(time.time()), uom=151)
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
        self.setDriver('TIME', int(time.time()), uom=151)
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

        configured_unit = self.get_configured_temp_unit()
        if not configured_unit:
            account_info = self.NuHeat.get_account()
            if account_info:
                self.temperature_scale = account_info.get('temperatureScale', 'Fahrenheit')
                if self.temperature_scale.lower().startswith('c'):
                    self.temp_unit = "C"
                    self.temp_uom = 4
                else:
                    self.temp_unit = "F"
                    self.temp_uom = 17
            else:
                self.temp_unit = "F"
                self.temp_uom = 17
            self._publish_profile()

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

            # In ISY, child nodes require their parent (primaryNode) to be a primary node (address == primary).
            # If the thermostat was previously registered with primaryNode='controller', remove it first
            # so it can be cleanly recreated as a primary node.
            existing_node = None
            if hasattr(self.poly, '_nodes') and isinstance(self.poly._nodes, dict):
                existing_node = self.poly._nodes.get(stat_address)
            if existing_node is None and hasattr(self.poly, 'getNode'):
                existing_node = self.poly.getNode(stat_address)
            elif existing_node is None and hasattr(self, 'nodes') and isinstance(self.nodes, dict):
                existing_node = self.nodes.get(stat_address)

            if existing_node is not None:
                current_primary = None
                if isinstance(existing_node, dict):
                    current_primary = existing_node.get('primaryNode') or existing_node.get('primary')
                else:
                    current_primary = getattr(existing_node, 'primary', None) or getattr(existing_node, 'primaryNode', None)

                if current_primary and current_primary != stat_address:
                    LOGGER.info(f"Node {stat_address} currently has parent '{current_primary}'. Removing so it can be created as primary node...")
                    if hasattr(self.poly, 'delNode'):
                        self.poly.delNode(stat_address)
                        time.sleep(1)

            stat_node = ThermostatNode(self.poly, stat_address, stat_address, name, self, temp_uom=self.temp_uom)
            add_node(stat_node)

            # Wait for PG3 confirmation of parent node before adding children
            self._wait_for_node_confirmed(stat_address, timeout=10.0)

            # Direct 1-level children under the thermostat primary
            add_node(EnergyLogDayNode(self.poly, stat_address, energy_log_day_address, f"{name} Energy-Day", self))
            add_node(EnergyLogWeekNode(self.poly, stat_address, energy_log_week_address, f"{name} Energy-Week", self))
            add_node(EnergyLogYearNode(self.poly, stat_address, energy_log_year_address, f"{name} Energy-Year", self))

        self.disco = 1

    def update_profile(self, command=None):
        LOGGER.info('Installing / Updating profile...')
        self._publish_profile(wait_response=True)
        return True

    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': update_profile
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
