import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
import json
from pathlib import Path
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
    NUM_ALERTS = 80
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
    
    # --- Data Templates ---
    MACHINE_NAMES = [
        "Primary Filler Alpha", "Secondary Filler Beta", "Quality Checker Gamma",
        "Conveyor Delta", "Packaging Unit Epsilon", "Ultima SV Zeta",
        "Conveyor Eta", "Quality Checker Theta", "Primary Filler Iota",
        "Packaging Unit Kappa"
    ]
    
    ERROR_CODES = [
        "E001", "E004", "E005", "E009", "E010", "E012", "E014", "E018", 
        "E019", "E022", "E023", "E024", "E027", "E030", "E034", "E036", 
        "E037", "E043"
    ]
    
    OPERATORS = [
        "John Smith", "Maria Garcia", "David Chen", "Sarah Johnson", "Mike Wilson",
        "Lisa Brown", "Tom Anderson", "Emma Davis", "Carlos Rodriguez", "Anna Kim"
    ]
    
    TECHNICIANS = [
        "Bob Miller", "Alice Cooper", "Frank Thompson", "Diana Prince", "Steve Rogers"
    ]
    
    PRODUCTS = [
        "Premium Energy Drink 500ml", "Natural Fruit Juice 1L", "Sparkling Water 350ml",
        "Protein Shake 400ml", "Vitamin Water 500ml", "Cold Brew Coffee 300ml"
    ]
    
    def __init__(self, couchbase_client: CouchbaseClient):
        self.couchbase_client = couchbase_client
        self.alert_templates = self._load_alert_templates()
    
    def _load_alert_templates(self) -> List[Dict[str, Any]]:
        """Load alert templates from external JSON file."""
        try:
            template_path = Path(__file__).with_name("alert_templates.json")
            with template_path.open("r", encoding="utf-8") as f:
                templates_raw = json.load(f)

            # Convert severity strings to AlertSeverity enum members
            templates = [
                {
                    **tpl,
                    "severity": AlertSeverity[tpl["severity"].upper()]
                }
                for tpl in templates_raw
            ]
            logger.info(f"Loaded {len(templates)} alert templates from {template_path.name}")
            return templates
        except Exception as exc:
            logger.error(f"Failed to load alert templates JSON: {exc}")
            return []
    
    def _store_model_as_document(self, doc_id: str, model_instance: Any, collection_type: str):
        """Convert a Pydantic model to a dict, remove its identifier field, and store it.

        The unique identifier value is already supplied as the document key (``doc_id``),
        so we strip it from the document body before persisting. This keeps the payload
        clean and avoids redundant data.
        """
        # Convert the model to a plain dict first
        doc = model_instance.dict()

        id_field = "id"
        if id_field:
            doc.pop(id_field, None)  # Remove the id field if present

        # Persist the document using the provided key
        self.couchbase_client.store_document(
            doc_id,
            doc,
            collection_type=collection_type,
        )
    
    def _create_production_line(self, line_number: int) -> ProductionLine:
        """Create a single production line."""
        line_id = f"LINE_{line_number:02d}"
        
        return ProductionLine(
            id=line_id,
            name=f"Production Line {line_number}",
            status=random.choice(list(ProductionLineStatus)),
            machines=[],  # Will be populated when machines are created
            current_product=random.choice(self.PRODUCTS),
            target_output=random.randint(*self.TARGET_OUTPUT_RANGE),
            actual_output=random.randint(*self.ACTUAL_OUTPUT_RANGE),
            efficiency=random.uniform(*self.EFFICIENCY_RANGE),
            shift_supervisor=random.choice(self.OPERATORS),
            operators=random.sample(self.OPERATORS, random.randint(*self.OPERATORS_PER_LINE_RANGE))
        )
    
    def _create_machine(self, machine_id_counter: int, production_line_id: str) -> Machine:
        """Create a single machine."""
        machine_id = f"MCH_{machine_id_counter:03d}"
        machine_type = random.choice(list(MachineType))
        
        # Special case for Ultima SV machines
        if random.random() < self.ULTIMA_SV_CHANCE:
            machine_type = MachineType.ULTIMA_SV
        
        return Machine(
            id=machine_id,
            machine_type=machine_type,
            production_line_id=production_line_id,
            name=self.MACHINE_NAMES[machine_id_counter % len(self.MACHINE_NAMES)],
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
    
    def generate_production_lines(self, count: int) -> List[ProductionLine]:
        """Generate sample production lines."""
        production_lines = []
        
        for i in range(count):
            production_line = self._create_production_line(i + 1)
            production_lines.append(production_line)
            
            # Store in Couchbase
            self._store_model_as_document(
                production_line.id,
                production_line,
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
                machine = self._create_machine(machine_id_counter, line.id)
                machines.append(machine)
                line_machines.append(machine.id)
                
                # Store in Couchbase
                self._store_model_as_document(
                    machine.id,
                    machine,
                    "machines"
                )
                
                machine_id_counter += 1
            
            # Update production line with machine IDs
            line.machines = line_machines
            self._store_model_as_document(
                line.id,
                line,
                "production_lines"
            )
        
        logger.info(f"Generated {len(machines)} machines")
        return machines
    
    def generate_alerts(self, machines: List[Machine], count: int) -> List[Alert]:
        """Generate sample alerts for machines."""
        if not self.alert_templates:
            logger.warning("No alert templates available, skipping alert generation")
            return []
        
        alerts = []
        
        for _ in range(count):
            machine = random.choice(machines)
            alert_template = random.choice(self.alert_templates)
            
            alert = Alert(
                id=str(uuid.uuid4()),
                machine_id=machine.id,
                production_line_id=machine.production_line_id,
                severity=alert_template["severity"],
                status=random.choice(list(AlertStatus)),
                solution_comment=alert_template["solution_comment"],
                error_code=alert_template["error_code"],
                timestamp=datetime.utcnow() - timedelta(
                    hours=random.randint(0, 72),
                    minutes=random.randint(0, 59)
                ),
                acknowledged_by=random.choice(self.OPERATORS) if random.random() > 0.3 else None,
                resolved_by=random.choice(self.OPERATORS) if random.random() > 0.5 else None,
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
                alert.id,
                alert,
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
                id=maintenance_id,
                machine_id=machine.id,
                maintenance_type=random.choice(maintenance_types),
                status=random.choice(list(MaintenanceStatus)),
                scheduled_date=scheduled_date,
                started_date=started_date if random.random() > 0.1 else None,
                completed_date=completed_date,
                technician=random.choice(self.TECHNICIANS),
                description=f"Routine maintenance for {machine.name}",
                parts_used=random.sample(parts_inventory, random.randint(0, 3)),
                cost=random.uniform(100.0, 2000.0),
                notes=f"Maintenance performed successfully. Next service in {random.randint(30, 90)} days.",
                follow_up_required=random.random() < 0.2
            )
            
            maintenance_records.append(maintenance_record)
            
            # Store in Couchbase
            self._store_model_as_document(
                maintenance_id,
                maintenance_record,
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
                        line_id=line.id,
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
                        f"{line.id}_{timestamp.strftime('%Y%m%d_%H%M')}",
                        metric,
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