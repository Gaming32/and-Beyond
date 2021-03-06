import asyncio
import logging
from asyncio.events import AbstractEventLoop
from typing import Optional

from and_beyond.client import globals
from and_beyond.client.ui import BACK_TEXT, Ui, UiButton, UiLabel
from and_beyond.client.ui.accounts.create_account_menu import CreateAccountMenu
from and_beyond.client.ui.accounts.log_in_menu import LogInMenu
from and_beyond.client.ui.accounts.update_profile_menu import UpdateProfileMenu
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.http_auth import AuthClient, AuthenticatedUser
from and_beyond.http_errors import AuthServerError
from and_beyond.text import EMPTY_TEXT, translatable_text


class AccountsMenu(Ui):
    instance: Optional['AccountsMenu'] = None
    aloop: AbstractEventLoop
    client: AuthClient
    current_profile: Optional[AuthenticatedUser]
    closed: bool

    header_label: UiLabel
    log_in_button: UiButton
    create_account_button: UiButton
    update_profile_button: UiButton
    logout_button: UiButton

    def __init__(self) -> None:
        self.header_label = UiLabel(EMPTY_TEXT)
        self.log_in_button = UiButton(translatable_text('accounts.log_in.title'), self.log_in_cb)
        self.create_account_button = UiButton(
            translatable_text('accounts.create_account.title'),
            self.create_account_cb
        )
        self.update_profile_button = UiButton(
            translatable_text('accounts.update_profile.title'),
            self.update_profile_cb
        )
        self.logout_button = UiButton(translatable_text('accounts.logout'), self.logout_cb)
        super().__init__([
            self.header_label,
            self.log_in_button,
            self.create_account_button,
            self.update_profile_button,
            self.logout_button,
            UiButton(BACK_TEXT, self.close),
        ])
        self.current_profile = None

    def show(self, parent: Optional['Ui'] = None) -> None:
        self.closed = False
        AccountsMenu.instance = self
        self.aloop = asyncio.get_event_loop()
        if (error := self.aloop.run_until_complete(self.ainit())) is not None:
            LabelScreen(error).show(parent)
            self._close()
            return
        self.init_elements()
        super().show(parent)

    def _close(self) -> None:
        AccountsMenu.instance = None

    def close(self) -> None:
        super().close()
        self._close()

    async def ainit(self) -> Optional[str]:
        self.client = await globals.get_auth_client()
        if (error := await self.client.verify_connection()) is not None:
            return error
        if (token := globals.config.config['auth_token']) is not None:
            try:
                self.current_profile = await self.client.auth.get_profile(token)
            except AuthServerError:
                logging.warn('Unable to authenticate', exc_info=True)
                self.current_profile = None
                globals.config.config['auth_token'] = None

    def init_elements(self) -> None:
        if self.current_profile is None:
            self.header_label.text = translatable_text('accounts.not_logged_in')
            self.log_in_button.hidden = False
            self.create_account_button.hidden = False
            self.logout_button.hidden = True
        else:
            self.header_label.text = translatable_text('accounts.logged_in', self.current_profile.username)
            self.log_in_button.hidden = True
            self.create_account_button.hidden = True
            self.logout_button.hidden = False

    def log_in_cb(self) -> None:
        LogInMenu(self).show(self)

    def create_account_cb(self) -> None:
        CreateAccountMenu(self).show(self)

    def update_profile_cb(self) -> None:
        UpdateProfileMenu(self).show(self)

    def logout_cb(self) -> None:
        assert self.current_profile is not None
        try:
            self.aloop.run_until_complete(
                self.current_profile.logout()
            )
        except Exception as e:
            logging.warn('Logout failed', exc_info=True)
            LabelScreen(translatable_text('accounts.logout_failed', str(e))).show(self)
            return
        globals.config.config['auth_token'] = None
        self.current_profile = None
        self.init_elements()
