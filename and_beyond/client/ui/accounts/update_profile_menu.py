import logging
from asyncio.events import AbstractEventLoop
from typing import TYPE_CHECKING

from and_beyond.client import globals
from and_beyond.client.ui import Ui, UiButton, UiLabel, UiTextInput
from and_beyond.client.ui.label_screen import LabelScreen
from and_beyond.common import USERNAME_REGEX
from zxcvbn import zxcvbn

if TYPE_CHECKING:
    from and_beyond.client.ui.accounts import AccountsMenu


class UpdateProfileMenu(Ui):
    accounts_menu: 'AccountsMenu'
    aloop: AbstractEventLoop
    username_text_input: UiTextInput
    old_password_text_input: UiTextInput
    password_text_input: UiTextInput
    repeat_password_text_input: UiTextInput
    info_text: UiLabel
    ready_to_send: bool

    def __init__(self, accounts_menu: 'AccountsMenu') -> None:
        self.accounts_menu = accounts_menu
        self.aloop = accounts_menu.aloop
        self.username_text_input = UiTextInput(self.update, globals.config.config['username'], placeholder='Username')
        self.old_password_text_input = UiTextInput(self.update, mask='\u25cf', placeholder='Old password')
        self.password_text_input = UiTextInput(self.update, mask='\u25cf', placeholder='New password')
        self.repeat_password_text_input = UiTextInput(self.update, mask='\u25cf', placeholder='Repeat new password')
        self.info_text = UiLabel('')
        super().__init__([
            UiLabel('Update profile'),
            self.username_text_input,
            self.old_password_text_input,
            self.password_text_input,
            self.repeat_password_text_input,
            UiButton('Update profile', self.update_profile_cb),
            UiButton('Back', self.close),
            self.info_text,
        ])
        self.ready_to_send = False

    def update_profile_cb(self) -> None:
        assert self.accounts_menu.current_profile is not None
        if not self.ready_to_send:
            return
        username = self.username_text_input.text
        old_password = self.old_password_text_input.text
        password = self.password_text_input.text
        kwargs = {}
        update_username = username != globals.config.config['username']
        update_password = bool(password)
        if update_username:
            kwargs['username'] = username
        if update_password:
            kwargs['old_password'] = old_password
            kwargs['password'] = password
        try:
            self.aloop.run_until_complete(
                self.accounts_menu.current_profile.update(**kwargs)
            )
        except Exception as e:
            logging.warn('Profile update failed', exc_info=True)
            LabelScreen(f'Profile update failed: {e}').show(self)
            return
        globals.config.config['username'] = self.username_text_input.text
        self.close()
        if (error := self.aloop.run_until_complete(self.accounts_menu.ainit())) is not None:
            self.accounts_menu.close()
            LabelScreen(error).show()
            return
        self.accounts_menu.init_elements()

    def update(self, *args) -> bool:
        self.ready_to_send = True
        info_text = []
        username = self.username_text_input.text
        if username:
            if USERNAME_REGEX.fullmatch(username) is None:
                info_text.append('Your username is invalid.')
        password = self.password_text_input.text
        old_password = self.old_password_text_input.text
        if password:
            if not old_password:
                info_text.append('You must enter your old password to change your password.')
                self.ready_to_send = False
            if password == old_password:
                info_text.append("Your new password can't be the same as your old one.")
                self.ready_to_send = False
            if self.repeat_password_text_input.text != password:
                info_text.append("Your new passwords don't match.")
                self.ready_to_send = False
            zxcvbn_info = zxcvbn(password, username)
            if zxcvbn_info['score'] < 2:
                info_text.append(f"Your new password has a score of {zxcvbn_info['score']}, "
                                "but a minimum of 2 is required.")
                self.ready_to_send = False
            else:
                info_text.append(f"Your new password has a score of {zxcvbn_info['score']}/4.")
            if warning := zxcvbn_info['feedback']['warning']:
                info_text.append('Warning: ' + warning)
            if suggestions := zxcvbn_info['feedback']['suggestions']:
                info_text.append("Here's a list of suggestions to make your new password stronger:")
                for suggestion in suggestions:
                    info_text.append('+ ' + suggestion)
        self.info_text.text = '\n'.join(info_text)
        self.ready_to_send = self.ready_to_send and bool(username or password)
        return self.ready_to_send
