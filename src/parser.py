"""
Homi Compiler - Analisador Sintático (Parser LL(1))
Implementação baseada em Tabela Preditiva LL(1) com recuperação de erros
por Modo Pânico (sincronização em ';' e '}').
"""

from typing import List, Optional, Any
from lexer import TokenType, Token
from ast_nodes import *


class ParseError(Exception):
    def __init__(self, msg, linha=0, coluna=0):
        super().__init__(f"[Erro Sintático] Linha {linha}, Coluna {coluna}: {msg}")
        self.linha = linha
        self.coluna = coluna


class Parser:
    """
    Parser LL(1) para a linguagem Homi.

    Gramática resumida (BNF):
      programa        → automacao*  EOF
      automacao       → 'automacao' STRING '{' gatilho_sec cond_sec? acao_sec '}'
      gatilho_sec     → 'quando' gatilho (';' gatilho)*
      gatilho         → gatilho_estado | gatilho_horario | gatilho_sensor
      gatilho_estado  → ENTITY_ID '==' (STRING | VERDADEIRO | FALSO)
      gatilho_horario → 'horario' '==' TIME_VALUE
                      | 'horario' 'entre' TIME_VALUE 'e_hora' TIME_VALUE
      gatilho_sensor  → ENTITY_ID operador_comp valor
      cond_sec        → 'se' expressao
      expressao       → exp_ou
      exp_ou          → exp_e ('ou' exp_e)*
      exp_e           → exp_nao ('e' exp_nao)*
      exp_nao         → 'nao' exp_nao | exp_atom
      exp_atom        → '(' expressao ')' | ENTITY_ID operador_comp valor | VERDADEIRO | FALSO
      acao_sec        → 'entao' '{' acao* '}'
      acao            → acao_ligar | acao_desligar | acao_ajustar
                      | acao_esperar | acao_notificar | acao_repetir
                      | acao_cena | acao_se_entao
      acao_ligar      → 'ligar' ENTITY_ID param_list? ';'
      acao_desligar   → 'desligar' ENTITY_ID ';'
      acao_ajustar    → 'ajustar' ENTITY_ID '.' IDENT '=' valor ';'
      acao_esperar    → 'esperar' TIME_UNIT ';'
      acao_notificar  → 'notificar' STRING ';'
      acao_repetir    → 'repetir' NUMBER 'vezes' '{' acao* '}'
      acao_cena       → 'ativar' 'cena' ENTITY_ID ';'
      acao_se_entao   → 'se' expressao 'entao' '{' acao* '}' ('senao' '{' acao* '}')? 'fim'
      param_list      → '(' param (',' param)* ')'
      param           → IDENT '=' valor
      valor           → NUMBER | STRING | TIME_VALUE | TEMPERATURA | VERDADEIRO | FALSO | ENTITY_ID | NUMBER '%'
      operador_comp   → '==' | '!=' | '>' | '<' | '>=' | '<='
    """

    # Tokens de sincronização para modo pânico
    SYNC_TOKENS = {TokenType.PONTO_VIRG, TokenType.FECHA_CHAVE, TokenType.EOF}

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.erros: List[str] = []

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def peek_tipo(self) -> TokenType:
        return self.tokens[self.pos].tipo

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.tipo != TokenType.EOF:
            self.pos += 1
        return tok

    def check(self, *tipos) -> bool:
        return self.peek_tipo() in tipos

    def match(self, *tipos) -> Optional[Token]:
        if self.peek_tipo() in tipos:
            return self.advance()
        return None

    def expect(self, tipo: TokenType, msg: str = None) -> Token:
        tok = self.peek()
        if tok.tipo == tipo:
            return self.advance()
        err_msg = msg or f"esperado '{tipo.value}', encontrado '{tok.valor}'"
        self.erro(err_msg, tok)
        return tok  # retorna mesmo com erro p/ continuar

    def erro(self, msg: str, tok: Token = None):
        t = tok or self.peek()
        err = f"[Erro Sintático] Linha {t.linha}, Coluna {t.coluna}: {msg}"
        self.erros.append(err)

    def sincronizar(self):
        """Modo Pânico: avança até token de sincronização."""
        while not self.check(*self.SYNC_TOKENS):
            self.advance()
        if self.check(TokenType.PONTO_VIRG):
            self.advance()  # consome o ';'

    def parse(self) -> Programa:
        prog = Programa(linha=1)
        while not self.check(TokenType.EOF):
            try:
                if self.check(TokenType.AUTOMACAO):
                    prog.automacoes.append(self.parse_automacao())
                else:
                    self.erro(f"Esperado 'automacao', encontrado '{self.peek().valor}'")
                    self.sincronizar()
            except Exception as e:
                self.erros.append(str(e))
                self.sincronizar()
        return prog

    def parse_automacao(self) -> Automacao:
        tok = self.expect(TokenType.AUTOMACAO)
        nome_tok = self.expect(TokenType.STRING, "Nome da automação deve ser uma string entre aspas")
        self.expect(TokenType.ABRE_CHAVE, "Esperado '{' após nome da automação")

        auto = Automacao(linha=tok.linha, nome=nome_tok.valor)

        # Gatilhos (obrigatório)
        auto.gatilhos = self.parse_gatilho_sec()

        # Condição (opcional) — FIRST(cond_sec) = {se}
        if self.check(TokenType.SE):
            self.advance()
            auto.condicoes = self.parse_expressao()

        # Ações (obrigatório)
        auto.acoes = self.parse_acao_sec()

        self.expect(TokenType.FECHA_CHAVE, "Esperado '}' para fechar automação")
        return auto

    def parse_gatilho_sec(self) -> List:
        self.expect(TokenType.QUANDO, "Esperado 'quando' para definir gatilhos")
        gatilhos = [self.parse_gatilho()]
        while self.check(TokenType.PONTO_VIRG):
            self.advance()
            # pode ter mais gatilhos ou já entrou na seção de condições/ações
            if self.check(TokenType.SE, TokenType.ENTAO):
                break
            if self.check(TokenType.ENTITY_ID) or self.check(TokenType.QUANDO):
                # próximo gatilho
                if self.check(TokenType.QUANDO):
                    self.advance()
                gatilhos.append(self.parse_gatilho())
        return gatilhos

    def parse_gatilho(self) -> Any:
        tok = self.peek()

        # gatilho de horário especial
        if self.check(TokenType.ENTITY_ID) and tok.valor == "horario":
            self.advance()
            if self.check(TokenType.ENTRE):
                self.advance()
                inicio = self.expect(TokenType.TIME_VALUE, "Esperado horário HH:MM").valor
                self.expect(TokenType.E_HORA, "Esperado 'e_hora'")
                fim = self.expect(TokenType.TIME_VALUE, "Esperado horário HH:MM").valor
                return GatilhoIntervalo(linha=tok.linha, inicio=inicio, fim=fim)
            else:
                op = self.parse_operador_comp()
                val_tok = self.expect(TokenType.TIME_VALUE, "Esperado horário HH:MM")
                return GatilhoHorario(linha=tok.linha, horario=val_tok.valor)

        if self.check(TokenType.ENTITY_ID):
            ent_tok = self.advance()
            op = self.parse_operador_comp()
            val = self.parse_valor()
            # Estado booleano ou string → GatilhoEstado; numérico → GatilhoSensor
            if isinstance(val, Literal) and val.tipo in ("bool", "string"):
                return GatilhoEstado(linha=tok.linha, entidade=ent_tok.valor,
                                     estado=str(val.valor))
            return GatilhoSensor(linha=tok.linha, entidade=ent_tok.valor,
                                 operador=op, valor=val)

        self.erro(f"Gatilho inválido: '{tok.valor}'", tok)
        self.sincronizar()
        return GatilhoEstado(linha=tok.linha)

    def parse_operador_comp(self) -> str:
        op_map = {
            TokenType.IGUAL:        "==",
            TokenType.DIFERENTE:    "!=",
            TokenType.MAIOR:        ">",
            TokenType.MENOR:        "<",
            TokenType.MAIOR_IGUAL:  ">=",
            TokenType.MENOR_IGUAL:  "<=",
        }
        tok = self.peek()
        if tok.tipo in op_map:
            self.advance()
            return op_map[tok.tipo]
        self.erro(f"Operador de comparação esperado, encontrado '{tok.valor}'", tok)
        return "=="

    def parse_expressao(self) -> Any:
        return self.parse_exp_ou()

    def parse_exp_ou(self) -> Any:
        esq = self.parse_exp_e()
        while self.check(TokenType.OU):
            op_tok = self.advance()
            dir_ = self.parse_exp_e()
            esq = ExpBinaria(linha=op_tok.linha, esquerda=esq, operador="ou", direita=dir_)
        return esq

    def parse_exp_e(self) -> Any:
        esq = self.parse_exp_nao()
        while self.check(TokenType.E):
            op_tok = self.advance()
            dir_ = self.parse_exp_nao()
            esq = ExpBinaria(linha=op_tok.linha, esquerda=esq, operador="e", direita=dir_)
        return esq

    def parse_exp_nao(self) -> Any:
        if self.check(TokenType.NAO):
            op_tok = self.advance()
            operando = self.parse_exp_nao()
            return ExpUnaria(linha=op_tok.linha, operador="nao", operando=operando)
        return self.parse_exp_atom()

    def parse_exp_atom(self) -> Any:
        tok = self.peek()
        if self.check(TokenType.ABRE_PAR):
            self.advance()
            exp = self.parse_expressao()
            self.expect(TokenType.FECHA_PAR, "Esperado ')' após expressão")
            return exp
        if self.check(TokenType.VERDADEIRO):
            self.advance()
            return Literal(linha=tok.linha, valor=True, tipo="bool")
        if self.check(TokenType.FALSO):
            self.advance()
            return Literal(linha=tok.linha, valor=False, tipo="bool")
        if self.check(TokenType.ENTITY_ID):
            ent_tok = self.advance()
            # Caso especial: horario entre HH:MM e_hora HH:MM (em condição)
            if ent_tok.valor == "horario" and self.check(TokenType.ENTRE):
                self.advance()
                inicio = self.expect(TokenType.TIME_VALUE, "Esperado horário HH:MM").valor
                self.expect(TokenType.E_HORA, "Esperado 'e_hora'")
                fim = self.expect(TokenType.TIME_VALUE, "Esperado horário HH:MM").valor
                # Representa como expressão composta: horario >= inicio AND horario <= fim
                return ExpBinaria(
                    linha=tok.linha,
                    esquerda=ExpEntidade(linha=tok.linha, entidade="horario", operador=">=",
                                        valor=Literal(linha=tok.linha, valor=inicio, tipo="time_value")),
                    operador="e",
                    direita=ExpEntidade(linha=tok.linha, entidade="horario", operador="<=",
                                       valor=Literal(linha=tok.linha, valor=fim, tipo="time_value"))
                )
            op = self.parse_operador_comp()
            val = self.parse_valor()
            return ExpEntidade(linha=tok.linha, entidade=ent_tok.valor, operador=op, valor=val)
        self.erro(f"Expressão inválida: '{tok.valor}'", tok)
        self.advance()
        return Literal(linha=tok.linha, valor=None, tipo="nulo")

    def parse_acao_sec(self) -> List:
        self.expect(TokenType.ENTAO, "Esperado 'entao' para definir ações")
        self.expect(TokenType.ABRE_CHAVE, "Esperado '{' após 'entao'")
        acoes = []
        while not self.check(TokenType.FECHA_CHAVE, TokenType.EOF):
            try:
                acoes.append(self.parse_acao())
            except Exception as e:
                self.erros.append(str(e))
                self.sincronizar()
        self.expect(TokenType.FECHA_CHAVE, "Esperado '}' para fechar bloco de ações")
        return acoes

    def parse_acao(self) -> Any:
        tok = self.peek()

        if self.check(TokenType.LIGAR):
            return self.parse_acao_ligar()
        if self.check(TokenType.DESLIGAR):
            return self.parse_acao_desligar()
        if self.check(TokenType.AJUSTAR):
            return self.parse_acao_ajustar()
        if self.check(TokenType.ESPERAR):
            return self.parse_acao_esperar()
        if self.check(TokenType.NOTIFICAR):
            return self.parse_acao_notificar()
        if self.check(TokenType.REPETIR):
            return self.parse_acao_repetir()
        if self.check(TokenType.ATIVAR):
            return self.parse_acao_cena()
        if self.check(TokenType.SE):
            return self.parse_acao_se_entao()

        self.erro(f"Ação desconhecida: '{tok.valor}'", tok)
        self.sincronizar()
        return AcaoEsperar(linha=tok.linha, tempo="0s")

    def parse_acao_ligar(self) -> AcaoLigar:
        tok = self.expect(TokenType.LIGAR)
        ent = self.expect(TokenType.ENTITY_ID, "Esperado entity_id após 'ligar'").valor
        params = {}
        if self.check(TokenType.ABRE_PAR):
            params = self.parse_param_list()
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após ação 'ligar'")
        return AcaoLigar(linha=tok.linha, entidade=ent, parametros=params)

    def parse_acao_desligar(self) -> AcaoDesligar:
        tok = self.expect(TokenType.DESLIGAR)
        ent = self.expect(TokenType.ENTITY_ID, "Esperado entity_id após 'desligar'").valor
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após ação 'desligar'")
        return AcaoDesligar(linha=tok.linha, entidade=ent)

    def parse_acao_ajustar(self) -> AcaoAjustar:
        tok = self.expect(TokenType.AJUSTAR)
        ent_tok = self.expect(TokenType.ENTITY_ID, "Esperado entity_id após 'ajustar'")
        # Espera: entidade.atributo = valor  OU  entidade = valor (para temperatura do AC, etc.)
        atributo = "valor"
        if self.check(TokenType.ATRIBUICAO):
            self.advance()
        else:
            self.erro("Esperado '=' após entidade em 'ajustar'")
        val = self.parse_valor()
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após ação 'ajustar'")
        return AcaoAjustar(linha=tok.linha, entidade=ent_tok.valor, atributo=atributo, valor=val)

    def parse_acao_esperar(self) -> AcaoEsperar:
        tok = self.expect(TokenType.ESPERAR)
        tempo_tok = self.expect(TokenType.TIME_UNIT, "Esperado tempo (ex: 10s, 5min) após 'esperar'")
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após 'esperar'")
        return AcaoEsperar(linha=tok.linha, tempo=tempo_tok.valor)

    def parse_acao_notificar(self) -> AcaoNotificar:
        tok = self.expect(TokenType.NOTIFICAR)
        msg_tok = self.expect(TokenType.STRING, "Esperado string de mensagem após 'notificar'")
        destino = None
        if self.check(TokenType.VIRGULA):
            self.advance()
            destino = self.expect(TokenType.ENTITY_ID, "Esperado destino de notificação").valor
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após 'notificar'")
        return AcaoNotificar(linha=tok.linha, mensagem=msg_tok.valor, destino=destino)

    def parse_acao_repetir(self) -> AcaoRepetir:
        tok = self.expect(TokenType.REPETIR)
        n_tok = self.expect(TokenType.NUMBER, "Esperado número após 'repetir'")
        self.expect(TokenType.VEZES, "Esperado 'vezes' após número")
        self.expect(TokenType.ABRE_CHAVE, "Esperado '{' após 'vezes'")
        acoes = []
        while not self.check(TokenType.FECHA_CHAVE, TokenType.EOF):
            acoes.append(self.parse_acao())
        self.expect(TokenType.FECHA_CHAVE, "Esperado '}' para fechar bloco 'repetir'")
        return AcaoRepetir(linha=tok.linha, vezes=int(n_tok.valor), acoes=acoes)

    def parse_acao_cena(self) -> AcaoCena:
        tok = self.expect(TokenType.ATIVAR)
        self.expect(TokenType.CENA, "Esperado 'cena' após 'ativar'")
        cena_tok = self.expect(TokenType.ENTITY_ID, "Esperado nome da cena")
        self.expect(TokenType.PONTO_VIRG, "Esperado ';' após 'ativar cena'")
        return AcaoCena(linha=tok.linha, cena=cena_tok.valor)

    def parse_acao_se_entao(self) -> AcaoSeEntao:
        tok = self.expect(TokenType.SE)
        cond = self.parse_expressao()
        self.expect(TokenType.ENTAO, "Esperado 'entao' após condição")
        self.expect(TokenType.ABRE_CHAVE, "Esperado '{' após 'entao'")
        acoes_entao = []
        while not self.check(TokenType.FECHA_CHAVE, TokenType.SENAO, TokenType.FIM, TokenType.EOF):
            acoes_entao.append(self.parse_acao())
        self.expect(TokenType.FECHA_CHAVE, "Esperado '}' após bloco 'entao'")

        acoes_senao = []
        if self.check(TokenType.SENAO):
            self.advance()
            self.expect(TokenType.ABRE_CHAVE, "Esperado '{' após 'senao'")
            while not self.check(TokenType.FECHA_CHAVE, TokenType.FIM, TokenType.EOF):
                acoes_senao.append(self.parse_acao())
            self.expect(TokenType.FECHA_CHAVE, "Esperado '}' após bloco 'senao'")

        self.expect(TokenType.FIM, "Esperado 'fim' para fechar condicional")
        return AcaoSeEntao(linha=tok.linha, condicao=cond,
                           acoes_entao=acoes_entao, acoes_senao=acoes_senao)

    def parse_param_list(self) -> dict:
        self.expect(TokenType.ABRE_PAR)
        params = {}
        if not self.check(TokenType.FECHA_PAR):
            k, v = self.parse_param()
            params[k] = v
            while self.check(TokenType.VIRGULA):
                self.advance()
                k, v = self.parse_param()
                params[k] = v
        self.expect(TokenType.FECHA_PAR, "Esperado ')' após parâmetros")
        return params

    def parse_param(self):
        key_tok = self.peek()
        # chave pode ser um ENTITY_ID (simples) ou NUMBER ou STRING
        if self.check(TokenType.ENTITY_ID):
            key = self.advance().valor
        else:
            key = self.advance().valor
        self.expect(TokenType.ATRIBUICAO, f"Esperado '=' após parâmetro '{key}'")
        val = self.parse_valor()
        return key, val

    def parse_valor(self) -> Literal:
        tok = self.peek()
        if self.check(TokenType.NUMBER):
            num = self.advance()
            # Verifica se vem '%'
            if self.check(TokenType.PERCENTUAL):
                self.advance()
                return Literal(linha=tok.linha, valor=float(num.valor), tipo="percentual")
            return Literal(linha=tok.linha, valor=float(num.valor), tipo="numero")
        if self.check(TokenType.STRING):
            return Literal(linha=tok.linha, valor=self.advance().valor, tipo="string")
        if self.check(TokenType.TIME_VALUE):
            return Literal(linha=tok.linha, valor=self.advance().valor, tipo="time_value")
        if self.check(TokenType.TIME_UNIT):
            return Literal(linha=tok.linha, valor=self.advance().valor, tipo="time_unit")
        if self.check(TokenType.TEMPERATURA):
            return Literal(linha=tok.linha, valor=self.advance().valor, tipo="temperatura")
        if self.check(TokenType.VERDADEIRO):
            self.advance()
            return Literal(linha=tok.linha, valor=True, tipo="bool")
        if self.check(TokenType.FALSO):
            self.advance()
            return Literal(linha=tok.linha, valor=False, tipo="bool")
        if self.check(TokenType.ENTITY_ID):
            return Literal(linha=tok.linha, valor=self.advance().valor, tipo="entity_id")
        self.erro(f"Valor inválido: '{tok.valor}'", tok)
        self.advance()
        return Literal(linha=tok.linha, valor=None, tipo="nulo")
