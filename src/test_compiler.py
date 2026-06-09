#!/usr/bin/env python3
"""
Homi Compiler - Testes Automatizados
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lexer import Lexer, TokenType
from automations_compiler.src.homi_parser import Parser
from semantic import AnalisadorSemantico
from codegen import GeradorYAML


def cor(texto, c):
    cores = {"verde": "\033[92m", "vermelho": "\033[91m", "amarelo": "\033[93m", "reset": "\033[0m"}
    return f"{cores.get(c,'')}{texto}{cores['reset']}"

passou = 0
falhou = 0

def test(nome, fonte, esperado_erros_lex=0, esperado_erros_sin=0, esperado_erros_sem=0, yaml_contem=None):
    global passou, falhou
    lexer = Lexer(fonte)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    sem = AnalisadorSemantico()
    sem.analisar(ast)

    ok = True
    msgs = []

    if len(lexer.erros) != esperado_erros_lex:
        ok = False
        msgs.append(f"  Erros léxicos: esperado {esperado_erros_lex}, obtido {len(lexer.erros)}: {lexer.erros}")
    if len(parser.erros) != esperado_erros_sin:
        ok = False
        msgs.append(f"  Erros sintáticos: esperado {esperado_erros_sin}, obtido {len(parser.erros)}: {parser.erros}")
    if len(sem.erros) != esperado_erros_sem:
        ok = False
        msgs.append(f"  Erros semânticos: esperado {esperado_erros_sem}, obtido {len(sem.erros)}: {sem.erros}")

    if yaml_contem and not (lexer.erros or parser.erros or sem.erros):
        gerador = GeradorYAML()
        yaml = gerador.gerar(ast)
        for trecho in yaml_contem:
            if trecho not in yaml:
                ok = False
                msgs.append(f"  YAML não contém: {trecho!r}")

    if ok:
        print(cor(f"  ✓ PASSOU: {nome}", "verde"))
        passou += 1
    else:
        print(cor(f"  ✗ FALHOU: {nome}", "vermelho"))
        for m in msgs:
            print(m)
        falhou += 1


print("\n══════════════════════════════════════════")
print("  Homi Compiler — Suite de Testes")
print("══════════════════════════════════════════\n")

print("─── Análise Léxica ───────────────────────")

test("Token entity_id simples",
     'automacao "X" { quando luz.sala == verdadeiro entao { ligar luz.sala; } }')

test("Token time_unit segundos",
     'automacao "X" { quando horario == 08:00 entao { esperar 10s; } }',
     yaml_contem=["00:00:10"])

test("Token time_unit minutos",
     'automacao "X" { quando horario == 08:00 entao { esperar 5min; } }',
     yaml_contem=["00:05:00"])

test("Token temperatura",
     'automacao "X" { quando sensor.temp > 28 entao { ajustar clima.ar = 22C; } }',
     yaml_contem=["temperature: 22"])

test("Comentário ignorado",
     '# comentário\nautomacao "X" { quando horario == 10:00 entao { ligar luz.sala; } }')

test("Caractere inválido gera erro léxico",
     'automacao "X" { quando @ == verdadeiro entao { ligar luz.sala; } }',
     esperado_erros_lex=1, esperado_erros_sin=3)

print("\n─── Análise Sintática ────────────────────")

test("Automação completa válida",
     'automacao "Sala" { quando luz.sala == falso entao { ligar luz.sala; } }',
     yaml_contem=["alias: Sala", "light.turn_on"])

test("Múltiplas ações",
     'automacao "Multi" { quando horario == 08:00 entao { ligar luz.sala; desligar luz.quarto; } }')

test("Condicional se/entao/senao/fim",
     'automacao "Cond" { quando sensor.temp > 25 entao { se sensor.temp > 30 entao { ligar luz.sala; } senao { desligar luz.sala; } fim } }')

test("Repetir",
     'automacao "Rep" { quando horario == 10:00 entao { repetir 3 vezes { ligar luz.sala; esperar 1s; desligar luz.sala; } } }',
     yaml_contem=["count: 3"])

test("Falta '{'",
     'automacao "Err" quando luz.sala == verdadeiro entao { ligar luz.sala; } }',
     esperado_erros_sin=1)

test("Falta ';' (recuperação modo pânico)",
     'automacao "Err" { quando horario == 08:00 entao { ligar luz.sala desligar luz.quarto; } }',
     esperado_erros_sin=1)

print("\n─── Análise Semântica ────────────────────")

test("Sensor não pode ser ligado",
     'automacao "X" { quando sensor.temperatura > 25 entao { ligar sensor.temperatura; } }',
     esperado_erros_sem=2)

test("Temperatura em lâmpada gera erro",
     'automacao "X" { quando luz.sala == falso entao { ajustar luz.sala = 25C; } }',
     esperado_erros_sem=1)

test("Luz pode ser ligada normalmente",
     'automacao "X" { quando luz.sala == falso entao { ligar luz.sala; } }',
     esperado_erros_sem=0)

test("Brilho 0-100% válido",
     'automacao "X" { quando horario == 20:00 entao { ligar luz.sala (brilho = 80%); } }',
     esperado_erros_sem=0)

test("Condição com operador em sensor binário inválido",
     'automacao "X" { quando binary_sensor.porta == verdadeiro se binary_sensor.porta > 1 entao { ligar luz.sala; } }',
     esperado_erros_sem=1)

print("\n─── Geração de Código YAML ───────────────")

test("Trigger por horário",
     'automacao "Horario" { quando horario == 08:00 entao { ligar luz.sala; } }',
     yaml_contem=["trigger: time", "at: '08:00'"])

test("Trigger por estado",
     'automacao "Estado" { quando interruptor.botao == verdadeiro entao { ligar luz.sala; } }',
     yaml_contem=["trigger: state", 'to: "on"'])

test("Trigger por sensor numérico",
     'automacao "Sensor" { quando sensor.temperatura > 28 entao { ligar luz.sala; } }',
     yaml_contem=["trigger: numeric_state", "above: 28.0"])

test("Mapeamento domínio luz→light",
     'automacao "Luz" { quando horario == 20:00 entao { ligar luz.sala; } }',
     yaml_contem=["light.turn_on", "light.sala"])

test("Notificar gera serviço notify",
     'automacao "Notif" { quando horario == 08:00 entao { notificar "Bom dia!"; } }',
     yaml_contem=["notify.notify", 'message: "Bom dia!"'])

test("Ativar cena",
     'automacao "Cena" { quando horario == 22:00 entao { ativar cena cena.modo_dormir; } }',
     yaml_contem=["scene.turn_on", "scene.modo_dormir"])

total = passou + falhou
print(f"\n══════════════════════════════════════════")
print(f"  Resultado: {cor(str(passou), 'verde')} passed, {cor(str(falhou), 'vermelho')} failed / {total} total")
print(f"══════════════════════════════════════════\n")
sys.exit(0 if falhou == 0 else 1)
