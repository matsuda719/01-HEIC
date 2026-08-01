"""Tkinter GUI for the HEIC to JPG converter.

A thin graphical front-end over the public :func:`heic_to_jpg.run` API. It lets
the user pick one or more HEIC/HEIF files (or a whole directory), choose an
output directory and options, then run the conversion on a background thread so
the window stays responsive.

Launch with::

    python -m heic_to_jpg.gui

The heavy lifting (decode, orientation, EXIF, encode) is delegated entirely to
the existing converter/orchestrator; this module only handles widgets and
wiring.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .models import ConversionConfig, ConversionSummary
from .orchestrator import run

# HEIC/HEIF file dialog filter.
_HEIC_FILETYPES = [
    ("HEIC/HEIF images", "*.heic *.HEIC *.heif *.HEIF"),
    ("All files", "*.*"),
]

_QUALITY_MIN = 1
_QUALITY_MAX = 100
_DEFAULT_QUALITY = 90


class ConverterGUI:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("HEIC → JPG コンバーター")
        root.minsize(560, 480)

        # Selected input paths (files and/or directories).
        self._inputs: list[Path] = []
        # Thread-safe channel for log/progress messages from the worker thread.
        self._msg_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._build_widgets()
        # Begin polling the message queue for updates from the worker thread.
        self.root.after(100, self._drain_queue)

    # ------------------------------------------------------------------ UI --

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=1)

        # --- Input selection ------------------------------------------------
        input_frame = ttk.LabelFrame(main, text="入力")
        input_frame.grid(row=0, column=0, sticky="ew", **pad)
        input_frame.columnconfigure(0, weight=1)

        self._input_list = tk.Listbox(input_frame, height=5)
        self._input_list.grid(row=0, column=0, columnspan=3, sticky="ew", **pad)

        ttk.Button(
            input_frame, text="ファイルを追加...", command=self._add_files
        ).grid(row=1, column=0, sticky="ew", **pad)
        ttk.Button(
            input_frame, text="フォルダを追加...", command=self._add_folder
        ).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(
            input_frame, text="クリア", command=self._clear_inputs
        ).grid(row=1, column=2, sticky="ew", **pad)

        # --- Output directory ----------------------------------------------
        output_frame = ttk.LabelFrame(main, text="出力先")
        output_frame.grid(row=1, column=0, sticky="ew", **pad)
        output_frame.columnconfigure(0, weight=1)

        self._output_var = tk.StringVar(value="")
        ttk.Entry(output_frame, textvariable=self._output_var).grid(
            row=0, column=0, sticky="ew", **pad
        )
        ttk.Button(
            output_frame, text="選択...", command=self._choose_output
        ).grid(row=0, column=1, **pad)
        ttk.Label(
            output_frame,
            text="※ 空欄の場合は入力ファイルと同じ場所に出力します",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8)

        # --- Options --------------------------------------------------------
        opt_frame = ttk.LabelFrame(main, text="オプション")
        opt_frame.grid(row=2, column=0, sticky="ew", **pad)
        opt_frame.columnconfigure(1, weight=1)

        ttk.Label(opt_frame, text="品質 (1-100):").grid(
            row=0, column=0, sticky="w", **pad
        )
        self._quality_var = tk.IntVar(value=_DEFAULT_QUALITY)
        ttk.Spinbox(
            opt_frame,
            from_=_QUALITY_MIN,
            to=_QUALITY_MAX,
            textvariable=self._quality_var,
            width=6,
        ).grid(row=0, column=1, sticky="w", **pad)

        self._recursive_var = tk.BooleanVar(value=False)
        self._overwrite_var = tk.BooleanVar(value=False)
        self._keep_meta_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="サブフォルダも再帰的に変換",
            variable=self._recursive_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(
            opt_frame,
            text="既存の JPG を上書きする",
            variable=self._overwrite_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        ttk.Checkbutton(
            opt_frame,
            text="EXIF メタデータを保持する",
            variable=self._keep_meta_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", **pad)

        # --- Action + progress ---------------------------------------------
        action_frame = ttk.Frame(main)
        action_frame.grid(row=3, column=0, sticky="ew", **pad)
        action_frame.columnconfigure(0, weight=1)

        self._convert_btn = ttk.Button(
            action_frame, text="変換する", command=self._start_conversion
        )
        self._convert_btn.grid(row=0, column=0, sticky="ew", **pad)

        self._progress = ttk.Progressbar(action_frame, mode="indeterminate")
        self._progress.grid(row=1, column=0, sticky="ew", **pad)

        # --- Log ------------------------------------------------------------
        log_frame = ttk.LabelFrame(main, text="結果")
        log_frame.grid(row=4, column=0, sticky="nsew", **pad)
        main.rowconfigure(4, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log = tk.Text(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self._log.grid(row=0, column=0, sticky="nsew", **pad)
        scroll = ttk.Scrollbar(log_frame, command=self._log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._log.configure(yscrollcommand=scroll.set)

    # ---------------------------------------------------------- selection --

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="HEIC/HEIF ファイルを選択",
            filetypes=_HEIC_FILETYPES,
        )
        self._append_inputs(Path(p) for p in paths)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="フォルダを選択")
        if folder:
            self._append_inputs([Path(folder)])

    def _append_inputs(self, paths) -> None:
        for p in paths:
            if p not in self._inputs:
                self._inputs.append(p)
                self._input_list.insert(tk.END, str(p))

    def _clear_inputs(self) -> None:
        self._inputs.clear()
        self._input_list.delete(0, tk.END)

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title="出力先フォルダを選択")
        if folder:
            self._output_var.set(folder)

    # ---------------------------------------------------------- conversion --

    def _start_conversion(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return  # a conversion is already running

        if not self._inputs:
            messagebox.showwarning(
                "入力なし", "変換するファイルまたはフォルダを追加してください。"
            )
            return

        try:
            quality = int(self._quality_var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("入力エラー", "品質は整数で指定してください。")
            return
        if not (_QUALITY_MIN <= quality <= _QUALITY_MAX):
            messagebox.showerror(
                "入力エラー",
                f"品質は {_QUALITY_MIN}〜{_QUALITY_MAX} の範囲で指定してください。",
            )
            return

        output_text = self._output_var.get().strip()
        output_dir = Path(output_text) if output_text else None

        # Snapshot settings for the worker thread.
        inputs = list(self._inputs)
        recursive = self._recursive_var.get()
        overwrite = self._overwrite_var.get()
        keep_metadata = self._keep_meta_var.get()

        self._clear_log()
        self._convert_btn.configure(state=tk.DISABLED)
        self._progress.start(12)

        self._worker = threading.Thread(
            target=self._run_conversion,
            args=(inputs, output_dir, quality, recursive, overwrite, keep_metadata),
            daemon=True,
        )
        self._worker.start()

    def _run_conversion(
        self,
        inputs: list[Path],
        output_dir: Path | None,
        quality: int,
        recursive: bool,
        overwrite: bool,
        keep_metadata: bool,
    ) -> None:
        """Worker thread body: convert each input and aggregate results."""
        all_results = []
        for src in inputs:
            try:
                config = ConversionConfig(
                    input_path=src,
                    output_dir=output_dir,
                    quality=quality,
                    recursive=recursive,
                    overwrite=overwrite,
                    keep_metadata=keep_metadata,
                )
                summary = run(config)
                all_results.extend(summary.results)
                self._post("log", f"[{src}] 完了 ({len(summary.results)} 件)")
            except Exception as exc:  # noqa: BLE001 - surface any error to the UI
                self._post("log", f"[{src}] エラー: {exc}")

        self._post("done", ConversionSummary(all_results))

    # ---------------------------------------------------- thread messaging --

    def _post(self, kind: str, payload: object) -> None:
        self._msg_queue.put((kind, payload))

    def _drain_queue(self) -> None:
        """Poll the worker->UI message queue on the Tk main loop."""
        try:
            while True:
                kind, payload = self._msg_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "done":
                    self._on_done(payload)  # type: ignore[arg-type]
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _on_done(self, summary: ConversionSummary) -> None:
        self._progress.stop()
        self._convert_btn.configure(state=tk.NORMAL)

        if not summary.results:
            self._append_log("変換対象の HEIC/HEIF ファイルが見つかりませんでした。")
            return

        self._append_log(
            f"\n=== 完了: 成功 {summary.succeeded} / "
            f"スキップ {summary.skipped} / 失敗 {summary.failed} ==="
        )
        if summary.failed > 0:
            self._append_log("失敗したファイル:")
            for r in summary.results:
                if r.status.name == "FAILED":
                    self._append_log(f"  {r.src}: {r.error_message}")

    # ----------------------------------------------------------------- log --

    def _clear_log(self) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)

    def _append_log(self, text: str) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, text + "\n")
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)


def main() -> int:
    """Launch the GUI. Returns 0 on normal window close."""
    root = tk.Tk()
    ConverterGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
