import logging

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

