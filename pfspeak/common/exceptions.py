
class MisakiImportError(ImportError):
    def __init__(self,
                 *args: object,
                 lang_code: str = 'unknown',
                 name: str | None = None,
                 path: str | None = None
                 ) -> None:
        self.lang_code = lang_code
        if not args:
            args = (
                    f"Misaki Import Error: lang_code was '{lang_code}' at the " 
                    "time at the time of the error."
                    ,
                    )
        else:
            self.message = args[0]
        super().__init__( *args, name=name, path=path)

class LanguageNotImplemented(NotImplementedError):
    def __init__(self, *args: object, lang_code: str = 'unknown') -> None:
        self.lang_code = lang_code
        if not args:
            args = (
                    f"Language Not Implemented: '{lang_code}'"
                    ,
                    )
        else:
            self.message = args[0]
        super().__init__(*args)
