from __future__ import annotations

from fastapi import APIRouter, Response
import tortoise.exceptions
from tortoise.expressions import F

from pwncore.config import config
from pwncore.models import (
    R2Container,
    R2Container_Pydantic,
    MetaTeam_Pydantic,
    MetaTeam,
    Team,
)
from pwncore.routes.auth import RequireJwt
from pwncore.routes.ctf import Flag

metadata = {
    "name": "round2",
    "decription": "Operations related to an attack defense round",
}

router = APIRouter(prefix="/round2", tags=["round2"])


@router.get("/list")
async def r2ctf_list():
    return await R2Container_Pydantic.from_queryset(
        R2Container.all().prefetch_related("problem", "ports")
    )


@router.get("/meta_lb")
async def r2_meta_lb():
    return await MetaTeam_Pydantic.from_queryset(MetaTeam.all())


@router.post("/{container_id}/flag")
async def r2_submit(container_id: int, flag: Flag, jwt: RequireJwt, response: Response):
    team_id = jwt["team_id"]
    try:
        container = await R2Container.get(id=container_id).prefetch_related(
            "meta_team", "problem"
        )
    except tortoise.exceptions.DoesNotExist:
        response.status_code = 404
        return {"msg_code": config.msg_codes["ctf_not_found"]}

    if container.solved:
        response.status_code = 401
        return {"msg_code": config.msg_codes["ctf_solved"]}

    team = await Team.get(id=team_id).prefetch_related("meta_team")

    if team.meta_team is None:
        response.status_code = 401
        return ""

    if container.flag != flag.flag:
        return {"status": False}

    if team.meta_team == container.meta_team:
        container.solved = True
        await container.save()
        return {"status": True, "action": "defend"}
    else:
        # Valid type error but we dont use this object again
        team.points = F("points") + round(container.problem.points / 4)  # type: ignore[unused-ignore]
        await team.save(update_fields=["points"])
        team.meta_team.points = F("points") + container.problem.points  # type: ignore[unused-ignore]
        await team.meta_team.save(update_fields=["points"])
        return {"status": True, "action": "attack"}
