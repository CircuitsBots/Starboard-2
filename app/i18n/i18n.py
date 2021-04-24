import contextvars
import gettext
import os.path
from glob import glob

from app.classes.t_string import TString

BASE_DIR = "app/"
LOCALE_DEFAULT = "en_US"
LOCALE_DIR = "locale"
locales = frozenset(
    map(
        lambda s: os.path.basename(s),
        filter(os.path.isdir, glob(os.path.join(BASE_DIR, LOCALE_DIR, "*"))),
    )
)

gettext_translations = {
    locale: gettext.translation(
        "bot",
        languages=(locale,),
        localedir=os.path.join(BASE_DIR, LOCALE_DIR),
    )
    for locale in locales
}

gettext_translations["en_US"] = gettext.NullTranslations()
locales |= {"en_US"}


def use_current_gettext(*args, **kwargs) -> str:
    if not gettext_translations:
        return gettext.gettext(*args, **kwargs)

    locale = current_locale.get()
    return gettext_translations.get(
        locale, gettext_translations[LOCALE_DEFAULT]
    ).gettext(*args, **kwargs)


def t_(string: str) -> TString:
    return TString(string, use_current_gettext)


current_locale: contextvars.ContextVar = contextvars.ContextVar("i18n")


def set_current_locale():
    current_locale.set(LOCALE_DEFAULT)


set_current_locale()
