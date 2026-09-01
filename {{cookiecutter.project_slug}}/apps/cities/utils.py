"""Nationality (demonym) lookup for :mod:`apps.cities.models`.

GeoNames ships country *names*, not demonyms, so a nationality dropdown would
otherwise need a second, hand-maintained choices list that drifts away from the
country table. This maps ISO 3166-1 alpha-2 to the demonym, per language, and
``Country.nationality`` reads it.

SCOPE: a deliberate, verified **subset** - the GCC, the wider Arab world, the
main labour-source countries and the major Western markets. It is not the full
ISO 3166 list, because a demonym nobody on the team can check is worse than no
demonym: ``get_nationality`` falls back to the country's own name for a code it
does not cover, so a gap renders the country name rather than a wrong word.

TO COMPLETE IT: add rows in the same shape, keyed by upper-case alpha-2, sorted
by key. Take the English demonym from the CIA World Factbook's "Nationality -
adjective" field{% if cookiecutter.languages == "en_ar" %}, and the Arabic one - masculine singular, matching the
style used below - from a native speaker{% endif %}. Where two countries would share a demonym,
disambiguate in the string itself (e.g. "Congolese (DRC)" for CD against
"Congolese" for CG).
"""

from django.conf import settings
from django.utils.translation import get_language

#: ISO 3166-1 alpha-2 -> {language code: demonym}. "en" is always present and is
#: the last resort for every other language.
NATIONALITY_BY_CODE2: dict[str, dict[str, str]] = {
    "AE": {"en": "Emirati"{% if cookiecutter.languages == "en_ar" %}, "ar": "إماراتي"{% endif %}},
    "AF": {"en": "Afghan"{% if cookiecutter.languages == "en_ar" %}, "ar": "أفغاني"{% endif %}},
    "AR": {"en": "Argentine"{% if cookiecutter.languages == "en_ar" %}, "ar": "أرجنتيني"{% endif %}},
    "AT": {"en": "Austrian"{% if cookiecutter.languages == "en_ar" %}, "ar": "نمساوي"{% endif %}},
    "AU": {"en": "Australian"{% if cookiecutter.languages == "en_ar" %}, "ar": "أسترالي"{% endif %}},
    "BD": {"en": "Bangladeshi"{% if cookiecutter.languages == "en_ar" %}, "ar": "بنغلاديشي"{% endif %}},
    "BE": {"en": "Belgian"{% if cookiecutter.languages == "en_ar" %}, "ar": "بلجيكي"{% endif %}},
    "BH": {"en": "Bahraini"{% if cookiecutter.languages == "en_ar" %}, "ar": "بحريني"{% endif %}},
    "BR": {"en": "Brazilian"{% if cookiecutter.languages == "en_ar" %}, "ar": "برازيلي"{% endif %}},
    "CA": {"en": "Canadian"{% if cookiecutter.languages == "en_ar" %}, "ar": "كندي"{% endif %}},
    "CH": {"en": "Swiss"{% if cookiecutter.languages == "en_ar" %}, "ar": "سويسري"{% endif %}},
    "CN": {"en": "Chinese"{% if cookiecutter.languages == "en_ar" %}, "ar": "صيني"{% endif %}},
    "DE": {"en": "German"{% if cookiecutter.languages == "en_ar" %}, "ar": "ألماني"{% endif %}},
    "DJ": {"en": "Djiboutian"{% if cookiecutter.languages == "en_ar" %}, "ar": "جيبوتي"{% endif %}},
    "DK": {"en": "Danish"{% if cookiecutter.languages == "en_ar" %}, "ar": "دنماركي"{% endif %}},
    "DZ": {"en": "Algerian"{% if cookiecutter.languages == "en_ar" %}, "ar": "جزائري"{% endif %}},
    "EG": {"en": "Egyptian"{% if cookiecutter.languages == "en_ar" %}, "ar": "مصري"{% endif %}},
    "ES": {"en": "Spanish"{% if cookiecutter.languages == "en_ar" %}, "ar": "إسباني"{% endif %}},
    "ET": {"en": "Ethiopian"{% if cookiecutter.languages == "en_ar" %}, "ar": "إثيوبي"{% endif %}},
    "FI": {"en": "Finnish"{% if cookiecutter.languages == "en_ar" %}, "ar": "فنلندي"{% endif %}},
    "FR": {"en": "French"{% if cookiecutter.languages == "en_ar" %}, "ar": "فرنسي"{% endif %}},
    "GB": {"en": "British"{% if cookiecutter.languages == "en_ar" %}, "ar": "بريطاني"{% endif %}},
    "GH": {"en": "Ghanaian"{% if cookiecutter.languages == "en_ar" %}, "ar": "غاني"{% endif %}},
    "GR": {"en": "Greek"{% if cookiecutter.languages == "en_ar" %}, "ar": "يوناني"{% endif %}},
    "ID": {"en": "Indonesian"{% if cookiecutter.languages == "en_ar" %}, "ar": "إندونيسي"{% endif %}},
    "IE": {"en": "Irish"{% if cookiecutter.languages == "en_ar" %}, "ar": "أيرلندي"{% endif %}},
    "IN": {"en": "Indian"{% if cookiecutter.languages == "en_ar" %}, "ar": "هندي"{% endif %}},
    "IQ": {"en": "Iraqi"{% if cookiecutter.languages == "en_ar" %}, "ar": "عراقي"{% endif %}},
    "IR": {"en": "Iranian"{% if cookiecutter.languages == "en_ar" %}, "ar": "إيراني"{% endif %}},
    "IT": {"en": "Italian"{% if cookiecutter.languages == "en_ar" %}, "ar": "إيطالي"{% endif %}},
    "JO": {"en": "Jordanian"{% if cookiecutter.languages == "en_ar" %}, "ar": "أردني"{% endif %}},
    "JP": {"en": "Japanese"{% if cookiecutter.languages == "en_ar" %}, "ar": "ياباني"{% endif %}},
    "KE": {"en": "Kenyan"{% if cookiecutter.languages == "en_ar" %}, "ar": "كيني"{% endif %}},
    "KM": {"en": "Comorian"{% if cookiecutter.languages == "en_ar" %}, "ar": "قمري"{% endif %}},
    "KR": {"en": "South Korean"{% if cookiecutter.languages == "en_ar" %}, "ar": "كوري جنوبي"{% endif %}},
    "KW": {"en": "Kuwaiti"{% if cookiecutter.languages == "en_ar" %}, "ar": "كويتي"{% endif %}},
    "LB": {"en": "Lebanese"{% if cookiecutter.languages == "en_ar" %}, "ar": "لبناني"{% endif %}},
    "LK": {"en": "Sri Lankan"{% if cookiecutter.languages == "en_ar" %}, "ar": "سريلانكي"{% endif %}},
    "LY": {"en": "Libyan"{% if cookiecutter.languages == "en_ar" %}, "ar": "ليبي"{% endif %}},
    "MA": {"en": "Moroccan"{% if cookiecutter.languages == "en_ar" %}, "ar": "مغربي"{% endif %}},
    "MR": {"en": "Mauritanian"{% if cookiecutter.languages == "en_ar" %}, "ar": "موريتاني"{% endif %}},
    "MX": {"en": "Mexican"{% if cookiecutter.languages == "en_ar" %}, "ar": "مكسيكي"{% endif %}},
    "MY": {"en": "Malaysian"{% if cookiecutter.languages == "en_ar" %}, "ar": "ماليزي"{% endif %}},
    "NG": {"en": "Nigerian"{% if cookiecutter.languages == "en_ar" %}, "ar": "نيجيري"{% endif %}},
    "NL": {"en": "Dutch"{% if cookiecutter.languages == "en_ar" %}, "ar": "هولندي"{% endif %}},
    "NO": {"en": "Norwegian"{% if cookiecutter.languages == "en_ar" %}, "ar": "نرويجي"{% endif %}},
    "NP": {"en": "Nepali"{% if cookiecutter.languages == "en_ar" %}, "ar": "نيبالي"{% endif %}},
    "NZ": {"en": "New Zealander"{% if cookiecutter.languages == "en_ar" %}, "ar": "نيوزيلندي"{% endif %}},
    "OM": {"en": "Omani"{% if cookiecutter.languages == "en_ar" %}, "ar": "عماني"{% endif %}},
    "PH": {"en": "Filipino"{% if cookiecutter.languages == "en_ar" %}, "ar": "فلبيني"{% endif %}},
    "PK": {"en": "Pakistani"{% if cookiecutter.languages == "en_ar" %}, "ar": "باكستاني"{% endif %}},
    "PL": {"en": "Polish"{% if cookiecutter.languages == "en_ar" %}, "ar": "بولندي"{% endif %}},
    "PS": {"en": "Palestinian"{% if cookiecutter.languages == "en_ar" %}, "ar": "فلسطيني"{% endif %}},
    "PT": {"en": "Portuguese"{% if cookiecutter.languages == "en_ar" %}, "ar": "برتغالي"{% endif %}},
    "QA": {"en": "Qatari"{% if cookiecutter.languages == "en_ar" %}, "ar": "قطري"{% endif %}},
    "RO": {"en": "Romanian"{% if cookiecutter.languages == "en_ar" %}, "ar": "روماني"{% endif %}},
    "RU": {"en": "Russian"{% if cookiecutter.languages == "en_ar" %}, "ar": "روسي"{% endif %}},
    "SA": {"en": "Saudi"{% if cookiecutter.languages == "en_ar" %}, "ar": "سعودي"{% endif %}},
    "SD": {"en": "Sudanese"{% if cookiecutter.languages == "en_ar" %}, "ar": "سوداني"{% endif %}},
    "SE": {"en": "Swedish"{% if cookiecutter.languages == "en_ar" %}, "ar": "سويدي"{% endif %}},
    "SO": {"en": "Somali"{% if cookiecutter.languages == "en_ar" %}, "ar": "صومالي"{% endif %}},
    "SY": {"en": "Syrian"{% if cookiecutter.languages == "en_ar" %}, "ar": "سوري"{% endif %}},
    "TH": {"en": "Thai"{% if cookiecutter.languages == "en_ar" %}, "ar": "تايلاندي"{% endif %}},
    "TN": {"en": "Tunisian"{% if cookiecutter.languages == "en_ar" %}, "ar": "تونسي"{% endif %}},
    "TR": {"en": "Turkish"{% if cookiecutter.languages == "en_ar" %}, "ar": "تركي"{% endif %}},
    "TZ": {"en": "Tanzanian"{% if cookiecutter.languages == "en_ar" %}, "ar": "تنزاني"{% endif %}},
    "UA": {"en": "Ukrainian"{% if cookiecutter.languages == "en_ar" %}, "ar": "أوكراني"{% endif %}},
    "UG": {"en": "Ugandan"{% if cookiecutter.languages == "en_ar" %}, "ar": "أوغندي"{% endif %}},
    "US": {"en": "American"{% if cookiecutter.languages == "en_ar" %}, "ar": "أمريكي"{% endif %}},
    "VN": {"en": "Vietnamese"{% if cookiecutter.languages == "en_ar" %}, "ar": "فيتنامي"{% endif %}},
    "YE": {"en": "Yemeni"{% if cookiecutter.languages == "en_ar" %}, "ar": "يمني"{% endif %}},
    "ZA": {"en": "South African"{% if cookiecutter.languages == "en_ar" %}, "ar": "جنوب أفريقي"{% endif %}},
}


def get_nationality(code2: str | None, fallback: str = "") -> str:
    """The demonym for ``code2`` in the active language.

    Falls back to English, then to ``fallback`` (normally the country's own
    name), so a missing or untranslated entry never renders an empty option.
    """
    entry = NATIONALITY_BY_CODE2.get((code2 or "").upper())
    if not entry:
        return fallback
    language = (get_language() or settings.LANGUAGE_CODE).split("-")[0]
    return entry.get(language) or entry.get("en") or fallback
