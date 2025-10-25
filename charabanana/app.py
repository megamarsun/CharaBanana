"""Tkinter application for CharaBanana."""

from __future__ import annotations

import os
import shutil
import webbrowser
from typing import Optional

from PIL import Image, ImageTk  # type: ignore
import tkinter as tk
import tkinter.messagebox as msg
from tkinter import filedialog, ttk

from .api_client import ApiClientError, NanoBananaClient
from .environment import ensure_dir
from .script_processing import ScriptProcessingError, process_script
from .storage import DataStore


class CharaBananaApp:
    def __init__(self, datastore: DataStore, client: NanoBananaClient) -> None:
        self.datastore = datastore
        self.client = client

        self.root = tk.Tk()
        self.root.title("CharaBanana ローカルGUI")

        self.current_preview_path: Optional[str] = None

        self._init_variables()
        self._build_ui()
        ensure_dir(self.client.paths.output_dir)

        self.refresh_char_list()
        self.refresh_scripts_list()
        self.refresh_gallery_list()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _init_variables(self) -> None:
        self.name_var = tk.StringVar()
        self.ref1_var = tk.StringVar()
        self.ref2_var = tk.StringVar()
        self.ref3_var = tk.StringVar()

        self.slot1_var = tk.StringVar()
        self.slot2_var = tk.StringVar()
        self.slot3_var = tk.StringVar()

        self.used_chars_var = tk.StringVar()
        self.aspect_var = tk.StringVar(value="自動")
        self.api_key_var = tk.StringVar()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        self._build_char_tab(notebook)
        self._build_script_tab(notebook)
        self._build_send_tab(notebook)
        self._build_config_tab(notebook)
        self._build_gallery_tab(notebook)

    # ------------------------------------------------------------------
    # Character tab
    # ------------------------------------------------------------------
    def _build_char_tab(self, notebook: ttk.Notebook) -> None:
        frame_char = ttk.Frame(notebook)
        notebook.add(frame_char, text="キャラ管理")

        left_frame = ttk.Frame(frame_char)
        left_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ttk.Label(left_frame, text="登録済みキャラ一覧").pack(anchor="w")
        self.char_list = tk.Listbox(left_frame, height=15)
        self.char_list.pack(fill="both", expand=True)
        self.char_list.bind("<<ListboxSelect>>", self.on_char_select)

        right_frame = ttk.Frame(frame_char)
        right_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ttk.Label(right_frame, text="キャラ名").pack(anchor="w")
        ttk.Entry(right_frame, textvariable=self.name_var, width=40).pack(fill="x")

        ttk.Label(
            right_frame,
            text="ベースプロンプト（一行目＝置換ラベル 以降＝詳細）",
        ).pack(anchor="w")
        self.base_text = tk.Text(right_frame, width=40, height=4)
        self.base_text.pack(fill="x")

        self._build_ref_entry(right_frame, "参照画像1", self.ref1_var)
        self._build_ref_entry(right_frame, "参照画像2", self.ref2_var)
        self._build_ref_entry(right_frame, "参照画像3", self.ref3_var)

        ttk.Button(right_frame, text="保存 新規 or 上書き", command=self.save_char).pack(pady=4)
        ttk.Button(right_frame, text="削除", command=self.delete_char).pack()

    def _build_ref_entry(self, parent: ttk.Frame, label: str, var: tk.StringVar) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        frame = ttk.Frame(parent)
        frame.pack(fill="x")
        ttk.Entry(frame, textvariable=var, width=35).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="参照", command=lambda: self.browse_file_to_var(var)).pack(
            side="left", padx=4
        )

    def refresh_char_list(self) -> None:
        db = self.datastore.load_characters()
        self.char_list.delete(0, tk.END)
        for name in db.keys():
            self.char_list.insert(tk.END, name)

    def on_char_select(self, event) -> None:  # type: ignore[override]
        sel = self.char_list.curselection()
        if not sel:
            return
        name = self.char_list.get(sel[0])
        db = self.datastore.load_characters()
        info = db.get(name)
        if not info:
            return

        self.name_var.set(name)
        self.base_text.delete("1.0", tk.END)
        self.base_text.insert("1.0", info.get("basePrompt", ""))

        refs = info.get("refs", [])
        self.ref1_var.set(refs[0] if len(refs) > 0 else "")
        self.ref2_var.set(refs[1] if len(refs) > 1 else "")
        self.ref3_var.set(refs[2] if len(refs) > 2 else "")

    def browse_file_to_var(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="参照画像を選択",
            filetypes=[
                ("画像ファイル", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("すべてのファイル", "*.*"),
            ],
        )
        if path:
            var.set(path)

    def save_char(self) -> None:
        name = self.name_var.get().strip()
        base_prompt = self.base_text.get("1.0", tk.END).strip()
        refs = [self.ref1_var.get().strip(), self.ref2_var.get().strip(), self.ref3_var.get().strip()]
        refs = [r for r in refs if r]

        if not name or not base_prompt:
            msg.showerror("エラー", "キャラ名とベースプロンプトは必須です")
            return

        db = self.datastore.load_characters()
        db[name] = {"basePrompt": base_prompt, "refs": refs[:3]}
        self.datastore.save_characters(db)
        self.refresh_char_list()
        msg.showinfo("OK", "保存したよ")

    def delete_char(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            msg.showerror("エラー", "削除対象のキャラ名がありません")
            return

        db = self.datastore.load_characters()
        if name in db:
            del db[name]
            self.datastore.save_characters(db)
            self.refresh_char_list()

            self.name_var.set("")
            self.base_text.delete("1.0", tk.END)
            self.ref1_var.set("")
            self.ref2_var.set("")
            self.ref3_var.set("")

            msg.showinfo("OK", "キャラ削除したよ")
        else:
            msg.showerror("エラー", "そのキャラは存在しないよ")

    # ------------------------------------------------------------------
    # Script tab
    # ------------------------------------------------------------------
    def _build_script_tab(self, notebook: ttk.Notebook) -> None:
        frame_script = ttk.Frame(notebook)
        notebook.add(frame_script, text="脚本入力")

        ttk.Label(frame_script, text="脚本テキスト").pack(anchor="w")
        self.script_box = tk.Text(frame_script, width=80, height=10)
        self.script_box.pack(fill="both", expand=True)

        ttk.Button(frame_script, text="変換して保存", command=self.convert_script).pack(pady=6)

        ttk.Label(frame_script, text="保存済み脚本").pack(anchor="w")
        self.scripts_list = tk.Listbox(frame_script, height=5)
        self.scripts_list.pack(fill="x")
        self.scripts_list.bind("<<ListboxSelect>>", self.on_script_select)

        ttk.Button(frame_script, text="この脚本を削除", command=self.delete_script).pack(pady=4)

        ttk.Label(frame_script, text="検出キャラ").pack(anchor="w")
        ttk.Entry(frame_script, textvariable=self.used_chars_var, width=80).pack(fill="x")

        ttk.Label(
            frame_script,
            text="生成プロンプト（置換後テキスト 全文 複数行OK）",
        ).pack(anchor="w")
        self.final_prompt_box = tk.Text(frame_script, width=80, height=4)
        self.final_prompt_box.pack(fill="x")

        ttk.Label(frame_script, text="参照画像スロット（3枚まで）").pack(anchor="w")
        self._build_slot_entry(frame_script, self.slot1_var)
        self._build_slot_entry(frame_script, self.slot2_var)
        self._build_slot_entry(frame_script, self.slot3_var)

    def _build_slot_entry(self, parent: ttk.Frame, var: tk.StringVar) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x")
        ttk.Entry(frame, textvariable=var, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="参照", command=lambda: self.browse_file_to_var(var)).pack(
            side="left", padx=4
        )

    def refresh_scripts_list(self) -> None:
        scripts = self.datastore.load_scripts()
        self.scripts_list.delete(0, tk.END)
        for i, item in enumerate(scripts):
            preview = item.get("script", "").replace("\n", " ")
            preview = preview[:20]
            self.scripts_list.insert(tk.END, f"{i:03d} | {preview}")

    def on_script_select(self, event) -> None:  # type: ignore[override]
        sel = self.scripts_list.curselection()
        if not sel:
            return
        idx = sel[0]

        scripts = self.datastore.load_scripts()
        if idx < 0 or idx >= len(scripts):
            return

        script_item = scripts[idx]
        original_script = script_item.get("script", "")

        self.script_box.delete("1.0", tk.END)
        self.script_box.insert("1.0", original_script)

        self._process_script(original_script, save_new=False)

    def delete_script(self) -> None:
        sel = self.scripts_list.curselection()
        if not sel:
            msg.showerror("エラー", "まず削除したい脚本を選んで")
            return
        idx = sel[0]

        scripts = self.datastore.load_scripts()
        if idx < 0 or idx >= len(scripts):
            msg.showerror("エラー", "その番号は無効だよ")
            return

        del scripts[idx]
        self.datastore.save_scripts(scripts)
        self.refresh_scripts_list()
        msg.showinfo("OK", "脚本削除したよ")

    def convert_script(self) -> None:
        text = self.script_box.get("1.0", tk.END).strip()
        if not text:
            msg.showerror("エラー", "脚本テキストが空だよ")
            return
        if self._process_script(text, save_new=True):
            msg.showinfo("OK", "変換して保存したよ")

    def _process_script(self, text: str, save_new: bool) -> bool:
        try:
            result = process_script(text, self.datastore, save_new)
        except ScriptProcessingError as exc:
            msg.showerror("エラー", str(exc))
            return False

        self.used_chars_var.set(", ".join(result.used_characters))

        self.final_prompt_box.delete("1.0", tk.END)
        self.final_prompt_box.insert("1.0", result.replaced_text)

        self.final_prompt_send_box.delete("1.0", tk.END)
        self.final_prompt_send_box.insert("1.0", result.replaced_text)

        self.slot1_var.set(result.ref_slots[0] if len(result.ref_slots) > 0 else "")
        self.slot2_var.set(result.ref_slots[1] if len(result.ref_slots) > 1 else "")
        self.slot3_var.set(result.ref_slots[2] if len(result.ref_slots) > 2 else "")
        return True

    # ------------------------------------------------------------------
    # Send tab
    # ------------------------------------------------------------------
    def _build_send_tab(self, notebook: ttk.Notebook) -> None:
        frame_send = ttk.Frame(notebook)
        notebook.add(frame_send, text="送信")

        ttk.Label(frame_send, text="最終プロンプト（編集可 複数行OK）").pack(anchor="w")
        self.final_prompt_send_box = tk.Text(frame_send, width=80, height=4)
        self.final_prompt_send_box.pack(fill="x")

        ttk.Label(frame_send, text="参照スロット最終確認（3枚まで）").pack(anchor="w")
        self._build_slot_entry(frame_send, self.slot1_var)
        self._build_slot_entry(frame_send, self.slot2_var)
        self._build_slot_entry(frame_send, self.slot3_var)

        ttk.Label(frame_send, text="アスペクト比").pack(anchor="w")
        aspect_choices = [
            "自動",
            "21:9",
            "16:9",
            "4:3",
            "3:2",
            "1:1",
            "9:16",
            "3:4",
            "2:3",
        ]
        aspect_box = ttk.Combobox(
            frame_send,
            textvariable=self.aspect_var,
            values=aspect_choices,
            state="readonly",
            width=10,
        )
        aspect_box.pack(anchor="w", pady=4)

        ttk.Button(frame_send, text="NanoBananaへ送信", command=self.send_to_api).pack(pady=10)

    # ------------------------------------------------------------------
    # Config tab
    # ------------------------------------------------------------------
    def _build_config_tab(self, notebook: ttk.Notebook) -> None:
        frame_conf = ttk.Frame(notebook)
        notebook.add(frame_conf, text="設定")

        cfg_current = self.datastore.load_config()
        self.api_key_var.set(cfg_current.get("apiKey", ""))

        ttk.Label(frame_conf, text="NanoBanana APIキー").pack(anchor="w")
        ttk.Entry(frame_conf, textvariable=self.api_key_var, width=60, show="*").pack(fill="x")

        ttk.Button(frame_conf, text="APIキー保存", command=self.save_api_key).pack(pady=4)
        ttk.Button(
            frame_conf,
            text="APIキー取得ページを開く",
            command=self.open_apikey_page,
        ).pack(pady=4)

    def save_api_key(self) -> None:
        key = self.api_key_var.get().strip()
        cfg = self.datastore.load_config()
        cfg["apiKey"] = key
        self.datastore.save_config(cfg)
        msg.showinfo("OK", "APIキーを保存したよ")

    def open_apikey_page(self) -> None:
        webbrowser.open("https://ai.google.dev/gemini-api/docs/api-key")

    # ------------------------------------------------------------------
    # Gallery tab
    # ------------------------------------------------------------------
    def _build_gallery_tab(self, notebook: ttk.Notebook) -> None:
        frame_gallery = ttk.Frame(notebook)
        notebook.add(frame_gallery, text="生成結果")

        gallery_left = ttk.Frame(frame_gallery)
        gallery_left.pack(side="left", fill="y", padx=8, pady=8)

        ttk.Label(gallery_left, text="生成済み一覧").pack(anchor="w")
        self.gallery_list = tk.Listbox(gallery_left, height=15)
        self.gallery_list.pack(fill="y", expand=False)
        self.gallery_list.bind("<<ListboxSelect>>", self.on_gallery_select)

        ttk.Button(gallery_left, text="エクスポート", command=self.export_selected_image).pack(
            pady=4, fill="x"
        )
        ttk.Button(gallery_left, text="削除", command=self.delete_selected_image).pack(
            pady=4, fill="x"
        )

        gallery_right = ttk.Frame(frame_gallery)
        gallery_right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        ttk.Label(gallery_right, text="プレビュー").pack(anchor="w")
        self.gallery_canvas = tk.Canvas(gallery_right, width=256, height=256, bg="#ddd")
        self.gallery_canvas.pack()

        ttk.Button(gallery_right, text="フルサイズ表示", command=self.open_full_image).pack(pady=4)

        ttk.Label(gallery_right, text="この画像のプロンプト").pack(anchor="w")
        self.gallery_prompt_box = tk.Text(gallery_right, width=60, height=4)
        self.gallery_prompt_box.pack(fill="x")

    def refresh_gallery_list(self) -> None:
        gallery = self.datastore.load_gallery()
        self.gallery_list.delete(0, tk.END)
        for i, item in enumerate(gallery):
            self.gallery_list.insert(tk.END, f"{i:03d} | {os.path.basename(item['file'])}")

    def on_gallery_select(self, event) -> None:  # type: ignore[override]
        sel = self.gallery_list.curselection()
        if not sel:
            return
        idx = sel[0]

        gallery = self.datastore.load_gallery()
        if idx < 0 or idx >= len(gallery):
            return

        info = gallery[idx]
        img_path = info.get("file")
        prompt = info.get("prompt", "")

        self.gallery_prompt_box.delete("1.0", tk.END)
        self.gallery_prompt_box.insert("1.0", prompt)

        if img_path:
            self.show_preview_image(img_path)

    def show_preview_image(self, path: str) -> None:
        self.current_preview_path = path

        try:
            img = Image.open(path)
            img.thumbnail((256, 256))
            tkimg = ImageTk.PhotoImage(img)
        except Exception:
            img = Image.new("RGB", (256, 256), (240, 240, 240))
            tkimg = ImageTk.PhotoImage(img)

        self.gallery_canvas.img_ref = tkimg
        self.gallery_canvas.delete("all")
        self.gallery_canvas.create_image(128, 128, image=tkimg)

    def export_selected_image(self) -> None:
        sel = self.gallery_list.curselection()
        if not sel:
            msg.showerror("エラー", "まずギャラリーから画像を選んで")
            return
        idx = sel[0]

        gallery = self.datastore.load_gallery()
        if idx < 0 or idx >= len(gallery):
            return

        info = gallery[idx]
        src = info.get("file")
        if not src or not os.path.isfile(src):
            msg.showerror("エラー", "元ファイルが見つからないよ")
            return

        out_path = filedialog.asksaveasfilename(
            title="画像を書き出す",
            initialfile=os.path.basename(src),
            defaultextension=".png",
            filetypes=[
                ("画像ファイル", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
                ("すべてのファイル", "*.*"),
            ],
        )
        if out_path:
            shutil.copyfile(src, out_path)
            msg.showinfo("OK", f"保存したよ\n{out_path}")

    def delete_selected_image(self) -> None:
        sel = self.gallery_list.curselection()
        if not sel:
            msg.showerror("エラー", "まず削除する画像を選んで")
            return
        idx = sel[0]

        gallery = self.datastore.load_gallery()
        if idx < 0 or idx >= len(gallery):
            msg.showerror("エラー", "その番号は無効だよ")
            return

        info = gallery[idx]
        img_path = info.get("file")

        del gallery[idx]
        self.datastore.save_gallery(gallery)

        if img_path and os.path.isfile(img_path):
            try:
                os.remove(img_path)
            except OSError:
                pass

        self.refresh_gallery_list()
        self.gallery_canvas.delete("all")
        self.gallery_prompt_box.delete("1.0", tk.END)
        msg.showinfo("OK", "画像と履歴を削除したよ")

    def open_full_image(self) -> None:
        if not self.current_preview_path or not os.path.isfile(self.current_preview_path):
            msg.showerror("エラー", "まずギャラリーから画像を選んでプレビューして")
            return

        try:
            full_img = Image.open(self.current_preview_path)
        except Exception as exc:
            msg.showerror("エラー", f"画像を開けないよ:\n{exc}")
            return

        top = tk.Toplevel(self.root)
        top.title(f"フルサイズプレビュー - {os.path.basename(self.current_preview_path)}")
        top.geometry("800x600")

        outer_frame = ttk.Frame(top)
        outer_frame.pack(fill="both", expand=True)

        x_scroll = tk.Scrollbar(outer_frame, orient="horizontal")
        y_scroll = tk.Scrollbar(outer_frame, orient="vertical")

        canvas_full = tk.Canvas(
            outer_frame,
            xscrollcommand=x_scroll.set,
            yscrollcommand=y_scroll.set,
            bg="#222",
        )

        x_scroll.config(command=canvas_full.xview)
        y_scroll.config(command=canvas_full.yview)

        canvas_full.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        outer_frame.rowconfigure(0, weight=1)
        outer_frame.columnconfigure(0, weight=1)

        tk_full_img = ImageTk.PhotoImage(full_img)

        canvas_full.create_image(0, 0, anchor="nw", image=tk_full_img)
        canvas_full.config(scrollregion=(0, 0, full_img.width, full_img.height))

        top.img_ref = tk_full_img  # type: ignore[attr-defined]
        top.canvas_widget = canvas_full  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # API interaction
    # ------------------------------------------------------------------
    def send_to_api(self) -> None:
        final_prompt_val = self.final_prompt_send_box.get("1.0", tk.END).strip()
        if not final_prompt_val:
            msg.showerror("エラー", "まず変換して最終プロンプトを用意して")
            return

        slot_paths = [
            self.slot1_var.get().strip(),
            self.slot2_var.get().strip(),
            self.slot3_var.get().strip(),
        ]
        slot_paths = [p for p in slot_paths if p]

        if len(slot_paths) == 0:
            msg.showerror("エラー", "最低1枚は画像スロットに入れて ベース画像にしてね")
            return

        base_img_path = slot_paths[0]
        ref_imgs = slot_paths[1:]

        cfg = self.datastore.load_config()
        api_key = cfg.get("apiKey", "").strip()

        try:
            result = self.client.generate_image(
                api_key=api_key,
                final_prompt=final_prompt_val,
                base_image=base_img_path,
                ref_images=ref_imgs,
                aspect_ratio=self.aspect_var.get().strip(),
            )
        except ApiClientError as exc:
            if exc.is_error:
                msg.showerror(exc.title, exc.message)
            else:
                msg.showinfo(exc.title, exc.message)
            return

        self.refresh_gallery_list()
        self.show_preview_image(result.output_path)
        msg.showinfo(
            "完了",
            "画像を保存したよ:\n"
            f"{result.output_path}\n\n"
            "テスト接続コード:"
            f" {result.test_status}",
        )

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()
