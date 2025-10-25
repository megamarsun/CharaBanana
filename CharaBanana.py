import os
import sys
import json
import base64
import shutil
import webbrowser
from PIL import Image, ImageTk      # pip install pillow
import tkinter as tk
import tkinter.messagebox as msg
from tkinter import ttk, filedialog

# ▼ 追加: certifi と CA 設定
import certifi

def _setup_ca_bundle():
    """
    requests が使うCA証明書の場所を決めて、環境変数にセットする
    - 通常のPython実行時:
        certifi.where() のパスを使う
    - PyInstallerで固めたexe実行時:
        dist\CharaBanana\certifi\cacert.pem を優先して使う
        (build.bat の --add-data で入れてるやつ)
    """
    # デフォルトは certifi の標準パス
    ca_path = certifi.where()

    # exe化されてる場合は同梱ファイル側を優先
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bundled = os.path.join(exe_dir, "certifi", "cacert.pem")
        if os.path.exists(bundled):
            ca_path = bundled

    # requests / OpenSSL が見る環境変数を上書き
    os.environ["REQUESTS_CA_BUNDLE"] = ca_path
    os.environ["SSL_CERT_FILE"] = ca_path

_setup_ca_bundle()

# ▼ ここで requests を import（CA設定の後にするのが大事）
import requests                     # pip install requests


# =========================================================
# データ保存先ディレクトリ関連
# =========================================================

def ensure_dir(path_dir):
    if not os.path.exists(path_dir):
        os.makedirs(path_dir, exist_ok=True)

def write_json(path, data):
    parent = os.path.dirname(path)
    ensure_dir(parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_clean_data_dir(target_dir):
    """
    data_work などのデータディレクトリを初期化する
    すでに存在する場合は壊さない
    無い場合は最小構成をつくる
    """
    ensure_dir(target_dir)

    # 必須サブフォルダ
    outputs_dir = os.path.join(target_dir, "outputs")
    ensure_dir(outputs_dir)

    # 必須JSONそれぞれ 無ければつくる
    cfg_path = os.path.join(target_dir, "config.json")
    if not os.path.exists(cfg_path):
        write_json(cfg_path, {"apiKey": ""})

    chars_path = os.path.join(target_dir, "characters.json")
    if not os.path.exists(chars_path):
        write_json(chars_path, {})

    gallery_path = os.path.join(target_dir, "gallery.json")
    if not os.path.exists(gallery_path):
        write_json(gallery_path, [])

    scripts_path = os.path.join(target_dir, "scripts.json")
    if not os.path.exists(scripts_path):
        write_json(scripts_path, [])

def get_base_dir():
    """
    実行中のベースディレクトリを返す
    exeなら dist\CharaBanana\
    python実行なら CharaBanana.py があるディレクトリ
    """
    if getattr(sys, "frozen", False):
        # PyInstallerで固めたexe
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        # 通常のPython実行
        return os.path.dirname(os.path.abspath(__file__))

def get_data_dir():
    """
    どこをデータ置き場にするか決定して返す
    ルール
      exeで動いてる場合:
        exeと同じフォルダを使う
        (dist\CharaBanana\ 内で config.json などを読む書く)

      通常のpython実行の場合:
        同じ階層に data_work フォルダを使う
        data_work が無ければここで自動的に初期化して作る
    """
    base = get_base_dir()

    if getattr(sys, "frozen", False):
        # 配布後のexeモード
        data_dir = base
        init_clean_data_dir(data_dir)  # 念のため ないファイルはここでも作る
        return data_dir
    else:
        # 開発/ローカルpythonモード
        data_dir = os.path.join(base, "data_work")
        init_clean_data_dir(data_dir)
        return data_dir

BASE_DIR = get_base_dir()
DATA_DIR = get_data_dir()
OUTPUT_DIR = os.path.join(DATA_DIR, "outputs")

# JSONファイルのパス
CHAR_FILE    = os.path.join(DATA_DIR, "characters.json")
CONFIG_FILE  = os.path.join(DATA_DIR, "config.json")
GALLERY_FILE = os.path.join(DATA_DIR, "gallery.json")
SCRIPTS_FILE = os.path.join(DATA_DIR, "scripts.json")

# NanoBananaエンドポイント
API_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-image:generateContent"
)

# 現在プレビュー中の画像フルパス
current_preview_path = None


# =========================================================
# JSON読み書きラッパ
# =========================================================

def load_json_fallback(path, default_val):
    # 念のため無ければ作る
    if not os.path.exists(path):
        write_json(path, default_val)
        return default_val
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_force(path, data):
    write_json(path, data)

def load_chars():
    return load_json_fallback(CHAR_FILE, {})

def save_chars(db):
    save_json_force(CHAR_FILE, db)

def load_config():
    return load_json_fallback(CONFIG_FILE, {"apiKey": ""})

def save_config(cfg):
    save_json_force(CONFIG_FILE, cfg)

def load_gallery():
    return load_json_fallback(GALLERY_FILE, [])

def save_gallery(gal):
    save_json_force(GALLERY_FILE, gal)

def load_scripts():
    return load_json_fallback(SCRIPTS_FILE, [])

def save_scripts(lst):
    save_json_force(SCRIPTS_FILE, lst)


# =========================================================
# 画像ユーティリティなど
# =========================================================

def guess_mime_type(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".jpg") or p.endswith(".jpeg"):
        return "image/jpeg"
    if p.endswith(".webp"):
        return "image/webp"
    if p.endswith(".bmp"):
        return "image/bmp"
    return "image/png"

def file_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def augment_prompt(user_text: str) -> str:
    guard = (
        "ゼロからの新規生成は禁止。最後の画像（ベース画像）を加工対象とし、"
        "構図・カメラ・照明・解像度・アスペクト比・被写体の形状を保持。"
        "他の参照画像は色味や質感などの雰囲気だけに使う。"
    )
    base = (user_text or "").strip()
    if base:
        return base + "\n" + guard
    else:
        return guard


# =========================================================
# キャラ管理タブ
# =========================================================

def refresh_char_list():
    db = load_chars()
    char_list.delete(0, tk.END)
    for name in db.keys():
        char_list.insert(tk.END, name)

def on_char_select(event):
    sel = char_list.curselection()
    if not sel:
        return
    name = char_list.get(sel[0])
    db = load_chars()
    info = db[name]

    name_var.set(name)

    base_text.delete("1.0", tk.END)
    base_text.insert("1.0", info.get("basePrompt", ""))

    refs_arr = info.get("refs", [])
    ref1_var.set(refs_arr[0] if len(refs_arr) > 0 else "")
    ref2_var.set(refs_arr[1] if len(refs_arr) > 1 else "")
    ref3_var.set(refs_arr[2] if len(refs_arr) > 2 else "")

def browse_file_to_var(var):
    path = filedialog.askopenfilename(
        title="参照画像を選択",
        filetypes=[
            ("画像ファイル", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
            ("すべてのファイル", "*.*")
        ]
    )
    if path:
        var.set(path)

def save_char():
    n = name_var.get().strip()
    bp = base_text.get("1.0", tk.END).strip()
    r1 = ref1_var.get().strip()
    r2 = ref2_var.get().strip()
    r3 = ref3_var.get().strip()

    if not n or not bp:
        msg.showerror("エラー", "キャラ名とベースプロンプトは必須です")
        return

    refs_list = [x for x in [r1, r2, r3] if x]

    db = load_chars()
    db[n] = {
        "basePrompt": bp,
        "refs": refs_list[:3]
    }
    save_chars(db)
    refresh_char_list()
    msg.showinfo("OK", "保存したよ")

def delete_char():
    n = name_var.get().strip()
    if not n:
        msg.showerror("エラー", "削除対象のキャラ名がありません")
        return

    db = load_chars()
    if n in db:
        del db[n]
        save_chars(db)
        refresh_char_list()

        name_var.set("")
        base_text.delete("1.0", tk.END)
        ref1_var.set("")
        ref2_var.set("")
        ref3_var.set("")

        msg.showinfo("OK", "キャラ削除したよ")
    else:
        msg.showerror("エラー", "そのキャラは存在しないよ")


# =========================================================
# 脚本処理
# =========================================================

def process_script(text, save_new):
    """
    text = 元の脚本全文
    save_new = True なら scripts.json に追加保存
    save_new = False なら読み込み再利用だけ
    """

    db = load_chars()

    found = []
    for cname in db.keys():
        if cname and (cname in text):
            found.append(cname)

    if len(found) == 0:
        msg.showerror("エラー", "登録済みキャラが見つからん")
        return

    if len(found) > 3:
        msg.showerror(
            "エラー",
            f"このシーンは{len(found)}人います: {', '.join(found)}\n3人までに分けて"
        )
        return

    replaced_text = text
    found_sorted = sorted(found, key=len, reverse=True)

    for cname in found_sorted:
        base_prompt_full = db[cname].get("basePrompt", "")
        short_desc = base_prompt_full.splitlines()[0] if base_prompt_full else cname
        token = f"[{short_desc}]"
        replaced_text = replaced_text.replace(cname, token)

    ref_slots = []
    for n in found_sorted:
        refs = db[n].get("refs", [])
        if len(refs) > 0:
            ref_slots.append(refs[0])
        if len(ref_slots) >= 3:
            break

    used_chars_var.set(", ".join(found))

    final_prompt_box.delete("1.0", tk.END)
    final_prompt_box.insert("1.0", replaced_text)

    final_prompt_send_box.delete("1.0", tk.END)
    final_prompt_send_box.insert("1.0", replaced_text)

    slot1_var.set(ref_slots[0] if len(ref_slots) > 0 else "")
    slot2_var.set(ref_slots[1] if len(ref_slots) > 1 else "")
    slot3_var.set(ref_slots[2] if len(ref_slots) > 2 else "")

    if save_new:
        scripts = load_scripts()
        scripts.append({
            "script": text,
            "prompt": replaced_text
        })
        save_scripts(scripts)
        refresh_scripts_list()
        msg.showinfo("OK", "変換して保存したよ")


def refresh_scripts_list():
    scripts = load_scripts()
    scripts_list.delete(0, tk.END)
    for i, item in enumerate(scripts):
        preview = item.get("script", "").replace("\n", " ")
        preview = preview[:20]
        scripts_list.insert(tk.END, f"{i:03d} | {preview}")

def on_script_select(event):
    sel = scripts_list.curselection()
    if not sel:
        return
    idx = sel[0]

    scripts = load_scripts()
    if idx < 0 or idx >= len(scripts):
        return

    sc = scripts[idx]
    original_script = sc.get("script", "")

    script_box.delete("1.0", tk.END)
    script_box.insert("1.0", original_script)

    process_script(original_script, save_new=False)

def delete_script():
    sel = scripts_list.curselection()
    if not sel:
        msg.showerror("エラー", "まず削除したい脚本を選んで")
        return
    idx = sel[0]

    scripts = load_scripts()
    if idx < 0 or idx >= len(scripts):
        msg.showerror("エラー", "その番号は無効だよ")
        return

    del scripts[idx]
    save_scripts(scripts)
    refresh_scripts_list()
    msg.showinfo("OK", "脚本削除したよ")

def convert_script():
    text = script_box.get("1.0", tk.END).strip()
    if not text:
        msg.showerror("エラー", "脚本テキストが空だよ")
        return
    process_script(text, save_new=True)


# =========================================================
# API送信 NanoBanana
# =========================================================

def send_to_api():
    # デバッグ情報: どの証明書を使ってるか確認
    # exe化後は dist\CharaBanana\certifi\cacert.pem を想定
    ca_path = None
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bundled = os.path.join(exe_dir, "certifi", "cacert.pem")
        if os.path.exists(bundled):
            ca_path = bundled
    if ca_path is None:
        # フォールバックで certifi.where() を使う
        try:
            import certifi
            ca_path = certifi.where()
        except Exception:
            ca_path = None

    # GUIから最終プロンプトと画像スロットを集める
    final_prompt_val = final_prompt_send_box.get("1.0", tk.END).strip()
    if not final_prompt_val:
        msg.showerror("エラー", "まず変換して最終プロンプトを用意して")
        return

    slot_paths = [
        slot1_var.get().strip(),
        slot2_var.get().strip(),
        slot3_var.get().strip()
    ]
    slot_paths = [p for p in slot_paths if p]

    if len(slot_paths) == 0:
        msg.showerror("エラー", "最低1枚は画像スロットに入れて ベース画像にしてね")
        return

    base_img_path = slot_paths[0]
    ref_imgs = slot_paths[1:]

    if not os.path.isfile(base_img_path):
        msg.showerror("エラー", "ベース画像のファイルが存在しないよ")
        return

    cfg = load_config()
    api_key = cfg.get("apiKey", "").strip()
    if not api_key:
        msg.showerror("エラー", "APIキーが未設定です 設定タブで保存してね")
        return

    # APIに投げるリクエスト本体
    parts = []
    parts.append({
        "text": augment_prompt(final_prompt_val)
    })

    # 雰囲気参照 (2枚まで)
    for refp in ref_imgs[:2]:
        if os.path.isfile(refp):
            parts.append({
                "inline_data": {
                    "mime_type": guess_mime_type(refp),
                    "data": file_to_b64(refp)
                }
            })

    # ベース画像 (最後に入れる)
    parts.append({
        "inline_data": {
            "mime_type": guess_mime_type(base_img_path),
            "data": file_to_b64(base_img_path)
        }
    })

    ar_val = aspect_var.get().strip()
    generation_config = {
        "responseModalities": ["Image"]
    }
    if ar_val and ar_val != "自動":
        generation_config["imageConfig"] = {
            "aspectRatio": ar_val
        }

    body = {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": generation_config
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    # ① まずは単純なHTTPS疎通テスト（GET）
    #    ここで失敗するならFWとかアンチウイルスがexeを弾いてる可能性が高い
    test_url = "https://generativelanguage.googleapis.com/"
    try:
        r_test = requests.get(test_url, timeout=5, verify=ca_path if ca_path else True)
        # 200とか404でもいい、レスポンスが返るならTLSは成功
        test_status = r_test.status_code
    except Exception as e:
        # ここで落ちる＝TLS確立すらできない＝今回のエラー再現ゾーン
        msg.showerror(
            "通信テスト失敗",
            "exeがHTTPS接続できなかったよ\n"
            f"証明書ファイル: {ca_path}\n"
            f"URL: {test_url}\n"
            f"例外: {e}\n\n"
            "セキュリティソフトやFWがexeの外向き通信を止めてる可能性が高い"
        )
        return

    # ② 本番POST
    try:
        resp = requests.post(
            API_ENDPOINT,
            headers=headers,
            json=body,
            timeout=180,
            verify=ca_path if ca_path else True
        )
    except requests.exceptions.RequestException as e:
        msg.showerror(
            "送信失敗",
            "HTTPエラー(POSTできなかった)\n"
            f"証明書ファイル: {ca_path}\n"
            f"ステップ: POST\n"
            f"例外: {e}"
        )
        return

    status = resp.status_code

    # レート制限・その他
    if status == 429:
        msg.showerror(
            "送信失敗",
            "429 レート制限 or 無料枠上限\n"
            f"{resp.text[:500]}"
        )
        return

    if status != 200:
        msg.showerror(
            "送信失敗",
            f"ステータス {status}\n"
            f"証明書ファイル: {ca_path}\n"
            f"レスポンス: {resp.text[:500]}"
        )
        return

    # レスポンス解析
    try:
        resp_json = resp.json()
    except Exception as e:
        msg.showerror(
            "解析失敗",
            "サーバーからJSONじゃないものが返ってきた\n"
            f"{e}\n"
            f"{resp.text[:500]}"
        )
        return

    # APIエラー形式チェック
    if isinstance(resp_json, dict) and "error" in resp_json:
        err = resp_json["error"]
        code = err.get("code")
        status_txt = err.get("status")
        message = err.get("message", "Unknown error")
        msg.showerror(
            "送信失敗",
            f"APIエラー: {code}/{status_txt}\n{message}"
        )
        return

    # 画像データ取り出し
    img_b64 = None
    try:
        parts_out = resp_json["candidates"][0]["content"]["parts"]
        for p in parts_out:
            if "inline_data" in p and "data" in p["inline_data"]:
                img_b64 = p["inline_data"]["data"]
                break
            if "inlineData" in p and "data" in p["inlineData"]:
                img_b64 = p["inlineData"]["data"]
                break
    except Exception:
        img_b64 = None

    if not img_b64:
        ensure_dir(OUTPUT_DIR)
        debug_path = os.path.join(OUTPUT_DIR, "last_response.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(resp_json, f, ensure_ascii=False, indent=2)

        preview_head = json.dumps(resp_json, ensure_ascii=False)[:800]
        msg.showinfo(
            "完了",
            "レスポンスに画像データが見つからなかった\n"
            f"{debug_path} を確認して\n\n"
            f"{preview_head}"
        )
        return

    # 画像保存
    ensure_dir(OUTPUT_DIR)
    gallery = load_gallery()
    next_index = len(gallery) + 1
    out_name = f"img_{next_index:04d}.png"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    with open(out_path, "wb") as f:
        f.write(base64.b64decode(img_b64))

    gallery.append({
        "file": out_path,
        "prompt": final_prompt_val
    })
    save_gallery(gallery)

    refresh_gallery_list()
    show_preview_image(out_path)

    msg.showinfo(
        "完了",
        "画像を保存したよ:\n"
        f"{out_path}\n\n"
        "テスト接続コード:"
        f" {test_status}"
    )


# =========================================================
# ギャラリー
# =========================================================

def refresh_gallery_list():
    gal = load_gallery()
    gallery_list.delete(0, tk.END)
    for i, item in enumerate(gal):
        gallery_list.insert(tk.END, f"{i:03d} | {os.path.basename(item['file'])}")

def on_gallery_select(event):
    sel = gallery_list.curselection()
    if not sel:
        return
    idx = sel[0]

    gal = load_gallery()
    if idx < 0 or idx >= len(gal):
        return

    info = gal[idx]
    img_path = info["file"]
    img_prompt = info.get("prompt", "")

    gallery_prompt_box.delete("1.0", tk.END)
    gallery_prompt_box.insert("1.0", img_prompt)

    show_preview_image(img_path)

def show_preview_image(path):
    global current_preview_path
    current_preview_path = path

    try:
        img = Image.open(path)
        img.thumbnail((256, 256))
        tkimg = ImageTk.PhotoImage(img)
    except Exception:
        img = Image.new("RGB", (256, 256), (240, 240, 240))
        tkimg = ImageTk.PhotoImage(img)

    gallery_canvas.img_ref = tkimg
    gallery_canvas.delete("all")
    gallery_canvas.create_image(128, 128, image=tkimg)

def export_selected_image():
    sel = gallery_list.curselection()
    if not sel:
        msg.showerror("エラー", "まずギャラリーから画像を選んで")
        return
    idx = sel[0]

    gal = load_gallery()
    if idx < 0 or idx >= len(gal):
        return

    info = gal[idx]
    src = info["file"]

    if not os.path.isfile(src):
        msg.showerror("エラー", "元ファイルが見つからないよ")
        return

    out_path = filedialog.asksaveasfilename(
        title="画像を書き出す",
        initialfile=os.path.basename(src),
        defaultextension=".png",
        filetypes=[
            ("画像ファイル", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"),
            ("すべてのファイル", "*.*")
        ]
    )
    if out_path:
        shutil.copyfile(src, out_path)
        msg.showinfo("OK", f"保存したよ\n{out_path}")

def delete_selected_image():
    sel = gallery_list.curselection()
    if not sel:
        msg.showerror("エラー", "まず削除する画像を選んで")
        return
    idx = sel[0]

    gal = load_gallery()
    if idx < 0 or idx >= len(gal):
        msg.showerror("エラー", "その番号は無効だよ")
        return

    info = gal[idx]
    img_path = info.get("file")

    del gal[idx]
    save_gallery(gal)

    if img_path and os.path.isfile(img_path):
        try:
            os.remove(img_path)
        except OSError:
            pass

    refresh_gallery_list()
    gallery_canvas.delete("all")
    gallery_prompt_box.delete("1.0", tk.END)
    msg.showinfo("OK", "画像と履歴を削除したよ")

def open_full_image():
    global current_preview_path
    if not current_preview_path or not os.path.isfile(current_preview_path):
        msg.showerror("エラー", "まずギャラリーから画像を選んでプレビューして")
        return

    try:
        full_img = Image.open(current_preview_path)
    except Exception as e:
        msg.showerror("エラー", f"画像を開けないよ:\n{e}")
        return

    top = tk.Toplevel(root)
    top.title(f"フルサイズプレビュー - {os.path.basename(current_preview_path)}")
    top.geometry("800x600")

    outer_frame = ttk.Frame(top)
    outer_frame.pack(fill="both", expand=True)

    x_scroll = tk.Scrollbar(outer_frame, orient="horizontal")
    y_scroll = tk.Scrollbar(outer_frame, orient="vertical")

    canvas_full = tk.Canvas(
        outer_frame,
        xscrollcommand=x_scroll.set,
        yscrollcommand=y_scroll.set,
        bg="#222"
    )

    x_scroll.config(command=canvas_full.xview)
    y_scroll.config(command=canvas_full.yview)

    canvas_full.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    x_scroll.grid(row=1, column=0, sticky="ew")

    outer_frame.rowconfigure(0, weight=1)
    outer_frame.columnconfigure(0, weight=1)

    tk_full_img = ImageTk.PhotoImage(full_img)

    img_id = canvas_full.create_image(0, 0, anchor="nw", image=tk_full_img)

    canvas_full.config(scrollregion=(0, 0, full_img.width, full_img.height))

    top.img_ref = tk_full_img
    top.canvas_item_id = img_id
    top.canvas_widget = canvas_full


# =========================================================
# 設定タブ
# =========================================================

def save_api_key():
    key_now = api_key_var.get().strip()
    cfg = load_config()
    cfg["apiKey"] = key_now
    save_config(cfg)
    msg.showinfo("OK", "APIキーを保存したよ")

def open_apikey_page():
    webbrowser.open("https://aistudio.google.com/app/apikey")


# =========================================================
# GUI構築
# =========================================================

root = tk.Tk()
root.title("CharaBanana ローカルGUI")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# タブ1 キャラ管理
frame_char = ttk.Frame(notebook)
notebook.add(frame_char, text="キャラ管理")

left_frame = ttk.Frame(frame_char)
left_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

ttk.Label(left_frame, text="登録済みキャラ一覧").pack(anchor="w")
char_list = tk.Listbox(left_frame, height=15)
char_list.pack(fill="both", expand=True)
char_list.bind("<<ListboxSelect>>", on_char_select)

right_frame = ttk.Frame(frame_char)
right_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

name_var = tk.StringVar()
ref1_var = tk.StringVar()
ref2_var = tk.StringVar()
ref3_var = tk.StringVar()

ttk.Label(right_frame, text="キャラ名").pack(anchor="w")
ttk.Entry(right_frame, textvariable=name_var, width=40).pack(fill="x")

ttk.Label(right_frame, text="ベースプロンプト（一行目＝置換ラベル 以降＝詳細）").pack(anchor="w")
base_text = tk.Text(right_frame, width=40, height=4)
base_text.pack(fill="x")

ttk.Label(right_frame, text="参照画像1").pack(anchor="w")
ref1_frame = ttk.Frame(right_frame)
ref1_frame.pack(fill="x")
ttk.Entry(ref1_frame, textvariable=ref1_var, width=35).pack(side="left", fill="x", expand=True)
ttk.Button(ref1_frame, text="参照", command=lambda: browse_file_to_var(ref1_var)).pack(side="left", padx=4)

ttk.Label(right_frame, text="参照画像2").pack(anchor="w")
ref2_frame = ttk.Frame(right_frame)
ref2_frame.pack(fill="x")
ttk.Entry(ref2_frame, textvariable=ref2_var, width=35).pack(side="left", fill="x", expand=True)
ttk.Button(ref2_frame, text="参照", command=lambda: browse_file_to_var(ref2_var)).pack(side="left", padx=4)

ttk.Label(right_frame, text="参照画像3").pack(anchor="w")
ref3_frame = ttk.Frame(right_frame)
ref3_frame.pack(fill="x")
ttk.Entry(ref3_frame, textvariable=ref3_var, width=35).pack(side="left", fill="x", expand=True)
ttk.Button(ref3_frame, text="参照", command=lambda: browse_file_to_var(ref3_var)).pack(side="left", padx=4)

ttk.Button(right_frame, text="保存 新規 or 上書き", command=save_char).pack(pady=4)
ttk.Button(right_frame, text="削除", command=delete_char).pack()

# タブ2 脚本入力
frame_script = ttk.Frame(notebook)
notebook.add(frame_script, text="脚本入力")

ttk.Label(frame_script, text="脚本テキスト").pack(anchor="w")
script_box = tk.Text(frame_script, width=80, height=10)
script_box.pack(fill="both", expand=True)

ttk.Button(frame_script, text="変換して保存", command=convert_script).pack(pady=6)

ttk.Label(frame_script, text="保存済み脚本").pack(anchor="w")
scripts_list = tk.Listbox(frame_script, height=5)
scripts_list.pack(fill="x")
scripts_list.bind("<<ListboxSelect>>", on_script_select)

ttk.Button(frame_script, text="この脚本を削除", command=delete_script).pack(pady=4)

used_chars_var = tk.StringVar()
slot1_var = tk.StringVar()
slot2_var = tk.StringVar()
slot3_var = tk.StringVar()

ttk.Label(frame_script, text="検出キャラ").pack(anchor="w")
ttk.Entry(frame_script, textvariable=used_chars_var, width=80).pack(fill="x")

ttk.Label(frame_script, text="生成プロンプト（置換後テキスト 全文 複数行OK）").pack(anchor="w")
final_prompt_box = tk.Text(frame_script, width=80, height=4)
final_prompt_box.pack(fill="x")

ttk.Label(frame_script, text="参照画像スロット（3枚まで）").pack(anchor="w")

slot1_frame = ttk.Frame(frame_script)
slot1_frame.pack(fill="x")
ttk.Entry(slot1_frame, textvariable=slot1_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot1_frame, text="参照", command=lambda: browse_file_to_var(slot1_var)).pack(side="left", padx=4)

slot2_frame = ttk.Frame(frame_script)
slot2_frame.pack(fill="x")
ttk.Entry(slot2_frame, textvariable=slot2_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot2_frame, text="参照", command=lambda: browse_file_to_var(slot2_var)).pack(side="left", padx=4)

slot3_frame = ttk.Frame(frame_script)
slot3_frame.pack(fill="x")
ttk.Entry(slot3_frame, textvariable=slot3_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot3_frame, text="参照", command=lambda: browse_file_to_var(slot3_var)).pack(side="left", padx=4)

# タブ3 送信
frame_send = ttk.Frame(notebook)
notebook.add(frame_send, text="送信")

ttk.Label(frame_send, text="最終プロンプト（編集可 複数行OK）").pack(anchor="w")
final_prompt_send_box = tk.Text(frame_send, width=80, height=4)
final_prompt_send_box.pack(fill="x")

ttk.Label(frame_send, text="参照スロット最終確認（3枚まで）").pack(anchor="w")

slot1_frame_send = ttk.Frame(frame_send)
slot1_frame_send.pack(fill="x")
ttk.Entry(slot1_frame_send, textvariable=slot1_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot1_frame_send, text="参照", command=lambda: browse_file_to_var(slot1_var)).pack(side="left", padx=4)

slot2_frame_send = ttk.Frame(frame_send)
slot2_frame_send.pack(fill="x")
ttk.Entry(slot2_frame_send, textvariable=slot2_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot2_frame_send, text="参照", command=lambda: browse_file_to_var(slot2_var)).pack(side="left", padx=4)

slot3_frame_send = ttk.Frame(frame_send)
slot3_frame_send.pack(fill="x")
ttk.Entry(slot3_frame_send, textvariable=slot3_var, width=70).pack(side="left", fill="x", expand=True)
ttk.Button(slot3_frame_send, text="参照", command=lambda: browse_file_to_var(slot3_var)).pack(side="left", padx=4)

ttk.Label(frame_send, text="アスペクト比").pack(anchor="w")
aspect_var = tk.StringVar(value="自動")

aspect_choices = [
    "自動",
    "21:9", "16:9", "4:3", "3:2",
    "1:1",
    "9:16", "3:4", "2:3"
]

aspect_box = ttk.Combobox(
    frame_send,
    textvariable=aspect_var,
    values=aspect_choices,
    state="readonly",
    width=10
)
aspect_box.pack(anchor="w", pady=4)

ttk.Button(frame_send, text="NanoBananaへ送信", command=send_to_api).pack(pady=10)

# タブ4 設定
frame_conf = ttk.Frame(notebook)
notebook.add(frame_conf, text="設定")

api_key_var = tk.StringVar()
cfg_current = load_config()
api_key_var.set(cfg_current.get("apiKey", ""))

ttk.Label(frame_conf, text="NanoBanana APIキー").pack(anchor="w")
ttk.Entry(frame_conf, textvariable=api_key_var, width=60, show="*").pack(fill="x")

ttk.Button(frame_conf, text="APIキー保存", command=save_api_key).pack(pady=4)
ttk.Button(frame_conf, text="APIキー取得ページを開く", command=open_apikey_page).pack(pady=4)

# タブ5 生成結果
frame_gallery = ttk.Frame(notebook)
notebook.add(frame_gallery, text="生成結果")

gallery_left = ttk.Frame(frame_gallery)
gallery_left.pack(side="left", fill="y", padx=8, pady=8)

ttk.Label(gallery_left, text="生成済み一覧").pack(anchor="w")
gallery_list = tk.Listbox(gallery_left, height=15)
gallery_list.pack(fill="y", expand=False)
gallery_list.bind("<<ListboxSelect>>", on_gallery_select)

ttk.Button(gallery_left, text="エクスポート", command=export_selected_image).pack(pady=4, fill="x")
ttk.Button(gallery_left, text="削除", command=delete_selected_image).pack(pady=4, fill="x")

gallery_right = ttk.Frame(frame_gallery)
gallery_right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

ttk.Label(gallery_right, text="プレビュー").pack(anchor="w")
gallery_canvas = tk.Canvas(gallery_right, width=256, height=256, bg="#ddd")
gallery_canvas.pack()

ttk.Button(gallery_right, text="フルサイズ表示", command=open_full_image).pack(pady=4)

ttk.Label(gallery_right, text="この画像のプロンプト").pack(anchor="w")
gallery_prompt_box = tk.Text(gallery_right, width=60, height=4)
gallery_prompt_box.pack(fill="x")

# 念のため outputs ディレクトリは確保
ensure_dir(OUTPUT_DIR)

# UI初期化
refresh_char_list()
refresh_scripts_list()
refresh_gallery_list()

root.mainloop()
