#!/usr/bin/env python3
"""
Homi Compiler - Ponto de Entrada
Uso: python homi.py <arquivo.homi> [-o saida.yaml] [-v] [--tokens] [--ast]
"""

import sys
import argparse
from pathlib import Path

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lexer import Lexer, TokenType
from homi_parser import Parser
from semantic import AnalisadorSemantico
from codegen import GeradorYAML


BANNER = """
╔══════════════════════════════════════════╗
║   Homi Compiler v1.0 — Home Assistant   ║
║   Linguagem para automações residenciais ║
╚══════════════════════════════════════════╝
"""

def compilar(source: str, verbose=False, mostrar_tokens=False, mostrar_ast=False):
    """Executa todas as fases do compilador."""
    erros_total = []

    print(BANNER)

    # ── FASE 1: Análise Léxica ───────────────────────────────
    print("━━━ Fase 1: Análise Léxica ━━━━━━━━━━━━━━━━━━━━━━━━━")
    lexer = Lexer(source)
    tokens = lexer.tokenize()

    if lexer.erros:
        for e in lexer.erros:
            print(f"  {e}")
        erros_total.extend(lexer.erros)
    else:
        print(f"  ✓ {len(tokens)-1} tokens reconhecidos sem erros.")

    if mostrar_tokens:
        print("\n  Tokens:")
        for tok in tokens:
            if tok.tipo != TokenType.EOF:
                print(f"    {tok}")

    # ── FASE 2: Análise Sintática ────────────────────────────
    print("\n━━━ Fase 2: Análise Sintática ━━━━━━━━━━━━━━━━━━━━━━")
    parser = Parser(tokens)
    ast = parser.parse()

    if parser.erros:
        for e in parser.erros:
            print(f"  {e}")
        erros_total.extend(parser.erros)
    else:
        print(f"  ✓ {len(ast.automacoes)} automação(ões) reconhecida(s) sem erros.")

    if mostrar_ast:
        print("\n  AST:")
        _print_ast(ast)

    # ── FASE 3: Análise Semântica ────────────────────────────
    print("\n━━━ Fase 3: Análise Semântica ━━━━━━━━━━━━━━━━━━━━━━")
    semantico = AnalisadorSemantico()
    semantico.analisar(ast)

    if semantico.avisos:
        for a in semantico.avisos:
            print(f"  ⚠  {a}")

    if semantico.erros:
        for e in semantico.erros:
            print(f"  {e}")
        erros_total.extend(semantico.erros)
    else:
        print(f"  ✓ Análise semântica concluída sem erros.")

    if verbose:
        print(f"\n{semantico.tabela}")

    # ── FASE 4: Geração de Código ────────────────────────────
    print("\n━━━ Fase 4: Geração de Código (YAML) ━━━━━━━━━━━━━━━")
    if erros_total:
        print(f"  ✗ Geração de código abortada: {len(erros_total)} erro(s) encontrado(s).")
        print(f"\n  Resumo de erros:")
        for e in erros_total:
            print(f"    {e}")
        return None, erros_total

    gerador = GeradorYAML()
    yaml_out = gerador.gerar(ast)
    print(f"  ✓ YAML gerado com sucesso.")
    return yaml_out, []


def _print_ast(node, indent=0):
    pad = "  " * indent
    nome = type(node).__name__
    if hasattr(node, '__dataclass_fields__'):
        print(f"{pad}{nome}:")
        for campo in node.__dataclass_fields__:
            val = getattr(node, campo)
            if campo == 'linha':
                continue
            if isinstance(val, list):
                if val:
                    print(f"{pad}  {campo}:")
                    for item in val:
                        _print_ast(item, indent + 2)
            elif hasattr(val, '__dataclass_fields__'):
                print(f"{pad}  {campo}:")
                _print_ast(val, indent + 2)
            elif val is not None and val != {}:
                print(f"{pad}  {campo}: {val!r}")
    else:
        print(f"{pad}{node!r}")


def main():
    ap = argparse.ArgumentParser(
        prog="homi",
        description="Compilador Homi → YAML (Home Assistant)"
    )
    ap.add_argument("arquivo", help="Arquivo fonte .homi")
    ap.add_argument("-o", "--saida", help="Arquivo de saída YAML", default=None)
    ap.add_argument("-v", "--verbose", action="store_true", help="Mostra tabela de símbolos")
    ap.add_argument("--tokens", action="store_true", help="Mostra lista de tokens")
    ap.add_argument("--ast", action="store_true", help="Mostra AST")
    args = ap.parse_args()

    path = Path(args.arquivo)
    if not path.exists():
        print(f"Erro: arquivo '{args.arquivo}' não encontrado.")
        sys.exit(1)

    source = path.read_text(encoding="utf-8")
    yaml_out, erros = compilar(source, args.verbose, args.tokens, args.ast)

    if yaml_out:
        saida = args.saida or path.with_suffix(".yaml").name
        Path(saida).write_text(yaml_out, encoding="utf-8")
        print(f"\n  📄 Arquivo gerado: {saida}")
        print(f"\n{'─'*50}")
        print(yaml_out)
    else:
        print(f"\n  Compilação falhou com {len(erros)} erro(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()