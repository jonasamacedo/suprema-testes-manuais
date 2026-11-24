using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class SupremaLauncher
{
    [STAThread]
    private static int Main()
    {
        var folder = AppDomain.CurrentDomain.BaseDirectory;
        var script = Path.Combine(folder, "Executar Testes Suprema.pyw");
        var python = Path.Combine(folder, ".venv", "Scripts", "pythonw.exe");
        if (!File.Exists(script))
        {
            MessageBox.Show("O arquivo Executar Testes Suprema.pyw precisa estar na mesma pasta do executável.",
                "Suprema Testes Manuais", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        try
        {
            var localPython = File.Exists(python);
            Process.Start(new ProcessStartInfo
            {
                FileName = localPython ? python : "pyw.exe",
                Arguments = (localPython ? "" : "-3 ") + "\"" + script + "\"",
                WorkingDirectory = folder,
                UseShellExecute = false,
                CreateNoWindow = true
            });
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show("Não foi possível abrir o aplicativo. Confira a instalação do Python.\n\n" + error.Message,
                "Suprema Testes Manuais", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
