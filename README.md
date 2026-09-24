# NuHeat Signature NodeServer

A Polyglot v3 (PG3 / PG3x) NodeServer for integrating **NuHeat Signature** radiant floor heating thermostats with Universal Devices controllers (eisy / Polisy / IoX).

---

## Requirements

- Universal Devices controller (**eisy** or **Polisy**) running **PG3** or **PG3x**
- One or more **NuHeat Signature** WiFi floor heating thermostats
- Active **[My NuHeat](https://mynuheat.com)** account
- NuHeat API OAuth credentials (**Client ID** & **Client Secret**)

---

## Installation

1. Open your PG3/PG3x dashboard.
2. Go to the **NodeServer Store**.
3. Locate **NuHeat** and click **Install** (or install from your GitHub repository URL).


## Configuration

In the PG3 dashboard under the NodeServer's **Configuration** tab, add the following **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `tz` | string | Your local tz database timezone name *(Required for energy logs)* | `America/New_York` |
| `temp_unit` | string | Temperature unit: `F` for Fahrenheit or `C` for Celsius | `F` |

*Refer to the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to find your timezone string (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> `clientId` and `clientSecret` can be configured either via PG3's OAuth setup or entered in **Custom Configuration Parameters** (`clientId` and `clientSecret`).

---

## First-Time Setup & Authentication

1. **Authenticate**: Click the **Authenticate** button on the NodeServer details page in the PG3 dashboard.
2. **Log In**: A browser window will open to the NuHeat login page. Sign into your My NuHeat account and grant access.
3. **Discovery**: Once authentication completes, the NodeServer automatically discovers your connected thermostats and creates all device nodes in your Admin Console.

---

## Setting Operating Mode & Setpoint

The thermostat uses 3 dedicated commands to control operating mode and heating setpoint:
- **Set Auto (`SETAUTO`)**: Follows internal schedule. Takes no parameters. Hold Time (`GV4`) displays as `0` minutes, Operating Mode (`CLIMD`) displays as `Auto`, and Setpoint (`CLISPH`) reflects the scheduled temperature.
- **Set Hold (`SETHOLD`)**: Temporary hold with 2 parameters:
  - **Hold Temperature (`TEMPHOLDF` / `TEMPHOLDC`)**: Target heating setpoint in configured scale (°F or °C).
  - **Hold Minutes (`HOLD`)**: Duration in minutes (0–1440). Sets `GV4` to remaining hold duration in minutes (UOM 45) and `CLIMD` to `Hold`.
- **Set Permanent Temp (`SETPERMHOLD`)**: Manual hold with 1 parameter:
  - **Temperature (`temp`)**: Target heating setpoint in configured scale (°F or °C) permanently until changed. `GV4` displays as `0` minutes and `CLIMD` displays as `Permanent Hold`.

---

## Features & Discovered Nodes

The NodeServer automatically detects your account's preferred temperature scale (°F or °C) and creates the following nodes:

- **Controller Node**:
  - **Drivers**:
    - **NodeServer Online (`ST`)**: Indicates whether the NodeServer process is running and connected (Online / Offline, UOM 2).
    - **Last Update (`TIME`)**: Unix epoch timestamp (UOM 151) of the last successful communication/poll with the controller.
  - **Heartbeat (`DON` / `DOF`)**: Emits alternating `DON` and `DOF` control events on each short poll for ISY watchdog / heartbeat monitoring programs.
  - **Commands**:
    - **Update (`UPDATE`)**: Immediately forces an update across all nodes and queries fresh energy metrics (executes long poll).

- **Thermostat Node (`°F` or `°C`)**:
  - **Temperature & Setpoint**: Reports current temperature (`ST`) and target heat setpoint (`CLISPH`).
  - **Operating Mode (`CLIMD`)**: Auto, Hold, or Permanent Hold.
  - **Heat State (`CLIHCS`)**: Idle or Heating.
  - **Hold Time (`GV4`)**: Duration in minutes (UOM 45); displays remaining minutes on Temporary Hold; 0 in Auto and Permanent Hold.
  - **Online Status (`GV5`)**: Thermostat connection status (Online / Offline, UOM 2).
  - **Last Update (`TIME`)**: Unix epoch timestamp (UOM 151) of the last data refresh for this thermostat.
  - **Commands**:
    - **Set Auto (`SETAUTO`)**: Sets thermostat to follow internal schedule.
    - **Set Hold (`SETHOLD`)**: Sets temporary hold with target temperature and hold duration in minutes.
    - **Set Permanent Temp (`SETPERMHOLD`)**: Sets permanent manual hold with target temperature.
    - **Force Update (`UPDATE`)**: Immediately forces a data update for this thermostat.
  - **Energy Metrics (UOM 33 / kWh)**:
    - **Daily Energy** (`GV0`): Energy used today in kWh.
    - **Last 7 Days Energy** (`GV1`): Energy used over the past 7 days in kWh.
    - **Monthly Energy** (`GV2`): Month-to-date energy usage in kWh.
    - **Yearly Energy** (`GV3`): Year-to-date energy usage in kWh.

---

## Polling

- **Short Poll (default 300s)**: Queries thermostat status, temperature, mode, and heating activity.
- **Long Poll (default 1800s)**: Updates energy usage metrics.

---

## Limitations

- Internal thermostat scheduling is not edited through the NodeServer (use ISY programs instead).
