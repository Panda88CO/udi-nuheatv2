# NuHeat NodeServer Configuration (PG3 / PG3x)

This NodeServer connects Universal Devices controllers (eisy / Polisy) to **NuHeat Signature** radiant floor heating thermostats via the official NuHeat Cloud API and OAuth 2.0.

---


## 1. Custom Configuration Parameters

In your PG3/PG3x NodeServer dashboard, configure the following keys under **Configuration** -> **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `tz` | string | Your local tz database timezone name (Required for accurate energy log timestamps) | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit (UOM 17) or `C` for Celsius (UOM 4) | `F` |
| `force_uom137` | boolean | *(Optional / Testing)* Set to `true` to force timestamp UOM 137 (ISY-994 NTP epoch) even on IoX 5.8+ | `false` |
| `time_uom` | integer | *(Optional / Testing)* Explicitly set timestamp UOM (`137` or `151`) | Auto |

*A complete list of timezone names can be found in the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> Client ID and Client Secret can be provided either via PG3's OAuth configuration setup or entered directly into **Custom Configuration Parameters** (`clientId` and `clientSecret`).


---

## 2. Authentication Steps

1. Configure `tz` and `temp_unit` (`F` or `C`) in **Custom Configuration Parameters** and click **Save**.
2. When the OAuth configuration is loaded in PG3, click the **Authenticate** button in the PG3 NodeServer details page.
3. Log into your **[My NuHeat](https://mynuheat.com)** account in the browser window and approve access.
4. Once authorized, the NodeServer will automatically discover your thermostats and create the corresponding nodes in your Admin Console.

---

## 3. Operating Mode & Setpoint Control
 
The thermostat uses 3 dedicated commands to control operating mode and heating setpoint:
- **Set Auto (`SETAUTO`)**: Follows internal schedule. Takes no parameters. Hold Time (`GV4`) displays as `0` minutes, Operating Mode (`CLIMD`) displays as `Auto`, and Setpoint (`CLISPH`) reflects the scheduled temperature.
- **Set Hold (`SETHOLD`)**: Temporary hold with 2 parameters:
  - **Hold Temperature (`TEMPHOLDF` / `TEMPHOLDC`)**: Target heating setpoint in °F or °C.
  - **Hold Minutes (`HOLD`)**: Duration in minutes (0–1440). Sets `GV4` to the hold duration in minutes (UOM 45) and `CLIMD` to `Hold`.
- **Set Permanent Temp (`SETPERMHOLD`)**: Manual hold with 1 parameter:
  - **Temperature (`temp`)**: Target heating setpoint in °F or °C indefinitely. `GV4` displays as `0` minutes and `CLIMD` displays as `Permanent Hold`.

---

## 4. Discovered Nodes

For each thermostat discovered on your account, nodes are created serially 1-by-1 with PG3 confirmation:
1. **Controller Node** (`controller`):
   - **Status Drivers**:
     - NodeServer Online (`ST` — Online / Offline, UOM 2)
     - Last Update (`TIME` — timestamp, UOM 151 on IoX 5.8+ / UOM 137 on ISY-994)
   - **Heartbeat**: Toggles `DON` / `DOF` on each short poll.
   - **Commands**:
     - **Update (`UPDATE`)**: Immediately force updates all nodes and energy logs.

2. **Thermostat Node** (`thermostatf` for Fahrenheit [UOM 17] or `thermostatc` for Celsius [UOM 4], determined during startup):
   - **Status Drivers**:
     - Current Temperature (`ST`)
     - Heat Setpoint (`CLISPH`)
     - Operating Mode (`CLIMD` — Auto, Hold, Permanent Hold)
     - Heat State (`CLIHCS` — Idle, Heating)
     - Hold Time (`GV4` — duration in minutes [UOM 45]; displays remaining minutes on Temporary Hold; 0 in Auto and Permanent Hold)
     - Online Status (`GV5` — Online / Offline, UOM 2)
     - Last Update (`TIME` — timestamp, UOM 151 on IoX 5.8+ / UOM 137 on ISY-994)
     - Daily Energy (`GV0` — kWh, UOM 33)
     - Last 7 Days Energy (`GV1` — kWh, UOM 33)
     - Monthly Energy (`GV2` — kWh, UOM 33)
     - Yearly Energy (`GV3` — kWh, UOM 33)
   - **Commands**:
     - **Set Auto (`SETAUTO`)**: Sets thermostat to follow internal schedule.
     - **Set Hold (`SETHOLD`)**: Sets temporary hold with target temperature and hold duration in minutes.
     - **Set Permanent Temp (`SETPERMHOLD`)**: Sets permanent manual hold with target temperature.
     - **Force Update (`UPDATE`)**: Immediately force updates thermostat status.
