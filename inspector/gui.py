"""Ventana de Windows/Tkinter: escoger HAR, analizar, consultar informe."""
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from .core import analyze_har
from .direct_model import check_screen


def main() -> None:
    window = tk.Tk()
    window.title("Inspector — Pragmatic HAR")
    window.geometry("820x530")
    window.minsize(650, 365)
    selected = tk.StringVar()
    output = tk.StringVar(value=str(Path.home() / "Inspector_resultados"))
    status = tk.StringVar(value="Seleccioná un HAR para comenzar.")
    running = tk.BooleanVar(value=False)
    screen_text = tk.StringVar()
    result_folder = [None]

    body = ttk.Frame(window, padding=18)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="INSPECTOR · Pragmatic Play", font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(body, text="Extracción offline de restricciones. No envía apuestas ni giros.").pack(anchor="w", pady=(1,14))
    ttk.Label(body, text="Archivo HAR").pack(anchor="w")
    hrow = ttk.Frame(body); hrow.pack(fill="x", pady=(4,10))
    ttk.Entry(hrow, textvariable=selected).pack(side="left", fill="x", expand=True)
    ttk.Button(hrow, text="Examinar...", command=lambda:
               selected.set(filedialog.askopenfilename(filetypes=[("HAR", "*.har"), ("Todos", "*.*")]) or selected.get())).pack(side="left", padx=6)

    ttk.Label(body, text="Carpeta de resultados").pack(anchor="w")
    orow = ttk.Frame(body); orow.pack(fill="x", pady=(4,14))
    ttk.Entry(orow, textvariable=output).pack(side="left", fill="x", expand=True)
    ttk.Button(orow, text="Elegir...", command=lambda:
               output.set(filedialog.askdirectory() or output.get())).pack(side="left", padx=6)

    progress = ttk.Progressbar(body, mode="indeterminate")
    progress.pack(fill="x")
    ttk.Label(body, textvariable=status).pack(anchor="w", pady=(8,8))
    ttk.Label(body, text="Consultar pantalla (una letra/código por símbolo, en orden por filas o columnas)").pack(anchor="w", pady=(4,2))
    qrow = ttk.Frame(body); qrow.pack(fill="x", pady=(0,8))
    ttk.Entry(qrow, textvariable=screen_text).pack(side="left", fill="x", expand=True)
    def query_screen():
        if not result_folder[0]:
            messagebox.showinfo("Inspector", "Primero analizá un HAR.")
            return
        try:
            folder = result_folder[0]
            rules = json.loads((folder / "reel_rules.json").read_text(encoding="utf-8"))
            summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
            checked = check_screen(rules["sets"], summary["geometry"]["width"],
                                   summary["geometry"]["height"], screen_text.get().strip())
            result = ("COINCIDE con paradas directas" if checked["direct_model_compatible"]
                      else "NO COINCIDE con paradas directas")
            append(result + "; validez matemática global: DESCONOCIDA")
            if checked["matching_sets_and_orientations"]:
                append("Coincidencias: " + ", ".join(
                    f"set {x['reel_set']} {x['orientation']}"
                    for x in checked["matching_sets_and_orientations"]))
            else:
                for x in checked["closest_direct_model_matches"][:2]:
                    append(f"Mejor aproximación: set {x['reel_set']} {x['orientation']} "
                           f"{x['matching_reels']}/{x['total_reels']} carretes")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            messagebox.showerror("Consulta de pantalla", str(exc))
    ttk.Button(qrow, text="Comprobar pantalla", command=query_screen).pack(side="left", padx=6)

    log = tk.Text(body, wrap="word", height=8)
    log.pack(fill="both", expand=True)
    log.insert("end", "Se extraen tiras, tabla de pagos, huellas de archivos y auditoría del modelo directo.\n")
    log.insert("end", "ATENCIÓN: no se certifican todas las tiradas permitidas o imposibles.\n")
    log.configure(state="disabled")

    def append(text: str):
        log.configure(state="normal")
        log.insert("end", text + "\n")
        log.see("end")
        log.configure(state="disabled")

    def finished(value=None, error=None):
        progress.stop()
        running.set(False)
        button.configure(state="normal")
        if error:
            status.set("Error: " + str(error))
            append(str(error))
            messagebox.showerror("Inspector", str(error))
        else:
            result_folder[0] = value[0]
            info = value[1]
            status.set("Completado: " + (info["game_symbol"] or "sin ID"))
            append("doInit: {} | conjuntos: {} | tiras: {} | assets: {}".format(
                info["doInit_count"], info["reel_set_count"],
                info["reel_strip_count"], info["assets_indexed"]))
            count = info.get("direct_model_union_unique_screen_count")
            if count is not None:
                append("Pantallas únicas en paradas directas: {:,}".format(count).replace(",", "."))
            evidence = info.get("client_server_result_visual_stop_evidence", "INCOMPLETE")
            append("Evidencia del cliente (render de respuesta): " + evidence)
            scene = info.get("client_evidence_status", "NOT_CAPTURED")
            append("Escena del cliente: " + scene)
            if scene == "PARSED":
                append("Detalles en client_evidence.json")
            try:
                trace = json.loads((value[0] / "animation_origin_trace.json").read_text(encoding="utf-8"))
                animation = trace.get("interpretation", "UNKNOWN")
                append("Origen de animaciones: " + animation)
                selector_fields = [
                    f"{k}: {v['status']}"
                    for k, v in trace.get("protocol_fields", {}).items()
                    if v.get("dictionary_declared_in_client")
                ]
                if selector_fields:
                    append("Selectores de protocolo (no necesariamente activos):")
                    for item in selector_fields[:12]:
                        append("  " + item)
                if trace.get("stop_logic", {}).get("blank_symbol_random_replacement_branch"):
                    append("Math.random detectado en sustitución visual; NO prueba RNG del servidor")
            except (OSError, ValueError, KeyError):
                append("El análisis de animación no pudo abrirse; consultar report.md")
            append("Validez matemática global del servidor: DESCONOCIDA")
            append("Archivos guardados: " + str(value[0]))

    def start():
        har = Path(selected.get())
        if running.get():
            return
        if not har.is_file() or har.suffix.lower() != ".har":
            messagebox.showerror("Inspector", "Elegí un archivo .har válido.")
            return
        folder = Path(output.get()) / har.stem
        folder = folder.with_name(folder.name[:65])
        running.set(True)
        button.configure(state="disabled")
        status.set("Analizando HAR...")
        progress.start(13)
        def task():
            try:
                info = analyze_har(har, folder)
                window.after(0, lambda: finished((folder, info), None))
            except Exception as exc:
                window.after(0, lambda: finished(None, exc))
        threading.Thread(target=task, daemon=True).start()

    controls = ttk.Frame(body); controls.pack(fill="x", pady=(10,0))
    button = ttk.Button(controls, text="Analizar HAR", command=start)
    button.pack(side="left")
    ttk.Button(controls, text="Abrir resultados", command=lambda:
               webbrowser.open(result_folder[0].as_uri())
               if result_folder[0] else messagebox.showinfo("Inspector", "Primero ejecutá un análisis.")).pack(side="left", padx=8)
    window.mainloop()


if __name__ == "__main__":
    main()
