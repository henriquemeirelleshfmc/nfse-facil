"""Testes automatizados para o repositório SqliteEmpresaRepository."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import pytest

from nfse_facil.domain.exceptions import CNPJDuplicadoError, PersistenciaError
from nfse_facil.domain.models import Empresa
from nfse_facil.infrastructure.database.connection import get_connection
from nfse_facil.infrastructure.repositories.sqlite import SqliteEmpresaRepository


class TestSqliteEmpresaRepository:
    """Validação completa das operações de persistência e regras de negócio no SQLite."""

    def test_insercao_e_leitura_cnpj_numerico_com_zeros(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_numerico.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        empresa = Empresa(
            razao_social="Banco do Brasil S/A",
            nome_fantasia="Banco do Brasil",
            cnpj="00.000.000/0001-91",  # Zeros à esquerda
            pasta_documentos=tmp_path / "bb",
        )
        repo.salvar(empresa)

        # Busca por ID
        encontrada = repo.obter_por_id(empresa.id)
        assert encontrada is not None
        assert encontrada.id == empresa.id
        assert encontrada.razao_social == "Banco do Brasil S/A"
        assert encontrada.cnpj == "00000000000191"  # Preserva zeros à esquerda rigorosamente
        assert encontrada.cnpj_formatado == "00.000.000/0001-91"

        # Busca por CNPJ com e sem máscara
        assert repo.obter_por_cnpj("00000000000191") == encontrada
        assert repo.obter_por_cnpj("00.000.000/0001-91") == encontrada

    def test_insercao_e_leitura_cnpj_alfanumerico(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_alfanumerico.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        empresa = Empresa(
            razao_social="Alfa Tecnologia e Inovação Ltda",
            nome_fantasia="Alfa Tech",
            cnpj="12.ABC.345/0001-88",
            pasta_documentos=tmp_path / "alfa",
        )
        repo.salvar(empresa)

        encontrada = repo.obter_por_id(empresa.id)
        assert encontrada is not None
        assert encontrada.cnpj == "12ABC345000188"
        assert encontrada.cnpj_formatado == "12.ABC.345/0001-88"

        # Busca em minúsculas
        assert repo.obter_por_cnpj("12abc345000188") == encontrada

    def test_atualizacao_preserva_id_e_criado_em_e_atualiza_timestamp(
        self, tmp_path: Path
    ) -> None:
        import re
        db_path = tmp_path / "repo_update.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        # Data inicial conhecida no passado com microsecond == 0 para comprovar timespec='microseconds'
        data_criacao = datetime(2020, 1, 1, 12, 0, 0, 0, tzinfo=timezone.utc)
        empresa = Empresa(
            razao_social="Oficina Original Ltda",
            cnpj="33.000.167/0001-01",
            pasta_documentos=tmp_path / "oficina",
            criado_em=data_criacao,
            atualizado_em=data_criacao,
        )
        repo.salvar(empresa)

        # 1. Valida texto bruto persistido no SQLite e formato ISO-8601 com 6 posições e +00:00
        padrao_iso = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$")
        with get_connection(repo.db_path) as conn:
            raw_row = conn.execute(
                "SELECT criado_em, atualizado_em FROM empresas WHERE id = ?",
                (empresa.id,),
            ).fetchone()
            assert raw_row is not None
            raw_criado = raw_row["criado_em"]
            raw_atualizado = raw_row["atualizado_em"]

        assert raw_criado == "2020-01-01T12:00:00.000000+00:00"
        assert padrao_iso.match(raw_criado) is not None
        assert padrao_iso.match(raw_atualizado) is not None
        assert raw_atualizado > raw_criado

        # 2. Confirma que o objeto em memória reflete exatamente o que foi persistido
        assert empresa.criado_em.isoformat(timespec="microseconds") == raw_criado
        assert empresa.atualizado_em.isoformat(timespec="microseconds") == raw_atualizado

        # 3. Modifica dados da empresa mantendo o mesmo ID (sem usar sleep!)
        empresa.razao_social = "Oficina Renovada Ltda"
        empresa.nome_fantasia = "Oficina Renovada"
        repo.salvar(empresa)

        # 4. Confirma atualização no banco bruto
        with get_connection(repo.db_path) as conn:
            raw_row_depois = conn.execute(
                "SELECT criado_em, atualizado_em FROM empresas WHERE id = ?",
                (empresa.id,),
            ).fetchone()
            assert raw_row_depois is not None
            raw_criado_depois = raw_row_depois["criado_em"]
            raw_atualizado_depois = raw_row_depois["atualizado_em"]

        # criado_em permanece intacto com os zeros de microssegundos
        assert raw_criado_depois == "2020-01-01T12:00:00.000000+00:00"
        # atualizado_em deve seguir o padrão de 6 posições e +00:00 e ser superior à data de 2020
        assert padrao_iso.match(raw_atualizado_depois) is not None
        assert raw_atualizado_depois >= raw_atualizado
        assert raw_atualizado_depois > raw_criado_depois

        # 5. Confirma dados no objeto em memória e recuperado
        atualizada = repo.obter_por_id(empresa.id)
        assert atualizada is not None
        assert atualizada.id == empresa.id
        assert atualizada.razao_social == "Oficina Renovada Ltda"
        assert atualizada.criado_em == data_criacao
        assert atualizada.atualizado_em > data_criacao
        assert atualizada.criado_em.isoformat(timespec="microseconds") == raw_criado_depois
        assert atualizada.atualizado_em.isoformat(timespec="microseconds") == raw_atualizado_depois
        assert empresa.atualizado_em.isoformat(timespec="microseconds") == raw_atualizado_depois

    def test_rejeicao_cnpj_duplicado_no_salvar(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_duplicado.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        emp1 = Empresa(
            razao_social="Primeira Empresa Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "e1",
        )
        repo.salvar(emp1)

        # Tentativa de salvar outra empresa com o mesmo CNPJ deve falhar
        emp2 = Empresa(
            razao_social="Segunda Empresa Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "e2",
        )
        with pytest.raises(CNPJDuplicadoError, match="Já existe uma empresa cadastrada"):
            repo.salvar(emp2)

    def test_edicao_permite_manter_proprio_cnpj(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_proprio_cnpj.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        emp = Empresa(
            razao_social="Auto Posto Central",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "posto",
        )
        repo.salvar(emp)

        # Alteração de nome mantendo o mesmo CNPJ não deve conflitar com ela mesma
        emp.nome_fantasia = "Posto Central VIP"
        repo.salvar(emp)

        consultada = repo.obter_por_id(emp.id)
        assert consultada is not None
        assert consultada.nome_fantasia == "Posto Central VIP"

    def test_remocao_empresa(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_delete.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        emp = Empresa(
            razao_social="Empresa Efemera Ltda",
            cnpj="33.000.167/0001-01",
            pasta_documentos=tmp_path / "efemera",
        )
        repo.salvar(emp)
        assert repo.obter_por_id(emp.id) is not None

        sucesso = repo.remover(emp.id)
        assert sucesso is True
        assert repo.obter_por_id(emp.id) is None
        # Remover ID inexistente retorna False
        assert repo.remover(emp.id) is False

    def test_pesquisa_unicode_acentuada(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_unicode.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        emp1 = Empresa(
            razao_social="João & Filhos Construções Ltda",
            nome_fantasia="Construtora João",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "joao",
        )
        emp2 = Empresa(
            razao_social="Assessoria Contábil Modelo",
            nome_fantasia="Modelo Contábil",
            cnpj="12.ABC.345/0001-88",
            pasta_documentos=tmp_path / "modelo",
        )
        emp3 = Empresa(
            razao_social="Álvaro Engenharia Ltda",
            nome_fantasia="Engenharia Álvaro",
            cnpj="33.000.167/0001-01",
            pasta_documentos=tmp_path / "alvaro",
        )
        repo.salvar(emp1)
        repo.salvar(emp2)
        repo.salvar(emp3)

        # Pesquisa com minúsculas acentuadas
        res1 = repo.pesquisar("joão")
        assert len(res1) == 1
        assert res1[0] == emp1

        # Pesquisa com maiúsculas acentuadas
        res2 = repo.pesquisar("JOÃO")
        assert len(res2) == 1
        assert res2[0] == emp1

        # Pesquisa contábil com e sem acento
        res3 = repo.pesquisar("contábil")
        assert len(res3) == 1
        assert res3[0] == emp2

        # Pesquisa por CNPJ alfanumérico minúsculo sem máscara
        res4 = repo.pesquisar("12abc")
        assert len(res4) == 1
        assert res4[0] == emp2

        # Pesquisa Álvaro: testa Álvaro, álvaro, ÁLVARO, alvaro, alvar
        for termo in ("Álvaro", "álvaro", "ÁLVARO", "alvaro", "alvar"):
            res_alvaro = repo.pesquisar(termo)
            assert len(res_alvaro) == 1, f"Falha ao pesquisar por '{termo}'"
            assert res_alvaro[0] == emp3

    def test_ordenacao_amigavel_deterministica(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_sort.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        # Adiciona em ordem não alfabética
        repo.salvar(Empresa(razao_social="Zeta Serviços", cnpj="33000167000101", pasta_documentos=tmp_path / "z"))
        repo.salvar(Empresa(razao_social="Álvaro Engenharia", cnpj="00000000000191", pasta_documentos=tmp_path / "a"))
        repo.salvar(Empresa(razao_social="Beta Comércio", cnpj="12ABC345000188", pasta_documentos=tmp_path / "b"))

        lista = repo.listar_todas()
        nomes = [e.nome_exibicao for e in lista]
        # Álvaro e Beta devem anteceder Zeta
        assert nomes == ["Álvaro Engenharia", "Beta Comércio", "Zeta Serviços"]

    def test_persistencia_real_apos_fechar_e_reabrir(self, tmp_path: Path) -> None:
        db_path = tmp_path / "repo_fechar_reabrir.db"

        # 1ª Sessão: salva empresas
        repo1 = SqliteEmpresaRepository(db_path=db_path)
        emp = Empresa(
            razao_social="Sessão Persistente Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "docs_sessao",
        )
        repo1.salvar(emp)
        del repo1

        # 2ª Sessão: nova instância de repositório sobre o mesmo arquivo de banco
        repo2 = SqliteEmpresaRepository(db_path=db_path)
        recuperada = repo2.obter_por_id(emp.id)

        assert recuperada is not None
        assert recuperada.razao_social == "Sessão Persistente Ltda"
        assert recuperada.cnpj == "00000000000191"
        assert recuperada.cnpj_formatado == "00.000.000/0001-91"
        assert recuperada.pasta_documentos == tmp_path / "docs_sessao"

    def test_erros_leitura_sqlite_sao_traduzidos_para_persistencia_error(
        self, tmp_path: Path
    ) -> None:
        """Comprova que falhas de SQLite em operações de leitura levantam PersistenciaError com chaining."""
        db_path = tmp_path / "repo_erro_leitura.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        # Provoca erro de leitura removendo a tabela empresas
        with get_connection(repo.db_path) as conn:
            conn.execute("DROP TABLE empresas")
            conn.commit()

        # listar_todas
        with pytest.raises(PersistenciaError, match="Erro ao listar empresas") as exc_listar:
            repo.listar_todas()
        assert isinstance(exc_listar.value.__cause__, sqlite3.Error)

        # obter_por_id
        with pytest.raises(PersistenciaError, match="Erro ao obter empresa por ID") as exc_id:
            repo.obter_por_id("id-qualquer")
        assert isinstance(exc_id.value.__cause__, sqlite3.Error)

        # obter_por_cnpj
        with pytest.raises(PersistenciaError, match="Erro ao obter empresa por CNPJ") as exc_cnpj:
            repo.obter_por_cnpj("00000000000191")
        assert isinstance(exc_cnpj.value.__cause__, sqlite3.Error)

        # remover
        with pytest.raises(PersistenciaError, match="Erro ao remover empresa") as exc_remover:
            repo.remover("id-qualquer")
        assert isinstance(exc_remover.value.__cause__, sqlite3.Error)

    def test_pesquisar_propaga_persistencia_error_sem_reempacotar(
        self, tmp_path: Path
    ) -> None:
        """Garante que pesquisar propaga PersistenciaError diretamente de listar_todas sem duplicar exceção."""
        db_path = tmp_path / "repo_pesquisa_erro.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        with get_connection(repo.db_path) as conn:
            conn.execute("DROP TABLE empresas")
            conn.commit()

        with pytest.raises(PersistenciaError, match="Erro ao listar empresas") as exc_pesq:
            repo.pesquisar("termo")
        # O __cause__ imediato deve ser o sqlite3.Error original, sem intermediários aninhados
        assert isinstance(exc_pesq.value.__cause__, sqlite3.Error)

    def test_normalizacao_real_para_utc_e_preservacao_em_falha(
        self, tmp_path: Path
    ) -> None:
        """Comprova a normalização estrita de fusos conscientes (ex: -04:00) para UTC:

        - o banco grava +00:00 com timespec='microseconds';
        - o instante de tempo permanece equivalente;
        - o objeto em memória fica com tzinfo == timezone.utc;
        - o objeto relido do banco fica com tzinfo == timezone.utc;
        - a atualização preserva exatamente criado_em;
        - uma falha de gravação não modifica os timestamps do objeto em memória.
        """
        from datetime import timedelta
        fuso_manaus = timezone(timedelta(hours=-4))
        # Instante consciente em fuso -04:00 (ex: 2025-06-15 08:30:00 -04:00 == 2025-06-15 12:30:00 UTC)
        data_manaus = datetime(2025, 6, 15, 8, 30, 0, 500000, tzinfo=fuso_manaus)

        db_path = tmp_path / "repo_utc.db"
        repo = SqliteEmpresaRepository(db_path=db_path)

        empresa = Empresa(
            razao_social="Manaus Tech Ltda",
            cnpj="00.000.000/0001-91",
            pasta_documentos=tmp_path / "manaus",
            criado_em=data_manaus,
        )

        # 1. No modelo, criado_em já é convertido para UTC
        assert empresa.criado_em.tzinfo == timezone.utc
        assert empresa.criado_em == data_manaus  # Instante equivalente
        assert empresa.criado_em.hour == 12      # 08:30 -04:00 -> 12:30 UTC

        repo.salvar(empresa)

        # 2. Confirma que o banco gravou terminando em +00:00 e com 6 casas de microssegundos
        with get_connection(repo.db_path) as conn:
            row = conn.execute(
                "SELECT criado_em, atualizado_em FROM empresas WHERE id = ?",
                (empresa.id,),
            ).fetchone()
            assert row is not None
            raw_criado = row["criado_em"]
            raw_atualizado = row["atualizado_em"]

        assert raw_criado.endswith("+00:00")
        assert raw_atualizado.endswith("+00:00")
        assert raw_criado == "2025-06-15T12:30:00.500000+00:00"

        # 3. Objeto em memória possui tzinfo == timezone.utc e reflete o banco
        assert empresa.criado_em.tzinfo == timezone.utc
        assert empresa.atualizado_em.tzinfo == timezone.utc
        assert empresa.criado_em.isoformat(timespec="microseconds") == raw_criado
        assert empresa.atualizado_em.isoformat(timespec="microseconds") == raw_atualizado

        # 4. Objeto relido do banco possui tzinfo == timezone.utc e instante idêntico
        relida = repo.obter_por_id(empresa.id)
        assert relida is not None
        assert relida.criado_em.tzinfo == timezone.utc
        assert relida.atualizado_em.tzinfo == timezone.utc
        assert relida.criado_em == data_manaus
        assert relida.criado_em.isoformat(timespec="microseconds") == raw_criado

        # 5. Atualização preserva exatamente criado_em
        empresa.nome_fantasia = "Manaus Tech VIP"
        repo.salvar(empresa)

        relida_apos_update = repo.obter_por_id(empresa.id)
        assert relida_apos_update is not None
        assert relida_apos_update.criado_em == data_manaus
        assert relida_apos_update.criado_em.isoformat(timespec="microseconds") == raw_criado
        assert empresa.criado_em.isoformat(timespec="microseconds") == raw_criado
        assert relida_apos_update.atualizado_em > relida.atualizado_em

        # 6. Uma falha de gravação não modifica os timestamps do objeto em memória
        # Cria uma segunda empresa que provocará CNPJDuplicadoError
        empresa_duplicada = Empresa(
            razao_social="Outra Empresa Conflitante",
            cnpj="00.000.000/0001-91",  # Mesmo CNPJ
            pasta_documentos=tmp_path / "outra",
            criado_em=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            atualizado_em=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )
        ts_dup_criado_antes = empresa_duplicada.criado_em
        ts_dup_atualizado_antes = empresa_duplicada.atualizado_em

        with pytest.raises(CNPJDuplicadoError):
            repo.salvar(empresa_duplicada)

        # Timestamps do objeto em memória NÃO foram modificados pela tentativa fracassada
        assert empresa_duplicada.criado_em == ts_dup_criado_antes
        assert empresa_duplicada.atualizado_em == ts_dup_atualizado_antes
