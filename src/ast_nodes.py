from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class ASTNode:
    linha: int = 0

# ── Programa ────────────────────────────────────────────────
@dataclass
class Programa(ASTNode):
    automacoes: List["Automacao"] = field(default_factory=list)

# ── Automação ────────────────────────────────────────────────
@dataclass
class Automacao(ASTNode):
    nome: str = ""
    gatilhos: List["Gatilho"] = field(default_factory=list)
    condicoes: Optional["Expressao"] = None
    acoes: List["Acao"] = field(default_factory=list)

# ── Gatilhos ─────────────────────────────────────────────────
@dataclass
class GatilhoEstado(ASTNode):
    """quando dispositivo muda para estado"""
    entidade: str = ""
    estado: str = ""

@dataclass
class GatilhoHorario(ASTNode):
    """quando horario == HH:MM"""
    horario: str = ""

@dataclass
class GatilhoIntervalo(ASTNode):
    """quando horario entre HH:MM e_hora HH:MM"""
    inicio: str = ""
    fim: str = ""

@dataclass
class GatilhoSensor(ASTNode):
    """quando sensor.x operador valor"""
    entidade: str = ""
    operador: str = ""
    valor: Any = None

Gatilho = GatilhoEstado | GatilhoHorario | GatilhoIntervalo | GatilhoSensor

# ── Expressões (condições) ───────────────────────────────────
@dataclass
class ExpBinaria(ASTNode):
    esquerda: Any = None
    operador: str = ""
    direita: Any = None

@dataclass
class ExpUnaria(ASTNode):
    operador: str = ""
    operando: Any = None

@dataclass
class ExpEntidade(ASTNode):
    entidade: str = ""
    operador: str = ""
    valor: Any = None

@dataclass
class Literal(ASTNode):
    valor: Any = None
    tipo: str = ""   # "numero", "string", "bool", "temperatura", "time_unit", "time_value"

Expressao = ExpBinaria | ExpUnaria | ExpEntidade | Literal

# ── Ações ────────────────────────────────────────────────────
@dataclass
class AcaoLigar(ASTNode):
    entidade: str = ""
    parametros: dict = field(default_factory=dict)

@dataclass
class AcaoDesligar(ASTNode):
    entidade: str = ""

@dataclass
class AcaoAjustar(ASTNode):
    entidade: str = ""
    atributo: str = ""
    valor: Any = None

@dataclass
class AcaoEsperar(ASTNode):
    tempo: str = ""   # ex: "10s", "5min"

@dataclass
class AcaoNotificar(ASTNode):
    mensagem: str = ""
    destino: Optional[str] = None

@dataclass
class AcaoRepetir(ASTNode):
    vezes: int = 1
    acoes: List["Acao"] = field(default_factory=list)

@dataclass
class AcaoCena(ASTNode):
    cena: str = ""

@dataclass
class AcaoSeEntao(ASTNode):
    condicao: Any = None
    acoes_entao: List["Acao"] = field(default_factory=list)
    acoes_senao: List["Acao"] = field(default_factory=list)

Acao = AcaoLigar | AcaoDesligar | AcaoAjustar | AcaoEsperar | AcaoNotificar | AcaoRepetir | AcaoCena | AcaoSeEntao
