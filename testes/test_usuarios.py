"""
Usuários e senhas do login próprio.

Módulo de credencial testa-se pelo que ele **recusa**: senha errada, e-mail
inexistente (sem vazar que não existe), senha curta, força bruta. E pelo que
ele guarda: nunca a senha, só o hash — com parâmetros gravados junto.

    pytest testes/test_usuarios.py -q
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_PROJETO))

from orga import usuarios                                                 # noqa: E402


@pytest.fixture()
def arquivo(tmp_path, monkeypatch):
    p = tmp_path / "usuarios.json"
    monkeypatch.setenv("ORG_USUARIOS_ARQUIVO", str(p))
    monkeypatch.delenv("ORG_ESPELHO", raising=False)
    usuarios._TENTATIVAS.clear()
    usuarios._CACHE.clear()
    return p


def test_hash_nao_guarda_a_senha(arquivo):
    usuarios.definir_senha("a@b.com", "segredo-forte")
    bruto = arquivo.read_text(encoding="utf-8")
    assert "segredo-forte" not in bruto
    d = json.loads(bruto)
    assert d["usuarios"]["a@b.com"]["hash"].startswith("scrypt$16384$8$1$")


def test_confere_certo_e_recusa_errado(arquivo):
    usuarios.definir_senha("A@B.com", "segredo-forte")          # normaliza o e-mail
    assert usuarios.conferir("a@b.com", "segredo-forte") is True
    assert usuarios.conferir("a@b.com", "segredo-fort") is False
    assert usuarios.conferir("ninguem@b.com", "segredo-forte") is False


def test_hashes_diferentes_para_a_mesma_senha(arquivo):
    """Salt aleatório: duas pessoas com a mesma senha não têm o mesmo hash."""
    assert usuarios.hash_senha("x" * 12) != usuarios.hash_senha("x" * 12)


def test_politica_recusa_senha_curta(arquivo):
    with pytest.raises(ValueError, match="pelo menos"):
        usuarios.definir_senha("a@b.com", "curta")
    assert usuarios.existe("a@b.com") is False


def test_politica_recusa_email_invalido(arquivo):
    with pytest.raises(ValueError):
        usuarios.definir_senha("sem-arroba", "segredo-forte")


def test_forca_bruta_trava_depois_de_cinco_erros(arquivo):
    usuarios.definir_senha("a@b.com", "segredo-forte")
    for _ in range(usuarios.TENTATIVAS_MAX):
        assert usuarios.conferir("a@b.com", "errada-errada") is False
    assert usuarios.travado("a@b.com") > 0
    # Travado, nem a senha CERTA entra — é o que torna o palpite caro.
    assert usuarios.conferir("a@b.com", "segredo-forte") is False


def test_acerto_zera_o_contador(arquivo):
    usuarios.definir_senha("a@b.com", "segredo-forte")
    usuarios.conferir("a@b.com", "errada-errada")
    assert usuarios.conferir("a@b.com", "segredo-forte") is True
    assert usuarios.travado("a@b.com") == 0


def test_email_inexistente_custa_o_mesmo_tempo(arquivo):
    """Sem enumeração: a resposta para quem não existe paga um scrypt também."""
    usuarios.definir_senha("a@b.com", "segredo-forte")
    t0 = time.perf_counter(); usuarios.conferir("a@b.com", "errada-errada"); t1 = time.perf_counter()
    usuarios.conferir("zz@b.com", "errada-errada"); t2 = time.perf_counter()
    existe, nao_existe = t1 - t0, t2 - t1
    assert nao_existe > existe * 0.3        # mesma ordem de grandeza, não "instantâneo"


def test_senha_temporaria_exige_troca(arquivo):
    usuarios.definir_senha("a@b.com", "temporaria-1", precisa_trocar=True, por="admin")
    assert usuarios.precisa_trocar("a@b.com") is True
    usuarios.definir_senha("a@b.com", "definitiva-1")
    assert usuarios.precisa_trocar("a@b.com") is False


def test_remover_bloqueia_o_login(arquivo):
    usuarios.definir_senha("a@b.com", "segredo-forte")
    assert usuarios.remover("a@b.com") is True
    assert usuarios.conferir("a@b.com", "segredo-forte") is False
    assert usuarios.remover("a@b.com") is False


def test_listar_nao_expoe_o_hash(arquivo):
    usuarios.definir_senha("a@b.com", "segredo-forte")
    (linha,) = usuarios.listar()
    assert linha["email"] == "a@b.com" and "hash" not in linha


def test_bootstrap_do_ambiente_so_no_vazio(arquivo, monkeypatch):
    monkeypatch.setenv("ORG_ADMIN_EMAIL", "op@gplansis.com")
    monkeypatch.setenv("ORG_ADMIN_SENHA", "senha-inicial")
    assert usuarios.bootstrap_do_ambiente() == "op@gplansis.com"
    # Já existe alguém: a variável não sobrescreve nem cria mais nada.
    monkeypatch.setenv("ORG_ADMIN_EMAIL", "outro@gplansis.com")
    assert usuarios.bootstrap_do_ambiente() is None
    assert usuarios.existe("outro@gplansis.com") is False


def test_arquivo_corrompido_nao_derruba(arquivo):
    arquivo.write_text("{lixo", encoding="utf-8")
    usuarios._CACHE.clear()
    assert usuarios.total() == 0
    assert usuarios.conferir("a@b.com", "x" * 10) is False
