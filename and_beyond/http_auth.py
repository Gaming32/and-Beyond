import binascii
from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from aiohttp.client import ClientSession
from aiohttp.client_exceptions import ClientResponseError
from aiohttp.client_reqrep import ClientResponse
from aiohttp.typedefs import StrOrURL
from yarl import URL

from and_beyond.common import AUTH_SERVER
from and_beyond.http_errors import SERVER_ERRORS, InsecureAuth


async def _check_error(resp: ClientResponse) -> None:
    def raise_for_status_none():
        '"from None" version of raise_for_status'
        raise ClientResponseError(
            resp.request_info,
            resp.history,
            status=resp.status,
            message=resp.reason,
            headers=resp.headers,
        ) from None
    if resp.status < 400:
        return
    try:
        json: dict[str, Any] = await resp.json()
    except Exception:
        raise_for_status_none()
    if 'type' not in json:
        raise_for_status_none()
    exc_type = SERVER_ERRORS.get(json['type'])
    if exc_type is None:
        raise_for_status_none()
    raise exc_type(json.get('human', None), json.get('args', None), resp.status)


class User:
    uuid: UUID
    username: str

    def __init__(self, uuid: UUID, username: str) -> None:
        self.uuid = uuid
        self.username = username

    @classmethod
    def from_json(cls, json: dict[str, Any]):
        return cls(
            UUID(json['uuid']),
            json['username'],
        )


class AuthenticatedUser(User):
    token: str
    client: '_AuthClient'

    def __init__(self, client: '_AuthClient', token: str, uuid: UUID, username: str) -> None:
        super().__init__(uuid, username)
        self.client = client
        self.token = token

    @classmethod
    def from_json(cls, client: '_AuthClient', json: dict[str, Any]):
        return cls(
            client,
            json['token'],
            UUID(json['uuid']),
            json['username'],
        )

    async def logout(self) -> None:
        return await self.client.logout(self.token)

    async def update(self,
            username: Optional[str] = None,
            password: Optional[str] = None
        ) -> int:
        return await self.client.update_profile(self.token, username, password)

    async def delete_user(self):
        return await self.client.delete_user(self.token)


class _AuthClient:
    client: 'AuthClient'

    def __init__(self, client: 'AuthClient') -> None:
        self.client = client

    @property
    def sess(self) -> ClientSession:
        return self.client.sess

    @property
    def root(self) -> URL:
        return self.client.server / 'auth'

    async def _login(self, route: str, username: str, password: str) -> AuthenticatedUser:
        async with self.sess.post(self.root / route, json={
            'username': username,
            'password': password,
        }) as resp:
            await _check_error(resp)
            return AuthenticatedUser.from_json(self, await resp.json())

    async def login(self, username: str, password: str) -> AuthenticatedUser:
        return await self._login('login', username, password)

    async def logout(self, token: str) -> None:
        async with self.sess.get(self.root / 'logout' / token) as resp:
            await _check_error(resp)

    async def create_user(self, username: str, password: str) -> AuthenticatedUser:
        return await self._login('create-user', username, password)

    async def get_profile(self, token: str) -> AuthenticatedUser:
        async with self.sess.get(self.root / 'profile' / token) as resp:
            await _check_error(resp)
            json = await resp.json()
            json['token'] = token
            return AuthenticatedUser.from_json(self, json)

    async def update_profile(self,
            token: str,
            username: Optional[str] = None,
            password: Optional[str] = None
        ) -> int:
        payload = {}
        if username is not None:
            payload['username'] = username
        if password is not None:
            payload['password'] = password
        async with self.sess.post(self.root / 'profile' / token, json=payload) as resp:
            await _check_error(resp)
            return (await resp.json())['changes']

    async def _simple_json_user(self, url: URL) -> User:
        async with self.sess.delete(url) as resp:
            await _check_error(resp)
            return User.from_json(await resp.json())

    async def delete_user(self, token: str) -> User:
        return await self._simple_json_user(self.root / 'profile' / token)

    async def get_by_uuid(self, uuid: UUID) -> User:
        return await self._simple_json_user(self.root / 'uuid' / str(uuid))

    async def get_by_username(self, username: str) -> User:
        return await self._simple_json_user(self.root / 'username' / username)


class Session:
    public_key: bytes
    expiry: datetime
    user: User

    def __init__(self, public_key: bytes, expiry: datetime, user: User) -> None:
        self.public_key = public_key
        self.expiry = expiry
        self.user = user

    @classmethod
    def from_json(cls, json: dict[str, Any]):
        return cls(
            binascii.a2b_base64(json['public_key']),
            datetime.fromisoformat(json['expiry']),
            User.from_json(json['user']),
        )


class _SessionClient:
    client: 'AuthClient'

    def __init__(self, client: 'AuthClient') -> None:
        self.client = client

    @property
    def sess(self) -> ClientSession:
        return self.client.sess

    @property
    def root(self) -> URL:
        return self.client.server / 'sessions'

    async def create(self, user_token: Union[AuthenticatedUser, str], public_key: bytes) -> tuple[str, Session]:
        if isinstance(user_token, AuthenticatedUser):
            user_token = user_token.token
        async with self.sess.post(self.root / 'new', json={
            'user_token': user_token,
            'public_key': binascii.b2a_base64(public_key).decode('ascii'),
        }) as resp:
            await _check_error(resp)
            json = await resp.json()
            return (json['session_token'], Session.from_json(json))

    async def retrieve(self, token: str) -> Session:
        async with self.sess.get(self.root / 'retrieve' / token) as resp:
            await _check_error(resp)
            return Session.from_json(await resp.json())


class AuthClient:
    sess: ClientSession
    server: URL
    auth: _AuthClient
    sessions: _SessionClient
    allow_insecure: bool

    def __init__(self, server_address: StrOrURL = AUTH_SERVER, allow_insecure: bool = False) -> None:
        self.sess = ClientSession()
        self.server = URL(server_address)
        self.auth = _AuthClient(self)
        self.sessions = _SessionClient(self)
        self.allow_insecure = allow_insecure

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return await self.close()

    async def close(self) -> None:
        return await self.sess.close()

    async def ping(self) -> None:
        async with self.sess.get(self.server / 'ping', allow_redirects=True) as resp:
            await _check_error(resp)
            if not self.allow_insecure and resp.url.scheme != 'https':
                raise InsecureAuth(f'Scheme was {resp.url.scheme}, not https')
            self.server = resp.url.parent

    async def teapot(self) -> None:
        async with self.sess.get(self.server / 'teapot') as resp:
            await _check_error(resp)
