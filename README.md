# Suprema Testes Manuais

Aplicativo desktop para organizar roteiros, registrar resultados de QA,
anexar evidências e exportar CSV ou relatório HTML com imagens.

No Windows, instale Python 3 com Tkinter e abra Abrir Testes Suprema.cmd.
Também é possível iniciar com `py -3 "Executar Testes Suprema.pyw"`.

Para adicionar um roteiro, copie o formato de Casos de Teste - Demonstração.txt.
Use um nome Casos de Teste - <solicitação e requisito>.txt e reabra o aplicativo.
Os resultados são salvos em JSON por roteiro. Use Relatório QA para gerar o HTML
e a opção de impressão do navegador para salvar em PDF.

## Executável no Windows

O inicializador usa o Python local e abre o aplicativo sem console.
Para compilar na pasta do repositório, use o compilador C# do .NET Framework.

```powershell
& "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:Suprema Testes Manuais.exe" SupremaLauncher.cs
```

Mantenha o executável junto de Executar Testes Suprema.pyw e dos roteiros.
Ele usa .venv quando disponível ou o inicializador Python do Windows.
