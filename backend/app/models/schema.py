from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    phone_number = Column(String(30), unique=True, index=True, nullable=False) # e.g. +2348012345678
    email = Column(String(120), unique=True, index=True, nullable=True)
    role = Column(String(20), default="client") # client, installer, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    devices = relationship("Device", back_populates="user", foreign_keys="[Device.user_id]")


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(32), primary_key=True, index=True) # e.g. NG-INV-00124
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    installer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    site_name = Column(String(120), nullable=False, default="Residential Solar Site")
    city = Column(String(60), default="Lagos")
    inverter_model = Column(String(60), default="Growatt SPF 5000 ES")
    battery_capacity_wh = Column(Float, default=10000.0) # 10 kWh battery bank
    battery_cutoff_soc = Column(Float, default=10.0) # 10% cutoff
    battery_type = Column(String(30), default="LiFePO4") # LiFePO4, Gel, AGM
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], back_populates="devices")


class TelemetryData(Base):
    __tablename__ = "telemetry_data"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    device_id = Column(String(32), primary_key=True, nullable=False)
    grid_voltage_v = Column(Float, nullable=False)
    grid_status = Column(Boolean, nullable=False)
    pv_voltage_v = Column(Float, nullable=False)
    pv_power_w = Column(Float, nullable=False)
    battery_voltage_v = Column(Float, nullable=False)
    battery_soc_pct = Column(Float, nullable=False)
    battery_current_a = Column(Float, nullable=False, default=0.0)
    output_active_power_w = Column(Float, nullable=False)
    inverter_temp_c = Column(Float, nullable=False)
    fault_code = Column(Integer, default=0)
    is_buffered = Column(Boolean, default=False)

    __table_args__ = (
        Index("idx_telemetry_device_time", "device_id", "time"),
    )


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(32), ForeignKey("devices.device_id"), index=True, nullable=False)
    alert_type = Column(String(50), nullable=False) # HEAVY_LOAD_CRITICAL, GRID_OUTAGE, GRID_RESTORED, FAULT_CODE
    severity = Column(String(20), default="CRITICAL") # INFO, WARNING, CRITICAL
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    whatsapp_sent = Column(Boolean, default=False)


class WhatsAppMessageLog(Base):
    __tablename__ = "whatsapp_message_logs"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(30), index=True, nullable=False)
    direction = Column(String(10), nullable=False) # INBOUND, OUTBOUND
    message_type = Column(String(20), default="text") # text, template, interactive
    content = Column(Text, nullable=False)
    meta_message_id = Column(String(100), nullable=True)
    delivery_status = Column(String(20), default="sent") # sent, delivered, read, failed
    created_at = Column(DateTime, default=datetime.utcnow)
