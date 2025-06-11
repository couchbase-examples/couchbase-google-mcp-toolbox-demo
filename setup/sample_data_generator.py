import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from .couchbase_client import CouchbaseClient
from src.models.manufacturing_models import (
    Alert, Machine, ProductionLine, MaintenanceRecord, ProductionMetrics,
    AlertSeverity, AlertStatus, MaintenanceStatus, ProductionLineStatus, MachineType
)

logger = logging.getLogger(__name__)

class SampleDataGenerator:
    """Generate sample manufacturing data for the demo."""
    
    # --- Generation Configuration ---
    NUM_PRODUCTION_LINES = 5
    NUM_ALERTS = 50
    NUM_MAINTENANCE_RECORDS = 30
    NUM_METRIC_DAYS = 7

    MIN_MACHINES_PER_LINE = 2
    MAX_MACHINES_PER_LINE = 3
    ULTIMA_SV_CHANCE = 0.3

    TARGET_OUTPUT_RANGE = (800, 1200)
    ACTUAL_OUTPUT_RANGE = (700, 1100)
    EFFICIENCY_RANGE = (75.0, 95.0)
    OPERATORS_PER_LINE_RANGE = (2, 4)

    INSTALLATION_DAYS_AGO_RANGE = (30, 1000)
    LAST_MAINTENANCE_DAYS_AGO_RANGE = (1, 30)
    NEXT_MAINTENANCE_DAYS_AHEAD_RANGE = (1, 60)

    MACHINE_STATUSES = ["operational", "maintenance", "warning", "error"]
    
    def __init__(self, couchbase_client: CouchbaseClient):
        self.couchbase_client = couchbase_client
        
        # Sample data templates
        self.machine_names = [
            "Primary Filler Alpha", "Secondary Filler Beta", "Quality Checker Gamma",
            "Conveyor Delta", "Packaging Unit Epsilon", "Ultima SV Zeta",
            "Conveyor Eta", "Quality Checker Theta", "Primary Filler Iota",
            "Packaging Unit Kappa"
        ]
        
        # Error codes from Manufacturing Technical Manual
        self.error_codes = [
            "E001", "E004", "E005", "E009", "E010", "E012", "E014", "E018", 
            "E019", "E022", "E023", "E024", "E027", "E030", "E034", "E036", 
            "E037", "E043"
        ]
        
        # Alert templates matching Manufacturing Technical Manual error codes
        self.alert_templates = [
            {
                "title": "Non-volatile Memory Endurance Exceeded",
                "description": "Non-volatile memory write cycles have exceeded rated endurance",
                "severity": AlertSeverity.MEDIUM,
                "error_code": "E001"
            },
            {
                "title": "Motor Overtemperature",
                "description": "Motor temperature exceeded safe operating limits (>155°C). Inadequate cooling or ventilation, overloading conditions, or blocked cooling vents detected.",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E004"
            },
            {
                "title": "IPM Fault",
                "description": "Intelligent Power Module fault condition detected. Power semiconductor failure, overcurrent or short circuit condition, or gate driver circuit malfunction.",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E005"
            },
            {
                "title": "Bus Undervoltage",
                "description": "Bus voltage has dropped below minimum threshold",
                "severity": AlertSeverity.HIGH,
                "error_code": "E009"
            },
            {
                "title": "Bus Overvoltage",
                "description": "Bus voltage has exceeded maximum threshold",
                "severity": AlertSeverity.HIGH,
                "error_code": "E010"
            },
            {
                "title": "Home Search Failed",
                "description": "Automatic home search sequence could not complete successfully",
                "severity": AlertSeverity.HIGH,
                "error_code": "E012"
            },
            {
                "title": "Communications Network Problem",
                "description": "SERCOS or DeviceNet communications network fault detected",
                "severity": AlertSeverity.HIGH,
                "error_code": "E014"
            },
            {
                "title": "Overspeed Fault",
                "description": "Motor speed has exceeded configured maximum limit",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E018"
            },
            {
                "title": "Excess Position Error",
                "description": "Position tracking error has exceeded allowable tolerance",
                "severity": AlertSeverity.HIGH,
                "error_code": "E019"
            },
            {
                "title": "Motor Thermal Protection Fault",
                "description": "Motor thermal protection system has been triggered",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E022"
            },
            {
                "title": "IPM Thermal Protection Fault",
                "description": "Intelligent Power Module thermal protection activated",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E023"
            },
            {
                "title": "Excess Velocity Error",
                "description": "Velocity tracking error has exceeded configured limit",
                "severity": AlertSeverity.HIGH,
                "error_code": "E024"
            },
            {
                "title": "Axis Not Homed",
                "description": "Machine axis has not completed homing sequence",
                "severity": AlertSeverity.MEDIUM,
                "error_code": "E027"
            },
            {
                "title": "Encoder Communication Fault",
                "description": "Communication error with position encoder detected",
                "severity": AlertSeverity.HIGH,
                "error_code": "E030"
            },
            {
                "title": "Ground Fault",
                "description": "Ground fault condition detected in motor circuit. Insulation breakdown in motor windings, moisture ingress, or cable damage exposing conductors.",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E034"
            },
            {
                "title": "Power Circuitry Overtemperature",
                "description": "Power electronics temperature exceeds safe operating range",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E036"
            },
            {
                "title": "AC Line Loss",
                "description": "AC input power supply has been lost or interrupted",
                "severity": AlertSeverity.CRITICAL,
                "error_code": "E037"
            },
            {
                "title": "Drive Enable Input",
                "description": "Drive enable signal has been lost or deactivated",
                "severity": AlertSeverity.MEDIUM,
                "error_code": "E043"
            }
        ]
        
        self.operators = [
            "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson", "Mike Wilson",
            "Lisa Brown", "Tom Anderson", "Emma Davis", "Carlos Rodriguez", "Anna Kim"
        ]
        
        self.technicians = [
            "Bob Miller", "Alice Cooper", "Frank Thompson", "Diana Prince", "Steve Rogers"
        ]
        
        self.products = [
            "Premium Energy Drink 500ml", "Natural Fruit Juice 1L", "Sparkling Water 350ml",
            "Protein Shake 400ml", "Vitamin Water 500ml", "Cold Brew Coffee 300ml"
        ]
    
    def _store_model_as_document(self, doc_id: str, model_instance: Any, doc_type: str, collection_type: str):
        """Converts a Pydantic model to a dict, adds a 'type' field, and stores it."""
        doc = model_instance.dict()
        doc["type"] = doc_type
        self.couchbase_client.store_document(
            doc_id, doc, collection_type=collection_type
        )
    
    def generate_production_lines(self, count: int) -> List[ProductionLine]:
        """Generate sample production lines."""
        production_lines = []
        
        for i in range(count):
            line_id = f"LINE_{i+1:02d}"
            
            production_line = ProductionLine(
                production_line_id=line_id,
                name=f"Production Line {i+1}",
                status=random.choice(list(ProductionLineStatus)),
                machines=[],  # Will be populated when machines are created
                current_product=random.choice(self.products),
                target_output=random.randint(*self.TARGET_OUTPUT_RANGE),
                actual_output=random.randint(*self.ACTUAL_OUTPUT_RANGE),
                efficiency=random.uniform(*self.EFFICIENCY_RANGE),
                shift_supervisor=random.choice(self.operators),
                operators=random.sample(self.operators, random.randint(*self.OPERATORS_PER_LINE_RANGE))
            )
            
            production_lines.append(production_line)
            
            # Store in Couchbase
            self._store_model_as_document(
                f"production_line_{line_id}",
                production_line,
                "production_line",
                "production_lines"
            )
        
        logger.info(f"Generated {len(production_lines)} production lines")
        return production_lines
    
    def generate_machines(self, production_lines: List[ProductionLine]) -> List[Machine]:
        """Generate sample machines for production lines."""
        machines = []
        machine_id_counter = 1
        
        for line in production_lines:
            # Generate 2-3 machines per production line
            machines_per_line = random.randint(self.MIN_MACHINES_PER_LINE, self.MAX_MACHINES_PER_LINE)
            line_machines = []
            
            for _ in range(machines_per_line):
                machine_id = f"MCH_{machine_id_counter:03d}"
                machine_type = random.choice(list(MachineType))
                
                # Special case for Ultima SV machines
                if random.random() < self.ULTIMA_SV_CHANCE:
                    machine_type = MachineType.ULTIMA_SV
                
                machine = Machine(
                    machine_id=machine_id,
                    machine_type=machine_type,
                    production_line_id=line.production_line_id,
                    name=self.machine_names[machine_id_counter % len(self.machine_names)],
                    model=f"{machine_type.value}_Model_{random.randint(100, 999)}",
                    serial_number=f"SN{random.randint(100000, 999999)}",
                    installation_date=datetime.utcnow() - timedelta(days=random.randint(*self.INSTALLATION_DAYS_AGO_RANGE)),
                    last_maintenance=datetime.utcnow() - timedelta(days=random.randint(*self.LAST_MAINTENANCE_DAYS_AGO_RANGE)),
                    next_maintenance=datetime.utcnow() + timedelta(days=random.randint(*self.NEXT_MAINTENANCE_DAYS_AHEAD_RANGE)),
                    current_status=random.choice(self.MACHINE_STATUSES),
                    operating_parameters={
                        "temperature": random.uniform(20.0, 80.0),
                        "pressure": random.uniform(1.0, 10.0),
                        "speed": random.uniform(100.0, 2000.0),
                        "vibration": random.uniform(0.1, 5.0),
                        "power_consumption": random.uniform(50.0, 500.0)
                    },
                    specifications={
                        "max_temperature": 85.0,
                        "max_pressure": 12.0,
                        "max_speed": 2500.0,
                        "max_vibration": 6.0,
                        "power_rating": 600.0
                    }
                )
                
                machines.append(machine)
                line_machines.append(machine_id)
                machine_id_counter += 1
                
                # Store in Couchbase
                self._store_model_as_document(
                    f"machine_{machine_id}",
                    machine,
                    "machine",
                    "machines"
                )
            
            # Update production line with machine IDs
            line.machines = line_machines
            self._store_model_as_document(
                f"production_line_{line.production_line_id}",
                line,
                "production_line",
                "production_lines"
            )
        
        logger.info(f"Generated {len(machines)} machines")
        return machines
    
    def generate_alerts(self, machines: List[Machine], count: int) -> List[Alert]:
        """Generate sample alerts for machines."""
        alerts = []
        
        for _ in range(count):
            machine = random.choice(machines)
            alert_template = random.choice(self.alert_templates)
            
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                machine_id=machine.machine_id,
                production_line_id=machine.production_line_id,
                severity=alert_template["severity"],
                status=random.choice(list(AlertStatus)),
                title=alert_template["title"],
                description=alert_template["description"],
                error_code=alert_template["error_code"],
                timestamp=datetime.utcnow() - timedelta(
                    hours=random.randint(0, 72),
                    minutes=random.randint(0, 59)
                ),
                acknowledged_by=random.choice(self.operators) if random.random() > 0.3 else None,
                resolved_by=random.choice(self.operators) if random.random() > 0.5 else None,
                resolution_time=datetime.utcnow() - timedelta(
                    hours=random.randint(0, 24)
                ) if random.random() > 0.5 else None,
                parameters={
                    "temperature": random.uniform(20.0, 100.0),
                    "pressure": random.uniform(0.5, 15.0),
                    "speed": random.uniform(50.0, 3000.0)
                }
            )
            
            alerts.append(alert)
            
            # Store in Couchbase
            self._store_model_as_document(
                f"alert_{alert.alert_id}",
                alert,
                "alert",
                "alerts"
            )
        
        logger.info(f"Generated {len(alerts)} alerts")
        return alerts
    
    def generate_maintenance_records(self, machines: List[Machine], count: int) -> List[MaintenanceRecord]:
        """Generate sample maintenance records."""
        maintenance_records = []
        
        maintenance_types = [
            "Preventive Maintenance", "Corrective Maintenance", "Emergency Repair",
            "Calibration", "Cleaning", "Lubrication", "Belt Replacement",
            "Filter Change", "Software Update", "Safety Inspection"
        ]
        
        parts_inventory = [
            "Oil Filter", "Air Filter", "Belt Drive", "Bearing Set", "Gasket Kit",
            "Hydraulic Fluid", "Motor Coupling", "Temperature Sensor", "Pressure Valve",
            "Control Board", "Fan Assembly", "Power Cable", "Fuse Set"
        ]
        
        for _ in range(count):
            machine = random.choice(machines)
            maintenance_id = str(uuid.uuid4())
            
            scheduled_date = datetime.utcnow() - timedelta(days=random.randint(0, 90))
            started_date = scheduled_date + timedelta(hours=random.randint(0, 24))
            completed_date = started_date + timedelta(hours=random.randint(1, 8)) if random.random() > 0.2 else None
            
            maintenance_record = MaintenanceRecord(
                maintenance_id=maintenance_id,
                machine_id=machine.machine_id,
                maintenance_type=random.choice(maintenance_types),
                status=random.choice(list(MaintenanceStatus)),
                scheduled_date=scheduled_date,
                started_date=started_date if random.random() > 0.1 else None,
                completed_date=completed_date,
                technician=random.choice(self.technicians),
                description=f"Routine maintenance for {machine.name}",
                parts_used=random.sample(parts_inventory, random.randint(0, 3)),
                cost=random.uniform(100.0, 2000.0),
                notes=f"Maintenance performed successfully. Next service in {random.randint(30, 90)} days.",
                follow_up_required=random.random() < 0.2
            )
            
            maintenance_records.append(maintenance_record)
            
            # Store in Couchbase
            self._store_model_as_document(
                f"maintenance_{maintenance_id}",
                maintenance_record,
                "maintenance_record",
                "maintenance"
            )
        
        logger.info(f"Generated {len(maintenance_records)} maintenance records")
        return maintenance_records
    
    def generate_production_metrics(self, production_lines: List[ProductionLine], days: int) -> List[ProductionMetrics]:
        """Generate sample production metrics."""
        metrics = []
        
        for line in production_lines:
            for day in range(days):
                for shift in range(3):  # 3 shifts per day
                    timestamp = datetime.utcnow() - timedelta(
                        days=day,
                        hours=shift * 8
                    )
                    
                    target_units = random.randint(800, 1200)
                    units_produced = random.randint(int(target_units * 0.7), int(target_units * 1.1))
                    efficiency = (units_produced / target_units) * 100
                    
                    metric = ProductionMetrics(
                        line_id=line.production_line_id,
                        timestamp=timestamp,
                        units_produced=units_produced,
                        target_units=target_units,
                        efficiency=efficiency,
                        quality_rate=random.uniform(95.0, 99.5),
                        downtime_minutes=random.randint(0, 60),
                        oee=random.uniform(75.0, 95.0),
                        reject_count=random.randint(0, 20),
                        energy_consumption=random.uniform(100.0, 500.0)
                    )
                    
                    metrics.append(metric)
                    
                    # Store in Couchbase
                    self._store_model_as_document(
                        f"metrics_{line.production_line_id}_{timestamp.strftime('%Y%m%d_%H%M')}",
                        metric,
                        "production_metrics",
                        "metrics"
                    )
        
        logger.info(f"Generated {len(metrics)} production metrics")
        return metrics
    
    def generate_all_sample_data(self) -> Dict[str, Any]:
        """Generate all sample data for the demo."""
        logger.info("Starting sample data generation...")
        
        # Generate production lines
        production_lines = self.generate_production_lines(self.NUM_PRODUCTION_LINES)
        
        # Generate machines
        machines = self.generate_machines(production_lines)
        
        # Generate alerts
        alerts = self.generate_alerts(machines, self.NUM_ALERTS)
        
        # Generate maintenance records
        maintenance_records = self.generate_maintenance_records(machines, self.NUM_MAINTENANCE_RECORDS)
        
        # Generate production metrics
        production_metrics = self.generate_production_metrics(production_lines, self.NUM_METRIC_DAYS)
        
        summary = {
            "production_lines": len(production_lines),
            "machines": len(machines),
            "alerts": len(alerts),
            "maintenance_records": len(maintenance_records),
            "production_metrics": len(production_metrics)
        }
        
        logger.info(f"Sample data generation complete: {summary}")
        return summary 