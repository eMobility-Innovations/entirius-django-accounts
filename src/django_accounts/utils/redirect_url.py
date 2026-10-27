# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

from django.core.exceptions import ImproperlyConfigured


def get_url_from_dict(dictionary: dict, key: str) -> str | dict | None:
    return dictionary.get(key, dictionary) if key is not None else None


def get_redirect_url(
    main_url: str | None = None,
    lang_iso2: str | None = None,
    channel_idx: str | None = None,
    channel_lang_iso2: str | None = None,
    *,
    setting_name: str = "redirect URL setting",
) -> str:
    """
    Funkcja zwraca URL przekierowania na podstawie parametrów językowych i kanału.
    Obsługuje zagnieżdżone słowniki z URL-ami.
    """

    if main_url is None:
        raise ImproperlyConfigured(f"{setting_name} is not set")

    if not isinstance(main_url, dict):
        return main_url

    result = get_url_from_dict(main_url, lang_iso2)
    if result is None:
        result = get_url_from_dict(main_url, channel_idx)
        if isinstance(result, dict):
            result = get_url_from_dict(result, lang_iso2)
    else:
        if isinstance(result, dict):
            result = get_url_from_dict(result, channel_idx)

    if isinstance(result, dict):
        result = get_url_from_dict(result, "default")

    url = result if result is not None else main_url
    if not isinstance(url, str):
        raise ImproperlyConfigured(
            f"{setting_name} has no URL for language {lang_iso2!r} / channel {channel_idx!r} and no 'default'"
        )
    return url
