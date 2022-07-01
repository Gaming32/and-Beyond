import logging
from asyncio.events import AbstractEventLoop
from typing import TYPE_CHECKING

from and_beyond.client import globals
from and_beyond.client.ui import CANCEL_TEXT, Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.text import translatable_text
from and_beyond.utils import NO_OP

if TYPE_CHECKING:
    from and_beyond.client.ui.accounts import AccountsMenu


class LogInMenu(Ui):
    accounts_menu: 'AccountsMenu'
    aloop: AbstractEventLoop
    username_text_input: UiTextInput
    password_text_input: UiTextInput

    def __init__(self, accounts_menu: 'AccountsMenu') -> None:
        self.accounts_menu = accounts_menu
        self.aloop = accounts_menu.aloop
        self.username_text_input = UiTextInput(NO_OP, placeholder=translatable_text('accounts.edit.username'))
        self.password_text_input = UiTextInput(
            NO_OP, mask='\u25cf',
            placeholder=translatable_text('accounts.edit.password')
        )
        super().__init__([
            UiLabel(translatable_text('accounts.log_in.title')),
            self.username_text_input,
            self.password_text_input,
            UiButton(translatable_text('accounts.log_in.title'), self.log_in_cb),
            UiButton(CANCEL_TEXT, self.close)
        ])

    def log_in_cb(self) -> None:
        username = self.username_text_input.text
        password = self.password_text_input.text
        try:
            user = self.aloop.run_until_complete(
                self.aloop.run_until_complete(
                    globals.get_auth_client()
                ).auth.login(username, password)
            )
        except Exception as e:
            logging.warn('Login failed', exc_info=True)
            LabelScreen(translatable_text('accounts.log_in.login_failed', str(e))).show(self)
            return
        globals.config.config['auth_token'] = user.token
        globals.config.uuid = user.uuid
        globals.config.config['username'] = user.username
        self.accounts_menu.current_profile = user
        self.accounts_menu.init_elements()
        self.close()
