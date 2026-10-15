import os
import sys
import logging
import time

NODE_SERVER_START_TIME = int(time.time())

def get_current_timestamp(uom: int = 151, start_time: int = None) -> int:
    """Return the current timestamp. For UOM 58, returns elapsed seconds since node started."""
    now = int(time.time())
    if int(uom) == 58:
        base = start_time if start_time is not None else NODE_SERVER_START_TIME
        return max(0, now - int(base))
    return now


def is_uom151_supported(poly) -> bool:
    """Check if ISY/IoX firmware supports UOM 151 (IoX 5.8.0+)."""
    if poly is not None:
        custom_params = getattr(poly, 'customParams', None) or getattr(poly, 'customparams', None)
        if custom_params:
            for k in ('forceOldFW', 'forceoldfw', 'FORCEOLDFW', 'force_old_fw', 'FORCE_OLD_FW'):
                val = custom_params.get(k) if hasattr(custom_params, 'get') else getattr(custom_params, k, None)
                if val and str(val).strip().lower() in ('true', '1', 'yes', 'on'):
                    return False

    isy_ver = None
    if poly is not None:
        if hasattr(poly, 'pg3init') and isinstance(poly.pg3init, dict):
            val = poly.pg3init.get('isyVersion')
            if isinstance(val, str) and val.strip():
                isy_ver = val.strip()
        if not isy_ver and hasattr(poly, 'serverdata') and isinstance(poly.serverdata, dict):
            val = poly.serverdata.get('isyVersion')
            if isinstance(val, str) and val.strip():
                isy_ver = val.strip()
        if not isy_ver and hasattr(poly, 'getIsyVersion') and callable(poly.getIsyVersion):
            try:
                val = poly.getIsyVersion()
                if isinstance(val, str) and val.strip():
                    isy_ver = val.strip()
            except Exception:
                pass
        if not isy_ver and hasattr(poly, 'isyVersion'):
            try:
                val = poly.isyVersion() if callable(poly.isyVersion) else poly.isyVersion
                if isinstance(val, str) and val.strip():
                    isy_ver = val.strip()
            except Exception:
                pass

    if not isy_ver:
        # Default to modern IoX (True) if version cannot be determined
        return True

    try:
        parts = []
        for p in str(isy_ver).split('.'):
            digits = ''
            for ch in p:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits:
                parts.append(int(digits))
            else:
                break
        if len(parts) >= 2:
            while len(parts) < 3:
                parts.append(0)
            return tuple(parts[:3]) >= (5, 8, 0)
        return True
    except Exception:
        return True


def is_dynamic_profile_supported(poly) -> bool:
    """Check if ISY/IoX firmware supports dynamic JSON profile loading (IoX 5.8.0+ and not forceOldFW)."""
    return is_uom151_supported(poly)


_dynamic_profile_builder = None

def register_profile_builder(builder):
    """Register the dynamic profile definition builder function."""
    global _dynamic_profile_builder
    _dynamic_profile_builder = builder


def load_nls_driver_names(profile_dir: str = None) -> dict:
    """Load driver names from the NLS file in the profile directory.
    Searches for profile/nls/en_us.txt, profile/nls.txt, profile/nls/nls.txt, profile/en_us.txt.
    Returns mapping: {'ctl': {'ST': '...', 'TIME': '...'}, 'tstat': {'ST': '...', ...}}
    """
    if profile_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        profile_dir = os.path.join(base_dir, 'profile')

    candidates = [
        os.path.join(profile_dir, 'nls', 'en_us.txt'),
        os.path.join(profile_dir, 'nls.txt'),
        os.path.join(profile_dir, 'nls', 'nls.txt'),
        os.path.join(profile_dir, 'en_us.txt'),
    ]
    nls_file = None
    for c in candidates:
        if os.path.isfile(c):
            nls_file = c
            break

    mapping = {}
    if not nls_file:
        return mapping

    try:
        with open(nls_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip()
                parts = k.split('-')
                if len(parts) >= 4 and parts[0] == 'ST' and parts[-1] == 'NAME':
                    prefix = parts[1].lower()
                    driver = parts[2].upper()
                    mapping.setdefault(prefix, {})[driver] = v
                elif len(parts) == 3 and parts[0] == 'ST' and parts[-1] == 'NAME':
                    driver = parts[1].upper()
                    mapping.setdefault('*', {})[driver] = v
    except Exception as e:
        LOGGER.warning(f"Error loading NLS file {nls_file}: {e}")

    return mapping


def get_driver_names_from_dynamic_profile(node_id: str, temp_unit: str = "F", time_uom: int = 151) -> dict:
    """Extract driver names for node_id from dynamic profile definition."""
    builder = _dynamic_profile_builder
    if builder is None:
        try:
            import nuheat
            builder = getattr(nuheat, '_build_profile_definition', None)
        except Exception:
            pass
    if builder is None:
        try:
            mod = sys.modules.get('__main__')
            builder = getattr(mod, '_build_profile_definition', None)
        except Exception:
            pass
    if builder is not None:
        try:
            profile = builder(temp_unit=temp_unit, time_uom=time_uom)
            target_id = str(node_id).lower()
            if target_id == 'thermostat':
                target_id = 'thermostatc' if temp_unit == 'C' else 'thermostatf'
            for nd in profile.get('nodedefs', []):
                if nd.get('id', '').lower() == target_id:
                    return {p['id'].upper(): p['name'] for p in nd.get('properties', []) if 'id' in p and 'name' in p}
        except Exception as e:
            LOGGER.warning(f"Error extracting driver names from dynamic profile: {e}")
    return {}


def get_driver_names(node_id: str, use_dynamic: bool = True, temp_unit: str = "F", time_uom: int = 151, profile_dir: str = None) -> dict:
    """Return dictionary of driver_id -> driver_name.
    If use_dynamic is True, retrieves names from the dynamic profile definition.
    If use_dynamic is False (or driver is not in dynamic profile), loads names from the NLS file in the profile directory.
    """
    node_id_lower = str(node_id).lower()
    names = {}

    if use_dynamic:
        dynamic_names = get_driver_names_from_dynamic_profile(node_id_lower, temp_unit=temp_unit, time_uom=time_uom)
        if dynamic_names:
            names.update(dynamic_names)
            return names

    # Fallback to NLS file
    nls_mapping = load_nls_driver_names(profile_dir)
    nls_prefix = 'ctl' if node_id_lower in ('controller', 'ctl') else ('tstat' if node_id_lower in ('thermostat', 'thermostatf', 'thermostatc', 'tstat') else node_id_lower)

    if nls_prefix in nls_mapping:
        names.update(nls_mapping[nls_prefix])
    if '*' in nls_mapping:
        for d, n in nls_mapping['*'].items():
            names.setdefault(d, n)

    # Standard default names if any driver was missing
    time_label = "Last Update" if int(time_uom) == 151 else "Time since node started"
    defaults = {
        'controller': {'ST': 'NodeServer Online', 'TIME': time_label},
        'ctl': {'ST': 'NodeServer Online', 'TIME': time_label},
        'thermostatf': {
            'ST': 'Current Temperature', 'CLISPH': 'Heat Setpoint', 'CLIMD': 'Mode',
            'CLIHCS': 'Heat State', 'GV0': 'Daily Energy', 'GV1': 'Last 7 Days Energy',
            'GV2': 'Monthly Energy', 'GV3': 'Yearly Energy', 'GV4': 'Hold Time',
            'GV5': 'Online', 'TIME': time_label
        },
        'thermostatc': {
            'ST': 'Current Temperature', 'CLISPH': 'Heat Setpoint', 'CLIMD': 'Mode',
            'CLIHCS': 'Heat State', 'GV0': 'Daily Energy', 'GV1': 'Last 7 Days Energy',
            'GV2': 'Monthly Energy', 'GV3': 'Yearly Energy', 'GV4': 'Hold Time',
            'GV5': 'Online', 'TIME': time_label
        },
        'energylog': {'GV0': 'Duration', 'ST': 'Energy', 'TIME': time_label}
    }
    def_map = defaults.get(node_id_lower, defaults.get('thermostatf' if 'thermostat' in node_id_lower else 'controller'))
    if def_map:
        for d, n in def_map.items():
            names.setdefault(d, n)

    return names


def apply_driver_names(node, use_dynamic: bool = None, temp_unit: str = None, time_uom: int = None, profile_dir: str = None):
    """Update node.drivers list in-place so every driver dict has its resolved 'name' field."""
    node_id = getattr(node, 'id', '')
    poly = getattr(node, 'poly', None) or getattr(node, 'polyglot', None)
    controller = getattr(node, 'controller', None)

    if use_dynamic is None:
        if controller is not None and hasattr(controller, '_is_dynamic_profile_supported'):
            use_dynamic = controller._is_dynamic_profile_supported()
        elif poly is not None:
            use_dynamic = is_dynamic_profile_supported(poly)
        else:
            use_dynamic = True

    if time_uom is None:
        time_uom = getattr(node, 'time_uom', None)
        if time_uom is None and controller is not None:
            time_uom = getattr(controller, 'time_uom', None)
        if time_uom is None:
            time_uom = 151 if (poly is not None and is_uom151_supported(poly)) else 58

    if temp_unit is None:
        temp_uom = getattr(node, 'temp_uom', None)
        if temp_uom == 4 or getattr(controller, 'temp_unit', 'F') == 'C':
            temp_unit = 'C'
        else:
            temp_unit = 'F'

    names = get_driver_names(node_id, use_dynamic=use_dynamic, temp_unit=temp_unit, time_uom=time_uom, profile_dir=profile_dir)

    if hasattr(node, 'drivers') and isinstance(node.drivers, list):
        for drv in node.drivers:
            if isinstance(drv, dict) and 'driver' in drv:
                d_id = drv['driver']
                if d_id in names:
                    drv['name'] = names[d_id]
                elif 'name' not in drv:
                    drv['name'] = d_id
                if d_id == 'TIME':
                    drv['uom'] = time_uom
                    drv['name'] = names.get('TIME', 'Last Update' if time_uom == 151 else 'Time since node started')



try:
    import udi_interface
    LOGGER = udi_interface.LOGGER
    BaseNode = udi_interface.Node
except ImportError:
    try:
        import polyinterface
        LOGGER = polyinterface.LOGGER
        BaseNode = polyinterface.Node
    except ImportError:
        try:
            import pgc_interface as polyinterface
            LOGGER = polyinterface.LOGGER
            BaseNode = polyinterface.Node
        except ImportError:
            LOGGER = logging.getLogger("nuheat")
            logging.basicConfig(level=logging.INFO)

            class BaseNode:
                def __init__(self, poly, primary, address, name):
                    self.poly = poly
                    self.primary = primary
                    self.address = address
                    self.name = name
                    self.drivers = [dict(d) for d in getattr(self.__class__, 'drivers', [])]

                def setDriver(self, driver, value, report=True, force=False, uom=None):
                    for d in self.drivers:
                        if isinstance(d, dict) and d.get('driver') == driver:
                            d['value'] = value
                            if uom is not None:
                                d['uom'] = uom
                            return
                    self.drivers.append({'driver': driver, 'value': value, 'uom': uom})

                def getDriver(self, driver):
                    for d in self.drivers:
                        if isinstance(d, dict) and d.get('driver') == driver:
                            return d
                    return None

                def reportDrivers(self):
                    pass

