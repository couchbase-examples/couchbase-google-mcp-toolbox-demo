from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class MaintenanceStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"

class ProductionLineStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    ERROR = "error"

class MachineType(str, Enum):
    ULTIMA_SV = "Ultima_SV"
    CONVEYOR = "Conveyor"
    PACKAGING = "Packaging"
    QUALITY_CONTROL = "Quality_Control"
    FILLER = "Filler"

class Alert(BaseModel):
    """Manufacturing alert model."""
    alert_id: str = Field(..., description="Unique alert identifier")
    machine_id: str = Field(..., description="Machine that generated the alert")
    production_line_id: str = Field(..., description="Production line identifier")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(default=AlertStatus.ACTIVE, description="Current alert status")
    solution_comment: str = Field(..., description="Recommended resolution steps or comment for the alert")
    error_code: Optional[str] = Field(None, description="Machine error code if applicable")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Alert timestamp")
    acknowledged_by: Optional[str] = Field(None, description="Operator who acknowledged the alert")
    resolved_by: Optional[str] = Field(None, description="Operator who resolved the alert")
    resolution_time: Optional[datetime] = Field(None, description="Time when alert was resolved")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional alert parameters")

class Machine(BaseModel):
    """Manufacturing machine model."""
    machine_id: str = Field(..., description="Unique machine identifier")
    machine_type: MachineType = Field(..., description="Type of machine")
    production_line_id: str = Field(..., description="Production line where machine is located")
    name: str = Field(..., description="Human-readable machine name")
    model: str = Field(..., description="Machine model")
    serial_number: str = Field(..., description="Machine serial number")
    installation_date: datetime = Field(..., description="Date machine was installed")
    last_maintenance: Optional[datetime] = Field(None, description="Last maintenance date")
    next_maintenance: Optional[datetime] = Field(None, description="Next scheduled maintenance")
    current_status: str = Field(default="operational", description="Current machine status")
    operating_parameters: Dict[str, Any] = Field(default_factory=dict, description="Current operating parameters")
    specifications: Dict[str, Any] = Field(default_factory=dict, description="Machine specifications")

class ProductionLine(BaseModel):
    """Production line model."""
    production_line_id: str = Field(..., description="Unique production line identifier")
    name: str = Field(..., description="Production line name")
    status: ProductionLineStatus = Field(..., description="Current line status")
    machines: List[str] = Field(default_factory=list, description="List of machine IDs on this line")
    current_product: Optional[str] = Field(None, description="Product currently being manufactured")
    target_output: Optional[int] = Field(None, description="Target units per hour")
    actual_output: Optional[int] = Field(None, description="Actual units per hour")
    efficiency: Optional[float] = Field(None, description="Current efficiency percentage")
    shift_supervisor: Optional[str] = Field(None, description="Current shift supervisor")
    operators: List[str] = Field(default_factory=list, description="List of operators on this line")

class MaintenanceRecord(BaseModel):
    """Maintenance record model."""
    maintenance_id: str = Field(..., description="Unique maintenance record identifier")
    machine_id: str = Field(..., description="Machine being maintained")
    maintenance_type: str = Field(..., description="Type of maintenance (preventive, corrective, etc.)")
    status: MaintenanceStatus = Field(..., description="Maintenance status")
    scheduled_date: datetime = Field(..., description="Scheduled maintenance date")
    started_date: Optional[datetime] = Field(None, description="Actual start date")
    completed_date: Optional[datetime] = Field(None, description="Actual completion date")
    technician: str = Field(..., description="Technician performing maintenance")
    description: str = Field(..., description="Maintenance description")
    parts_used: List[str] = Field(default_factory=list, description="Parts used during maintenance")
    cost: Optional[float] = Field(None, description="Maintenance cost")
    notes: Optional[str] = Field(None, description="Additional maintenance notes")
    follow_up_required: bool = Field(default=False, description="Whether follow-up is required")

class OperatorQuery(BaseModel):
    """Operator query to the AI assistant."""
    query_id: str = Field(..., description="Unique query identifier")
    operator_id: str = Field(..., description="Operator making the query")
    query_text: str = Field(..., description="The operator's question or issue")
    query_type: str = Field(..., description="Type of query (troubleshooting, maintenance, etc.)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

class AIResponse(BaseModel):
    """AI assistant response model."""
    response_id: str = Field(..., description="Unique response identifier")
    query_id: str = Field(..., description="ID of the query being answered")
    response_text: str = Field(..., description="AI response text")

class ProductionMetrics(BaseModel):
    """Production metrics model."""
    line_id: str = Field(..., description="Production line identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Metrics timestamp")
    units_produced: int = Field(..., description="Units produced in time period")
    target_units: int = Field(..., description="Target units for time period")
    efficiency: float = Field(..., description="Efficiency percentage")
    quality_rate: float = Field(..., description="Quality rate percentage")
    downtime_minutes: int = Field(default=0, description="Downtime in minutes")
    oee: float = Field(..., description="Overall Equipment Effectiveness")
    reject_count: int = Field(default=0, description="Number of rejected units")
    energy_consumption: Optional[float] = Field(None, description="Energy consumption")

class ShiftReport(BaseModel):
    """Shift report model."""
    shift_id: str = Field(..., description="Unique shift identifier")
    production_line_id: str = Field(..., description="Production line identifier")
    shift_start: datetime = Field(..., description="Shift start time")
    shift_end: datetime = Field(..., description="Shift end time")
    supervisor: str = Field(..., description="Shift supervisor")
    operators: List[str] = Field(..., description="Operators on shift")
    production_metrics: ProductionMetrics = Field(..., description="Production metrics for shift")
    alerts_generated: int = Field(default=0, description="Number of alerts during shift")
    maintenance_performed: List[str] = Field(default_factory=list, description="Maintenance activities")
    issues_encountered: List[str] = Field(default_factory=list, description="Issues during shift")
    notes: Optional[str] = Field(None, description="Additional shift notes") 