import re
import hunspell
from pygls.server import LanguageServer
from lsprotocol.types import (
    CodeAction,
    TextEdit,
    CodeActionParams,
    Diagnostic,
    DiagnosticSeverity,
    DidChangeTextDocumentParams,
    Position,
    Range,
    TEXT_DOCUMENT_CODE_ACTION,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    WorkspaceEdit,
)


class LSP(LanguageServer):
    def get_words(self, text) -> list[tuple[int, int, int, str]]:
        words = []
        line = 0
        line_start = 0

        for word_boundary in re.finditer(r"\S+", text):
            start, end = word_boundary.start(), word_boundary.end()
            word = text[start:end]

            word_lines = text.count("\n", line_start, start)
            if word_lines > 0:
                line += word_lines
                line_start = text.rfind("\n", 0, start) + 1

            words.append((line, start - line_start, end - line_start, word))
        return words

    def get_diagnostics(self, words) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for word in words:
            if not self.hunspell.spell(word[3]):
                range = Range(
                    Position(word[0], word[1]),
                    Position(word[0], word[2]),
                )
                diagnostic = Diagnostic(range, word[3], DiagnosticSeverity.Error)
                diagnostics.append(diagnostic)

        return diagnostics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hunspell = hunspell.HunSpell(
            "/usr/share/hunspell/en_US.dic", "/usr/share/hunspell/en_US.aff"
        )
        self.diagnostics: list[Diagnostic] = []

        @self.feature(TEXT_DOCUMENT_DID_CHANGE)
        @self.feature(TEXT_DOCUMENT_DID_OPEN)
        def _(params: DidChangeTextDocumentParams):
            text = self.workspace.get_document(params.text_document.uri).source
            words = self.get_words(text)
            self.diagnostics = self.get_diagnostics(words)
            self.publish_diagnostics(params.text_document.uri, self.diagnostics)

        @self.feature(TEXT_DOCUMENT_CODE_ACTION)
        def _(params: CodeActionParams):
            uri = params.text_document.uri

            cursor = (
                params.range.start.character,
                params.range.end.character,
                params.range.start.line,
                params.range.end.line,
            )

            diags: list[tuple[int, int, int, int, str]] = [
                (
                    i.range.start.character,
                    i.range.end.character,
                    i.range.start.line,
                    i.range.end.line,
                    i.message,
                )
                for i in self.diagnostics
            ]

            for diag in diags:
                if (
                    diag[0] <= cursor[0]
                    and cursor[1] <= diag[1]
                    and diag[2] <= cursor[2]
                    and cursor[3] <= diag[3]
                ):
                    suggestions = self.hunspell.suggest(diag[4])
                    range = Range(
                        Position(diag[2], diag[0]),
                        Position(diag[3], diag[1]),
                    )

                    actions: list[CodeAction] = []
                    for i in suggestions:
                        changes = {uri: [TextEdit(range, i)]}
                        edit = WorkspaceEdit(changes)
                        action = CodeAction(
                            title=i,
                            edit=edit,
                        )
                        actions.append(action)

                    return actions


def main():
    LSP("", "").start_io()
