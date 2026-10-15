"""Auth routes: login, refresh (rotation), logout, admin-gated user register, me."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..errors import ApiError
from ..models import User
from ..schemas import LoginIn, MeOut, RefreshIn, RegisterIn, TokenPair, UserOut
from . import service
from .deps import Actor, get_actor

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
async def login(body: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
	user, access, refresh = await service.login(db, body.email, body.password)
	await db.commit()  # persist the issued refresh token
	return TokenPair(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
	user, raw = await service.rotate_refresh(db, body.refresh_token)
	await db.commit()  # persist the rotation: old revoked, new live
	return TokenPair(
		access_token=service.create_access_token(user), refresh_token=raw, user=UserOut.model_validate(user)
	)


@router.post("/logout", status_code=204)
async def logout(body: RefreshIn, db: AsyncSession = Depends(get_db)) -> None:
	await service.revoke_refresh(db, body.refresh_token)
	await db.commit()


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
	body: RegisterIn,
	actor: Actor = Depends(get_actor),
	db: AsyncSession = Depends(get_db),
) -> User:
	if actor.role != "admin":  # user management is admin-only; not in the entity matrix
		raise ApiError(403, "permission_denied", "Only admins may create users")
	user = User(
		email=body.email,
		password_hash=service.hash_password(body.password),
		full_name=body.full_name,
		role=body.role,
	)
	db.add(user)
	await db.flush()  # surface duplicate_email here, not at commit
	await db.commit()
	await db.refresh(user)
	return user


@router.get("/me", response_model=MeOut)
async def me(actor: Actor = Depends(get_actor)) -> MeOut:
	out = MeOut.model_validate(actor.user)
	out.scholar_id = actor.scholar_id
	out.supervisor_id = actor.supervisor_id
	return out