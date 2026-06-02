"""
Homi Compiler - Gerador de Código (AST → YAML Home Assistant)
Traduz a AST para o formato declarativo do Home Assistant.
"""

import re
from typing import Any, List
from ast_nodes import *


def _yaml_str(s: str) -> str:
    """Encapsula string em aspas simples se necessário."""
    if any(c in s for c in [':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`', "'"]):
        return f'"{s}"'
    if s.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', 'null', '~'):
        return f'"{s}"'
    return s


def _indent(text: str, n: int) -> str:
    pad = "  " * n
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


def _bool_to_yaml(v) -> str:
    return "true" if v else "false"


def _valor_to_yaml(val: Any) -> str:
    if isinstance(val, Literal):
        if val.tipo == "bool":
            return _bool_to_yaml(val.valor)
        if val.tipo == "string":
            return _yaml_str(str(val.valor))
        if val.tipo == "percentual":
            # converte % para 0-255
            return str(int(float(val.valor) * 255 / 100))
        if val.tipo == "temperatura":
            # remove 'C' do final
            return str(val.valor).rstrip("C")
        return str(val.valor)
    return str(val)


def _entity_to_ha(entity_id: str) -> str:
    """Normaliza entity_id para o padrão Home Assistant (dominio.nome)."""
    # Mapeamento de domínios Homi → HA
    mapa = {
        "luz": "light",
        "interruptor": "switch",
        "sensor": "sensor",
        "clima": "climate",
        "cena": "scene",
        "cobertura": "cover",
        "media": "media_player",
        "notificacao": "notify",
        "alarme": "alarm_control_panel",
    }
    partes = entity_id.split(".", 1)
    if len(partes) == 2:
        dom = mapa.get(partes[0].lower(), partes[0].lower())
        return f"{dom}.{partes[1]}"
    return entity_id


def _servico_ligar(entity_id: str) -> str:
    """Retorna o serviço HA correto para 'ligar'."""
    dom = entity_id.split(".")[0].lower()
    mapa_ligar = {
        "light": "light.turn_on",
        "switch": "switch.turn_on",
        "climate": "climate.turn_on",
        "cover": "cover.open_cover",
        "media_player": "media_player.media_play",
        "alarm_control_panel": "alarm_control_panel.alarm_disarm",
        "script": "script.turn_on",
        "scene": "scene.turn_on",
        "automation": "automation.turn_on",
    }
    return mapa_ligar.get(dom, f"homeassistant.turn_on")


def _servico_desligar(entity_id: str) -> str:
    dom = entity_id.split(".")[0].lower()
    mapa_desligar = {
        "light": "light.turn_off",
        "switch": "switch.turn_off",
        "climate": "climate.turn_off",
        "cover": "cover.close_cover",
        "media_player": "media_player.media_pause",
        "alarm_control_panel": "alarm_control_panel.alarm_arm_away",
        "script": "script.turn_off",
        "automation": "automation.turn_off",
    }
    return mapa_desligar.get(dom, "homeassistant.turn_off")


def _op_ha(op: str) -> str:
    mapa = {"==": "=", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<="}
    return mapa.get(op, op)


class GeradorYAML:
    """Gera YAML compatível com Home Assistant a partir da AST."""

    def __init__(self):
        self.saida: List[str] = []

    def gerar(self, prog: Programa) -> str:
        blocos = []
        for auto in prog.automacoes:
            blocos.append(self.gerar_automacao(auto))
        return "\n\n".join(blocos)

    def gerar_automacao(self, auto: Automacao) -> str:
        lines = []
        nome_slug = re.sub(r'\s+', '_', auto.nome.lower())
        lines.append(f"- id: '{nome_slug}'")
        lines.append(f"  alias: {_yaml_str(auto.nome)}")
        lines.append(f"  description: 'Gerado pelo compilador Homi'")

        # Triggers
        lines.append("  triggers:")
        for g in auto.gatilhos:
            lines.extend(self.gerar_gatilho(g))

        # Conditions
        if auto.condicoes:
            lines.append("  conditions:")
            lines.extend(self.gerar_condicao(auto.condicoes))
        else:
            lines.append("  conditions: []")

        # Actions
        lines.append("  actions:")
        for a in auto.acoes:
            lines.extend(self.gerar_acao(a))

        lines.append("  mode: single")
        return "\n".join(lines)

    # ── Gatilhos ─────────────────────────────────────────────
    def gerar_gatilho(self, g) -> List[str]:
        lines = []
        if isinstance(g, GatilhoEstado):
            ha_ent = _entity_to_ha(g.entidade)
            estado_ha = {"verdadeiro": "on", "falso": "off", "true": "on", "false": "off"}.get(
                g.estado.lower(), g.estado
            )
            lines.append(f"    - trigger: state")
            lines.append(f"      entity_id: {ha_ent}")
            lines.append(f"      to: {_yaml_str(estado_ha)}")

        elif isinstance(g, GatilhoHorario):
            lines.append(f"    - trigger: time")
            lines.append(f"      at: '{g.horario}'")

        elif isinstance(g, GatilhoIntervalo):
            lines.append(f"    - trigger: time")
            lines.append(f"      at: '{g.inicio}'")
            lines.append(f"    - trigger: time")
            lines.append(f"      at: '{g.fim}'")

        elif isinstance(g, GatilhoSensor):
            ha_ent = _entity_to_ha(g.entidade)
            val_yaml = _valor_to_yaml(g.valor) if isinstance(g.valor, Literal) else str(g.valor)
            lines.append(f"    - trigger: numeric_state")
            lines.append(f"      entity_id: {ha_ent}")
            if g.operador in (">", ">="):
                lines.append(f"      above: {val_yaml}")
            elif g.operador in ("<", "<="):
                lines.append(f"      below: {val_yaml}")
            else:
                lines.append(f"      above: {val_yaml}")
                lines.append(f"      below: {val_yaml}")

        return lines

    # ── Condições ─────────────────────────────────────────────
    def gerar_condicao(self, exp, indent=4) -> List[str]:
        pad = "  " * indent
        lines = []
        if isinstance(exp, ExpBinaria):
            if exp.operador == "e":
                lines.append(f"{pad}- condition: and")
                lines.append(f"{pad}  conditions:")
                lines.extend(self.gerar_condicao(exp.esquerda, indent + 2))
                lines.extend(self.gerar_condicao(exp.direita, indent + 2))
            elif exp.operador == "ou":
                lines.append(f"{pad}- condition: or")
                lines.append(f"{pad}  conditions:")
                lines.extend(self.gerar_condicao(exp.esquerda, indent + 2))
                lines.extend(self.gerar_condicao(exp.direita, indent + 2))

        elif isinstance(exp, ExpUnaria) and exp.operador == "nao":
            lines.append(f"{pad}- condition: not")
            lines.append(f"{pad}  conditions:")
            lines.extend(self.gerar_condicao(exp.operando, indent + 2))

        elif isinstance(exp, ExpEntidade):
            ha_ent = _entity_to_ha(exp.entidade)
            val_yaml = _valor_to_yaml(exp.valor)
            dom = ha_ent.split(".")[0]
            if dom in ("sensor", "input_number", "binary_sensor"):
                lines.append(f"{pad}- condition: numeric_state")
                lines.append(f"{pad}  entity_id: {ha_ent}")
                if exp.operador in (">", ">="):
                    lines.append(f"{pad}  above: {val_yaml}")
                elif exp.operador in ("<", "<="):
                    lines.append(f"{pad}  below: {val_yaml}")
                else:
                    lines.append(f"{pad}  above: {val_yaml}")
            else:
                lines.append(f"{pad}- condition: state")
                lines.append(f"{pad}  entity_id: {ha_ent}")
                estado = {"verdadeiro": "on", "falso": "off", "True": "on", "False": "off"}.get(
                    str(val_yaml), val_yaml
                )
                lines.append(f"{pad}  state: {_yaml_str(str(estado))}")

        elif isinstance(exp, Literal):
            if exp.tipo == "bool":
                lines.append(f"{pad}- condition: template")
                lines.append(f"{pad}  value_template: '{_bool_to_yaml(exp.valor)}'")

        return lines

    # ── Ações ─────────────────────────────────────────────────
    def gerar_acao(self, acao, indent=2) -> List[str]:
        pad = "  " * indent
        lines = []

        if isinstance(acao, AcaoLigar):
            ha_ent = _entity_to_ha(acao.entidade)
            servico = _servico_ligar(ha_ent)
            lines.append(f"{pad}- action: {servico}")
            lines.append(f"{pad}  target:")
            lines.append(f"{pad}    entity_id: {ha_ent}")
            if acao.parametros:
                lines.append(f"{pad}  data:")
                for k, v in acao.parametros.items():
                    # Normaliza nomes de parâmetros
                    ha_key = {"brilho": "brightness", "cor": "color_name",
                              "temperatura_cor": "color_temp"}.get(k, k)
                    lines.append(f"{pad}    {ha_key}: {_valor_to_yaml(v)}")

        elif isinstance(acao, AcaoDesligar):
            ha_ent = _entity_to_ha(acao.entidade)
            servico = _servico_desligar(ha_ent)
            lines.append(f"{pad}- action: {servico}")
            lines.append(f"{pad}  target:")
            lines.append(f"{pad}    entity_id: {ha_ent}")

        elif isinstance(acao, AcaoAjustar):
            ha_ent = _entity_to_ha(acao.entidade)
            dom = ha_ent.split(".")[0]
            if dom == "climate":
                lines.append(f"{pad}- action: climate.set_temperature")
                lines.append(f"{pad}  target:")
                lines.append(f"{pad}    entity_id: {ha_ent}")
                lines.append(f"{pad}  data:")
                lines.append(f"{pad}    temperature: {_valor_to_yaml(acao.valor)}")
            elif dom == "media_player":
                lines.append(f"{pad}- action: media_player.volume_set")
                lines.append(f"{pad}  target:")
                lines.append(f"{pad}    entity_id: {ha_ent}")
                lines.append(f"{pad}  data:")
                val = _valor_to_yaml(acao.valor)
                if isinstance(acao.valor, Literal) and acao.valor.tipo == "percentual":
                    val = str(float(acao.valor.valor) / 100)
                lines.append(f"{pad}    volume_level: {val}")
            else:
                lines.append(f"{pad}- action: light.turn_on")
                lines.append(f"{pad}  target:")
                lines.append(f"{pad}    entity_id: {ha_ent}")
                lines.append(f"{pad}  data:")
                lines.append(f"{pad}    brightness: {_valor_to_yaml(acao.valor)}")

        elif isinstance(acao, AcaoEsperar):
            lines.append(f"{pad}- delay: '{_tempo_ha(acao.tempo)}'")

        elif isinstance(acao, AcaoNotificar):
            destino = _entity_to_ha(acao.destino) if acao.destino else "notify.notify"
            servico = destino if "." in destino else f"notify.{destino}"
            lines.append(f"{pad}- action: {servico}")
            lines.append(f"{pad}  data:")
            lines.append(f"{pad}    message: {_yaml_str(acao.mensagem)}")

        elif isinstance(acao, AcaoCena):
            ha_cena = _entity_to_ha(acao.cena)
            lines.append(f"{pad}- action: scene.turn_on")
            lines.append(f"{pad}  target:")
            lines.append(f"{pad}    entity_id: {ha_cena}")

        elif isinstance(acao, AcaoRepetir):
            lines.append(f"{pad}- repeat:")
            lines.append(f"{pad}    count: {acao.vezes}")
            lines.append(f"{pad}    sequence:")
            for a in acao.acoes:
                lines.extend(self.gerar_acao(a, indent + 2))

        elif isinstance(acao, AcaoSeEntao):
            lines.append(f"{pad}- choose:")
            lines.append(f"{pad}    - conditions:")
            lines.extend(self.gerar_condicao(acao.condicao, indent + 3))
            lines.append(f"{pad}      sequence:")
            for a in acao.acoes_entao:
                lines.extend(self.gerar_acao(a, indent + 3))
            if acao.acoes_senao:
                lines.append(f"{pad}  default:")
                for a in acao.acoes_senao:
                    lines.extend(self.gerar_acao(a, indent + 2))

        return lines


def _tempo_ha(tempo: str) -> str:
    """Converte tempo Homi para formato HH:MM:SS do Home Assistant."""
    m = re.match(r'^(\d+(?:\.\d+)?)(s|min|h)$', tempo)
    if not m:
        return "00:00:01"
    val, unidade = float(m.group(1)), m.group(2)
    if unidade == "s":
        segundos = int(val)
        return f"00:00:{segundos:02d}"
    elif unidade == "min":
        minutos = int(val)
        return f"00:{minutos:02d}:00"
    elif unidade == "h":
        horas = int(val)
        return f"{horas:02d}:00:00"
    return "00:00:01"
