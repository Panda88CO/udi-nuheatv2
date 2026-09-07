from .base import LOGGER, BaseNode

from datetime import date


class EnergyLogYearNode(BaseNode):
    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(EnergyLogYearNode, self).__init__(polyglot, primary, address, name)
        self.controller = controller

    def start(self):
        self.update_info()

    def update_info(self):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        year_str = str(date.today().year)
        energy_used = nuheat_client.get_energy_log_year(self.primary, year_str)
        if energy_used is not None:
            self.setDriver('GV0', energy_used[0], uom=45)
            self.setDriver('ST', energy_used[1], uom=33)
            self.setDriver('GV1', energy_used[2], uom=103)
        else:
            LOGGER.error(f"Energy Log Year returned None for {self.primary}")

    def query(self, command=None):
        self.reportDrivers()

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 45},
        {'driver': 'ST', 'value': 0, 'uom': 33},
        {'driver': 'GV1', 'value': 0, 'uom': 103}
    ]

    id = 'ENERGYLOG'

    commands = {'QUERY': query}

