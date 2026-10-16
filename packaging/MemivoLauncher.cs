using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;
using System.Drawing;
using System.Reflection;
[assembly: AssemblyTitle("Memivo")]
[assembly: AssemblyProduct("Memivo")]
[assembly: AssemblyVersion("0.3.1.0")]
class MemivoLauncher {
    static string Quote(string value) { return "\"" + value.Replace("\"", "\\\"") + "\""; }
    static string FindOnPath(string name) {
        foreach (string part in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';')) {
            try { string path = Path.Combine(part.Trim('"'),name); if (File.Exists(path)) return path; } catch {}
        }
        return null;
    }
    static bool Supported(string executable, string prefix) {
        try {
            var start = new ProcessStartInfo(executable,prefix+" -c \"import sys;sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 2)\"");
            start.UseShellExecute=false;start.CreateNoWindow=true;start.RedirectStandardOutput=true;start.RedirectStandardError=true;
            using(var process=Process.Start(start)) { if(!process.WaitForExit(15000)){process.Kill();return false;}return process.ExitCode==0; }
        } catch { return false; }
    }
    [STAThread] static int Main(string[] args) {
        bool check=Array.IndexOf(args,"--check")>=0;
        string home=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"Memivo");
        string root=AppDomain.CurrentDomain.BaseDirectory;
        Directory.CreateDirectory(home);
        try {
            string python=null,prefix="";
            string explicitPython=Environment.GetEnvironmentVariable("MEMIVO_PYTHON");
            if(!String.IsNullOrEmpty(explicitPython)) {
                if(!File.Exists(explicitPython)||!Supported(explicitPython,""))throw new Exception("MEMIVO_PYTHON must point to Python 3.10-3.12.");
                python=explicitPython;
            }
            string saved=Path.Combine(home,"ui","Scripts","python.exe");
            if(python==null&&File.Exists(saved)&&Supported(saved,""))python=saved;
            string py=FindOnPath("py.exe");
            if(python==null&&py!=null)foreach(string version in new[]{"-3.12","-3.11","-3.10"}) {
                if(Supported(py,version)){python=py;prefix=version;break;}
            }
            string normal=FindOnPath("python.exe");
            if(python==null&&normal!=null&&Supported(normal,""))python=normal;
            if(python==null)throw new Exception("Install Python 3.12 (64-bit) from python.org, or set MEMIVO_PYTHON.\nMemivo does not bundle Python.");
            string script=Path.Combine(root,"app","scripts","launch_release.py");
            if(!File.Exists(script))throw new Exception("The app folder is missing. Extract the entire Memivo ZIP; keep Memivo.exe next to app/.");
            var info=new ProcessStartInfo(python,prefix+" "+Quote(script)+(check?" --check":""));
            info.WorkingDirectory=root;info.UseShellExecute=false;info.CreateNoWindow=true;
            info.RedirectStandardOutput=true;info.RedirectStandardError=true;info.StandardOutputEncoding=Encoding.UTF8;info.StandardErrorEncoding=Encoding.UTF8;
            info.EnvironmentVariables["PYTHONUTF8"]="1";info.EnvironmentVariables["PYTHONUNBUFFERED"]="1";
            info.EnvironmentVariables["MEMIVO_HOME"]=Path.Combine(home,"data");
            info.EnvironmentVariables["MEMIVO_RELEASE_HOME"]=home;
            info.EnvironmentVariables["MEMIVO_MODEL_ROOT"]=Path.Combine(root,"model");
            var process=new Process();process.StartInfo=info;
            object sync=new object();string log=Path.Combine(home,"launcher.log");
            File.WriteAllText(log,DateTime.Now.ToString("s")+" Memivo launcher\r\n",Encoding.UTF8);
            Form form=null;Label status=null;
            if(!check) {
                Application.EnableVisualStyles();
                form=new Form();form.Text="Memivo";form.StartPosition=FormStartPosition.CenterScreen;
                form.ClientSize=new Size(570,170);form.FormBorderStyle=FormBorderStyle.FixedDialog;form.MaximizeBox=false;
                form.BackColor=Color.White;form.Font=new Font("Segoe UI",10);form.Icon=Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
                var title=new Label();title.Text="Memivo — Organize memories, together.";title.Location=new Point(24,22);title.Size=new Size(520,30);title.Font=new Font("Segoe UI",13,FontStyle.Bold);form.Controls.Add(title);
                status=new Label();status.Text="Preparing the local interface. First launch may download UI dependencies.";status.Location=new Point(24,65);status.Size=new Size(520,48);form.Controls.Add(status);
                var bar=new ProgressBar();bar.Style=ProgressBarStyle.Marquee;bar.Location=new Point(24,125);bar.Size=new Size(520,8);form.Controls.Add(bar);
            }
            Action<string> output=delegate(string line) {
                if(line==null)return;lock(sync){File.AppendAllText(log,line+"\r\n",Encoding.UTF8);}
                if(form!=null&&form.IsHandleCreated&&!form.IsDisposed)try { form.BeginInvoke((Action)delegate {
                    if(line.Contains("MEMIVO_WINDOW_READY"))form.Hide();
                    else if(status!=null)status.Text=line.Length>200?line.Substring(0,200):line;
                }); } catch {}
            };
            process.OutputDataReceived+=(sender,e)=>output(e.Data);process.ErrorDataReceived+=(sender,e)=>output(e.Data);
            process.Start();process.BeginOutputReadLine();process.BeginErrorReadLine();
            if(check){process.WaitForExit();return process.ExitCode;}
            bool finished=false;
            var timer=new Timer();timer.Interval=400;timer.Tick+=delegate {
                if(process.HasExited){finished=true;timer.Stop();if(process.ExitCode!=0)MessageBox.Show("Memivo could not start. See:\n"+log,"Memivo",MessageBoxButtons.OK,MessageBoxIcon.Error);form.Close();}
            };timer.Start();
            form.FormClosing+=delegate {if(!finished&&!process.HasExited){try{var kill=new ProcessStartInfo("taskkill","/PID "+process.Id+" /T /F");kill.UseShellExecute=false;kill.CreateNoWindow=true;Process.Start(kill).WaitForExit();}catch{}}};
            Application.Run(form);return process.HasExited?process.ExitCode:1;
        } catch(Exception error) {
            File.WriteAllText(Path.Combine(home,"launcher-error.txt"),error.ToString(),Encoding.UTF8);
            if(!check)MessageBox.Show(error.Message,"Memivo",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
