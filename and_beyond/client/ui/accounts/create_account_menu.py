import logging
from asyncio.events import AbstractEventLoop
from typing import TYPE_CHECKING

from zxcvbn import zxcvbn

from and_beyond.client import globals
from and_beyond.client.ui import CANCEL_TEXT, Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.common import USERNAME_REGEX
from and_beyond.text import translatable_text, translate

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
        self.username_text_input = UiTextInput(
            self.update,
            placeholder=translatable_text('accounts.edit.username')
        )
        self.password_text_input = UiTextInput(
            self.update, mask='\u25cf',
            placeholder=translatable_text('accounts.edit.password')
        )
        self.repeat_password_text_input = UiTextInput(
            self.update, mask='\u25cf',
            placeholder=translatable_text('accounts.create_account.repeat_password')
        )
        self.info_text = UiLabel('')
        super().__init__([
            UiLabel(translatable_text('accounts.create_account.title')),
            self.username_text_input,
            self.password_text_input,
            self.repeat_password_text_input,
            UiButton(translatable_text('accounts.create_account.title'), self.create_account_cb),
            UiButton(CANCEL_TEXT, self.close),
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
            LabelScreen(translatable_text('accounts.create_account.creation_failed', str(e))).show(self)
            return
        globals.config.config['auth_token'] = user.token
        globals.config.uuid = user.uuid
        globals.config.config['username'] = user.username
        self.accounts_menu.current_profile = user
        self.accounts_menu.init_elements()
        self.close()

    def update(self, *args) -> bool:
        self.ready_to_send = True
        info_text: list[str] = []
        username = self.username_text_input.text
        if username:
            if USERNAME_REGEX.fullmatch(username) is None:
                info_text.append(translate('accounts.edit.invalid_username'))
        else:
            self.ready_to_send = False
        password = self.password_text_input.text
        if password:
            if self.repeat_password_text_input.text != password:
                info_text.append(translate('accounts.create_account.password_mismatch'))
                self.ready_to_send = False
            zxcvbn_info = zxcvbn(password, username)
            if zxcvbn_info['score'] < 2:
                info_text.append(translate('accounts.create_account.weak_password', zxcvbn_info['score']))
                self.ready_to_send = False
            else:
                info_text.append(translate('accounts.create_account.password_score', zxcvbn_info['score']))
            if warning := zxcvbn_info['feedback']['warning']:
                info_text.append(translate('accounts.edit.warning', warning))
            if suggestions := zxcvbn_info['feedback']['suggestions']:
                info_text.append(translate('accounts.create_account.suggestions'))
                for suggestion in suggestions:
                    info_text.append('+ ' + suggestion)
        else:
            self.ready_to_send = False
        self.info_text.text = '\n'.join(info_text)
        return self.ready_to_send
