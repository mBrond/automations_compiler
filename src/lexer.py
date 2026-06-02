from enum import Enum
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    # Palavras-chave
    AUTOMACAO     = "automacao"
    QUANDO        = "quando"
    SE            = "se"
    ENTAO         = "entao"
    SENAO         = "senao"
    FIM           = "fim"
    DISPOSITIVO   = "dispositivo"
    LIGAR         = "ligar"
    DESLIGAR      = "desligar"
    AJUSTAR       = "ajustar"
    ESPERAR       = "esperar"
    NOTIFICAR     = "notificar"
    REPETIR       = "repetir"
    VEZES         = "vezes"
    E             = "e"
    OU            = "ou"
    NAO           = "nao"
    VERDADEIRO    = "verdadeiro"
    FALSO         = "falso"
    ENTRE         = "entre"
    E_HORA        = "e_hora"   # para "entre 08:00 e_hora 22:00"
    CENA          = "cena"
    ATIVAR        = "ativar"
    MODO          = "modo"

    # Literais
    ENTITY_ID     = "ENTITY_ID"     
    NUMBER        = "NUMBER"
    STRING        = "STRING"
    TIME_UNIT     = "TIME_UNIT"     
    TIME_VALUE    = "TIME_VALUE"
    TEMPERATURA   = "TEMPERATURA"

    # Operadores e Comparadores
    MAIOR         = ">"
    MENOR         = "<"
    MAIOR_IGUAL   = ">="
    MENOR_IGUAL   = "<="
    IGUAL         = "=="
    DIFERENTE     = "!="
    ATRIBUICAO    = "="

    # Delimitadores
    ABRE_CHAVE    = "{"
    FECHA_CHAVE   = "}"
    ABRE_PAR      = "("
    FECHA_PAR     = ")"
    PONTO_VIRG    = ";"
    VIRGULA       = ","
    DOIS_PONTOS   = ":"
    PERCENTUAL    = "%"

    # Especiais
    NEWLINE       = "NEWLINE"
    EOF           = "EOF"
    ERRO          = "ERRO"


@dataclass
class Token:
    tipo: TokenType
    valor: str
    linha: int
    coluna: int

    def __repr__(self):
        return f"Token({self.tipo.name}, {self.valor!r}, L{self.linha}:C{self.coluna})"


# Mapeamento de palavras-chave
KEYWORDS = {
    "automacao": TokenType.AUTOMACAO,
    "quando":    TokenType.QUANDO,
    "se":        TokenType.SE,
    "entao":     TokenType.ENTAO,
    "senao":     TokenType.SENAO,
    "fim":       TokenType.FIM,
    "dispositivo": TokenType.DISPOSITIVO,
    "ligar":     TokenType.LIGAR,
    "desligar":  TokenType.DESLIGAR,
    "ajustar":   TokenType.AJUSTAR,
    "esperar":   TokenType.ESPERAR,
    "notificar": TokenType.NOTIFICAR,
    "repetir":   TokenType.REPETIR,
    "vezes":     TokenType.VEZES,
    "e":         TokenType.E,
    "ou":        TokenType.OU,
    "nao":       TokenType.NAO,
    "verdadeiro": TokenType.VERDADEIRO,
    "falso":     TokenType.FALSO,
    "entre":     TokenType.ENTRE,
    "e_hora":    TokenType.E_HORA,
    "cena":      TokenType.CENA,
    "ativar":    TokenType.ATIVAR,
    "modo":      TokenType.MODO,
}


class LexerError(Exception):
    def __init__(self, msg, linha, coluna):
        super().__init__(f"[Erro Léxico] Linha {linha}, Coluna {coluna}: {msg}")
        self.linha = linha
        self.coluna = coluna


class Lexer:
    """
    DFA Manual para tokenização da linguagem Homi.
    Estados: START, IN_IDENT, IN_NUMBER, IN_STRING, IN_COMMENT,
             IN_TIME, IN_ENTITY, IN_OPERATOR
    """

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.linha = 1
        self.coluna = 1
        self.tokens: List[Token] = []
        self.erros: List[str] = []

    def erro(self, msg: str):
        err = f"[Erro Léxico] Linha {self.linha}, Coluna {self.coluna}: {msg}"
        self.erros.append(err)

    def peek(self, offset=0) -> Optional[str]:
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1
        return ch

    def skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
            self.advance()

    def skip_comment(self):
        """Pula comentários de linha iniciados com #"""
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            self.advance()

    def read_string(self) -> Token:
        linha, col = self.linha, self.coluna
        self.advance()  # consume "
        buf = ""
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '"':
                self.advance()
                return Token(TokenType.STRING, buf, linha, col)
            if ch == '\n':
                self.erro("String não fechada")
                return Token(TokenType.ERRO, buf, linha, col)
            if ch == '\\':
                self.advance()
                esc = self.source[self.pos] if self.pos < len(self.source) else ''
                escapes = {'n': '\n', 't': '\t', '"': '"', '\\': '\\'}
                buf += escapes.get(esc, esc)
                self.advance()
            else:
                buf += ch
                self.advance()
        self.erro("String não fechada no fim do arquivo")
        return Token(TokenType.ERRO, buf, linha, col)

    def read_number_or_time(self) -> Token:
        """
        Lê número, unidade de tempo (10s, 5min, 2h), temperatura (25C, 18.5C)
        ou horário HH:MM já tratado como TIME_VALUE quando encontrar padrão.
        """
        linha, col = self.linha, self.coluna
        buf = ""
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            buf += self.advance()

        # Verifica unidade de tempo: s, min, h
        rest = self.source[self.pos:self.pos+3]
        if rest.startswith("min"):
            buf += self.source[self.pos:self.pos+3]
            self.pos += 3; self.coluna += 3
            return Token(TokenType.TIME_UNIT, buf, linha, col)
        elif self.pos < len(self.source) and self.source[self.pos] == 's' and (self.pos+1 >= len(self.source) or not self.source[self.pos+1].isalpha()):
            buf += self.advance()
            return Token(TokenType.TIME_UNIT, buf, linha, col)
        elif self.pos < len(self.source) and self.source[self.pos] == 'h' and (self.pos+1 >= len(self.source) or not self.source[self.pos+1].isalpha()):
            buf += self.advance()
            return Token(TokenType.TIME_UNIT, buf, linha, col)
        elif self.pos < len(self.source) and self.source[self.pos] == 'C' and (self.pos+1 >= len(self.source) or not self.source[self.pos+1].isalpha()):
            buf += self.advance()
            return Token(TokenType.TEMPERATURA, buf, linha, col)
        elif self.pos < len(self.source) and self.source[self.pos] == ':':
            # horário HH:MM
            buf += self.advance()
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                buf += self.advance()
            return Token(TokenType.TIME_VALUE, buf, linha, col)

        return Token(TokenType.NUMBER, buf, linha, col)

    def read_ident_or_entity(self) -> Token:
        """
        Lê identificador, palavra-chave ou entity_id (dominio.nome_entidade).
        Entity IDs têm formato: palavra.palavra(_palavra)*
        """
        linha, col = self.linha, self.coluna
        buf = ""
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] in '_'):
            buf += self.advance()

        # Verifica se é entity_id: tem um ponto seguido de identificador
        if self.pos < len(self.source) and self.source[self.pos] == '.':
            after_dot = self.pos + 1
            if after_dot < len(self.source) and (self.source[after_dot].isalpha() or self.source[after_dot] == '_'):
                buf += self.advance()  # consume '.'
                while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] in '_'):
                    buf += self.advance()
                return Token(TokenType.ENTITY_ID, buf, linha, col)

        lower = buf.lower()
        kw = KEYWORDS.get(lower)
        if kw:
            return Token(kw, lower, linha, col)

        return Token(TokenType.ENTITY_ID, buf, linha, col)

    def next_token(self) -> Token:
        self.skip_whitespace()

        if self.pos >= len(self.source):
            return Token(TokenType.EOF, "", self.linha, self.coluna)

        ch = self.source[self.pos]
        linha, col = self.linha, self.coluna

        # Comentários
        if ch == '#':
            self.skip_comment()
            return self.next_token()

        # Nova linha (relevante para recuperação)
        if ch == '\n':
            self.advance()
            return Token(TokenType.NEWLINE, "\\n", linha, col)

        # String
        if ch == '"':
            return self.read_string()

        # Número ou tempo ou temperatura
        if ch.isdigit():
            return self.read_number_or_time()

        # Identificadores, palavras-chave, entity_ids
        if ch.isalpha() or ch == '_':
            return self.read_ident_or_entity()

        # Operadores de dois caracteres
        if ch == '>' and self.peek(1) == '=':
            self.advance(); self.advance()
            return Token(TokenType.MAIOR_IGUAL, ">=", linha, col)
        if ch == '<' and self.peek(1) == '=':
            self.advance(); self.advance()
            return Token(TokenType.MENOR_IGUAL, "<=", linha, col)
        if ch == '=' and self.peek(1) == '=':
            self.advance(); self.advance()
            return Token(TokenType.IGUAL, "==", linha, col)
        if ch == '!' and self.peek(1) == '=':
            self.advance(); self.advance()
            return Token(TokenType.DIFERENTE, "!=", linha, col)

        # Operadores e delimitadores simples
        simples = {
            '>': TokenType.MAIOR,
            '<': TokenType.MENOR,
            '=': TokenType.ATRIBUICAO,
            '{': TokenType.ABRE_CHAVE,
            '}': TokenType.FECHA_CHAVE,
            '(': TokenType.ABRE_PAR,
            ')': TokenType.FECHA_PAR,
            ';': TokenType.PONTO_VIRG,
            ',': TokenType.VIRGULA,
            ':': TokenType.DOIS_PONTOS,
            '%': TokenType.PERCENTUAL,
        }
        if ch in simples:
            self.advance()
            return Token(simples[ch], ch, linha, col)

        # Caractere desconhecido
        self.erro(f"Caractere inesperado: '{ch}'")
        self.advance()
        return Token(TokenType.ERRO, ch, linha, col)

    def tokenize(self) -> List[Token]:
        """Tokeniza todo o source e retorna lista de tokens (sem NEWLINEs internos)."""
        self.tokens = []
        while True:
            tok = self.next_token()
            if tok.tipo == TokenType.NEWLINE:
                continue  # ignorar newlines no fluxo principal
            self.tokens.append(tok)
            if tok.tipo == TokenType.EOF:
                break
        return self.tokens
