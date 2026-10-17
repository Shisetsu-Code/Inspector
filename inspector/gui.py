"""Ventana de Windows/Tkinter: escoger HAR, analizar, consultar informe."""
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from .core import analyze_har
from .direct_model import check_screen
from .payment_contract import evaluate_symbol_count, evaluate_declared_bonus


def main() -> None:
    window = tk.Tk()
    window.title("Inspector — Pragmatic HAR")
    window.geometry("880x680")
    window.minsize(650, 365)
    selected = tk.StringVar()
    output = tk.StringVar(value=str(Path.home() / "Inspector_resultados"))
    status = tk.StringVar(value="Seleccioná un HAR para comenzar.")
    running = tk.BooleanVar(value=False)
    screen_text = tk.StringVar()
    payout_symbol = tk.StringVar(value="1")
    payout_count = tk.StringVar(value="2")
    bonus_money = tk.StringVar(value="8")
    bonus_collect = tk.BooleanVar(value=True)
    bonus_plus_one = tk.BooleanVar(value=False)
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

    ttk.Label(body, text="Tabla de pagos (condición por símbolo; no confirma cobro real)").pack(
        anchor="w", pady=(3, 2))
    prow = ttk.Frame(body); prow.pack(fill="x", pady=(0, 8))
    ttk.Label(prow, text="Símbolo").pack(side="left")
    ttk.Entry(prow, textvariable=payout_symbol, width=8).pack(side="left", padx=(4, 12))
    ttk.Label(prow, text="Coincidencias").pack(side="left")
    ttk.Combobox(prow, textvariable=payout_count, width=5, state="readonly",
                 values=[str(i) for i in range(1, 13)]).pack(side="left", padx=(4, 12))
    def query_payment():
        if not result_folder[0]:
            messagebox.showinfo("Inspector", "Primero analizá un HAR.")
            return
        try:
            folder = result_folder[0]
            contract = json.loads((folder / "payment_contract.json").read_text(encoding="utf-8"))
            record = evaluate_symbol_count(contract, payout_symbol.get().strip(),
                                           int(payout_count.get()))
            if record["table_entry_exists"]:
                append("Paytable: símbolo {} × {} -> multiplicador {} (declarado)".format(
                    record["symbol"], record["count"], record["declared_multiplier"]))
            elif record["status"] == "NO_TABLE_ENTRY":
                append("Paytable: NO hay entrada para símbolo {} con {} coincidencias".format(
                    record["symbol"], record["count"]))
            else:
                append("Símbolo {}: no identificado en la tabla de pagos".format(record["symbol"]))
            append("El cobro efectivo requiere línea/vía válida, wilds, apuesta y estado del servidor.")
            scatter_status = contract.get("scatter", {}).get("status", "UNKNOWN")
            append("Free Spins: umbral de activación NO DEMOSTRADO. Tabla scatter: " + scatter_status)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            messagebox.showerror("Consulta de paytable", str(exc))
    ttk.Button(prow, text="Evaluar condición", command=query_payment).pack(side="left")

    ttk.Label(body, text="Bonus (money symbols y Collect, según reglas publicadas)").pack(
        anchor="w", pady=(4, 2))
    brow = ttk.Frame(body); brow.pack(fill="x", pady=(0, 9))
    ttk.Label(brow, text="Money symbols").pack(side="left")
    ttk.Entry(brow, textvariable=bonus_money, width=5).pack(side="left", padx=(5, 9))
    ttk.Checkbutton(brow, text="Collect carrete 5", variable=bonus_collect).pack(side="left", padx=5)
    ttk.Checkbutton(brow, text="Collect +1", variable=bonus_plus_one).pack(side="left", padx=5)
    def query_bonus():
        if not result_folder[0]:
            messagebox.showinfo("Inspector", "Primero analizá un HAR.")
            return
        try:
            contract = json.loads((result_folder[0] / "payment_contract.json").read_text(encoding="utf-8"))
            checked = evaluate_declared_bonus(
                contract, money_symbol_count=int(bonus_money.get()),
                collect_on_reel_5=bool(bonus_collect.get()),
                collect_plus_one=bool(bonus_plus_one.get()))
            if checked["status"] == "CONTRACT_UNKNOWN":
                append("BONUS: no hay regla pública reconocida en la captura; estado desconocido.")
            elif checked["bonus_trigger_declared_match"]:
                append("BONUS: cumple regla publicada; {} free spins iniciales.".format(
                    checked["predicted_initial_free_spins"]))
            else:
                append("BONUS: no cumple la condición publicada de activación.")
            append("Fuente: ficha oficial. Resultado de servidor NO VERIFICADO.")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            messagebox.showerror("Consulta de bonus", str(exc))
    ttk.Button(brow, text="Evaluar bonus", command=query_bonus).pack(side="left", padx=5)

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
            selector = info.get("initial_reel_set")
            if selector is not None:
                append("reel_set declarado en doInit: " + str(selector))
                count_sel = info.get("initial_direct_screen_count")
                if count_sel is not None:
                    append("Pantallas del modelo directo para ese set: {:,}".format(count_sel).replace(",", "."))
            else:
                append("reel_set inicial: " + info.get("initial_reel_set_status", "UNKNOWN"))
            pay_ids = info.get("paytable_two_symbol_paying_ids", [])
            if pay_ids:
                append("También pagan con 2 coincidencias: " + ", ".join(pay_ids))
            append("Regla de bonus de ficha oficial: "
                   + info.get("official_feature_rules_status", "NOT_AVAILABLE_IN_HAR"))
            if info.get("official_bonus_min_money_symbols") is not None:
                append("Umbral publicado: {} money symbols + Collect; {} free spins.".format(
                    info["official_bonus_min_money_symbols"], info["official_initial_free_spins"]))
            append("Free spins: " + info.get("scatter_declaration_status", "NOT_DECLARED")
                   + " (umbral pendiente de demostrar)")
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
