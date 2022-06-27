import logging
from asyncio.events import AbstractEventLoop
from typing import TYPE_CHECKING

from zxcvbn import zxcvbn

from and_beyond.client import globals
from and_beyond.client.ui import Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.common import USERNAME_REGEX

if TYPE_CHECKING:
    from and_beyond.client.ui.accounts import AccountsMenu


class CreateAccountMenu(Ui):
    accounts_menu: 'AccountsMenu'
    aloop: AbstractEventLoop
    username_text_input: UiTextInput
    password_text_input: UiTextInput
    repeat_password_text_input: UiTextInput
    info_text: UiLabel
    ready_to_send: bool

    def __init__(self, accounts_menu: 'AccountsMenu') -> None:
        self.accounts_menu = accounts_menu
        self.aloop = accounts_menu.aloop
        self.username_text_input = UiTextInput(self.update, placeholder='Username')
        self.password_text_input = UiTextInput(self.update, mask='\u25cf', placeholder='Password')
        self.repeat_password_text_input = UiTextInput(self.update, mask='\u25cf', placeholder='Repeat password')
        self.info_text = UiLabel('')
        super().__init__([
            UiLabel('Create account'),
            self.username_text_input,
            self.password_text_input,
            self.repeat_password_text_input,
            UiButton('Create account', self.create_account_cb),
            UiButton('Cancel', self.close),
            self.info_text,
        ])
        self.ready_to_send = False

    def create_account_cb(self) -> None:
        if not self.ready_to_send:
            return
        username = self.username_text_input.text
        password = self.password_text_input.text
        try:
            user = self.aloop.run_until_complete(
                self.aloop.run_until_complete(
                    globals.get_auth_client()
                ).auth.create_user(username, password)
            )
        except Exception as e:
            logging.warn('Account creation failed', exc_info=True)
            LabelScreen(f'Account creation failed: {e}').show(self)
            return
        globals.config.config['auth_token'] = user.token
        globals.config.uuid = user.uuid
        globals.config.config['username'] = user.username
        self.accounts_menu.current_profile = user
        self.accounts_menu.init_elements()
        self.close()

    def update(self, *args) -> bool:
        self.ready_to_send = True
        info_text = []
        username = self.username_text_input.text
        if username:
            if USERNAME_REGEX.fullmatch(username) is None:
                info_text.append('Your username is invalid.')
        else:
            self.ready_to_send = False
        password = self.password_text_input.text
        if password:
            if self.repeat_password_text_input.text != password:
                info_text.append("Your passwords don't match.")
                self.ready_to_send = False
            zxcvbn_info = zxcvbn(password, username)
            if zxcvbn_info['score'] < 2:
                info_text.append(f"Your password has a score of {zxcvbn_info['score']}, "
                                  "but a minimum of 2 is required.")
                self.ready_to_send = False
            else:
                info_text.append(f"Your password has a score of {zxcvbn_info['score']}/4.")
            if warning := zxcvbn_info['feedback']['warning']:
                info_text.append('Warning: ' + warning)
            if suggestions := zxcvbn_info['feedback']['suggestions']:
                info_text.append("Here's a list of suggestions to make your password stronger:")
                for suggestion in suggestions:
                    info_text.append('+ ' + suggestion)
        else:
            self.ready_to_send = False
        self.info_text.text = '\n'.join(info_text)
        return self.ready_to_send
