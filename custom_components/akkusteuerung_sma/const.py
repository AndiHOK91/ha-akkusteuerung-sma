"""Constants for SMA battery control integration."""

DOMAIN = "akkusteuerung_sma"
VERSION = "0.2.0"
DEFAULT_NAME = "SMA Akku Steuerung"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_MODBUS_ID = "modbus_id"
CONF_SLAVE = "slave"

CONF_BATTERY_CAPACITY_ENTITY = "battery_capacity_entity"
CONF_BATTERY_SOC_ENTITY = "battery_soc_entity"
CONF_BATTERY_POWER_ENTITY = "battery_power_entity"
CONF_PV_POWER_ENTITY = "pv_power_entity"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_HOUSE_CONSUMPTION_ENTITY = "house_consumption_entity"

CONF_INVERTER_LIMIT_ENTITY = "inverter_limit_entity"
CONF_INVERTER_STATUS_ENTITY = "inverter_status_entity"
CONF_INVERTER_TEMPERATURE_ENTITY = "inverter_temperature_entity"

DEFAULT_PORT = 502
DEFAULT_MODBUS_ID = 3
DEFAULT_SLAVE = 3
