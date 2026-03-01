"""Rules upload endpoint."""

import shutil
import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.config.ba_rules_template_converter import BARulesTemplateConverter
from src.config.rules_template_converter import RulesTemplateConverter

router = APIRouter()

RULES_DIR = Path("config/rules")
RULES_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_rules_template(
    file: UploadFile = File(...),
    rules_name: str = Query(None, description="Name for the rules config"),
    rules_type: str = Query("ba_friendly", description="ba_friendly or technical"),
):
    """Upload Excel/CSV rules template and convert to rules JSON."""
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .csv files are supported.")

    upload_path = UPLOADS_DIR / file.filename
    with open(upload_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        if rules_type == "technical":
            converter = RulesTemplateConverter()
        else:
            converter = BARulesTemplateConverter()

        if file.filename.endswith((".xlsx", ".xls")):
            converter.from_excel(str(upload_path))
        else:
            converter.from_csv(str(upload_path))

        rules_id = rules_name or Path(file.filename).stem
        if hasattr(converter, "rules_config") and converter.rules_config:
            converter.rules_config.setdefault("metadata", {})["name"] = rules_id

        output_path = RULES_DIR / f"{rules_id}.json"
        converter.save(str(output_path))

        return {
            "rules_id": rules_id,
            "filename": file.filename,
            "size": upload_path.stat().st_size,
            "message": f"Rules template converted and created successfully. Rules saved as '{rules_id}'",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting rules template: {str(e)}")

    finally:
        if upload_path.exists():
            upload_path.unlink()
