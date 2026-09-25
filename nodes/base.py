import logging
import time

# NTP epoch offset: Seconds between 1900-01-01 00:00:00 UTC and 1970-01-01 00:00:00 UTC
# 70 years (17 leap years: 1904, 1908 ... 1968) = 25567 days * 86400 s/day = 2,208,988,800 seconds
NTP_EPOCH_OFFSET = 2208988800


def get_current_timestamp(uom: int = 151) -> int:
    """Return the current timestamp formatted for the target UOM.

    - UOM 151: Unix timestamp (seconds since Jan 1, 1970 00:00:00 UTC).
    - UOM 137: Seconds since Jan 1, 1900 00:00:00 UTC (NTP / ISY epoch, offset +2208988800).
    """
    now = int(time.time())
    if int(uom) == 137:
        return now + NTP_EPOCH_OFFSET
    return now


def is_uom151_supported(poly) -> bool:
    """Check if ISY/IoX firmware supports UOM 151 (IoX 5.8.0+)."""
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

