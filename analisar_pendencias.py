from pathlib import Path
import argparse
import re
import pandas as pd

PASTA_ENTRADA = Path('entrada')
PASTA_SAIDA = Path('saida')
PASTA_SAIDA.mkdir(exist_ok=True)

ENCODINGS = ['utf-16', 'latin1', 'cp1252', 'utf-8-sig']
SEPARADORES = ['\t', ';', ',', None]


def ler_csv_robusto(caminho_arquivo: Path) -> pd.DataFrame:
    for encoding in ENCODINGS:
        for sep in SEPARADORES:
            try:
                df = pd.read_csv(
                    caminho_arquivo,
                    encoding=encoding,
                    sep=sep,
                    engine='python',
                    dtype=str
                )
                if df.shape[1] > 3:
                    return df.fillna('')
            except Exception:
                continue
    raise ValueError(f'Não foi possível ler o arquivo: {caminho_arquivo}')


def extrair_metadados(nome_arquivo: str):
    partes = Path(nome_arquivo).stem.split('_')
    turma = partes[0].strip() if len(partes) > 0 else 'SEM_TURMA'
    disciplina = partes[1].strip() if len(partes) > 1 else 'SEM_DISCIPLINA'
    bimestre = partes[2].strip() if len(partes) > 2 else 'SEM_BIMESTRE'
    return turma, disciplina, bimestre


def eh_coluna_registro(nome_coluna: str) -> bool:
    return bool(re.search(r'registro da aula|registro de aula', str(nome_coluna), re.I))


def eh_coluna_quiz(nome_coluna: str) -> bool:
    return bool(re.search(r'pause\s*e\s*responda', str(nome_coluna), re.I))


def extrair_semana(nome_coluna: str):
    match = re.search(r'\bS(\d+)', str(nome_coluna), re.I)
    if match:
        return int(match.group(1))
    return 'sem semana'


def status_atividade(valor: str) -> str:
    texto = str(valor).strip().lower()
    if texto.startswith('conclu'):
        return 'concluido'
    return 'pendente'


def slug(texto: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '_', str(texto).strip()).strip('_').lower()


def filtrar_ate_semana(base: pd.DataFrame, semana_limite: int) -> pd.DataFrame:
    semanas_numericas = pd.to_numeric(base['semana'], errors='coerce')
    return base[semanas_numericas.le(semana_limite)].copy()


def contar_pendencias_por_aluno(base_ate_semana: pd.DataFrame, base_pendencias: pd.DataFrame) -> pd.DataFrame:
    alunos = base_ate_semana[['turma', 'aluno']].drop_duplicates()
    pendencias = (
        base_pendencias
        .groupby(['turma', 'aluno'])
        .size()
        .reset_index(name='total_pendencias_ate_semana')
    )
    return (
        alunos
        .merge(pendencias, on=['turma', 'aluno'], how='left')
        .fillna({'total_pendencias_ate_semana': 0})
        .assign(total_pendencias_ate_semana=lambda df: df['total_pendencias_ate_semana'].astype(int))
        .sort_values(['turma', 'total_pendencias_ate_semana', 'aluno'], ascending=[True, False, True])
    )


def montar_base_consolidada():
    arquivos_csv = sorted(PASTA_ENTRADA.glob('*.csv'))
    if not arquivos_csv:
        raise FileNotFoundError('Nenhum arquivo CSV encontrado na pasta entrada/.')

    linhas = []
    conferencia = []
    semanas_detalhe = []

    for arquivo in arquivos_csv:
        turma, disciplina, bimestre = extrair_metadados(arquivo.name)
        df = ler_csv_robusto(arquivo)
        colunas = list(df.columns)

        nome_coluna_aluno = colunas[0]
        colunas_registro = [c for c in colunas if eh_coluna_registro(c)]
        colunas_quiz = [c for c in colunas if eh_coluna_quiz(c)]
        colunas_interesse = colunas_registro + colunas_quiz

        semanas_encontradas = []
        colunas_sem_semana = 0
        for coluna in colunas_interesse:
            semana = extrair_semana(coluna)
            if semana == 'sem semana':
                colunas_sem_semana += 1
            else:
                semanas_encontradas.append(semana)
                semanas_detalhe.append({
                    'turma': turma,
                    'disciplina': disciplina,
                    'bimestre': bimestre,
                    'arquivo': arquivo.name,
                    'coluna_origem': coluna,
                    'tipo': 'registro' if coluna in colunas_registro else 'quiz',
                    'semana': semana
                })

        semanas_unicas = sorted(set(semanas_encontradas))
        total_alunos = len(df)
        total_registros = len(colunas_registro)
        total_quizzes = len(colunas_quiz)
        total_teorico_registros = total_alunos * total_registros
        total_teorico_quizzes = total_alunos * total_quizzes

        conferencia.append({
            'turma': turma,
            'disciplina': disciplina,
            'bimestre': bimestre,
            'arquivo': arquivo.name,
            'alunos': total_alunos,
            'colunas_registro': total_registros,
            'colunas_quiz': total_quizzes,
            'total_teorico_registros': total_teorico_registros,
            'total_teorico_quizzes': total_teorico_quizzes,
            'colunas_sem_semana': colunas_sem_semana,
            'quantidade_semanas_no_arquivo': len(semanas_unicas),
            'lista_semanas': ', '.join(str(s) for s in semanas_unicas) if semanas_unicas else 'nenhuma'
        })

        for _, row in df.iterrows():
            aluno = str(row[nome_coluna_aluno]).strip()

            for coluna in colunas_registro:
                linhas.append({
                    'turma': turma,
                    'disciplina': disciplina,
                    'bimestre': bimestre,
                    'aluno': aluno,
                    'tipo': 'registro',
                    'coluna_origem': coluna,
                    'semana': extrair_semana(coluna),
                    'status': status_atividade(row[coluna]),
                    'arquivo_origem': arquivo.name
                })

            for coluna in colunas_quiz:
                linhas.append({
                    'turma': turma,
                    'disciplina': disciplina,
                    'bimestre': bimestre,
                    'aluno': aluno,
                    'tipo': 'quiz',
                    'coluna_origem': coluna,
                    'semana': extrair_semana(coluna),
                    'status': status_atividade(row[coluna]),
                    'arquivo_origem': arquivo.name
                })

    base = pd.DataFrame(linhas)
    conferencia_df = pd.DataFrame(conferencia)
    semanas_df = pd.DataFrame(semanas_detalhe)
    return base, conferencia_df, semanas_df


def salvar_relatorios_por_turma(base: pd.DataFrame):
    for turma, base_turma in base.groupby('turma'):
        pasta_turma = PASTA_SAIDA / slug(turma)
        pasta_turma.mkdir(exist_ok=True)

        base_pendencias = base_turma[base_turma['status'] == 'pendente'].copy()

        resumo_por_disciplina = (
            base_pendencias
            .groupby(['disciplina', 'tipo'])
            .size()
            .reset_index(name='pendencias')
            .sort_values(['disciplina', 'tipo'])
        )

        resumo_por_semana = (
            base_pendencias
            .groupby(['disciplina', 'semana', 'tipo'])
            .size()
            .reset_index(name='pendencias')
            .sort_values(['disciplina', 'semana', 'tipo'])
        )

        resumo_por_aluno = (
            base_pendencias
            .groupby(['aluno'])
            .size()
            .reset_index(name='total_pendencias')
            .sort_values(['total_pendencias', 'aluno'], ascending=[False, True])
        )

        cobranca_alunos = (
            base_pendencias
            .groupby(['aluno', 'disciplina', 'tipo'])
            .size()
            .reset_index(name='pendencias')
            .sort_values(['aluno', 'disciplina', 'tipo'])
        )

        detalhamento_aluno_semana = (
            base_pendencias
            .groupby(['aluno', 'disciplina', 'semana', 'tipo'])
            .size()
            .reset_index(name='pendencias')
            .sort_values(['aluno', 'disciplina', 'semana', 'tipo'])
        )

        base_turma.to_csv(pasta_turma / 'base_consolidada.csv', index=False, encoding='utf-8-sig')
        resumo_por_disciplina.to_csv(pasta_turma / 'resumo_por_disciplina.csv', index=False, encoding='utf-8-sig')
        resumo_por_semana.to_csv(pasta_turma / 'resumo_por_semana.csv', index=False, encoding='utf-8-sig')
        resumo_por_aluno.to_csv(pasta_turma / 'resumo_por_aluno.csv', index=False, encoding='utf-8-sig')
        cobranca_alunos.to_csv(pasta_turma / 'cobranca_alunos.csv', index=False, encoding='utf-8-sig')
        detalhamento_aluno_semana.to_csv(pasta_turma / 'detalhamento_aluno_semana.csv', index=False, encoding='utf-8-sig')

        with pd.ExcelWriter(pasta_turma / f'{slug(turma)}_analise_pendencias.xlsx', engine='openpyxl') as writer:
            base_turma.to_excel(writer, sheet_name='Base Consolidada', index=False)
            resumo_por_disciplina.to_excel(writer, sheet_name='Resumo Disciplina', index=False)
            resumo_por_semana.to_excel(writer, sheet_name='Resumo Semana', index=False)
            resumo_por_aluno.to_excel(writer, sheet_name='Resumo por Aluno', index=False)
            cobranca_alunos.to_excel(writer, sheet_name='Cobranca', index=False)
            detalhamento_aluno_semana.to_excel(writer, sheet_name='Aluno Semana', index=False)


def gerar_relatorios_gerais(base: pd.DataFrame, conferencia_df: pd.DataFrame, semanas_df: pd.DataFrame):
    base_pendencias = base[base['status'] == 'pendente'].copy()

    resumo_por_turma = (
        base_pendencias
        .groupby(['turma', 'tipo'])
        .size()
        .reset_index(name='pendencias')
        .sort_values(['turma', 'tipo'])
    )

    conferencia_df.to_csv(PASTA_SAIDA / 'conferencia_estrutural.csv', index=False, encoding='utf-8-sig')
    semanas_df.to_csv(PASTA_SAIDA / 'conferencia_semanas_colunas.csv', index=False, encoding='utf-8-sig')
    resumo_por_turma.to_csv(PASTA_SAIDA / 'resumo_geral_por_turma.csv', index=False, encoding='utf-8-sig')

    with pd.ExcelWriter(PASTA_SAIDA / 'conferencia_geral.xlsx', engine='openpyxl') as writer:
        conferencia_df.to_excel(writer, sheet_name='Conferencia Estrutural', index=False)
        semanas_df.to_excel(writer, sheet_name='Semanas por Coluna', index=False)
        resumo_por_turma.to_excel(writer, sheet_name='Resumo Geral Turma', index=False)


def gerar_relatorios_ate_semana(base: pd.DataFrame, semana_limite: int):
    if semana_limite < 1:
        raise ValueError('A semana limite precisa ser maior ou igual a 1.')

    base_ate_semana = filtrar_ate_semana(base, semana_limite)
    base_pendencias = base_ate_semana[base_ate_semana['status'] == 'pendente'].copy()

    pasta_recorte = PASTA_SAIDA / f'ate_semana_{semana_limite}'
    pasta_recorte.mkdir(exist_ok=True)

    pendencias_por_aluno_turma = contar_pendencias_por_aluno(base_ate_semana, base_pendencias)

    pendencias_por_aluno_disciplina = (
        base_pendencias
        .groupby(['turma', 'aluno', 'disciplina', 'tipo'])
        .size()
        .reset_index(name='pendencias_ate_semana')
        .sort_values(['turma', 'aluno', 'disciplina', 'tipo'])
    )

    pendencias_por_turma_disciplina = (
        base_pendencias
        .groupby(['turma', 'disciplina', 'tipo'])
        .size()
        .reset_index(name='pendencias_ate_semana')
        .sort_values(['turma', 'disciplina', 'tipo'])
    )

    pendencias_por_semana = (
        base_pendencias
        .groupby(['turma', 'disciplina', 'semana', 'tipo'])
        .size()
        .reset_index(name='pendencias_ate_semana')
        .sort_values(['turma', 'disciplina', 'semana', 'tipo'])
    )

    base_ate_semana.to_csv(pasta_recorte / 'base_consolidada_ate_semana.csv', index=False, encoding='utf-8-sig')
    pendencias_por_aluno_turma.to_csv(
        pasta_recorte / 'pendencias_por_aluno_turma.csv',
        index=False,
        encoding='utf-8-sig',
        sep=';'
    )
    pendencias_por_aluno_disciplina.to_csv(
        pasta_recorte / 'pendencias_por_aluno_disciplina.csv',
        index=False,
        encoding='utf-8-sig'
    )
    pendencias_por_turma_disciplina.to_csv(
        pasta_recorte / 'pendencias_por_turma_disciplina.csv',
        index=False,
        encoding='utf-8-sig'
    )
    pendencias_por_semana.to_csv(pasta_recorte / 'pendencias_por_semana.csv', index=False, encoding='utf-8-sig')

    for turma, base_turma in base_pendencias.groupby('turma'):
        pasta_turma = pasta_recorte / slug(turma)
        pasta_turma.mkdir(exist_ok=True)

        base_ate_semana_turma = base_ate_semana[base_ate_semana['turma'] == turma]
        resumo_aluno_turma = contar_pendencias_por_aluno(base_ate_semana_turma, base_turma).drop(columns=['turma'])

        resumo_aluno_disciplina = (
            base_turma
            .groupby(['aluno', 'disciplina', 'tipo'])
            .size()
            .reset_index(name='pendencias_ate_semana')
            .sort_values(['aluno', 'disciplina', 'tipo'])
        )

        resumo_aluno_turma.to_csv(
            pasta_turma / 'pendencias_por_aluno.csv',
            index=False,
            encoding='utf-8-sig',
            sep=';'
        )
        resumo_aluno_disciplina.to_csv(
            pasta_turma / 'pendencias_por_aluno_disciplina.csv',
            index=False,
            encoding='utf-8-sig'
        )

    with pd.ExcelWriter(pasta_recorte / f'analise_pendencias_ate_semana_{semana_limite}.xlsx', engine='openpyxl') as writer:
        pendencias_por_aluno_turma.to_excel(writer, sheet_name='Aluno Turma', index=False)
        pendencias_por_aluno_disciplina.to_excel(writer, sheet_name='Aluno Disciplina', index=False)
        pendencias_por_turma_disciplina.to_excel(writer, sheet_name='Turma Disciplina', index=False)
        pendencias_por_semana.to_excel(writer, sheet_name='Semana', index=False)


def parse_args():
    parser = argparse.ArgumentParser(description='Analisa pendencias de atividades dos alunos.')
    parser.add_argument(
        '--ate-semana',
        type=int,
        help='Gera relatorios adicionais considerando apenas atividades ate a semana informada.'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print('Iniciando análise de pendências...')
    base, conferencia_df, semanas_df = montar_base_consolidada()
    salvar_relatorios_por_turma(base)
    gerar_relatorios_gerais(base, conferencia_df, semanas_df)
    if args.ate_semana is not None:
        gerar_relatorios_ate_semana(base, args.ate_semana)
        print(f'Relatorios ate a semana {args.ate_semana} gerados com sucesso!')
    print('Análise concluída com sucesso!')
    print(f'Relatórios salvos em: {PASTA_SAIDA.resolve()}')


if __name__ == '__main__':
    main()
