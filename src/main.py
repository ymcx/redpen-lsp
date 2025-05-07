from pygls.server import LanguageServer
from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
)


class LSP(LanguageServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        @self.feature(TEXT_DOCUMENT_DID_CHANGE)
        @self.feature(TEXT_DOCUMENT_DID_OPEN)
        def update(params):
            diagnostic = Diagnostic(
                Range(Position(0, 0), Position(0, 5)),
                "TEST",
                DiagnosticSeverity.Error,
            )
            self.publish_diagnostics(params.text_document.uri, [diagnostic])


def main():
    LSP("", "").start_io()
