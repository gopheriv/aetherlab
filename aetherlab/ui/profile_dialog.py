"""View, edit, create, and switch local learner profiles."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from aetherlab.core.language import normalize_language
from aetherlab.services.student_profiles import StudentProfile, StudentProfileStore
from aetherlab.ui.profile_avatar import ProfileAvatarWidget
from aetherlab.ui.qt_compat import QtCore, QtGui, QtWidgets, require_qt
from aetherlab.ui.style import AETHERLAB_QSS

require_qt()


_COPY = {
    "kk": {
        "title": "Оқушы профилі",
        "intro": "Оқушы туралы мәліметтер мен профиль суретін басқарыңыз.",
        "profile": "Профиль",
        "first_name": "Аты",
        "last_name": "Тегі",
        "username": "Пайдаланушы аты",
        "photo_accessible": "Профиль суреті: {name}",
        "class_name": "Сыныбы",
        "school_id": "Мектеп ID-і",
        "login": "Логин",
        "placeholder_first": "Аты",
        "placeholder_last": "Тегі",
        "placeholder_username": "мысалы, aruzhan",
        "placeholder_class": "мысалы, 11 A",
        "placeholder_school_id": "Мектеп берген ID",
        "school_id_hint": "Бірдей мектеп ID-ін енгізген оқушылар ортақ рейтингте көрінеді.",
        "photo": "Фотоны өзгерту",
        "new": "Жаңа профиль",
        "edit": "Өңдеу",
        "save": "Сақтау",
        "discard": "Болдырмау",
        "use": "Осы профильді қолдану",
        "close": "Жабу",
        "photo_filter": "Суреттер (*.png *.jpg *.jpeg *.webp *.bmp)",
        "photo_title": "Профиль суретін таңдау",
        "empty_name": "Аты мен тегін енгізіңіз.",
        "too_long": "Аты немесе тегі 40 таңбадан аспауы керек.",
        "invalid_username": "Username латын әріптерімен, сандармен, нүкте, сызықша не төменгі сызықпен жазылуы керек.",
        "duplicate": "Мұндай аты бар профиль бар. Мәліметтерді тексеріңіз.",
        "duplicate_username": "Бұл username басқа профильде қолданылған.",
        "save_error": "Профильді сақтау мүмкін болмады.",
        "photo_error": "Фотоны ашу немесе сақтау мүмкін болмады. Басқа суретті таңдаңыз.",
        "load_error": "Профильдерді оқу мүмкін болмады. Деректер өзгерген жоқ. Қайталап көріңіз.",
        "saved_reload_error": "Профиль сақталды, бірақ тізімді жаңарту мүмкін болмады. Қайталап көріңіз.",
        "retry": "Қайталау",
    },
    "ru": {
        "title": "Профиль ученика",
        "intro": "Управляйте данными ученика и фотографией профиля.",
        "profile": "Профиль",
        "first_name": "Имя",
        "last_name": "Фамилия",
        "username": "Имя пользователя",
        "photo_accessible": "Фото профиля: {name}",
        "class_name": "Класс",
        "school_id": "ID школы",
        "login": "Логин",
        "placeholder_first": "Имя",
        "placeholder_last": "Фамилия",
        "placeholder_username": "например, aruzhan",
        "placeholder_class": "например, 11 A",
        "placeholder_school_id": "ID, выданный школой",
        "school_id_hint": "Ученики с одинаковым ID школы будут в одном общем рейтинге.",
        "photo": "Изменить фото",
        "new": "Новый профиль",
        "edit": "Изменить",
        "save": "Сохранить",
        "discard": "Отмена",
        "use": "Использовать профиль",
        "close": "Закрыть",
        "photo_filter": "Изображения (*.png *.jpg *.jpeg *.webp *.bmp)",
        "photo_title": "Выбрать фото профиля",
        "empty_name": "Введите имя и фамилию.",
        "too_long": "Имя и фамилия не должны превышать 40 символов каждое.",
        "invalid_username": "Имя пользователя должно содержать латинские буквы, цифры или . _ -.",
        "duplicate": "Профиль с таким именем уже есть. Проверьте данные.",
        "duplicate_username": "Это имя пользователя уже используется в другом профиле.",
        "save_error": "Не удалось сохранить профиль.",
        "photo_error": "Не удалось открыть или сохранить фото. Выберите другое изображение.",
        "load_error": "Не удалось прочитать профили. Данные не изменены. Повторите попытку.",
        "saved_reload_error": "Профиль сохранён, но список не удалось обновить. Повторите попытку.",
        "retry": "Повторить",
    },
    "en": {
        "title": "Student profile",
        "intro": "Manage the student details and profile photo.",
        "profile": "Profile",
        "first_name": "First name",
        "last_name": "Surname",
        "username": "Username",
        "photo_accessible": "Profile photo: {name}",
        "class_name": "Class",
        "school_id": "School ID",
        "login": "Login",
        "placeholder_first": "First name",
        "placeholder_last": "Surname",
        "placeholder_username": "for example, aruzhan",
        "placeholder_class": "for example, 11 A",
        "placeholder_school_id": "ID issued by the school",
        "school_id_hint": "Students with the same school ID appear in one shared leaderboard.",
        "photo": "Change photo",
        "new": "New profile",
        "edit": "Edit profile",
        "save": "Save profile",
        "discard": "Cancel edit",
        "use": "Use this profile",
        "close": "Close",
        "photo_filter": "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        "photo_title": "Choose profile photo",
        "empty_name": "Enter a first name and surname.",
        "too_long": "First name and surname can be up to 40 characters each.",
        "invalid_username": "Use Latin letters, numbers, and . _ or - in the username.",
        "duplicate": "A profile with that name already exists. Check the details.",
        "duplicate_username": "That username is already used by another profile.",
        "save_error": "Could not save the profile.",
        "photo_error": "Could not open or save the photo. Choose another image.",
        "load_error": "Could not read profiles. Data is unchanged. Please retry.",
        "saved_reload_error": "The profile was saved, but the list could not reload. Please retry.",
        "retry": "Retry",
    },
}


class StudentProfileDialog(QtWidgets.QDialog):
    def __init__(
        self,
        store: StudentProfileStore,
        language: str = "kk",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.language = normalize_language(language, "kk")
        self.selected_profile: StudentProfile | None = None
        self._current_profile: StudentProfile | None = None
        self._new_profile = False
        self._avatar_source = ""
        self._registry_ready = False
        self._pending_profile_id: str | None = None
        self.setObjectName("StudentProfileDialog")
        self.setStyleSheet(AETHERLAB_QSS)
        self.setMinimumSize(620, 430)
        self.resize(720, 500)
        text = _COPY[self.language]
        self.setWindowTitle(text["title"])

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        heading_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(text["title"])
        title.setStyleSheet("font-size:20px; font-weight:700; color:#18283D;")
        heading_row.addWidget(title, 1)
        self.profile_label = QtWidgets.QLabel(text["profile"])
        heading_row.addWidget(self.profile_label)
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.setObjectName("StudentProfileCombo")
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        heading_row.addWidget(self.profile_combo)
        root.addLayout(heading_row)

        intro = QtWidgets.QLabel(text["intro"])
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#65758A; font-size:12px;")
        root.addWidget(intro)

        content = QtWidgets.QHBoxLayout()
        content.setSpacing(24)
        form = QtWidgets.QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(11)
        self.first_name_edit = QtWidgets.QLineEdit()
        self.first_name_edit.setMaxLength(40)
        self.first_name_edit.setPlaceholderText(text["placeholder_first"])
        self.last_name_edit = QtWidgets.QLineEdit()
        self.last_name_edit.setMaxLength(40)
        self.last_name_edit.setPlaceholderText(text["placeholder_last"])
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setMaxLength(30)
        self.username_edit.setPlaceholderText(text["placeholder_username"])
        self.class_edit = QtWidgets.QLineEdit()
        self.class_edit.setMaxLength(24)
        self.class_edit.setPlaceholderText(text["placeholder_class"])
        self.login_edit = QtWidgets.QLineEdit()
        self.login_edit.setReadOnly(True)
        self.login_edit.setObjectName("ProfileLogin")
        for key, widget in (
            ("first_name", self.first_name_edit),
            ("last_name", self.last_name_edit),
            ("username", self.username_edit),
            ("class_name", self.class_edit),
            ("login", self.login_edit),
        ):
            form.addRow(text[key], widget)
        self.username_edit.textChanged.connect(self._update_login)
        content.addLayout(form, 1)

        photo_panel = QtWidgets.QVBoxLayout()
        photo_panel.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignTop)
        self.avatar = ProfileAvatarWidget(size=132)
        photo_panel.addWidget(self.avatar, 0, QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.photo_button = QtWidgets.QPushButton(text["photo"])
        self.photo_button.setObjectName("SecondaryButton")
        self.photo_button.clicked.connect(self._choose_photo)
        photo_panel.addWidget(self.photo_button)
        self.school_id_label = QtWidgets.QLabel(text["school_id"])
        self.school_id_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        photo_panel.addWidget(self.school_id_label)
        self.school_id_edit = QtWidgets.QLineEdit()
        self.school_id_edit.setMaxLength(40)
        self.school_id_edit.setPlaceholderText(text["placeholder_school_id"])
        photo_panel.addWidget(self.school_id_edit)
        self.school_id_hint = QtWidgets.QLabel(text["school_id_hint"])
        self.school_id_hint.setWordWrap(True)
        self.school_id_hint.setStyleSheet("color:#65758A; font-size:10px;")
        photo_panel.addWidget(self.school_id_hint)
        photo_panel.addStretch(1)
        content.addLayout(photo_panel)
        root.addLayout(content, 1)

        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color:#A13C4A; font-size:11px;")
        self.message.hide()
        error_row = QtWidgets.QHBoxLayout()
        error_row.addWidget(self.message, 1)
        self.retry_button = QtWidgets.QPushButton(text["retry"])
        self.retry_button.setObjectName("SecondaryButton")
        self.retry_button.clicked.connect(self._retry_refresh)
        self.retry_button.hide()
        error_row.addWidget(self.retry_button)
        root.addLayout(error_row)

        actions = QtWidgets.QHBoxLayout()
        self.new_button = QtWidgets.QPushButton(text["new"])
        self.new_button.setObjectName("SecondaryButton")
        self.new_button.clicked.connect(self._begin_new_profile)
        actions.addWidget(self.new_button)
        actions.addStretch(1)
        self.edit_button = QtWidgets.QPushButton(text["edit"])
        self.edit_button.setObjectName("SecondaryButton")
        self.edit_button.clicked.connect(self._begin_edit)
        actions.addWidget(self.edit_button)
        self.save_button = QtWidgets.QPushButton(text["save"])
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save_profile)
        actions.addWidget(self.save_button)
        self.discard_button = QtWidgets.QPushButton(text["discard"])
        self.discard_button.setObjectName("SecondaryButton")
        self.discard_button.clicked.connect(self._discard_edit)
        actions.addWidget(self.discard_button)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
        close_button.setText(text["close"])
        close_button.setObjectName("SecondaryButton")
        self.use_button = buttons.addButton(
            text["use"], QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.use_button.setObjectName("PrimaryButton")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._activate_selected)
        actions.addWidget(buttons)
        root.addLayout(actions)

        self._refresh_profiles()
        self._set_editing(False)

    def _refresh_profiles(self, selected_id: str | None = None, *, saved: bool = False) -> bool:
        try:
            profiles = self.store.list_profiles()
            desired_id = selected_id or self.store.active_profile().id
        except OSError:
            self._load_failed(selected_id or self.profile_combo.currentData(), saved=saved)
            return False
        # Read first: a failed reload must not empty the choices or leave the
        # selection signal blocked. Render the selected snapshot without a
        # second registry read halfway through updating the widgets.
        self.profile_combo.blockSignals(True)
        try:
            self.profile_combo.clear()
            for profile in profiles:
                self.profile_combo.addItem(profile.name, profile.id)
            index = self.profile_combo.findData(desired_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        finally:
            self.profile_combo.blockSignals(False)
        profile = next((item for item in profiles if item.id == self.profile_combo.currentData()), None)
        if profile is None:
            self._load_failed(desired_id, saved=saved)
            return False
        self._display_profile(profile)
        return True

    def _profile_changed(self, _index: int) -> None:
        if not self._new_profile:
            self._load_selected_profile()

    def _load_selected_profile(self) -> bool:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            self._current_profile = None
            return False
        try:
            profile = self.store.get_profile(str(profile_id))
        except OSError:
            self._load_failed(str(profile_id))
            return False
        if profile is None:
            self._load_failed(str(profile_id))
            return False
        self._display_profile(profile)
        return True

    def _display_profile(self, profile: StudentProfile) -> None:
        self._current_profile = profile
        self._registry_ready = True
        self._pending_profile_id = None
        self.first_name_edit.setText(profile.first_name or profile.name)
        self.last_name_edit.setText(profile.last_name)
        self.username_edit.setText(profile.username)
        self.class_edit.setText(profile.class_name)
        self.school_id_edit.setText(profile.school_id)
        self._avatar_source = profile.avatar_path
        self._set_avatar(profile.name, profile.avatar_path)
        self.message.clear()
        self.message.hide()
        self.retry_button.hide()
        self.edit_button.setEnabled(True)
        self.new_button.setEnabled(True)
        self.use_button.setEnabled(not self._new_profile)

    def _load_failed(self, profile_id: str | None, *, saved: bool = False) -> None:
        self._registry_ready = False
        self._pending_profile_id = str(profile_id) if profile_id else None
        if self._current_profile is not None and self._current_profile.id != self._pending_profile_id:
            self._current_profile = None
        self.edit_button.setEnabled(False)
        self.new_button.setEnabled(False)
        self.use_button.setEnabled(False)
        key = "saved_reload_error" if saved else "load_error"
        self._show_error(_COPY[self.language][key], retry=True)

    def _retry_refresh(self) -> None:
        if self._refresh_profiles(self._pending_profile_id):
            self._set_editing(False)

    def _set_editing(self, enabled: bool, *, new_profile: bool = False) -> None:
        self._new_profile = new_profile
        for field in (
            self.first_name_edit,
            self.last_name_edit,
            self.username_edit,
            self.class_edit,
            self.school_id_edit,
        ):
            field.setReadOnly(not enabled)
        self.profile_combo.setEnabled(not enabled)
        self.photo_button.setEnabled(enabled)
        self.new_button.setVisible(not enabled)
        self.edit_button.setVisible(not enabled)
        self.save_button.setVisible(enabled)
        self.discard_button.setVisible(enabled)
        self.use_button.setEnabled(not enabled and self._registry_ready and self._current_profile is not None)
        self.edit_button.setEnabled(self._registry_ready and self._current_profile is not None)
        self.new_button.setEnabled(self._registry_ready)

    def _begin_edit(self) -> None:
        self.message.hide()
        self._set_editing(True)
        self.first_name_edit.setFocus()

    def _begin_new_profile(self) -> None:
        text = _COPY[self.language]
        self._current_profile = None
        self._avatar_source = ""
        self.profile_combo.setCurrentIndex(-1)
        self.first_name_edit.clear()
        self.last_name_edit.clear()
        self.username_edit.clear()
        self.class_edit.clear()
        self.school_id_edit.clear()
        self.login_edit.clear()
        self._set_avatar(text["new"], "")
        self.message.clear()
        self.message.hide()
        self._set_editing(True, new_profile=True)
        self.first_name_edit.setFocus()

    def _discard_edit(self) -> None:
        self.message.hide()
        if self._new_profile:
            loaded = self._refresh_profiles()
        else:
            loaded = self._load_selected_profile()
        if loaded:
            self._set_editing(False)

    def _choose_photo(self) -> None:
        text = _COPY[self.language]
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, text["photo_title"], "", text["photo_filter"]
        )
        if not path:
            return
        pixmap = QtGui.QPixmap(path)
        if pixmap.isNull():
            self._show_error(text["photo_error"])
            return
        self._avatar_source = path
        display_name = " ".join(
            value for value in (self.first_name_edit.text(), self.last_name_edit.text()) if value
        )
        self._set_avatar(display_name, path)

    def _set_avatar(self, name: str, path: str) -> None:
        self.avatar.set_profile(name, path)
        self.avatar.setAccessibleName(_COPY[self.language]["photo_accessible"].format(name=name))

    def _update_login(self, username: str) -> None:
        safe = str(username or "").strip().lower()
        self.login_edit.setText(f"{safe}@gmail.com" if safe else "")

    def _persist_avatar(self, profile: StudentProfile | None, source: str) -> str:
        if not source:
            return ""
        if profile is not None and source == profile.avatar_path:
            # Unchanged photos need no rewrite and remain usable on a name edit.
            return source
        pixmap = QtGui.QPixmap(source)
        if pixmap.isNull():
            raise OSError("photo source cannot be read")
        # A new immutable file lets a rejected registry transaction retain the
        # previous photo. Never overwrite an existing avatar before validation.
        target = self.store.data_dir / "profile_avatars" / f"{uuid.uuid4().hex}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        output = QtCore.QSaveFile(str(target))
        try:
            if not output.open(QtCore.QIODevice.OpenModeFlag.WriteOnly):
                raise OSError("photo destination cannot be opened")
            if not pixmap.save(output, "PNG") or not output.commit():
                raise OSError("photo destination cannot be committed")
        except Exception:
            output.cancelWriting()
            raise
        return str(target)

    @staticmethod
    def _discard_staged_avatar(path: Path | None) -> None:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _save_profile(self) -> None:
        text = _COPY[self.language]
        first = self.first_name_edit.text().strip()
        last = self.last_name_edit.text().strip()
        username = self.username_edit.text().strip().lower()
        if not first or not last:
            self._show_error(text["empty_name"])
            return
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,29}", username):
            self._show_error(text["invalid_username"])
            return
        profile_name = f"{first} {last}"
        staged_avatar = None
        if not self._new_profile and self._current_profile is None:
            self._show_error(text["save_error"])
            return
        try:
            avatar_path = self._persist_avatar(self._current_profile, self._avatar_source)
        except OSError:
            self._show_error(text["photo_error"])
            return
        if avatar_path and avatar_path != self._avatar_source:
            staged_avatar = Path(avatar_path)
        try:
            if self._new_profile:
                profile = self.store.create_profile(
                    profile_name,
                    first_name=first,
                    last_name=last,
                    username=username,
                    class_name=self.class_edit.text(),
                    school_id=self.school_id_edit.text(),
                    avatar_path=avatar_path,
                    make_active=True,
                )
            else:
                profile = self.store.update_profile(
                    self._current_profile.id,
                    first_name=first,
                    last_name=last,
                    username=username,
                    class_name=self.class_edit.text(),
                    school_id=self.school_id_edit.text(),
                    avatar_path=avatar_path,
                )
        except ValueError as exc:
            self._discard_staged_avatar(staged_avatar)
            message = {
                "empty_name": text["empty_name"],
                "too_long": text["too_long"],
                "invalid_username": text["invalid_username"],
                "duplicate": text["duplicate"],
                "duplicate_username": text["duplicate_username"],
            }.get(str(exc), text["save_error"])
            self._show_error(message)
            return
        except OSError:
            self._discard_staged_avatar(staged_avatar)
            self._show_error(text["save_error"])
            return
        self._current_profile = profile
        self._avatar_source = profile.avatar_path
        self._set_editing(False)
        self._refresh_profiles(profile.id, saved=True)

    def _show_error(self, message: str, *, retry: bool = False) -> None:
        self.message.setStyleSheet("color:#A13C4A; font-size:11px;")
        self.message.setText(message)
        self.message.show()
        self.retry_button.setVisible(retry)

    def _activate_selected(self) -> None:
        profile_id = self.profile_combo.currentData()
        if not profile_id or self._new_profile:
            return
        try:
            profile = self.store.set_active_profile(str(profile_id))
        except (OSError, ValueError):
            self._show_error(_COPY[self.language]["save_error"])
            return
        self.selected_profile = profile
        self.accept()
