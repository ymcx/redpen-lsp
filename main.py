#!/usr/bin/env python

import asyncio
import re
import sys
from asyncio import Event, Task, CancelledError
from hunspell import HunSpell
from typing import List, Tuple, Optional, Union
from pygls.server import LanguageServer
from lsprotocol.types import (
    CodeAction,
    Command,
    DidOpenTextDocumentParams,
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


class Server(LanguageServer):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hunspell = None
        self.diagnostics: List[Diagnostic] = []
        self.task: Optional[Task] = None
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.feature(TEXT_DOCUMENT_DID_CHANGE)
        @self.feature(TEXT_DOCUMENT_DID_OPEN)
        async def on_document_change(
            params: Union[DidOpenTextDocumentParams, DidChangeTextDocumentParams],
        ) -> None:
            if self.task and not self.task.done():
                self.task.cancel()

            self.task = asyncio.create_task(self._on_document_change(params))

        @self.feature(TEXT_DOCUMENT_CODE_ACTION)
        def on_code_action(params: CodeActionParams) -> Optional[List[CodeAction]]:
            return self._get_actions(params.text_document.uri, params.range)

        async def on_ignore(*args) -> None:
            word = args[0][0]
            self.hunspell.add(word)

        self.command("ignore")(on_ignore)

    async def _on_document_change(
        self, params: Union[DidOpenTextDocumentParams, DidChangeTextDocumentParams]
    ) -> None:
        await asyncio.sleep(0.5)

        document = self.workspace.get_document(params.text_document.uri)
        if not self.hunspell:
            self.hunspell = self._get_hunspell(document.source)

        words = self._get_words(document.source)
        self.diagnostics = self._get_diagnostics(words)
        self.publish_diagnostics(params.text_document.uri, self.diagnostics)

    def _get_hunspell(self, document: str) -> HunSpell:
        line = document.split("\n")[0].split(" ")
        directory = "/usr/share/hunspell"
        language = "en_US"

        if len(sys.argv) >= 2:
            directory = sys.argv[1]
        if len(sys.argv) >= 3:
            language = sys.argv[2]
        if len(line) >= 2 and line[0] == "#":
            language = line[1]

        return HunSpell(f"{directory}/{language}.dic", f"{directory}/{language}.aff")

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
        actions: List[CodeAction] = []
        for diagnostic in self.diagnostics:
            if (
                diagnostic.range.start.line
                <= cursor.start.line
                <= diagnostic.range.end.line
                and diagnostic.range.start.character
                <= cursor.start.character
                <= diagnostic.range.end.character
            ):
                command = Command("Ignore suggestion", "ignore", [diagnostic.message])
                action = CodeAction(title="Ignore suggestion", command=command)
                actions.append(action)

                suggestions = self.hunspell.suggest(diagnostic.message)
                for suggestion in suggestions:
                    edit = TextEdit(diagnostic.range, suggestion)
                    edit = WorkspaceEdit({uri: [edit]})
                    action = CodeAction(title=suggestion, edit=edit)
                    actions.append(action)

                return actions


if __name__ == "__main__":
    Server("", "").start_io()
