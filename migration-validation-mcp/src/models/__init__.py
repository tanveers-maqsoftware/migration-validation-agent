"""
Pydantic models for migration validation agent.

Defines data structures for reports, visuals, validation results, and comparisons.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Visual(BaseModel):
    """Represents a single visual/chart in a report."""
    visual_id: str = Field(..., description="Unique identifier for the visual")
    visual_type: str = Field(..., description="Type of visual (e.g., bar_chart, line_chart, pie, table, etc.)")
    title: str = Field(..., description="Title or name of the visual")
    page_name: str = Field(..., description="Name of the page containing this visual")
    platform: str = Field(..., description="Platform source (tableau or powerbi)")
    url: str = Field(..., description="URL where this visual is located")
    
    # Data extraction fields
    data_values: Dict[str, Any] = Field(default_factory=dict, description="Extracted data values from the visual")
    filters_applied: List[Dict[str, Any]] = Field(default_factory=list, description="Filters applied to this visual")
    
    # Layout/position fields
    position: Optional[Dict[str, float]] = Field(default=None, description="Position coordinates {x, y, width, height}")
    scrollable: bool = Field(default=False, description="Whether the visual has scrollable content")
    
    # Validation metadata
    extraction_method: str = Field(default="tooltip", description="Method used to extract data (tooltip, screenshot, evaluate)")
    extraction_timestamp: Optional[str] = Field(default=None, description="Timestamp of data extraction")
    
    def __str__(self) -> str:
        return f"Visual({self.visual_id}, {self.visual_type}, {self.title}, {self.platform})"


class Page(BaseModel):
    """Represents a page in a report containing multiple visuals."""
    page_name: str = Field(..., description="Name of the page")
    page_url: str = Field(..., description="URL of the page")
    platform: str = Field(..., description="Platform (tableau or powerbi)")
    
    visuals: List[Visual] = Field(default_factory=list, description="List of visuals on this page")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Page-level filters")
    
    # Layout validation
    screenshot_path: Optional[str] = Field(default=None, description="Path to page screenshot")
    layout_valid: Optional[bool] = Field(default=None, description="Whether layout validation passed")
    
    def add_visual(self, visual: Visual) -> None:
        """Add a visual to this page."""
        visual.page_name = self.page_name
        self.visuals.append(visual)
    
    def get_visual_count(self) -> int:
        """Return number of visuals on this page."""
        return len(self.visuals)
    
    def __str__(self) -> str:
        return f"Page({self.page_name}, {self.platform}, {self.get_visual_count()} visuals)"


class Report(BaseModel):
    """Represents a complete report (Tableau or Power BI)."""
    report_name: str = Field(..., description="Name of the report")
    report_url: str = Field(..., description="URL of the report")
    platform: str = Field(..., description="Platform (tableau or powerbi)")
    
    pages: List[Page] = Field(default_factory=list, description="List of pages in the report")
    
    # Report-level metadata
    total_visuals: int = Field(default=0, description="Total number of visuals across all pages")
    extraction_complete: bool = Field(default=False, description="Whether data extraction is complete")
    
    def add_page(self, page: Page) -> None:
        """Add a page to this report."""
        page.platform = self.platform
        self.pages.append(page)
        self.total_visuals += page.get_visual_count()
    
    def get_total_pages(self) -> int:
        """Return number of pages in this report."""
        return len(self.pages)
    
    def __str__(self) -> str:
        return f"Report({self.report_name}, {self.platform}, {self.get_total_pages()} pages, {self.total_visuals} visuals)"


class ValidationResult(BaseModel):
    """Represents the validation result for a single visual comparison."""
    visual_id: str = Field(..., description="ID of the visual being validated")
    visual_title: str = Field(..., description="Title of the visual")
    page_name: str = Field(..., description="Page containing the visual")
    
    # Comparison data
    tableau_visual: Optional[Visual] = Field(default=None, description="Tableau visual data")
    powerbi_visual: Optional[Visual] = Field(default=None, description="Power BI visual data")
    
    # Validation outcome
    status: str = Field(..., description="Validation status: Pass, Warning, Fail, Error")
    variance_percentage: float = Field(default=0.0, description="Percentage variance between values")
    
    # Details
    message: str = Field(default="", description="Human-readable validation message")
    root_cause: Optional[str] = Field(default=None, description="AI-analyzed root cause of variance")
    
    # Filter validation
    filters_match: bool = Field(default=True, description="Whether filters match between platforms")
    filter_differences: List[Dict[str, Any]] = Field(default_factory=list, description="Filter differences found")
    
    # Data comparison
    data_points_compared: int = Field(default=0, description="Number of data points compared")
    data_points_matched: int = Field(default=0, description="Number of data points that matched")
    
    # Screenshot evidence
    tableau_screenshot_path: Optional[str] = Field(default=None, description="Path to Tableau screenshot")
    powerbi_screenshot_path: Optional[str] = Field(default=None, description="Path to Power BI screenshot")
    
    def is_passed(self) -> bool:
        """Check if validation passed (Pass or Warning)."""
        return self.status in ["Pass", "Warning"]
    
    def is_failed(self) -> bool:
        """Check if validation failed."""
        return self.status in ["Fail", "Error"]
    
    def __str__(self) -> str:
        return f"ValidationResult({self.visual_id}, {self.status}, {self.variance_percentage:.2f}% variance)"


class Comparison(BaseModel):
    """Represents a complete comparison between Tableau and Power BI reports."""
    comparison_id: str = Field(..., description="Unique ID for this comparison")
    report_name: str = Field(..., description="Name of the report being compared")
    
    # Source reports
    tableau_report: Optional[Report] = Field(default=None, description="Tableau report data")
    powerbi_report: Optional[Report] = Field(default=None, description="Power BI report data")
    
    # Validation results
    validation_results: List[ValidationResult] = Field(default_factory=list, description="List of visual validation results")
    
    # Summary statistics
    total_visuals_compared: int = Field(default=0, description="Total visuals compared")
    passed_count: int = Field(default=0, description="Number of visuals that passed")
    warning_count: int = Field(default=0, description="Number of visuals with warnings")
    failed_count: int = Field(default=0, description="Number of visuals that failed")
    error_count: int = Field(default=0, description="Number of visuals with errors")
    
    # Completeness check
    tableau_visual_count: int = Field(default=0, description="Total visuals in Tableau report")
    powerbi_visual_count: int = Field(default=0, description="Total visuals in Power BI report")
    visual_count_match: bool = Field(default=False, description="Whether visual counts match")
    
    # Report output
    report_path: Optional[str] = Field(default=None, description="Path to generated Word report")
    comparison_timestamp: Optional[str] = Field(default=None, description="Timestamp of comparison")
    
    def add_validation_result(self, result: ValidationResult) -> None:
        """Add a validation result and update counts."""
        self.validation_results.append(result)
        self.total_visuals_compared += 1
        
        if result.status == "Pass":
            self.passed_count += 1
        elif result.status == "Warning":
            self.warning_count += 1
        elif result.status == "Fail":
            self.failed_count += 1
        elif result.status == "Error":
            self.error_count += 1
    
    def get_pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_visuals_compared == 0:
            return 0.0
        return ((self.passed_count + self.warning_count) / self.total_visuals_compared) * 100
    
    def __str__(self) -> str:
        return f"Comparison({self.comparison_id}, {self.report_name}, {self.total_visuals_compared} visuals, {self.get_pass_rate():.1f}% pass rate)"


# Export all model classes for easy imports
__all__ = [
    "Visual",
    "Page",
    "Report",
    "ValidationResult",
    "Comparison"
]
