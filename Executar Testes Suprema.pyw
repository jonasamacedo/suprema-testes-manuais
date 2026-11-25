import base64
import csv
import html
import os
import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

ROOT = Path(__file__).resolve().parent
def listar_roteiros():
    caminhos = list(ROOT.glob("Casos de Teste - *.txt"))
    pasta = ROOT / "Suprema Testes Manuais"
    caminhos.extend(pasta.glob("**/Casos de Teste - *.txt"))
    return {c.stem.removeprefix("Casos de Teste - "): c for c in sorted(caminhos)}
STATUS = ("Não executado", "Aprovado", "Reprovado", "Bloqueado")


ASSINATURA_PADRAO = "Atenciosamente,\nJonas Arcelino de Macêdo"
TIPOS_ACHADO = ("Ajuste", "Adaptação", "Implementação", "Erro de fábrica")
MODELO_ACHADO = """PROBLEMA:


COMO SIMULAR:


RESULTADO ESPERADO:


BASE/ARQUIVOS:


EMPRESA:


PERÍODO:
"""


def assinatura_do_relatorio(resultados):
    return resultados.get("_relatorio", {}).get("assinatura", ASSINATURA_PADRAO)


def texto_achado(achado):
    titulo = f"{achado['tipo']} — {achado['titulo']}"
    if achado.get("versao"):
        titulo += f" (versão prevista: {achado['versao']})"
    return titulo + "\n" + achado["descricao"]


def exportar_txt(caminho, nome, casos, resultados):
    linhas = [f"Resultado da homologação — {nome}", ""]
    for codigo, titulo, roteiro in casos:
        registro = resultados.get(codigo, {})
        linhas += [titulo, f"Resultado: {registro.get('status', STATUS[0])}"]
        for rotulo, valor in (
            ("Resultado esperado", roteiro.partition("Esperado:")[2].strip()),
            ("Resultado observado", registro.get("observado", "")),
            ("Observações", registro.get("notas", "")),
        ):
            if valor.strip():
                linhas.append(f"{rotulo}: {valor.strip()}")
        imagens, outras = evidencias_do_caso(nome, codigo, registro.get("evidencias", ""))
        if imagens or outras:
            linhas.append("Evidências para anexar:")
            linhas.extend(f"- {imagem.name}" for imagem in imagens)
            linhas.extend(f"- {ref}" for ref in outras)
        for achado in registro.get("achados", []):
            linhas.extend(("", texto_achado(achado)))
        linhas.append("")
    assinatura = assinatura_do_relatorio(resultados)
    if assinatura:
        linhas.append(assinatura)
    Path(caminho).write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8-sig")


def carregar_roteiro(caminho):
    return interpretar_roteiro(caminho.read_text(encoding="utf-8-sig"))


def interpretar_roteiro(texto):
    partes = re.split(r"(?m)^(CT\d{2} — .+)$", texto)
    return partes[0].strip(), [
        (titulo[:4], titulo, texto.strip())
        for titulo, texto in zip(partes[1::2], partes[2::2])
    ]


def secoes_do_roteiro(texto):
    rotulos = {
        "Dados": "Dados",
        "Passos": "Passos para executar",
        "Esperado": "Resultado esperado",
    }
    padrao = r"(?m)^(Dados|Passos|Esperado):[ \t]*"
    marcadores = list(re.finditer(padrao, texto))
    if not marcadores:
        return [("Roteiro", texto)]
    secoes = []
    if texto[:marcadores[0].start()].strip():
        secoes.append(("Roteiro", texto[:marcadores[0].start()].strip()))
    for indice, marcador in enumerate(marcadores):
        fim = marcadores[indice + 1].start() if indice + 1 < len(marcadores) else len(texto)
        secoes.append((rotulos[marcador[1]], texto[marcador.end():fim].strip()))
    return secoes


def salvar_resultados(caminho, resultados):
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def exportar_csv(caminho, casos, resultados):
    with open(caminho, "w", encoding="utf-8-sig", newline="") as saida:
        escritor = csv.writer(saida, delimiter=";")
        escritor.writerow([
            "Caso", "Título", "Resultado", "Resultado esperado",
            "Resultado observado", "Observações", "Evidências",
        ])
        for codigo, titulo, roteiro in casos:
            registro = resultados.get(codigo, {})
            escritor.writerow([
                codigo, titulo.removeprefix(f"{codigo} — "),
                registro.get("status", STATUS[0]), roteiro.partition("Esperado:")[2].strip(),
                registro.get("observado", ""), registro.get("notas", ""),
                registro.get("evidencias", ""),
            ])


IMAGENS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def pasta_evidencias(nome, codigo):
    numero, _, requisito = nome.partition(" - ")
    diretorios = sorted((ROOT / "Suprema Testes Manuais").glob(f"**/Solicitação {numero}"))
    for diretorio in diretorios:
        pasta = diretorio / (requisito or "Evidencias") / codigo
        if pasta.is_dir():
            return pasta
    return None


def evidencias_do_caso(nome, codigo, referencias):
    caminhos = []
    pasta = pasta_evidencias(nome, codigo)
    if not referencias.strip() and pasta:
        caminhos.append(pasta)
    outras = []
    for referencia in referencias.splitlines():
        referencia = referencia.strip().strip('"')
        if referencia.startswith(("http://", "https://")):
            outras.append(referencia)
        elif referencia:
            caminhos.append(Path(referencia))
    imagens = {}
    for caminho in caminhos:
        if not caminho.is_absolute():
            caminho = ROOT / caminho
        arquivos = sorted(caminho.rglob("*")) if caminho.is_dir() else [caminho]
        for arquivo in arquivos:
            if arquivo.suffix.lower() in IMAGENS and arquivo.is_file():
                imagens.setdefault(arquivo.resolve(), None)
        if not caminho.is_dir() and caminho.resolve() not in imagens:
            outras.append(str(caminho))
    return imagens, outras


def exportar_relatorio(caminho, nome, referencia, casos, resultados):
    e = html.escape
    estilos = """
    @page { size: A4; margin: 14mm; }
    body { margin: 0 auto; padding: 28px 20px; max-width: 1020px; color: #172b3a;
           font: 15px/1.5 'Segoe UI', sans-serif; background: #fff; }
    h1 { font-size: 28px; margin: 0; } h2 { font-size: 20px; margin: 0 0 8px; }
    header, article { border-top: 3px solid #146678; padding-top: 14px; margin-bottom: 22px; }
    article { margin-top: 24px; } p { margin: 4px 0 12px; }
    .texto { white-space: pre-wrap; overflow-wrap: anywhere; }
    .estado { display: inline-block; padding: 2px 9px; background: #e8f3f5; font-weight: 600; }
    figure { margin: 16px 0; break-inside: avoid; }
    img { display: block; max-width: 100%; max-height: 176mm; object-fit: contain; border: 1px solid #d1dee3; }
    figcaption { color: #435869; padding-top: 4px; overflow-wrap: anywhere; }
    h2, strong { break-after: avoid; }
    @media print { button { display: none; } body { padding: 0; } article + article { break-before: page; } }
    """
    trechos = [
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8">',
        f'<title>Relatório QA | {e(nome)}</title><style>{estilos}</style><body>',
        '<header><h1>Relatório de testes manuais</h1>',
        f'<p>Suprema 8.10a · Solicitação {e(nome)}</p>',
        '<button type="button" onclick="window.print()">Imprimir / salvar em PDF</button></header>',
    ]
    resumo = [f"{status}: {sum(resultados.get(c, {}).get('status', STATUS[0]) == status for c, _, _ in casos)}"
              for status in STATUS]
    trechos.append(f'<p><strong>{len(casos)} casos</strong> · {e(" · ".join(resumo))}</p>')
    if referencia:
        trechos.append(f'<details><summary>Preparação e dados de referência</summary><p class="texto">{e(referencia)}</p></details>')
    for codigo, titulo, roteiro in casos:
        registro = resultados.get(codigo, {})
        trechos.append(f'<article><h2>{e(titulo)}</h2><p class="estado">{e(registro.get("status", STATUS[0]))}</p>')
        for rotulo, valor in [
            ("Resultado esperado", roteiro.partition("Esperado:")[2].strip()),
            ("Resultado observado", registro.get("observado", "")),
            ("Observações", registro.get("notas", "")),
        ]:
            if valor.strip():
                trechos.append(f'<strong>{rotulo}</strong><p class="texto">{e(valor)}</p>')
        imagens, outras = evidencias_do_caso(nome, codigo, registro.get("evidencias", ""))
        for numero, imagem in enumerate(imagens, 1):
            dados = base64.b64encode(imagem.read_bytes()).decode("ascii")
            legenda = e(f"{codigo} · Evidência {numero} · {imagem.name}")
            trechos.append(f'<figure><img src="data:{IMAGENS[imagem.suffix.lower()]};base64,{dados}" alt="{legenda}"><figcaption>{legenda}</figcaption></figure>')
        if outras:
            refs = e(chr(10).join(outras))
            trechos.append(f'<strong>Outras referências</strong><p class="texto">{refs}</p>')
        for achado in registro.get("achados", []):
            trechos.append(f'<strong>Achado</strong><p class="texto">{e(texto_achado(achado))}</p>')
        trechos.append('</article>')
    assinatura = assinatura_do_relatorio(resultados)
    if assinatura:
        trechos.append(f'<footer class="texto">{e(assinatura)}</footer>')
    Path(caminho).write_text("\n".join(trechos) + '</body></html>', encoding="utf-8")


class Aplicativo:
    def __init__(self, janela):
        self.janela = janela
        self.roteiros = listar_roteiros()
        if not self.roteiros:
            raise ValueError("Nenhum roteiro de testes encontrado.")
        self.roteiro_atual = None
        self.indice = 0
        janela.geometry("1080x760")
        janela.minsize(850, 675)
        quadro = ttk.Frame(janela, padding=16)
        quadro.pack(fill="both", expand=True)
        quadro.columnconfigure(1, weight=1)
        quadro.rowconfigure(1, weight=1)
        cabecalho = ttk.Frame(quadro)
        cabecalho.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(cabecalho, text="Solicitação e requisito").pack(anchor="w")
        escolhas = ttk.Frame(cabecalho)
        escolhas.pack(anchor="w", pady=(4, 8))
        self.seletor = ttk.Combobox(escolhas, values=tuple(self.roteiros), state="readonly", width=36)
        self.seletor.pack(side="left")
        ttk.Button(escolhas, text="Incluir solicitação e requisito", command=lambda: self.editar_roteiro(novo=True)).pack(side="left", padx=6)
        ttk.Button(escolhas, text="Editar roteiro", command=self.editar_roteiro).pack(side="left")
        self.seletor.bind("<<ComboboxSelected>>", self.trocar_roteiro)
        self.resumo = ttk.Label(cabecalho)
        self.resumo.pack(anchor="w")
        acoes = ttk.Frame(cabecalho)
        acoes.pack(anchor="w", pady=(5, 0))
        ttk.Button(acoes, text="Assinatura…", command=self.editar_assinatura).pack(side="left")
        ttk.Button(acoes, text="Exportar TXT", command=self.relatorio_txt).pack(side="left", padx=6)
        self.botao_achados = ttk.Button(acoes, text="Achados do caso…", command=self.editar_achados)
        self.botao_achados.pack(side="left")

        self.lista = tk.Listbox(quadro, width=36, exportselection=False)
        self.lista.grid(row=1, column=0, sticky="ns", padx=(0, 12))
        self.lista.bind("<<ListboxSelect>>", self.selecionar)
        detalhe = ttk.Frame(quadro)
        detalhe.grid(row=1, column=1, sticky="nsew")
        self.titulo = ttk.Label(detalhe, wraplength=560, font=("Segoe UI", 13, "bold"))
        self.titulo.pack(anchor="w")
        self.passos = scrolledtext.ScrolledText(detalhe, wrap="word", height=8, font=("Segoe UI", 10))
        self.passos.tag_configure("secao", font=("Segoe UI", 10, "bold"), foreground="#14596b")
        self.passos.pack(fill="both", expand=True, pady=8)
        ttk.Label(detalhe, text="Resultado").pack(anchor="w")
        self.status = ttk.Combobox(detalhe, values=STATUS, state="readonly")
        self.status.pack(anchor="w", pady=(0, 8))
        self.campos = {}
        for chave, rotulo, altura in (
            ("observado", "Resultado observado", 3),
            ("notas", "Observações ou motivo do bloqueio", 3),
            ("evidencias", "Evidências (um caminho ou link por linha)", 2),
        ):
            ttk.Label(detalhe, text=rotulo).pack(anchor="w")
            campo = tk.Text(detalhe, wrap="word", height=altura, font=("Segoe UI", 10))
            campo.pack(fill="x", pady=(0, 4))
            self.campos[chave] = campo
        ttk.Button(detalhe, text="Anexar imagens…", command=self.anexar_imagens).pack(anchor="w")
        botoes = ttk.Frame(detalhe)
        botoes.pack(fill="x", pady=10)
        ttk.Button(botoes, text="Salvar", command=self.salvar).pack(side="left")
        ttk.Button(botoes, text="Salvar e avançar", command=self.avancar).pack(side="left", padx=6)
        ttk.Button(botoes, text="Dados de referência", command=self.mostrar_referencia).pack(side="left")
        ttk.Button(botoes, text="Relatório QA", command=self.relatorio).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Exportar CSV", command=self.exportar).pack(side="right")
        janela.protocol("WM_DELETE_WINDOW", self.fechar)
        self.abrir_roteiro(next(iter(self.roteiros)))

    def editar_roteiro(self, novo=False):
        if not self.salvar(atualizar=False):
            return
        nome_atual = self.roteiro_atual
        janela = tk.Toplevel(self.janela)
        janela.title("Incluir solicitação e requisito" if novo else "Editar roteiro")
        janela.geometry("760x580")
        janela.transient(self.janela)
        quadro = ttk.Frame(janela, padding=12)
        quadro.pack(fill="both", expand=True)
        if novo:
            campos = ttk.Frame(quadro)
            campos.pack(fill="x", pady=(0, 6))
            ttk.Label(campos, text="Nº da solicitação").grid(row=0, column=0, sticky="w")
            solicitacao = ttk.Entry(campos, width=18)
            solicitacao.grid(row=1, column=0, sticky="w", padx=(0, 12))
            ttk.Label(campos, text="Nº do requisito").grid(row=0, column=1, sticky="w")
            requisito = ttk.Entry(campos, width=12)
            requisito.grid(row=1, column=1, sticky="w")
            requisito.insert(0, "1")
        else:
            ttk.Label(quadro, text=nome_atual).pack(anchor="w", pady=(0, 6))
        ttk.Label(quadro, text="Use CT01 — Título e preencha Dados, Passos e Esperado em cada caso.").pack(anchor="w")
        campo = scrolledtext.ScrolledText(quadro, wrap="word", font=("Segoe UI", 10))
        campo.pack(fill="both", expand=True, pady=6)
        modelo = ("SUPREMA — Solicitação e requisito\n"
                  "Preparação: empresa, período, build e base de teste.\n\n"
                  "CT01 — Título do caso\n"
                  "Dados: informe a massa e as condições.\n"
                  "Passos:\n1. Descreva a primeira ação.\n"
                  "Esperado: descreva o que deve ser observado.")
        campo.insert("1.0", modelo if novo else self.roteiros[nome_atual].read_text(encoding="utf-8-sig"))

        def gravar():
            chave = nome_atual
            texto = campo.get("1.0", "end-1c").strip()
            _, casos = interpretar_roteiro(texto)
            ids = [codigo for codigo, _, _ in casos]
            try:
                if novo:
                    numeros = (solicitacao.get().strip().lstrip("#"), requisito.get().strip())
                    if any(not re.fullmatch(r"[0-9]+", numero) or int(numero) == 0 for numero in numeros):
                        raise ValueError("Informe números positivos para a solicitação e o requisito.")
                    numero_solicitacao, numero_requisito = map(int, numeros)
                    chave = f"{numero_solicitacao} - Requisito {numero_requisito}"
                if not casos or len(ids) != len(set(ids)):
                    raise ValueError("Inclua ao menos um caso e use um código CT diferente para cada caso.")
                if any(not {"Passos para executar", "Resultado esperado"} <=
                       {rotulo for rotulo, valor in secoes_do_roteiro(corpo) if valor}
                       for _, _, corpo in casos):
                    raise ValueError("Preencha Passos e Esperado em todos os casos.")
                if novo and any(k.casefold() == chave.casefold() for k in listar_roteiros()):
                    raise ValueError("Já existe um roteiro com esse nome.")
                destino = ROOT / f"Casos de Teste - {chave}.txt" if novo else self.roteiros[nome_atual]
                with destino.open("x" if novo else "w", encoding="utf-8-sig") as arquivo:
                    arquivo.write(texto + "\n")
                self.roteiros = listar_roteiros()
                self.seletor.configure(values=tuple(self.roteiros))
                self.abrir_roteiro(chave)
            except (ValueError, OSError) as erro:
                messagebox.showerror("Falha ao salvar roteiro", str(erro), parent=janela)
                return
            janela.destroy()

        ttk.Button(quadro, text="Salvar roteiro", command=gravar).pack(anchor="e")
        janela.grab_set()
        if novo:
            solicitacao.focus_set()

    def abrir_roteiro(self, nome):
        referencia, casos = carregar_roteiro(self.roteiros[nome])
        if not casos:
            raise ValueError(f"Roteiro sem casos: {nome}")
        arquivo = ROOT / f"Resultados - {nome}.json"
        resultados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.exists() else {}
        self.referencia, self.casos = referencia, casos
        self.arquivo_resultados = arquivo
        self.resultados = resultados
        self.roteiro_atual = nome
        self.seletor.set(nome)
        self.janela.title(f"Suprema 8.10a | Testes manuais #{nome}")
        self.mostrar(0)

    def trocar_roteiro(self, _evento):
        nome = self.seletor.get()
        if nome == self.roteiro_atual:
            return
        if self.salvar(atualizar=False):
            try:
                self.abrir_roteiro(nome)
                return
            except (OSError, ValueError) as erro:
                messagebox.showerror("Falha ao abrir roteiro", str(erro), parent=self.janela)
        self.seletor.set(self.roteiro_atual)

    def mostrar(self, indice):
        self.indice = indice
        self.lista.delete(0, tk.END)
        for codigo, _, _ in self.casos:
            self.lista.insert(tk.END, f"{codigo}   {self.resultados.get(codigo, {}).get('status', STATUS[0])}")
        self.lista.selection_set(indice)
        self.lista.see(indice)
        codigo, titulo, texto = self.casos[indice]
        registro = self.resultados.get(codigo, {})
        self.titulo.config(text=titulo)
        self.passos.config(state="normal")
        self.passos.delete("1.0", tk.END)
        for rotulo, conteudo in secoes_do_roteiro(texto):
            self.passos.insert(tk.END, rotulo + "\n", "secao")
            self.passos.insert(tk.END, conteudo + "\n\n")
        self.passos.see("1.0")
        self.passos.config(state="disabled")
        self.status.set(registro.get("status", STATUS[0]))
        quantidade = len(registro.get("achados", []))
        self.botao_achados.config(text=f"Achados do caso ({quantidade})…" if quantidade else "Achados do caso…")

        for chave, campo in self.campos.items():
            campo.delete("1.0", tk.END)
            campo.insert("1.0", registro.get(chave, ""))
        self.resumo.config(text="   |   ".join(
            f"{status}: {sum(self.resultados.get(codigo, {}).get('status', STATUS[0]) == status for codigo, _, _ in self.casos)}"
            for status in STATUS
        ))

    def salvar(self, atualizar=True):
        codigo = self.casos[self.indice][0]
        anterior = self.resultados.get(codigo, {})
        registro = {"status": self.status.get()}
        registro.update({chave: campo.get("1.0", "end-1c") for chave, campo in self.campos.items()})
        if registro["status"] != anterior.get("status", STATUS[0]) or any(
            registro[chave] != anterior.get(chave, "") for chave in self.campos
        ):
            novos = {**self.resultados, codigo: {**anterior, **registro}}
            if not self.persistir(novos, self.janela):
                return False
        if atualizar:
            self.mostrar(self.indice)
        return True

    def selecionar(self, _evento):
        selecao = self.lista.curselection()
        if not selecao or selecao[0] == self.indice:
            return
        if self.salvar(atualizar=False):
            self.mostrar(selecao[0])
        else:
            self.lista.selection_clear(0, tk.END)
            self.lista.selection_set(self.indice)

    def avancar(self):
        if self.salvar(atualizar=False):
            self.mostrar(min(self.indice + 1, len(self.casos) - 1))

    def fechar(self):
        if self.salvar(atualizar=False):
            self.janela.destroy()

    def mostrar_referencia(self):
        janela = tk.Toplevel(self.janela)
        janela.title("Preparação e dados de referência")
        texto = tk.Text(janela, wrap="none", width=87, height=20)
        texto.pack(fill="both", expand=True, padx=12, pady=12)
        texto.insert("1.0", self.referencia)
        texto.config(state="disabled")

    def persistir(self, novos, janela):
        try:
            salvar_resultados(self.arquivo_resultados, novos)
        except OSError as erro:
            messagebox.showerror("Falha ao salvar", str(erro), parent=janela)
            return False
        self.resultados = novos
        return True

    def editar_assinatura(self):
        if not self.salvar(atualizar=False):
            return
        janela = tk.Toplevel(self.janela)
        janela.title("Assinatura do relatório")
        janela.transient(self.janela)
        janela.grab_set()
        campo = tk.Text(janela, width=46, height=4)
        campo.pack(padx=12, pady=12)
        campo.insert("1.0", assinatura_do_relatorio(self.resultados))

        def gravar():
            metadados = {**self.resultados.get("_relatorio", {}), "assinatura": campo.get("1.0", "end-1c").strip()}
            if self.persistir({**self.resultados, "_relatorio": metadados}, janela):
                janela.destroy()

        ttk.Button(janela, text="Salvar assinatura", command=gravar).pack(pady=(0, 12))

    def editar_achados(self):
        if not self.salvar(atualizar=False):
            return
        codigo = self.casos[self.indice][0]
        registro = self.resultados.get(codigo, {})
        achados = list(registro.get("achados", []))
        janela = tk.Toplevel(self.janela)
        janela.title(f"{codigo} | Achados")
        janela.geometry("760x600")
        janela.transient(self.janela)
        janela.grab_set()
        quadro = ttk.Frame(janela, padding=12)
        quadro.pack(fill="both", expand=True)
        selecao = ttk.Combobox(quadro, state="readonly")
        selecao.pack(fill="x", pady=(0, 8))
        entradas = {}
        for chave, rotulo in (("tipo", "Tipo"), ("titulo", "Título"), ("versao", "Versão prevista (opcional)")):
            ttk.Label(quadro, text=rotulo).pack(anchor="w")
            campo = ttk.Combobox(quadro, values=TIPOS_ACHADO, state="readonly") if chave == "tipo" else ttk.Entry(quadro)
            campo.pack(fill="x", pady=(0, 5))
            entradas[chave] = campo
        corpo = scrolledtext.ScrolledText(quadro, wrap="word", height=12)
        corpo.pack(fill="both", expand=True)

        def carregar(indice):
            selecao.configure(values=("Novo achado", *(f"{a['tipo']} — {a['titulo']}" for a in achados)))
            selecao.current(indice)
            achado = achados[indice - 1] if indice else {}
            entradas["tipo"].set(achado.get("tipo", TIPOS_ACHADO[0]))
            for chave in ("titulo", "versao"):
                entradas[chave].delete(0, tk.END)
                entradas[chave].insert(0, achado.get(chave, ""))
            corpo.delete("1.0", tk.END)
            corpo.insert("1.0", achado.get("descricao", MODELO_ACHADO))

        def gravar():
            achado = {chave: campo.get().strip() for chave, campo in entradas.items()}
            achado["descricao"] = corpo.get("1.0", "end-1c").strip()
            if not achado["titulo"] or not achado["descricao"] or achado["descricao"] == MODELO_ACHADO.strip():
                messagebox.showerror("Preencha o achado", "Informe o título e descreva o que foi observado.", parent=janela)
                return
            indice = selecao.current()
            atualizados = achados.copy()
            if indice:
                atualizados[indice - 1] = achado
            else:
                atualizados.append(achado)
            novos = {**self.resultados, codigo: {**registro, "achados": atualizados}}
            if self.persistir(novos, janela):
                janela.destroy()
                self.mostrar(self.indice)

        def exportar_achado():
            indice = selecao.current()
            if not indice:
                messagebox.showinfo("Exportar achado", "Salve o achado e selecione-o para exportar.", parent=janela)
                return
            caminho = filedialog.asksaveasfilename(
                parent=janela, defaultextension=".txt", initialfile=f"Achado - {self.roteiro_atual} - {codigo}.txt",
                filetypes=[("Texto", "*.txt")],
            )
            if caminho:
                try:
                    texto = f"Solicitação {self.roteiro_atual} | {codigo}\n\n" + texto_achado(achados[indice - 1])
                    assinatura = assinatura_do_relatorio(self.resultados)
                    Path(caminho).write_text(texto + ("\n\n" + assinatura if assinatura else "") + "\n", encoding="utf-8-sig")
                except OSError as erro:
                    messagebox.showerror("Falha ao exportar achado", str(erro), parent=janela)

        selecao.bind("<<ComboboxSelected>>", lambda _: carregar(selecao.current()))
        botoes = ttk.Frame(quadro)
        botoes.pack(fill="x", pady=(8, 0))
        ttk.Button(botoes, text="Salvar achado", command=gravar).pack(side="left")
        ttk.Button(botoes, text="Exportar achado salvo em TXT", command=exportar_achado).pack(side="left", padx=6)
        carregar(1 if achados else 0)

    def relatorio_txt(self):
        if not self.salvar():
            return
        caminho = filedialog.asksaveasfilename(
            parent=self.janela, defaultextension=".txt", initialfile=f"Relatório QA - {self.roteiro_atual}.txt",
            filetypes=[("Texto", "*.txt")],
        )
        if caminho:
            try:
                exportar_txt(caminho, self.roteiro_atual, self.casos, self.resultados)
            except OSError as erro:
                messagebox.showerror("Falha ao exportar TXT", str(erro), parent=self.janela)

    def anexar_imagens(self):
        codigo = self.casos[self.indice][0]
        pasta = pasta_evidencias(self.roteiro_atual, codigo)
        arquivos = filedialog.askopenfilenames(
            parent=self.janela, initialdir=pasta or ROOT,
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")],
        )
        if arquivos:
            campo = self.campos["evidencias"]
            referencias = campo.get("1.0", "end-1c").splitlines()
            referencias.extend(str(Path(arquivo)) for arquivo in arquivos)
            campo.delete("1.0", tk.END)
            campo.insert("1.0", "\n".join(dict.fromkeys(referencias)))
            self.salvar()

    def relatorio(self):
        if not self.salvar():
            return
        arquivo = filedialog.asksaveasfilename(
            parent=self.janela, defaultextension=".html",
            initialfile=f"Relatório QA - {self.roteiro_atual}.html",
            filetypes=[("Relatório HTML", "*.html")],
        )
        if not arquivo:
            return
        try:
            exportar_relatorio(arquivo, self.roteiro_atual, self.referencia, self.casos, self.resultados)
            os.startfile(arquivo)
        except OSError as erro:
            messagebox.showerror("Falha no relatório QA", str(erro), parent=self.janela)

    def exportar(self):
        if not self.salvar():
            return
        arquivo = filedialog.asksaveasfilename(
            parent=self.janela, defaultextension=".csv", initialfile=f"Resultados - {self.roteiro_atual}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not arquivo:
            return
        try:
            exportar_csv(arquivo, self.casos, self.resultados)
        except OSError as erro:
            messagebox.showerror("Falha ao exportar", str(erro), parent=self.janela)


if __name__ == "__main__":
    janela = tk.Tk()
    try:
        app = Aplicativo(janela)
    except (OSError, ValueError) as erro:
        messagebox.showerror("Falha ao carregar a solicitação", str(erro), parent=janela)
        janela.destroy()
    else:
        janela.mainloop()
