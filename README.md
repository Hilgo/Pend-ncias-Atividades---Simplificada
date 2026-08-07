# 📚 Pendências Simplificada

Sistema para análise e acompanhamento de pendências de estudantes em cursos técnicos utilizando relatórios da Plataforma AVA (Educação Profissional).

---

## 🎯 Objetivo

Auxiliar **professores** a:
- ✅ Consolidar múltiplos relatórios de registros e quizzes
- 📊 Identificar atividades **concluídas** 
- 👥 Acompanhar pendências **por aluno**, **disciplina** e **semana**
- 📈 Gerar relatórios automáticos em CSV e Excel para análise e cobrança

---

## 🚀 Como Funciona

### 1️⃣ **Preparar os Relatórios**

Exporte os relatórios da Plataforma AVA seguindo este padrão de nomenclatura:

```
TURMA_DISCIPLINA_BIMESTRE.csv
```

**Exemplos:**
- `2DS_Logica_1BI.csv` (Turma 2DS, Disciplina Logica, Bimestre 1)
- `3DS_BancoDados_2BI.csv` (Turma 3DS, Banco de Dados, Bimestre 2)

**Componentes do nome:**
- **TURMA**: Identificação da turma (ex: 2DS, 3DS)
- **DISCIPLINA**: Nome da disciplina sem espaços (ex: Logica, BancoDados)
- **BIMESTRE**: Número do bimestre (1, 2, 3 ou 4)

> **Dica:** para facilitar esse processo já no momento do download, use o script disponível no repositório [Scripts-Tampermonkey](https://github.com/Hilgo/Scripts-Tampermonkey). Ele gera o relatório da plataforma AVA já no template de nomenclatura usado neste projeto, reduzindo a necessidade de renomear os arquivos manualmente.

### 2️⃣ **Estrutura do Arquivo CSV**

O relatório foi desenvolvido à partir do arquivo gerado do relatório de Conclusão de Atividades da plataforma AVA, que contém:
- **1ª Coluna**: Nomes dos alunos
- **Demais Colunas**: Atividades com padrões reconhecidos:
  - `Registro da Aula - S1` (Registro de semana 1)
  - `Registro de Aula - S2` (Registro de semana 2)
  - `Pause e Responda - S1` (Quiz de semana 1)
  - `Pause e Responda - S2` (Quiz de semana 2)

**Valor das Células:**
- `Concluído` ou similar → ✅ Atividade concluída
- Qualquer outro valor → ⏳ Atividade pendente

### 3️⃣ **Colocar Arquivos na Pasta de Entrada**

```
projeto/
└── entrada/
    ├── 2DS_Logica_1.csv
    ├── 2DS_BD_1.csv
    └── 3DS_Logica_1.csv
```

Copie todos os arquivos CSV exportados da plataforma AVA para a pasta `entrada/`. É possível manter arquivos de mais de um bimestre juntos: os relatórios são separados por turma e bimestre.

### 4️⃣ **Executar o Script**

#### Execução Padrão
```bash
python analisar_pendencias.py
```
Processa todos os CSVs da pasta `entrada/` e gera os relatórios na pasta `saida/`.

#### Com Recorte por Semana (Opcional)
```bash
python analisar_pendencias.py --ate-semana 8
```

Gera relatórios adicionais considerando apenas atividades até a semana 8. Útil para acompanhamento parcial durante o bimestre.

---

## 📁 Estrutura de Saída

Após a execução, a pasta `saida/` conterá **arquivos Excel**:

### **Relatórios Gerais**
```
saida/
└── conferencia_geral.xlsx            # Consolidação em Excel com abas:
                                       # - Conferencia Estrutural
                                       # - Semanas por Coluna
                                       # - Resumo Geral Turma
```

### **Relatórios por Turma e Bimestre**
```
saida/
    └── 2ds/
        ├── 2ds_todos_bimestres_analise_pendencias.xlsx  # Consolida todos os bimestres da turma
        └── 2bi/
            └── 2ds_2bi_analise_pendencias.xlsx   # Excel com abas:
                                       # - Base Consolidada
                                       # - Resumo Disciplina
                                       # - Resumo Semana
                                       # - Resumo por Aluno
                                       # - Cobranca
                                       # - Aluno Semana
```

### **Relatórios Recortados por Semana** (se `--ate-semana` usado)
```
saida/
└── ate_semana_8/
    ├── 2ds/
    │   ├── 2ds_todos_bimestres_ate_semana_8.xlsx  # Consolida os bimestres sem atividades futuras
    │   └── 2bi/
    │       └── 2ds_2bi_ate_semana_8.xlsx # Excel com abas:
    │                                      # - Base Consolidada
    │                                      # - Resumo por Aluno
    │                                      # - Resumo Disciplina
    │                                      # - Resumo Semana
    │                                      # - Cobranca
    │                                      # - Aluno Semana
    └── 3ds/
        └── 2bi/
            └── 3ds_2bi_ate_semana_8.xlsx # (mesma estrutura)
```

---

## 📊 Entendendo os Relatórios

### `conferencia_geral.xlsx`
Arquivo consolidado com 3 abas:
- **Conferencia Estrutural**: Validação dos arquivos importados
- **Semanas por Coluna**: Detalhe das semanas detectadas em cada coluna
- **Resumo Geral Turma**: Pendências resumidas por turma e tipo

### `[TURMA]_[BIMESTRE]_analise_pendencias.xlsx`
Relatório completo de cada turma e bimestre com 6 abas:
- **Base Consolidada**: Todos os registros (aluno, atividade, status, semana)
- **Resumo por Aluno**: Ranking de pendências (inclui todos os alunos, mesmo com 0 pendências)
- **Resumo Disciplina**: Pendências por disciplina
- **Resumo Semana**: Pendências por semana
- **Cobrança**: Detalhe para cobrar (aluno + disciplina + tipo) - apenas alunos com pendências
- **Aluno Semana**: Máximo detalhe (aluno + disciplina + semana + tipo) - apenas alunos com pendências

---

## ⚙️ Requisitos

- **Python 3.7+**
- **pandas**: Processamento de dados
- **openpyxl**: Geração de arquivos Excel

### Instalação de Dependências

```bash
pip install -r requirements.txt
```

---

## 🌐 Uso pela Web

A aplicação web usa a mesma lógica do script local. Os CSVs e os relatórios são mantidos apenas em uma pasta temporária durante o processamento; ao terminar o download do ZIP, essa pasta é removida.

```bash
uvicorn app_web:app --reload
```

Abra `http://127.0.0.1:8000`, envie os CSVs e, opcionalmente, informe a semana limite. O navegador receberá um arquivo `relatorios_pendencias.zip`.

O modo local continua disponível e inalterado:

```bash
python analisar_pendencias.py --ate-semana 8
```

> Para disponibilizar a aplicação a outros professores, use HTTPS e inclua autenticação antes de torná-la pública. Os relatórios contêm dados pessoais de estudantes.

---

## 🔧 Troubleshooting

### ❌ Erro: "Nenhum arquivo CSV encontrado"
- Verifique se há arquivos `.csv` na pasta `entrada/`
- Confirme a extensão do arquivo (deve ser `.csv`)

### ❌ Colunas não aparecem nos relatórios
- Verifique se o nome da coluna contém:
  - `Registro da Aula` ou `Registro de Aula` (case-insensitive)
  - `Pause e Responda` (case-insensitive)
  - Um padrão `S` + número (ex: S1, S2, S15)

### ❌ Erro de encoding
- O script tenta automaticamente: UTF-16, Latin1, CP1252, UTF-8-sig
- Se ainda falhar, abra o CSV no Excel e re-exporte como UTF-8

### ❌ Arquivo Excel corrompido
- Execute novamente
- Verifique se não há `saida/[turma]/*.xlsx` aberto em outro programa

---

## 💡 Dicas de Uso


### 1. **Análise Parcial do Bimestre**
Use `--ate-semana` durante o semestre:
```bash
python analisar_pendencias.py --ate-semana 8
```
Isso gera uma cópia dos relatórios considerando apenas até a semana 8.

### 2. **Rastrear Histórico**
Renomeie a pasta `saida/` antes de cada execução para não sobrescrever:
```bash
move saida saida_2026_05_semana1
```

---

## 📝 Exemplo Prático

**Passo 1**: Exporte 3 relatórios da AVA
```
2DS_Logica_1.csv
2DS_BD_1.csv
3DS_Logica_1.csv
```

**Passo 2**: Copie para `entrada/`

**Passo 3**: Execute
```bash
python analisar_pendencias.py
```

**Passo 4**: Abra `saida/2ds/2ds_analise_pendencias.xlsx`
- Clique na aba "Resumo por Aluno"
- Veja o ranking de alunos com mais pendências

**Passo 5**: Use os dados para cobrança de atividades pendentes!

---

## 📄 Licença

Projeto educacional para fins acadêmicos.

---

## 👤 Autor

**Desenvolvido por**: Lucas Palma Stabile

**Objetivo**: Auxiliar professores da Educação Profissional no acompanhamento de atividades e pendências dos estudantes em cursos técnicos.

---

**Desenvolvido para auxiliar professores da Educação Profissional** 🎓
