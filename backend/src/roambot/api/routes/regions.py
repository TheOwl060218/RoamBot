from fastapi import APIRouter

from roambot.domain.regions import region_catalog

router = APIRouter()


@router.get('/regions')
def get_regions() -> dict:
    return region_catalog()
