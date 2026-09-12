# NuHeat Signature NodeServer

A Polyglot v3 (PG3 / PG3x) NodeServer for integrating **NuHeat Signature** radiant floor heating thermostats with Universal Devices controllers (eisy / Polisy / IoX).

---

## Requirements

- Universal Devices controller (**eisy** or **Polisy**) running **PG3** or **PG3x**
- One or more **NuHeat Signature** WiFi floor heating thermostats
- Active **[My NuHeat](https://mynuheat.com)** portal account
- NuHeat API OAuth credentials (**Client ID** & **Client Secret**)

---

## Installation

1. Open your PG3/PG3x dashboard.
2. Go to the **NodeServer Store**.
3. Locate **NuHeat** and click **Install** (or install from your GitHub repository URL).

---

## OAuth Client Settings

When requesting or configuring your OAuth application with NuHeat, use the following settings:

| Setting | Value |
| :--- | :--- |
| **Grant Type** | `Authorization Code` (`authorization_code`) & `Refresh Token` (`offline_access`) |
| **Return URI (Redirect URI)** | `https://my.isy.io/api/cloudlink/redirect` |
| **Authorization Endpoint** | `https://identity.mynuheat.com/connect/authorize` |
| **Token Endpoint** | `https://identity.mynuheat.com/connect/token` |
| **Scopes** | `openapi openid profile offline_access` |

---

## Configuration

In the PG3 dashboard under the NodeServer's **Configuration** tab, add the following **Custom Configuration Parameters**:

| Key | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `clientId` | string | Your NuHeat OAuth Client ID *(Required)* | *(none)* |
| `clientSecret` | string | Your NuHeat OAuth Client Secret *(Required)* | *(none)* |
| `tz` | string | Your local tz database timezone name *(Required for energy logs)* | `America/New_York` |
| `TEMP_UNIT` | string | *(Optional)* Temperature scale override: `F` or `C`. Auto-detected if omitted. | *(auto)* |

*Refer to the [tz database time zones list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) to find your timezone string (e.g., `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).*

> [!NOTE]
> `clientId` and `clientSecret` are now managed directly via PG3's OAuth / customNS configuration (similar to TeslaEVstream). They are no longer required in Custom Configuration Parameters.

---

## First-Time Setup & Authentication

1. **Enter Credentials**: Save your `clientId`, `clientSecret`, and `tz` in the Custom Configuration Parameters.
1. **Enter Credentials**: Save your `tz` in the Custom Configuration Parameters.
2. **Authenticate**: Click the **Authenticate** button on the NodeServer details page in the PG3 dashboard.
3. **Log In**: A browser window will open to the NuHeat login page. Sign into your My NuHeat account and grant access.
4. **Discovery**: Once authentication completes, the NodeServer will automatically discover your connected thermostats and create all device nodes in your Admin Console. You can also trigger discovery manually by clicking **Discover** on the Controller node.

---

## Thermostat Operating Mode

For the NodeServer to have full setpoint control without conflicting with built-in schedules:
1. On the physical thermostat screen, tap **Setup** → **Preferences**.
2. Tap **Operating Mode** at the bottom of the screen.
3. Change the selection from **Auto** to **Manual**.
4. *(Note: Manual mode disables internal cloud/app schedules so that your ISY/eisy programs have exclusive control).*

---

## Features & Discovered Nodes

The NodeServer automatically detects your account's preferred temperature scale (°F or °C) and creates the following nodes for each thermostat:

- **Controller Node**: Manages connection, authentication status, and discovery.
- **Thermostat Node (`°F` or `°C`)**:
  - Reports current floor temperature and target setpoint.
  - Reports heating status (idle / heating).
  - Set target heating temperature directly from programs and Admin Console.
- **Energy Log Nodes**:
  - **Energy Log - Day**: Daily power consumption (watt-hours).
  - **Energy Log - Week**: Weekly power consumption (watt-hours).
  - **Energy Log - Year**: Yearly power consumption (watt-hours).

---

## Polling

- **Short Poll (default 300s)**: Queries thermostat status, temperature, and heating activity.
- **Long Poll (default 900s)**: Updates energy usage metrics.

---

## Limitations

- Internal thermostat scheduling is not edited through the NodeServer (use ISY programs instead).
- Mode changes (e.g. Away mode) are currently managed via the NuHeat app or physical thermostat.
