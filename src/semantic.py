"""
Homi Compiler - Analisador Semântico
Tabela de Símbolos, Verificação de Tipos e Consistência de Domínios.
"""

from typing import Dict, List, Optional, Any
from ast_nodes import *


# Mapeamento: domínio → tipo_homi
DOMINIOS = {
    "luz":          "luz",
    "light":        "luz",
    "interruptor":  "interruptor",
    "switch":       "interruptor",
    "sensor":       "sensor",
    "clima":        "clima",
    "climate":      "clima",
    "cena":         "cena",
    "scene":        "cena",
    "notificacao":  "notificacao",
    "notify":       "notificacao",
    "cobertura":    "cobertura",
    "cover":        "cobertura",
    "media":        "media",
    "media_player": "media",
    "automacao":    "automacao",
    "automation":   "automacao",
    "input_boolean": "interruptor",
    "input_number":  "sensor",
    "binary_sensor": "sensor_binario",
    "person":        "pessoa",
    "zone":          "zona",
    "alarm_control_panel": "alarme",
    "script":        "script",
    "camera":        "camera",
}

# Ações válidas por tipo de domínio
ACOES_VALIDAS = {
    "luz":          {"ligar", "desligar", "ajustar"},
    "interruptor":  {"ligar", "desligar"},
    "sensor":       set(),          # sensores só são lidos, não comandados
    "sensor_binario": set(),
    "clima":        {"ligar", "desligar", "ajustar"},
    "cena":         {"ativar"},
    "notificacao":  {"notificar"},
    "cobertura":    {"ligar", "desligar", "ajustar"},
    "media":        {"ligar", "desligar", "ajustar"},
    "pessoa":       set(),
    "zona":         set(),
    "alarme":       {"ligar", "desligar"},
    "script":       {"ativar"},
    "camera":       set(),
    "automacao":    {"ligar", "desligar"},
}

# Atributos ajustáveis por tipo
ATRIBUTOS_VALIDOS = {
    "luz":   {"brilho", "cor", "temperatura_cor", "valor"},
    "clima": {"temperatura", "modo", "valor"},
    "media": {"volume", "valor"},
    "cobertura": {"posicao", "valor"},
}

# Operadores válidos para cada tipo de sensor
TIPOS_SENSOR = {
    "temperatura": "numero",
    "umidade":     "numero",
    "pressao":     "numero",
    "luminosidade": "numero",
    "movimento":   "bool",
    "porta":       "bool",
    "janela":      "bool",
    "fumaca":      "bool",
    "contato":     "bool",
    "presenca":    "bool",
    "energia":     "numero",
    "potencia":    "numero",
    "bateria":     "numero",
}


class EntradaTabela:
    def __init__(self, nome: str, dominio: str, tipo_homi: str, linha: int = 0):
        self.nome = nome
        self.dominio = dominio
        self.tipo_homi = tipo_homi
        self.linha = linha

    def __repr__(self):
        return f"<{self.nome}: dominio={self.dominio}, tipo={self.tipo_homi}>"


class TabelaSimbolos:
    def __init__(self):
        self.tabela: Dict[str, EntradaTabela] = {}

    def registrar(self, entity_id: str, linha: int = 0) -> EntradaTabela:
        if entity_id in self.tabela:
            return self.tabela[entity_id]
        partes = entity_id.split(".", 1)
        dominio = partes[0].lower()
        tipo_homi = DOMINIOS.get(dominio, "desconhecido")
        entrada = EntradaTabela(entity_id, dominio, tipo_homi, linha)
        self.tabela[entity_id] = entrada
        return entrada

    def buscar(self, entity_id: str) -> Optional[EntradaTabela]:
        return self.tabela.get(entity_id)

    def listar(self) -> List[EntradaTabela]:
        return list(self.tabela.values())

    def __str__(self):
        linhas = ["┌─ Tabela de Símbolos ─────────────────────────────"]
        for nome, ent in self.tabela.items():
            linhas.append(f"│  {nome:<40} domínio={ent.dominio:<15} tipo={ent.tipo_homi}")
        linhas.append("└──────────────────────────────────────────────────")
        return "\n".join(linhas)


class SemanticError(Exception):
    def __init__(self, msg, linha=0):
        super().__init__(f"[Erro Semântico] Linha {linha}: {msg}")
        self.linha = linha


class AnalisadorSemantico:
    """
    Percorre a AST e verifica:
    1. Todos os entity_ids são registrados na tabela de símbolos.
    2. Ações são compatíveis com o domínio da entidade.
    3. Tipos de valores são compatíveis com as ações.
    4. Sensores não recebem comandos.
    """

    def __init__(self):
        self.tabela = TabelaSimbolos()
        self.erros: List[str] = []
        self.avisos: List[str] = []

    def erro(self, msg: str, linha: int = 0):
        err = f"[Erro Semântico] Linha {linha}: {msg}"
        self.erros.append(err)

    def aviso(self, msg: str, linha: int = 0):
        aviso = f"[Aviso Semântico] Linha {linha}: {msg}"
        self.avisos.append(aviso)

    def analisar(self, prog: Programa):
        for auto in prog.automacoes:
            self.analisar_automacao(auto)

    def analisar_automacao(self, auto: Automacao):
        for g in auto.gatilhos:
            self.analisar_gatilho(g)
        if auto.condicoes:
            self.analisar_expressao(auto.condicoes)
        for a in auto.acoes:
            self.analisar_acao(a)

    def analisar_gatilho(self, g):
        if isinstance(g, (GatilhoEstado, GatilhoSensor)):
            entrada = self.tabela.registrar(g.entidade, g.linha)
            if isinstance(g, GatilhoSensor):
                if entrada.tipo_homi not in ("sensor", "sensor_binario", "clima", "media", "desconhecido"):
                    self.aviso(
                        f"Entidade '{g.entidade}' (tipo '{entrada.tipo_homi}') usada como sensor de valor.",
                        g.linha
                    )
        elif isinstance(g, (GatilhoHorario, GatilhoIntervalo)):
            pass  # sem entidade para verificar

    def analisar_expressao(self, exp):
        if isinstance(exp, ExpBinaria):
            self.analisar_expressao(exp.esquerda)
            self.analisar_expressao(exp.direita)
        elif isinstance(exp, ExpUnaria):
            self.analisar_expressao(exp.operando)
        elif isinstance(exp, ExpEntidade):
            entrada = self.tabela.registrar(exp.entidade, exp.linha)
            self.verificar_comparacao(entrada, exp.operador, exp.valor, exp.linha)

    def verificar_comparacao(self, entrada: EntradaTabela, op: str, val: Any, linha: int):
        if isinstance(val, Literal):
            if entrada.tipo_homi == "luz" and val.tipo == "temperatura":
                self.erro(
                    f"Não é possível comparar temperatura com entidade do tipo 'luz' ('{entrada.nome}').",
                    linha
                )
            if entrada.tipo_homi in ("sensor_binario", "interruptor") and val.tipo == "numero":
                if op not in ("==", "!="):
                    self.erro(
                        f"Operador '{op}' inválido para entidade binária '{entrada.nome}'. Use '==' ou '!='.",
                        linha
                    )

    def analisar_acao(self, acao):
        if isinstance(acao, AcaoLigar):
            entrada = self.tabela.registrar(acao.entidade, acao.linha)
            acoes_ok = ACOES_VALIDAS.get(entrada.tipo_homi, set())
            if "ligar" not in acoes_ok and entrada.tipo_homi != "desconhecido":
                self.erro(
                    f"Não é possível usar 'ligar' com entidade do tipo '{entrada.tipo_homi}' ('{acao.entidade}').",
                    acao.linha
                )
            if entrada.tipo_homi == "sensor" or entrada.tipo_homi == "sensor_binario":
                self.erro(
                    f"Sensores não podem ser comandados. '{acao.entidade}' é somente leitura.",
                    acao.linha
                )
            # Verifica parâmetros
            if "brilho" in acao.parametros:
                val = acao.parametros["brilho"]
                if isinstance(val, Literal) and val.tipo == "percentual":
                    if val.valor < 0 or val.valor > 100:
                        self.erro(f"Brilho deve estar entre 0% e 100%.", acao.linha)
                elif isinstance(val, Literal) and val.tipo == "numero":
                    if val.valor < 0 or val.valor > 255:
                        self.erro(f"Brilho numérico deve estar entre 0 e 255.", acao.linha)

        elif isinstance(acao, AcaoDesligar):
            entrada = self.tabela.registrar(acao.entidade, acao.linha)
            acoes_ok = ACOES_VALIDAS.get(entrada.tipo_homi, set())
            if "desligar" not in acoes_ok and entrada.tipo_homi != "desconhecido":
                self.erro(
                    f"Não é possível usar 'desligar' com entidade do tipo '{entrada.tipo_homi}' ('{acao.entidade}').",
                    acao.linha
                )

        elif isinstance(acao, AcaoAjustar):
            entrada = self.tabela.registrar(acao.entidade, acao.linha)
            if "ajustar" not in ACOES_VALIDAS.get(entrada.tipo_homi, set()) and entrada.tipo_homi != "desconhecido":
                self.erro(
                    f"Não é possível usar 'ajustar' com entidade do tipo '{entrada.tipo_homi}' ('{acao.entidade}').",
                    acao.linha
                )
            # Verifica compatibilidade: temperatura para AC etc.
            if isinstance(acao.valor, Literal):
                if acao.valor.tipo == "temperatura" and entrada.tipo_homi not in ("clima", "desconhecido"):
                    self.erro(
                        f"Atribuição de temperatura inválida para entidade '{acao.entidade}' (tipo '{entrada.tipo_homi}').",
                        acao.linha
                    )

        elif isinstance(acao, AcaoCena):
            entrada = self.tabela.registrar(acao.cena, acao.linha)

        elif isinstance(acao, AcaoRepetir):
            if acao.vezes <= 0:
                self.erro(f"Número de repetições deve ser positivo.", acao.linha)
            for a in acao.acoes:
                self.analisar_acao(a)

        elif isinstance(acao, AcaoSeEntao):
            self.analisar_expressao(acao.condicao)
            for a in acao.acoes_entao:
                self.analisar_acao(a)
            for a in acao.acoes_senao:
                self.analisar_acao(a)
