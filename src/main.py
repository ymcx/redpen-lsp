import re
from hunspell import HunSpell
from typing import List, Tuple, Optional
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
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hunspell = HunSpell(
            "/usr/share/hunspell/en_US.dic", "/usr/share/hunspell/en_US.aff"
        )
        self.diagnostics: List[Diagnostic] = []
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.feature(TEXT_DOCUMENT_DID_CHANGE)
        @self.feature(TEXT_DOCUMENT_DID_OPEN)
        def on_document_change(params: DidChangeTextDocumentParams) -> None:
            document = self.workspace.get_document(params.text_document.uri)
            words = self._get_words(document.source)
            self.diagnostics = self._get_diagnostics(words)
            self.publish_diagnostics(params.text_document.uri, self.diagnostics)

        @self.feature(TEXT_DOCUMENT_CODE_ACTION)
        def on_code_action(params: CodeActionParams) -> Optional[List[CodeAction]]:
            return self._get_actions(params.text_document.uri, params.range)

    def _get_words(self, document: str) -> List[Tuple[int, int, int, str]]:
        words: List[Tuple[int, int, int, str]] = []
        for match in re.finditer(r"\S+", document):
            line = document.count("\n", 0, match.start())
            line_start = document.rfind("\n", 0, match.start()) + 1

            word = (
                line,
                match.start() - line_start,
                match.end() - line_start,
                document[match.start() : match.end()],
            )
            words.append(word)

        return words

    def _get_diagnostics(
        self, words: List[Tuple[int, int, int, str]]
    ) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        for line, start, end, word in words:
            if not self.hunspell.spell(word):
                diagnostic = Diagnostic(
                    Range(Position(line, start), Position(line, end)),
                    word,
                    DiagnosticSeverity.Error,
                )
                diagnostics.append(diagnostic)

        return diagnostics

    def _get_actions(self, uri: str, cursor: Range) -> Optional[List[CodeAction]]:
        for diagnostic in self.diagnostics:
            if (
                diagnostic.range.start.line
                <= cursor.start.line
                <= diagnostic.range.end.line
                and diagnostic.range.start.character
                <= cursor.start.character
                <= diagnostic.range.end.character
            ):
                suggestions = self.hunspell.suggest(diagnostic.message)
                if not suggestions:
                    break

                actions = [
                    CodeAction(
                        title=suggestion,
                        edit=WorkspaceEdit(
                            {uri: [TextEdit(diagnostic.range, suggestion)]}
                        ),
                    )
                    for suggestion in suggestions
                ]

                return actions


def main():
    LSP("lsp", "0.0.1").start_io()


if __name__ == "__main__":
    main()
