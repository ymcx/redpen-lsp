import re
import hunspell
from pygls.server import LanguageServer
from lsprotocol.types import (
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    Position,
    Range,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
)


class LSP(LanguageServer):
    def get_diagnostics(self, document):
        diagnostics = []
        line = 0
        line_start = 0

        for word_boundary in re.finditer(r"\S+", document):
            start, end = word_boundary.start(), word_boundary.end()
            word = document[start:end]

            word_lines = document.count("\n", line_start, start)
            if word_lines > 0:
                line += word_lines
                line_start = document.rfind("\n", 0, start) + 1

            if not self.hunspell.spell(word):
                range = Range(
                    Position(line, start - line_start),
                    Position(line, end - line_start),
                )
                diagnostic = Diagnostic(range, "", DiagnosticSeverity.Error)
                diagnostics.append(diagnostic)

        return diagnostics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hunspell = hunspell.HunSpell(
            "/usr/share/hunspell/en_US.dic", "/usr/share/hunspell/en_US.aff"
        )

        @self.feature(TEXT_DOCUMENT_DID_CHANGE)
        @self.feature(TEXT_DOCUMENT_DID_OPEN)
        def _(params: DidChangeTextDocumentParams):
            document = self.workspace.get_document(params.text_document.uri).source
            diagnostics = self.get_diagnostics(document)
            self.publish_diagnostics(params.text_document.uri, diagnostics)


def main():
    LSP("", "").start_io()
