import logging
from asyncio.events import AbstractEventLoop
from typing import TYPE_CHECKING

from and_beyond.client import globals
from and_beyond.client.ui import Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.label_screen import LabelScreen
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
        self.username_text_input = UiTextInput(NO_OP)
        self.password_text_input = UiTextInput(NO_OP, mask='\u25cf')
        super().__init__([
            UiLabel('Username/Password'),
            self.username_text_input,
            self.password_text_input,
            UiButton('Log in', self.log_in_cb),
            UiButton('Cancel', self.close)
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
            self.close()
            LabelScreen(f'Login failed: {e}').show(self.accounts_menu)
            return
        globals.config.config['auth_token'] = user.token
        globals.config.uuid = user.uuid
        globals.config.config['username'] = user.username
        self.accounts_menu.current_profile = user
        self.accounts_menu.init_elements()
        self.close()
