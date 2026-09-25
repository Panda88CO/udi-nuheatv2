import time
from datetime import date

from .base import LOGGER, BaseNode, get_current_timestamp


class EnergyLogYearNode(BaseNode):
    id = 'ENERGYLOG'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 45},
        {'driver': 'ST', 'value': 0, 'uom': 33},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(EnergyLogYearNode, self).__init__(polyglot, primary, address, name)
        self.controller = controller
        self.stat_address = address[3:] if address.startswith('ely') else primary

    def start(self):
        self.update_info()

    def update_info(self):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        year_str = str(date.today().year)
        stat_id = getattr(self, 'stat_address', self.primary)
        energy_used = nuheat_client.get_energy_log_year(stat_id, year_str)
        if energy_used is not None:
            self.setDriver('GV0', energy_used[0], uom=45)
            self.setDriver('ST', energy_used[1], uom=33)
            time_uom = 151
            if self.controller and hasattr(self.controller, 'time_uom'):
                val = getattr(self.controller, 'time_uom', None)
                if isinstance(val, (int, str)):
                    try:
                        time_uom = int(val)
                    except (ValueError, TypeError):
                        time_uom = 151
            self.setDriver('TIME', get_current_timestamp(time_uom), uom=time_uom)
        else:
            LOGGER.error(f"Energy Log Year returned None for {stat_id}")

    def query(self, command=None):
        self.reportDrivers()

    commands = {'QUERY': query}
