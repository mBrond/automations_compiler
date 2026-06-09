"""Interface Kivy para visualizar as fases do compilador Homi.

Uso:
    python GUI.py caminho\arquivo.homi
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView


from ast_nodes import *
from lexer import Lexer, TokenType
from homi_parser import Parser
from semantic import AnalisadorSemantico
from textwrap import wrap

from kivy.config import Config

Config.set(
    'input',
    'mouse',
    'mouse,disable_multitouch'
)


@dataclass
class CompileResult:
    source_path: Optional[Path]
    source: str
    tokens: List[Any]
    lexer_errors: List[str]
    ast: Programa
    parser_errors: List[str]
    semantic_errors: List[str]
    semantic_warnings: List[str]
    symbol_table: Any


def compile_homi(source: str) -> CompileResult:
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    parser = Parser(tokens)
    ast = parser.parse()

    semantic = AnalisadorSemantico()
    semantic.analisar(ast)

    return CompileResult(
        source_path=None,
        source=source,
        tokens=tokens,
        lexer_errors=list(lexer.erros),
        ast=ast,
        parser_errors=list(parser.erros),
        semantic_errors=list(semantic.erros),
        semantic_warnings=list(semantic.avisos),
        symbol_table=semantic.tabela,
    )


def compile_file(path: Path) -> CompileResult:
    source = path.read_text(encoding="utf-8")
    result = compile_homi(source)
    result.source_path = path
    return result


def format_tokens(tokens: List[Any]) -> str:
    if not tokens:
        return "Nenhum token encontrado."

    lines = []
    for token in tokens:
        if token.tipo == TokenType.EOF:
            continue
        lines.append(f"{token.linha:>4}:{token.coluna:<3} {token.tipo.name:<14} {token.valor!r}")
    return "\n".join(lines) if lines else "A entrada só produziu EOF."


def format_ast(node: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if node is None:
        return f"{pad}None"
    if isinstance(node, list):
        if not node:
            return f"{pad}[]"
        return "\n".join(format_ast(item, indent) for item in node)
    if not hasattr(node, "__dataclass_fields__"):
        return f"{pad}{node!r}"

    linhas = [f"{pad}{type(node).__name__}"]
    for campo in node.__dataclass_fields__:
        if campo == "linha":
            continue
        valor = getattr(node, campo)
        if isinstance(valor, list):
            if not valor:
                linhas.append(f"{pad}  {campo}: []")
            else:
                linhas.append(f"{pad}  {campo}:")
                for item in valor:
                    linhas.append(format_ast(item, indent + 2))
        elif hasattr(valor, "__dataclass_fields__"):
            linhas.append(f"{pad}  {campo}:")
            linhas.append(format_ast(valor, indent + 2))
        elif valor is not None:
            linhas.append(f"{pad}  {campo}: {valor!r}")
    return "\n".join(linhas)


def format_symbol_table(symbol_table: Any) -> str:
    entries = getattr(symbol_table, "listar", lambda: [])()
    if not entries:
        return "Tabela de símbolos vazia."

    lines = ["NOME | DOMÍNIO | TIPO", "-" * 50]
    for entry in entries:
        lines.append(f"{entry.nome} | {entry.dominio} | {entry.tipo_homi}")
    return "\n".join(lines)


def join_messages(title: str, messages: List[str]) -> str:
    if not messages:
        return f"{title}\n\nNenhuma ocorrência registrada."
    body = "\n".join(f"- {message}" for message in messages)
    return f"{title}\n\n{body}"


class StageScreen(Screen):
    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.content = Label(
            text="",
            halign="left",
            valign="top",
            size_hint_y=None,
            font_size="16sp",
            color=(0, 0, 0, 1),
        )
        self.content.bind(texture_size=self._resize_content)
        self.bind(size=self._resize_content)

        scroll = ScrollView()
        scroll.add_widget(self.content)

        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(12), 0, dp(12), 0],
            spacing=dp(2)
        )
        heading = Label(
            text=title,
            size_hint_y=None,
            height=dp(24),
            font_size="22sp",
            bold=True,
            color=(0, 0, 0, 1),
        )
        layout.add_widget(heading)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _resize_content(self, *_):
        self.content.text_size = (max(self.width - dp(40), dp(200)), None)
        self.content.height = self.content.texture_size[1] + dp(24)

    def set_text(self, text: str) -> None:
        self.content.text = text
        self._resize_content()


class VisualizadorRoot(BoxLayout):
    def __init__(self, arquivo_inicial: Optional[Path] = None, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(10), **kwargs)
        self.arquivo_atual: Optional[Path] = arquivo_inicial
        self.resultado: Optional[CompileResult] = None

        barra = BoxLayout(
            size_hint_y=None,
            height=dp(44),
            spacing=dp(8),
            size_hint_x=None
        )
        botao_abrir = Button(text="Abrir arquivo", size_hint_x=None, width=dp(130))
        # botão "Compilar" removido: a abertura de arquivo já dispara a compilação
        self.status = Label(text="Selecione um arquivo .homi para Compilar.", halign="left", color=(0,0,0,1),
        size_hint_y=None,
        height=dp(28))
        self.status.bind(size=self._wrap_status)

        botao_abrir.bind(on_release=self.abrir_seletor_arquivo)
        botao_arvore = Button(text="Árvore", size_hint_x=None, width=dp(90))
        botao_arvore.bind(on_release=lambda *_: self.mostrar_arvore())

        barra.add_widget(botao_abrir)
        barra.add_widget(botao_arvore)

        self.add_widget(barra)
        self.add_widget(self.status)

        self.manager = ScreenManager(
            transition=SlideTransition(duration=0.18),
            size_hint_y=1
        )
        self.tela_lexica = StageScreen(name="lexica", title="Análise Léxica")
        self.tela_sintatica = StageScreen(name="sintatica", title="Análise Sintática")
        self.tela_semantica = StageScreen(name="semantica", title="Análise Semântica")
        self.manager.add_widget(self.tela_lexica)
        self.manager.add_widget(self.tela_sintatica)
        self.manager.add_widget(self.tela_semantica)
        self.add_widget(self.manager)

        navegacao = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.botao_anterior = Button(text="<", size_hint_x=None, width=dp(60))
        self.botao_proximo = Button(text=">", size_hint_x=None, width=dp(60))
        self.indicador = Label(text="Tela 1 de 3")
        self.botao_anterior.bind(on_release=lambda *_: self.mudar_tela(-1))
        self.botao_proximo.bind(on_release=lambda *_: self.mudar_tela(1))
        navegacao.add_widget(self.botao_anterior)
        navegacao.add_widget(self.indicador)
        navegacao.add_widget(self.botao_proximo)
        self.add_widget(navegacao)

        Window.bind(on_key_down=self._on_key_down)
        Clock.schedule_once(lambda *_: self._auto_compilar_inicial())

        # Improve default background for better contrast
        Window.clearcolor = (1, 1, 1, 1)

    def _wrap_status(self, *_):
        self.status.text_size = (self.status.width, None)

    def _auto_compilar_inicial(self) -> None:
        if self.arquivo_atual and self.arquivo_atual.exists():
            self.compilar_arquivo()

    def abrir_seletor_arquivo(self, *_):
        chooser = FileChooserIconView(path=str(self.arquivo_atual.parent) if self.arquivo_atual else str(PROJECT_ROOT))

        popup = Popup(title="Selecionar arquivo Homi", content=chooser, size_hint=(0.9, 0.9))

        def on_selection(instance, selection):
            if selection:
                caminho = Path(selection[0])
                self.arquivo_atual = caminho
                popup.dismiss()
                self.compilar_arquivo()

        chooser.bind(on_submit=lambda instance, selection, touch: on_selection(instance, selection))
        popup.open()

    def compilar_arquivo(self, *_):

        if not self.arquivo_atual:
            self.status.text = (
                "Selecione um arquivo .homi."
            )
            return

        caminho = self.arquivo_atual

        try:
            self.resultado = compile_file(caminho)
        except Exception as exc:
            self.status.text = f"Falha ao processar o arquivo: {exc}"
            return

        self.arquivo_atual = caminho
        self._renderizar_resultado()
        self.status.text = f"Arquivo carregado: {caminho.name}"
        self.manager.current = "lexica"
        self._atualizar_indicador()

    def _renderizar_resultado(self):
        if not self.resultado:
            return

        lexer_summary = [
            f"Arquivo: {self.arquivo_atual}",
            "",
            f"Tokens reconhecidos: {sum(1 for token in self.resultado.tokens if token.tipo != TokenType.EOF)}",
            f"Erros léxicos: {len(self.resultado.lexer_errors)}",
            "",
            format_tokens(self.resultado.tokens),
            "",
            join_messages("Erros léxicos", self.resultado.lexer_errors),
        ]
        self.tela_lexica.set_text("\n".join(lexer_summary))

        sintatico_summary = [
            f"Automações reconhecidas: {len(self.resultado.ast.automacoes)}",
            f"Erros sintáticos: {len(self.resultado.parser_errors)}",
            "",
            format_ast(self.resultado.ast),
            "",
            join_messages("Erros sintáticos", self.resultado.parser_errors),
        ]
        self.tela_sintatica.set_text("\n".join(sintatico_summary))

        semantico_summary = [
            f"Símbolos registrados: {len(getattr(self.resultado.symbol_table, 'listar', lambda: [])())}",
            f"Avisos semânticos: {len(self.resultado.semantic_warnings)}",
            f"Erros semânticos: {len(self.resultado.semantic_errors)}",
            "",
            format_symbol_table(self.resultado.symbol_table),
            "",
            join_messages("Avisos semânticos", self.resultado.semantic_warnings),
            "",
            join_messages("Erros semânticos", self.resultado.semantic_errors),
        ]
        self.tela_semantica.set_text("\n".join(semantico_summary))

    def mudar_tela(self, delta: int):
        telas = ["lexica", "sintatica", "semantica"]
        indice_atual = telas.index(self.manager.current)
        novo_indice = max(0, min(len(telas) - 1, indice_atual + delta))
        self.manager.current = telas[novo_indice]
        self.manager.transition.direction = "left" if delta > 0 else "right"
        self._atualizar_indicador()

    def _atualizar_indicador(self):
        ordem = {"lexica": 1, "sintatica": 2, "semantica": 3}
        self.indicador.text = f"Tela {ordem.get(self.manager.current, 1)} de 3"

    def _on_key_down(self, _window, keycode, _scancode, _codepoint, _modifiers):
        key = keycode[1] if isinstance(keycode, tuple) and len(keycode) > 1 else keycode
        if key in (276, "left"):
            self.mudar_tela(-1)
            return True
        if key in (275, "right"):
            self.mudar_tela(1)
            return True
        return False

    def mostrar_arvore(self):

        if not self.resultado:
            self.status.text = (
                "Compile um arquivo antes de visualizar a árvore sintática."
            )
            return

        popup = Popup(
            title="Árvore Sintática",
            size_hint=(0.95, 0.95)
        )

        widget = ASTTreeWidget(
            self.resultado.ast
        )

        popup.content = widget
        popup.open()


class HomiVisualizerApp(App):
    def __init__(self, arquivo_inicial: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        self.arquivo_inicial = arquivo_inicial

    def build(self):
        self.title = "Homi Visualizador"
        return VisualizadorRoot(arquivo_inicial=self.arquivo_inicial)


class ASTTreeWidget(ScrollView):

    LEFT_MARGIN = 1000
    RIGHT_MARGIN = 1000
    TOP_MARGIN = 1000
    BOTTOM_MARGIN = 1000

    LEVEL_GAP = 220
    LEAF_GAP = 180

    def __init__(self, ast_root, **kwargs):
        super().__init__(**kwargs)

        self.ast_root = ast_root

        self.scale = 1.0

        self.offset_x = 0
        self.offset_y = 0

        self._panning = False
        self._last_pan = (0, 0)

        self.do_scroll_x = True
        self.do_scroll_y = True

        self.panel = FloatLayout(
            size_hint=(None, None),
            size=(4000, 4000)
        )

        self.add_widget(self.panel)

        self.bind(size=self._redraw)

        Clock.schedule_once(lambda *_: self._redraw())

    # =====================================================
    # Zoom
    # =====================================================

    def zoom_in(self, factor=1.2):
        self.scale *= factor
        self._redraw()

    def zoom_out(self, factor=1.2):

        self.scale /= factor

        if self.scale < 0.1:
            self.scale = 0.1

        self._redraw()

    def reset_zoom(self):

        self.scale = 1.0

        self.offset_x = 0
        self.offset_y = 0

        self.scroll_x = 0
        self.scroll_y = 1

        self._redraw()

    def _wrap_text(self, text, width=20):

        lines = []

        for line in str(text).splitlines():

            wrapped = wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=False
            )

            lines.extend(wrapped if wrapped else [""])

        return "\n".join(lines)

    # =====================================================
    # Mouse
    # =====================================================

    def on_touch_down(self, touch):

        if getattr(touch, "is_mouse_scrolling", False):

            if touch.button == "scrolldown":
                self.zoom_in()
                return True

            if touch.button == "scrollup":
                self.zoom_out()
                return True

        if getattr(touch, "button", None) == "middle":

            self._panning = True
            self._last_pan = (touch.x, touch.y)

            return True

        return super().on_touch_down(touch)

    def on_touch_move(self, touch):

        if self._panning:

            dx = touch.x - self._last_pan[0]
            dy = touch.y - self._last_pan[1]

            self.offset_x += dx
            self.offset_y += dy

            self._last_pan = (touch.x, touch.y)

            self._redraw()

            return True

        return super().on_touch_move(touch)

    def on_touch_up(self, touch):

        if getattr(touch, "button", None) == "middle":

            self._panning = False
            return True

        return super().on_touch_up(touch)

    # =====================================================
    # AST -> Dict
    # =====================================================

    def _node_to_dict(self, node):

        if node is None:
            return {"label": "None", "children": []}

        if isinstance(node, list):
            return {
                "label": "list",
                "children": [
                    self._node_to_dict(x)
                    for x in node
                ]
            }

        if not hasattr(node, "__dataclass_fields__"):
            return {
                "label": repr(node),
                "children": []
            }

        children = []

        for field in node.__dataclass_fields__:

            if field == "linha":
                continue

            value = getattr(node, field)

            if isinstance(value, list):

                children.append({
                    "label": field,
                    "children": [
                        self._node_to_dict(item)
                        for item in value
                    ]
                })

            elif hasattr(value, "__dataclass_fields__"):

                children.append(
                    self._node_to_dict(value)
                )

            elif value is not None:

                children.append({
                    "label": (
                        f"{field}:\n"
                        f"{self._wrap_text(value, 20)}"
                    ),
                    "children": []
                })

        return {
            "label": type(node).__name__,
            "children": children
        }

    # =====================================================
    # Layout
    # =====================================================

    def _assign_positions(self, root):

        next_leaf = [0]

        def visit(node, depth=0):

            if not node["children"]:

                x = (
                    next_leaf[0]
                    * self.LEAF_GAP
                    + self.LEFT_MARGIN
                )

                next_leaf[0] += 1

            else:

                for child in node["children"]:
                    visit(child, depth + 1)

                xs = [c["_x"] for c in node["children"]]

                x = sum(xs) / len(xs)

            node["_depth"] = depth
            node["_x"] = x

        visit(root)

        max_depth = [0]

        def find_depth(node):

            max_depth[0] = max(
                max_depth[0],
                node["_depth"]
            )

            for c in node["children"]:
                find_depth(c)

        find_depth(root)

        def assign_y(node):

            node["_y"] = (
                (max_depth[0] - node["_depth"])
                * self.LEVEL_GAP
                + self.TOP_MARGIN
            )

            for c in node["children"]:
                assign_y(c)

        assign_y(root)

    def _flatten(self, node, result):

        result.append(node)

        for child in node["children"]:
            self._flatten(child, result)

    # =====================================================
    # Draw
    # =====================================================

    def _redraw(self, *_):

        root = self._node_to_dict(self.ast_root)

        self._assign_positions(root)

        nodes = []

        self._flatten(root, nodes)

        max_x = max(
            node["_x"]
            for node in nodes
        )

        max_y = max(
            node["_y"]
            for node in nodes
        )

        panel_width = int(
            (
                max_x
                + self.RIGHT_MARGIN
            )
            * self.scale
        )

        panel_height = int(
            (
                max_y
                + self.BOTTOM_MARGIN
            )
            * self.scale
        )

        panel_width = max(
            panel_width,
            int(self.width)
        )

        panel_height = max(
            panel_height,
            int(self.height)
        )

        self.panel.size = (
            panel_width,
            panel_height
        )

        self.panel.canvas.clear()

        with self.panel.canvas:

            Color(0, 0, 0, 1)

            # -------------------------
            # Linhas
            # -------------------------

            for node in nodes:

                for child in node["children"]:

                    x1 = (
                        node["_x"]
                        * self.scale
                        + self.offset_x
                    )

                    y1 = (
                        node["_y"]
                        * self.scale
                        + self.offset_y
                    )

                    x2 = (
                        child["_x"]
                        * self.scale
                        + self.offset_x
                    )

                    y2 = (
                        child["_y"]
                        * self.scale
                        + self.offset_y
                    )

                    Line(
                        points=[
                            x1, y1,
                            x2, y2
                        ],
                        width=max(
                            1,
                            self.scale
                        )
                    )

            # -------------------------
            # Nós
            # -------------------------

            for node in nodes:

                x = (
                    node["_x"]
                    * self.scale
                    + self.offset_x
                )

                y = (
                    node["_y"]
                    * self.scale
                    + self.offset_y
                )

                r = max(
                    5,
                    8 * self.scale
                )

                Ellipse(
                    pos=(x-r, y-r),
                    size=(2*r, 2*r)
                )

                label = CoreLabel(
                    text=str(node["label"]),
                    font_size=max(
                        10,
                        14 * self.scale
                    )
                )

                label.refresh()

                tex = label.texture

                Rectangle(
                    texture=tex,
                    pos=(
                        x - tex.size[0] / 2,
                        y + 15
                    ),
                    size=tex.size
                )

        self.canvas.ask_update()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualizador Kivy das fases do compilador Homi")
    parser.add_argument("arquivo", nargs="?", help="Arquivo .homi para compilar e visualizar")
    return parser.parse_args()


def main():
    args = parse_args()
    arquivo = Path(args.arquivo).resolve() if args.arquivo else None
    HomiVisualizerApp(arquivo_inicial=arquivo).run()


if __name__ == "__main__":
    main()