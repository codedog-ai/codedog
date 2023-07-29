from codedog.templates import grimoire_cn, grimoire_en, template_cn, template_en


class Localization:
    templates = {
        "en": template_en,
        "cn": template_cn,
    }

    grimoires = {
        "en": grimoire_en,
        "cn": grimoire_cn,
    }

    def __init__(self, language="en"):
        assert language in self.templates
        assert language in self.grimoires
        self._lang = language

    @property
    def lang(self):
        return self.lang

    @property
    def template(self):
        return self.templates[self._lang]

    def grimoire(self):
        return self.grimoires[self._lang]
